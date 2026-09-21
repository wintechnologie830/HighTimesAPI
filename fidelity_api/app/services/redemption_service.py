import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    CustomerCredential,
    LoyaltyAccount,
    Redemption,
    RedemptionStatus,
    StaffCredential,
)

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 6


class RedemptionNotFoundError(Exception):
    pass


class AlreadyFulfilledError(Exception):
    pass


def _generate_unique_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        exists = db.query(Redemption).filter(Redemption.code == code).first()
        if not exists:
            return code
    raise RuntimeError("Could not generate a unique redemption code")


def create_redemption(
    db: Session,
    account_id: int,
    product_id: int,
    product_name: str,
    quantity: int,
    points_spent: float,
) -> Redemption:
    redemption = Redemption(
        account_id=account_id,
        product_id=product_id,
        product_name=product_name,
        quantity=quantity,
        points_spent=points_spent,
        code=_generate_unique_code(db),
        status=RedemptionStatus.PENDING,
    )
    db.add(redemption)
    db.commit()
    db.refresh(redemption)
    return redemption


def _customer_name(db: Session, aronium_customer_id: int) -> str | None:
    cred = (
        db.query(CustomerCredential)
        .filter(CustomerCredential.aronium_customer_id == aronium_customer_id)
        .first()
    )
    return cred.name if cred else None


def _staff_name(db: Session, staff_id: int | None) -> str | None:
    if staff_id is None:
        return None
    staff = db.query(StaffCredential).filter(StaffCredential.id == staff_id).first()
    return staff.name if staff else None


def to_out_dict(db: Session, redemption: Redemption) -> dict:
    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.id == redemption.account_id).first()
    aronium_customer_id = account.aronium_customer_id if account else None
    return {
        "id": redemption.id,
        "code": redemption.code,
        "aronium_customer_id": aronium_customer_id,
        "customer_name": _customer_name(db, aronium_customer_id) if aronium_customer_id else None,
        "product_id": redemption.product_id,
        "product_name": redemption.product_name,
        "quantity": redemption.quantity,
        "points_spent": redemption.points_spent,
        "status": redemption.status.value,
        "date_created": redemption.date_created,
        "date_fulfilled": redemption.date_fulfilled,
        "staff_id": redemption.staff_id,
    }


def to_staff_out_dict(db: Session, redemption: Redemption) -> dict:
    out = to_out_dict(db, redemption)
    out["staff_name"] = _staff_name(db, redemption.staff_id)
    return out


def get_by_code(db: Session, code: str) -> Redemption | None:
    normalized = code.strip().upper()
    return db.query(Redemption).filter(Redemption.code == normalized).first()


def list_for_customer(db: Session, aronium_customer_id: int, limit: int = 50) -> list[Redemption]:
    account = (
        db.query(LoyaltyAccount)
        .filter(LoyaltyAccount.aronium_customer_id == aronium_customer_id)
        .first()
    )
    if account is None:
        return []
    return (
        db.query(Redemption)
        .filter(Redemption.account_id == account.id)
        .order_by(Redemption.date_created.desc())
        .limit(limit)
        .all()
    )


def list_pending(db: Session, search: str | None = None, limit: int = 100) -> list[Redemption]:
    query = db.query(Redemption).filter(Redemption.status == RedemptionStatus.PENDING)
    if search:
        like = f"%{search.strip()}%"
        query = query.join(LoyaltyAccount, Redemption.account_id == LoyaltyAccount.id).join(
            CustomerCredential,
            CustomerCredential.aronium_customer_id == LoyaltyAccount.aronium_customer_id,
        ).filter(CustomerCredential.name.ilike(like))
    return query.order_by(Redemption.date_created.asc()).limit(limit).all()


def list_fulfilled(db: Session, search: str | None = None, limit: int = 100) -> list[Redemption]:
    query = db.query(Redemption).filter(Redemption.status == RedemptionStatus.FULFILLED)
    if search:
        like = f"%{search.strip()}%"
        query = query.join(LoyaltyAccount, Redemption.account_id == LoyaltyAccount.id).join(
            CustomerCredential,
            CustomerCredential.aronium_customer_id == LoyaltyAccount.aronium_customer_id,
        ).filter(CustomerCredential.name.ilike(like))
    return query.order_by(Redemption.date_fulfilled.desc()).limit(limit).all()


def list_fulfilled_by_staff(db: Session, staff_id: int, limit: int = 100) -> list[Redemption]:
    return (
        db.query(Redemption)
        .filter(Redemption.status == RedemptionStatus.FULFILLED, Redemption.staff_id == staff_id)
        .order_by(Redemption.date_fulfilled.desc())
        .limit(limit)
        .all()
    )


def fulfill(db: Session, redemption_id: int, staff_id: int) -> Redemption:
    redemption = db.query(Redemption).filter(Redemption.id == redemption_id).first()
    if redemption is None:
        raise RedemptionNotFoundError(f"No redemption with id {redemption_id}")
    if redemption.status == RedemptionStatus.FULFILLED:
        raise AlreadyFulfilledError(f"Redemption {redemption_id} was already picked up")

    redemption.status = RedemptionStatus.FULFILLED
    redemption.date_fulfilled = datetime.now()
    redemption.staff_id = staff_id
    db.add(redemption)
    db.commit()
    db.refresh(redemption)
    return redemption
