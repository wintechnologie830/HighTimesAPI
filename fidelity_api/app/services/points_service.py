from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import general_client
from app.config import settings
from app.models import LoyaltyAccount, PointsTransaction, TransactionType
from app.services import inventory
from app.services import redemption_service


class InsufficientPointsError(Exception):
    pass


class DuplicateReferenceError(Exception):
    pass


class OutOfStockError(Exception):
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
        raise DuplicateReferenceError(f"Points already awarded for reference '{reference}'")
    db.refresh(tx)
    return tx


def purchase_product(
    db: Session,
    aronium_customer_id: int,
    product_id: int,
    quantity: int = 1,
    reference: str | None = None,
    note: str | None = None,
) -> PointsTransaction:
    product = general_client.get_product(product_id)
    amount_spent = round(product["Price"] * quantity, 2)

    sale = general_client.record_sale(
        customer_id=aronium_customer_id,
        product_id=product_id,
        quantity=quantity,
        unit_price=product["Price"],
    )
    if sale is None:
        raise OutOfStockError(
            f"Not enough stock for product #{product_id} (requested {quantity})"
        )

    default_note = f"Bought {quantity} x {product['Name']} (Aronium doc {sale['number']})"

    tx = earn_points(
        db,
        aronium_customer_id=aronium_customer_id,
        amount_spent=amount_spent,
        reference=reference or f"sale:{sale['document_id']}",
        note=note or default_note,
    )

    inventory.reduce_inventory(db, product_id, quantity)

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
        raise DuplicateReferenceError(f"Redemption already recorded for reference '{reference}'")
    db.refresh(tx)
    return tx


def redeem_points_for_product(
    db: Session,
    aronium_customer_id: int,
    product_id: int,
    quantity: int = 1,
) -> PointsTransaction:
    product = general_client.get_product(product_id)
    points_needed = round(
        (product["Price"] * quantity) / settings.point_redemption_value, 2
    )

    account = get_or_create_account(db, aronium_customer_id)
    if account.points_balance < points_needed:
        raise InsufficientPointsError(
            f"Account has {account.points_balance} points, needs {points_needed}"
        )

    if not general_client.reduce_stock(product_id, quantity):
        raise OutOfStockError(
            f"Not enough stock for product #{product_id} (requested {quantity})"
        )

    note = f"Redeemed {quantity} x {product['Name']} (product #{product_id})"

    try:
        tx = redeem_points(
            db,
            aronium_customer_id=aronium_customer_id,
            points=points_needed,
            reference=f"product:{product_id}:{quantity}:{int(datetime.utcnow().timestamp())}",
            note=note,
        )
    except (InsufficientPointsError, DuplicateReferenceError):
        general_client.increase_stock(product_id, quantity)
        raise

    inventory.reduce_inventory(db, product_id, quantity)

    redemption = redemption_service.create_redemption(
        db,
        account_id=account.id,
        product_id=product_id,
        product_name=product["Name"],
        quantity=quantity,
        points_spent=points_needed,
    )

    tx.redemption_id = redemption.id
    tx.redemption_code = redemption.code
    tx.product_name = product["Name"]
    tx.quantity = quantity

    return tx

def adjust_points(
    db: Session, aronium_customer_id: int, points: float, note: str
) -> PointsTransaction:
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
