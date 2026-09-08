from sqlalchemy.orm import Session
from app.models import ProductInventory


def get_inventory(db: Session, product_id: int) -> int:
    """Get current quantity for a product."""
    inv = db.query(ProductInventory).filter(ProductInventory.product_id == product_id).first()
    return inv.quantity if inv else 0


def reduce_inventory(db: Session, product_id: int, quantity: int = 1) -> bool:
    """
    Reduce inventory by quantity.
    Returns False if insufficient stock (prevents overselling).
    """
    inv = db.query(ProductInventory).filter(ProductInventory.product_id == product_id).first()
    
    if not inv:
        # Product not in inventory system - default to 0
        return False
    
    if inv.quantity < quantity:
        return False
    
    inv.quantity -= quantity
    db.commit()
    return True


def initialize_inventory(db: Session, product_id: int, quantity: int = 0) -> None:
    """Called during sync to create inventory entries for new products."""
    existing = db.query(ProductInventory).filter(ProductInventory.product_id == product_id).first()
    if not existing:
        inv = ProductInventory(product_id=product_id, quantity=quantity)
        db.add(inv)
        db.commit()
