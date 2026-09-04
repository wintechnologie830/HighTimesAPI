from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.database import get_db
from app.schemas import (
    AdjustPointsIn,
    EarnPointsIn,
    PointsBalanceOut,
    RedeemPointsIn,
    TransactionOut,
)
from app.services import points_service

router = APIRouter(
    prefix="/points",
    tags=["points"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/{aronium_customer_id}", response_model=PointsBalanceOut)
def get_balance(aronium_customer_id: int, db: Session = Depends(get_db)):
    account = points_service.get_balance(db, aronium_customer_id)
    return PointsBalanceOut(
        aronium_customer_id=account.aronium_customer_id,
        points_balance=account.points_balance,
        point_value_currency=round(account.points_balance * settings.point_redemption_value, 2),
    )


@router.get("/{aronium_customer_id}/history", response_model=list[TransactionOut])
def get_history(aronium_customer_id: int, limit: int = 50, db: Session = Depends(get_db)):
    return points_service.get_history(db, aronium_customer_id, limit=limit)


@router.post("/earn", response_model=TransactionOut)
def earn(payload: EarnPointsIn, db: Session = Depends(get_db)):
    try:
        return points_service.earn_points(
            db,
            aronium_customer_id=payload.aronium_customer_id,
            amount_spent=payload.amount_spent,
            reference=payload.reference,
            note=payload.note,
        )
    except points_service.DuplicateReferenceError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/redeem", response_model=TransactionOut)
def redeem(payload: RedeemPointsIn, db: Session = Depends(get_db)):
    try:
        return points_service.redeem_points(
            db,
            aronium_customer_id=payload.aronium_customer_id,
            points=payload.points,
            reference=payload.reference,
            note=payload.note,
        )
    except points_service.InsufficientPointsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except points_service.DuplicateReferenceError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/adjust", response_model=TransactionOut)
def adjust(payload: AdjustPointsIn, db: Session = Depends(get_db)):
    """Manual staff correction, e.g. goodwill points or fixing a mistake."""
    return points_service.adjust_points(
        db,
        aronium_customer_id=payload.aronium_customer_id,
        points=payload.points,
        note=payload.note,
    )
