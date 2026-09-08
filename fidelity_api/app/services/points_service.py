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
    """Raised when the same (account, reference, type) has already been recorded."""
    pass


class OutOfStockError(Exception):
    """Raised when Aronium's real stock (pos.db, via generalAPI) doesn't have enough units."""
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


def purchase_product(
    db: Session,
    aronium_customer_id: int,
    product_id: int,
    quantity: int = 1,
    reference: str | None = None,
    note: str | None = None,
) -> PointsTransaction:
    """
    Buy a product with real money. This earns points as usual, but - unlike
    a plain earn_points() call, which has no idea what was bought - it also
    takes the purchased quantity out of Aronium's real stock (pos.db, via
    generalAPI), the same way redeem_points_for_product() does for points
    purchases. That keeps the "Quantity" shown to customers accurate no
    matter which way a unit left the shelf.
    """
    # 1. Get the product's live price from generalAPI (also confirms it exists).
    product = general_client.get_product(product_id)
    amount_spent = round(product["Price"] * quantity, 2)

    # 2. Record it as a real Aronium sale: a Document + line item + payment,
    # atomically with the stock reduction. This is what makes the sale show
    # up on Aronium's own Sales screen and in "popular products" - not just
    # affect the loyalty side.
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

    # 3. Award the points. If this fails (e.g. a duplicate reference from a
    # retried request), the sale itself still stands in Aronium - it really
    # happened - so we don't try to undo it here, unlike the points-for-
    # product redemption flow below where the "sale" only exists because
    # the points succeeded.
    tx = earn_points(
        db,
        aronium_customer_id=aronium_customer_id,
        amount_spent=amount_spent,
        reference=reference or f"sale:{sale['document_id']}",
        note=note or default_note,
    )

    # 4. Keep the local redeemable-stock cache in sync too (best-effort;
    # pos.db is the source of truth, this is only used for quick lookups).
    inventory.reduce_inventory(db, product_id, quantity)

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
    Spend points on an actual product. This is a real sale, so it has to
    take the stock out of Aronium's own database (pos.db), not just a
    local counter - otherwise the till still thinks that unit is available
    and it can be sold twice.

    generalAPI is the only thing allowed to write to pos.db, so the actual
    stock decrement happens there; fidelityAPI just calls it.
    """
    # 1. Get product price from generalAPI (also confirms the product exists)
    product = general_client.get_product(product_id)
    points_needed = round(
        (product["Price"] * quantity) / settings.point_redemption_value, 2
    )

    # 2. Make sure the customer can actually afford it before we touch
    # anything external - cheap to check, and avoids taking real stock for
    # a redemption that was never going to succeed.
    account = get_or_create_account(db, aronium_customer_id)
    if account.points_balance < points_needed:
        raise InsufficientPointsError(
            f"Account has {account.points_balance} points, needs {points_needed}"
        )

    # 3. Take the stock out of pos.db, via generalAPI. This is the real,
    # authoritative check for "is there actually enough stock" - not the
    # local cache below, which can drift.
    if not general_client.reduce_stock(product_id, quantity):
        raise OutOfStockError(
            f"Not enough stock for product #{product_id} (requested {quantity})"
        )

    note = f"Redeemed {quantity} x {product['Name']} (product #{product_id})"

    # 4. Deduct the points. If this fails for any reason (e.g. a race where
    # another redemption slipped in between steps 2 and 4), put the real
    # stock back so pos.db doesn't end up short for no reason.
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

    # 5. Keep the local cache in sync too (best-effort; pos.db is the
    # source of truth now, this is only used for quick local lookups).
    inventory.reduce_inventory(db, product_id, quantity)

    # 6. Leave a paper trail for pickup: the points and stock are already
    # spent, but the customer isn't standing at a register when this
    # happens - they redeemed from home and will walk in later. The code
    # on this row is what they show the cashier, and what lets staff tell
    # "already picked up" from "still owed" (see redemptions.py / the
    # staff pickup screen).
    redemption = redemption_service.create_redemption(
        db,
        account_id=account.id,
        product_id=product_id,
        product_name=product["Name"],
        quantity=quantity,
        points_spent=points_needed,
    )

    # Attached as plain attributes (not DB columns) so the /redeem-product
    # endpoint can hand the pickup code straight back to the app without
    # a second round trip. RedeemProductOut reads these the same way it
    # reads tx's own mapped columns.
    tx.redemption_id = redemption.id
    tx.redemption_code = redemption.code
    tx.product_name = product["Name"]
    tx.quantity = quantity

    return tx

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
