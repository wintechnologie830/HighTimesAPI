from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_mobile_api_key, require_staff_pin
from app.database import get_db
from app.schemas import RedemptionOut
from app.services import redemption_service

# Split into two routers with different gating: the customer-facing "what
# have I redeemed" view only needs the regular API key (same as the rest
# of the app), while everything that can look someone else's code up or
# mark it fulfilled additionally requires the staff PIN.

router = APIRouter(
    prefix="/redemptions",
    tags=["redemptions"],
    dependencies=[Depends(require_mobile_api_key)],
)

staff_router = APIRouter(
    prefix="/redemptions/staff",
    tags=["redemptions", "staff"],
    dependencies=[Depends(require_mobile_api_key), Depends(require_staff_pin)],
)


@router.get("/customer/{aronium_customer_id}", response_model=list[RedemptionOut])
def list_my_redemptions(aronium_customer_id: int, limit: int = 20, db: Session = Depends(get_db)):
    """
    So a customer can come back to the app and see their pickup code again
    if they closed the confirmation screen, plus their past pickups.
    """
    redemptions = redemption_service.list_for_customer(db, aronium_customer_id, limit=limit)
    return [redemption_service.to_out_dict(db, r) for r in redemptions]


@staff_router.get("/by-code/{code}", response_model=RedemptionOut)
def lookup_by_code(code: str, db: Session = Depends(get_db)):
    """Option 1: cashier types the code the customer is showing them."""
    redemption = redemption_service.get_by_code(db, code)
    if redemption is None:
        raise HTTPException(status_code=404, detail="No redemption found for that code")
    return redemption_service.to_out_dict(db, redemption)


@staff_router.get("/pending", response_model=list[RedemptionOut])
def list_pending(search: str | None = None, db: Session = Depends(get_db)):
    """Option 3: everyone with an unpicked-up redemption, optionally
    filtered by customer name - the fallback for when someone doesn't
    have their code handy."""
    redemptions = redemption_service.list_pending(db, search=search)
    return [redemption_service.to_out_dict(db, r) for r in redemptions]


@staff_router.post("/{redemption_id}/fulfill", response_model=RedemptionOut)
def fulfill(redemption_id: int, db: Session = Depends(get_db)):
    """Cashier confirms the product was actually handed over."""
    try:
        redemption = redemption_service.fulfill(db, redemption_id)
    except redemption_service.RedemptionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except redemption_service.AlreadyFulfilledError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return redemption_service.to_out_dict(db, redemption)
