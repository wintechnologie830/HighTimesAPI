from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import general_client
from app.config import settings
from app.models import LoyaltyAccount, PointsTransaction, TransactionType


class InsufficientPointsError(Exception):
    pass


class DuplicateReferenceError(Exception):
    """Raised when the same (account, reference, type) has already been recorded."""
    pass


def get_or_create_account(db: Session, aronium_customer_id: int) -> LoyaltyAccount:
    """
    Each Aronium customer gets exactly one account and one points_balance -
    accounts are never merged or shared, so every customer's points are
    entirely their own.
    """
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
    """Award points for a purchase. `amount_spent` is currency spent, not points."""
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
        raise DuplicateReferenceError(f"Points already awarded for reference '{reference}'")
    db.refresh(tx)
    return tx


def redeem_points(
    db: Session,
    aronium_customer_id: int,
    points: float,
    reference: str | None = None,
    note: str | None = None,
) -> PointsTransaction:
    """Spend a raw number of points (e.g. for a cash-value discount)."""
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
        raise DuplicateReferenceError(f"Redemption already recorded for reference '{reference}'")
    db.refresh(tx)
    return tx


def redeem_points_for_product(
    db: Session,
    aronium_customer_id: int,
    product_id: int,
    quantity: int = 1,
) -> PointsTransaction:
    """
    Spend points on an actual product instead of a raw point amount.
    fidelityAPI never stores its own copy of product prices - it asks
    generalAPI for the live price, so a price change in Aronium is
    reflected immediately without touching loyalty.db.
    """
    product = general_client.get_product(product_id)
    points_needed = round(
        (product["Price"] * quantity) / settings.point_redemption_value, 2
    )
    note = f"Redeemed {quantity} x {product['Name']} (product #{product_id})"
    return redeem_points(
        db,
        aronium_customer_id=aronium_customer_id,
        points=points_needed,
        reference=f"product:{product_id}:{quantity}",
        note=note,
    )


def adjust_points(
    db: Session, aronium_customer_id: int, points: float, note: str
) -> PointsTransaction:
    """Manual staff/admin correction - can be positive or negative."""
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
