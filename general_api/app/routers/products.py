from fastapi import APIRouter, Depends, HTTPException, Query

from app import aronium_db
from app.auth import require_internal_api_key
from app.schemas import ProductOut

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(require_internal_api_key)],
)


@router.get("", response_model=list[ProductOut])
def list_products(search: str | None = Query(default=None), limit: int = Query(default=200, le=500)):
    return aronium_db.list_products(search=search, limit=limit)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    product = aronium_db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
