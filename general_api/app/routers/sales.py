from fastapi import APIRouter, Depends, HTTPException

from app import aronium_db
from app.auth import require_internal_api_key
from app.schemas import SaleIn, SaleOut

router = APIRouter(
    prefix="/sales",
    tags=["sales"],
    dependencies=[Depends(require_internal_api_key)],
)


@router.post("", response_model=SaleOut)
def record_sale(payload: SaleIn):
    """
    Called by fidelityAPI right when a cash purchase completes in the
    loyalty app. Writes a real Sales Document + DocumentItem + Payment (so
    Aronium's own Sales screen and "popular products" reflect it) and takes
    the quantity out of Stock, in one atomic transaction. Returns 409 if
    there isn't enough stock - in that case nothing was written.
    """
    result = aronium_db.record_sale(
        customer_id=payload.customer_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        payment_type_id=payload.payment_type_id,
    )
    if result is None:
        raise HTTPException(status_code=409, detail="Not enough stock")
    return result
