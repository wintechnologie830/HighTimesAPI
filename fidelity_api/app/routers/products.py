from fastapi import APIRouter, Depends, Query

from app import general_client
from app.auth import require_mobile_api_key
from app.schemas import ProductOut

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(require_mobile_api_key)],
)


@router.get("", response_model=list[ProductOut])
def list_products(search: str | None = Query(default=None)):
    """So the app can show a catalog of what points can be redeemed for."""
    return general_client.list_products(search=search)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    return general_client.get_product(product_id)
