from fastapi import APIRouter, Depends, HTTPException, Query

from app import aronium_db
from app.auth import require_internal_api_key
from app.schemas import ProductOut, StockAdjustIn, StockAdjustOut

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


@router.post("/{product_id}/reduce-stock", response_model=StockAdjustOut)
def reduce_stock(product_id: int, payload: StockAdjustIn):
    product = aronium_db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    ok = aronium_db.reduce_stock(product_id, payload.quantity)
    if not ok:
        raise HTTPException(status_code=409, detail="Not enough stock")
    return StockAdjustOut(product_id=product_id, quantity_changed=-payload.quantity)


@router.post("/{product_id}/increase-stock", response_model=StockAdjustOut)
def increase_stock(product_id: int, payload: StockAdjustIn):
    product = aronium_db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    aronium_db.increase_stock(product_id, payload.quantity)
    return StockAdjustOut(product_id=product_id, quantity_changed=payload.quantity)
