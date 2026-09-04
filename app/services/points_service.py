from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LoyaltyAccount, PointsTransaction, TransactionType


class InsufficientPointsError(Exception):
    pass


class DuplicateReferenceError(Exception):
    """Raised when the same (account, reference, type) has already been recorded."""
    pass


def get_or_create_account(db: Session, aronium_customer_id: int) -> LoyaltyAccount:
    account = (
        db.query(LoyaltyAccount)
        .filter(LoyaltyAccount.aronium_customer_id == aronium_customer_id)
        .first()
    )
    if account is None:
        account = LoyaltyAccount(aronium_customer_id=aronium_customer_id, points_balance=0.0)
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def get_balance(db: Session, aronium_customer_id: int) -> LoyaltyAccount:
    return get_or_create_account(db, aronium_customer_id)


def earn_points(
    db: Session,
    aronium_customer_id: int,
    amount_spent: float,
    reference: str | None = None,
    note: str | None = None,
) -> PointsTransaction:
    account = get_or_create_account(db, aronium_customer_id)
    points = round(amount_spent * settings.points_per_currency_unit, 2)

    tx = PointsTransaction(
        account_id=account.id,
        type=TransactionType.EARN,
        points=points,
        reference=reference,
        note=note,
    )
    account.points_balance += points

    db.add(tx)
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateReferenceError(
            f"Points already awarded for reference '{reference}'"
        )
    db.refresh(tx)
    return tx


def redeem_points(
    db: Session,
    aronium_customer_id: int,
    points: float,
    reference: str | None = None,
    note: str | None = None,
) -> PointsTransaction:
    account = get_or_create_account(db, aronium_customer_id)
    if account.points_balance < points:
        raise InsufficientPointsError(
            f"Account has {account.points_balance} points, tried to redeem {points}"
        )

    tx = PointsTransaction(
        account_id=account.id,
        type=TransactionType.REDEEM,
        points=-points,
        reference=reference,
        note=note,
    )
    account.points_balance -= points

    db.add(tx)
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateReferenceError(
            f"Redemption already recorded for reference '{reference}'"
        )
    db.refresh(tx)
    return tx


def adjust_points(
    db: Session, aronium_customer_id: int, points: float, note: str
) -> PointsTransaction:
    """Manual staff/admin correction — can be positive or negative."""
    account = get_or_create_account(db, aronium_customer_id)

    tx = PointsTransaction(
        account_id=account.id,
        type=TransactionType.ADJUST,
        points=points,
        note=note,
    )
    account.points_balance += points

    db.add(tx)
    db.add(account)
    db.commit()
    db.refresh(tx)
    return tx


def get_history(db: Session, aronium_customer_id: int, limit: int = 50) -> list[PointsTransaction]:
    account = get_or_create_account(db, aronium_customer_id)
    return (
        db.query(PointsTransaction)
        .filter(PointsTransaction.account_id == account.id)
        .order_by(PointsTransaction.date_created.desc())
        .limit(limit)
        .all()
    )
