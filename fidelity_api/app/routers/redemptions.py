from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_mobile_api_key, require_staff_auth, require_staff_pin
from app.database import get_db
from app.models import StaffCredential
from app.schemas import RedemptionOut, RedemptionStaffOut
from app.services import redemption_service

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
    redemptions = redemption_service.list_for_customer(db, aronium_customer_id, limit=limit)
    return [redemption_service.to_out_dict(db, r) for r in redemptions]


@staff_router.get("/by-code/{code}", response_model=RedemptionStaffOut)
def lookup_by_code(code: str, db: Session = Depends(get_db)):
    redemption = redemption_service.get_by_code(db, code)
    if redemption is None:
        raise HTTPException(status_code=404, detail="No redemption found for that code")
    return redemption_service.to_staff_out_dict(db, redemption)


@staff_router.get("/pending", response_model=list[RedemptionStaffOut])
def list_pending(search: str | None = None, db: Session = Depends(get_db)):
    redemptions = redemption_service.list_pending(db, search=search)
    return [redemption_service.to_staff_out_dict(db, r) for r in redemptions]


@staff_router.get("/mine", response_model=list[RedemptionStaffOut])
def list_my_pickups(
    staff: StaffCredential = Depends(require_staff_auth),
    db: Session = Depends(get_db),
):
    redemptions = redemption_service.list_fulfilled_by_staff(db, staff_id=staff.id)
    return [redemption_service.to_staff_out_dict(db, r) for r in redemptions]


@staff_router.get("/fulfilled", response_model=list[RedemptionStaffOut])
def list_all_pickups(search: str | None = None, db: Session = Depends(get_db)):
    redemptions = redemption_service.list_fulfilled(db, search=search)
    return [redemption_service.to_staff_out_dict(db, r) for r in redemptions]


@staff_router.post("/{redemption_id}/fulfill", response_model=RedemptionStaffOut)
def fulfill(
    redemption_id: int,
    staff: StaffCredential = Depends(require_staff_auth),
    db: Session = Depends(get_db),
):
    try:
        redemption = redemption_service.fulfill(db, redemption_id, staff_id=staff.id)
    except redemption_service.RedemptionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except redemption_service.AlreadyFulfilledError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return redemption_service.to_staff_out_dict(db, redemption)
