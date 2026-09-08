import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import CustomerCredential, LoyaltyAccount, Redemption, RedemptionStatus

# Excludes 0/O and 1/I/L - characters people commonly misread off a phone
# screen at the counter.
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
    # Astronomically unlikely with a 32^6 keyspace, but fail loudly rather
    # than silently hand out a colliding code.
    raise RuntimeError("Could not generate a unique redemption code")


def create_redemption(
    db: Session,
    account_id: int,
    product_id: int,
    product_name: str,
    quantity: int,
    points_spent: float,
) -> Redemption:
    """
    Called right after points_service.redeem_points_for_product() takes the
    points and stock. This row - and the code on it - is what lets the
    customer prove at pickup that they already paid with points, and lets
    staff mark it handed over.
    """
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


def to_out_dict(db: Session, redemption: Redemption) -> dict:
    """Attaches the customer's aronium_customer_id + name for display,
    since Redemption itself only stores the internal account_id."""
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
    }


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
    """
    Option 3's staff queue: everyone with an unfulfilled redemption,
    newest first, so the cashier can find someone by name even if they
    forgot / can't show their code.
    """
    query = db.query(Redemption).filter(Redemption.status == RedemptionStatus.PENDING)
    if search:
        like = f"%{search.strip()}%"
        query = query.join(LoyaltyAccount, Redemption.account_id == LoyaltyAccount.id).join(
            CustomerCredential,
            CustomerCredential.aronium_customer_id == LoyaltyAccount.aronium_customer_id,
        ).filter(CustomerCredential.name.ilike(like))
    return query.order_by(Redemption.date_created.asc()).limit(limit).all()


def fulfill(db: Session, redemption_id: int) -> Redemption:
    redemption = db.query(Redemption).filter(Redemption.id == redemption_id).first()
    if redemption is None:
        raise RedemptionNotFoundError(f"No redemption with id {redemption_id}")
    if redemption.status == RedemptionStatus.FULFILLED:
        raise AlreadyFulfilledError(f"Redemption {redemption_id} was already picked up")

    redemption.status = RedemptionStatus.FULFILLED
    redemption.date_fulfilled = datetime.utcnow()
    db.add(redemption)
    db.commit()
    db.refresh(redemption)
    return redemption
