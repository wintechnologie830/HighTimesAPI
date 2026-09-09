from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import general_client
from app.auth import require_mobile_api_key
from app.database import get_db
from app.schemas import ProductOut
from app.services import inventory

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(require_mobile_api_key)],
)


@router.get("", response_model=list[ProductOut])
def list_products(search: str | None = Query(default=None), db: Session = Depends(get_db)):
    products = general_client.list_products(search=search)
    
    for product in products:
        product["Inventory"] = inventory.get_inventory(db, product["Id"])
    
    return products


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = general_client.get_product(product_id)
    product["Inventory"] = inventory.get_inventory(db, product_id)
    return product
