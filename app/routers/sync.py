from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import aronium_db
from app.auth import require_api_key
from app.database import get_db
from app.models import SyncState
from app.schemas import SyncResultOut
from app.services import points_service

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    dependencies=[Depends(require_api_key)],
)

# Document type codes that should earn points, matched against
# DocumentType.Code in YOUR pos.db (check yours with:
#   SELECT Id, Name, Code FROM DocumentType;
# ). Standard Aronium install ships with:
#   100 Purchase | 200 Sales | 300 Inventory Count | 220 Refund
#   120 Stock Return | 400 Loss And Damage | 230 Proforma
# By default we only earn points on "Sales" (200) — NOT refunds/purchases/etc.
EARNABLE_DOCUMENT_TYPE_CODES = {"200"}


def _get_sync_state(db: Session) -> SyncState:
    state = db.query(SyncState).first()
    if state is None:
        state = SyncState(last_document_id=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


@router.post("/run", response_model=SyncResultOut)
def run_sync(db: Session = Depends(get_db)):
    """
    Reads any new sales from Aronium (pos.db, read-only) that haven't been
    turned into points yet, and awards points for each one. Safe to call
    repeatedly (e.g. every few minutes from a scheduler) — already-processed
    documents are never re-awarded, and pos.db is never modified.
    """
    state = _get_sync_state(db)
    documents = aronium_db.list_recent_documents(since_id=state.last_document_id, limit=200)

    processed = 0
    total_points = 0.0

    for doc in documents:
        if doc["DocumentTypeCode"] in EARNABLE_DOCUMENT_TYPE_CODES and doc["CustomerId"]:
            try:
                tx = points_service.earn_points(
                    db,
                    aronium_customer_id=doc["CustomerId"],
                    amount_spent=doc["Total"],
                    reference=doc["Number"],
                    note=f"Auto-earned from Aronium document #{doc['Number']}",
                )
                total_points += tx.points
                processed += 1
            except points_service.DuplicateReferenceError:
                # Already awarded for this document number, skip.
                pass

        state.last_document_id = doc["Id"]

    db.add(state)
    db.commit()

    return SyncResultOut(
        processed_documents=processed,
        points_awarded=round(total_points, 2),
        last_document_id=state.last_document_id,
    )
