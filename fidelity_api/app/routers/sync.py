from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import general_client
from app.auth import require_mobile_api_key
from app.database import get_db
from app.models import SyncState
from app.schemas import SyncResultOut
from app.services import points_service
from app.services import inventory

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    dependencies=[Depends(require_mobile_api_key)],
)

# Document type codes that should earn points, matched against
# DocumentType.Code in your pos.db (check with:
#   SELECT Id, Name, Code FROM DocumentType;
# via generalAPI's machine). Standard Aronium install ships with:
#   100 Purchase | 200 Sales | 300 Inventory Count | 220 Refund
#   120 Stock Return | 400 Loss And Damage | 230 Proforma
# By default we only earn points on "Sales" (200).
EARNABLE_DOCUMENT_TYPE_CODES = {"200"}


def _get_sync_state(db: Session) -> SyncState:
    state = db.query(SyncState).first()
    if state is None:
        state = SyncState(last_document_id=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def perform_sync(db: Session) -> SyncResultOut:
    """
    Core sync logic - finds new Aronium documents tied to a real customer
    and awards points for the "Sales" ones. This is what makes a purchase
    rung up directly at the Aronium till (customer selected via the
    "Search customer" screen, not just one made through the loyalty app)
    earn that customer points too.

    Callable both from the manual POST /sync/run endpoint below and from
    the background auto-sync loop in main.py, which is what makes till
    purchases earn points automatically without anyone pressing a button.

    Reference format `sale:{document_id}` deliberately matches the one
    purchase_product() uses for app purchases (see points_service.py).
    That's what stops a document from ever earning points twice no matter
    which path it came from: an app purchase already recorded under that
    reference makes this a harmless no-op (DuplicateReferenceError, caught
    below) when this sync later sees the same document again.
    """
    state = _get_sync_state(db)
    documents = general_client.list_recent_documents(since_id=state.last_document_id, limit=200)

    processed = 0
    total_points = 0.0

    # Process sales for points
    for doc in documents:
        if doc["DocumentTypeCode"] in EARNABLE_DOCUMENT_TYPE_CODES and doc.get("CustomerId"):
            try:
                tx = points_service.earn_points(
                    db,
                    aronium_customer_id=doc["CustomerId"],
                    amount_spent=doc["Total"],
                    reference=f"sale:{doc['Id']}",
                    note=f"Auto-earned from Aronium document #{doc['Number']}",
                )
                total_points += tx.points
                processed += 1
            except points_service.DuplicateReferenceError:
                pass

        state.last_document_id = doc["Id"]

    # Initialize inventory for any new products (only if they don't have inventory yet),
    # seeded from Aronium's real Stock quantity - not a guessed default.
    products = general_client.list_products(limit=500)
    for product in products:
        if not product.get("IsService", False):  # Only track inventory for products
            real_quantity = int(product.get("Quantity", 0))
            inventory.initialize_inventory(db, product["Id"], real_quantity)

    db.add(state)
    db.commit()

    return SyncResultOut(
        processed_documents=processed,
        points_awarded=round(total_points, 2),
        last_document_id=state.last_document_id,
    )


@router.post("/run", response_model=SyncResultOut)
def run_sync(db: Session = Depends(get_db)):
    """
    Manual trigger for perform_sync() - the same logic the background
    auto-sync loop runs on a timer (see main.py).
    """
    return perform_sync(db)
