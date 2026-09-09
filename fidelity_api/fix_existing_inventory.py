from app.database import SessionLocal
from app.models import ProductInventory
from app import general_client

def main():
    db = SessionLocal()
    try:
        products = general_client.list_products(limit=500)
        by_id = {p["Id"]: p for p in products}

        rows = db.query(ProductInventory).all()
        changed = 0
        for row in rows:
            product = by_id.get(row.product_id)
            if not product:
                continue
            real_quantity = int(product.get("Quantity", 0))
            if row.quantity != real_quantity:
                print(f"Product {row.product_id} ({product['Name']}): "
                      f"{row.quantity} -> {real_quantity}")
                row.quantity = real_quantity
                changed += 1
        db.commit()
        print(f"Done. Updated {changed} row(s).")
    finally:
        db.close()

if __name__ == "__main__":
    main()
