from fastapi import APIRouter, Depends, HTTPException, Query

from app import aronium_db
from app.auth import require_api_key
from app.schemas import CustomerOut, DocumentOut

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=list[CustomerOut])
def list_customers(search: str | None = Query(default=None)):
    """List customers from Aronium (read-only). Optional ?search=name/email/code."""
    return aronium_db.list_customers(search=search)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int):
    customer = aronium_db.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/by-card/{card_number}", response_model=CustomerOut)
def get_customer_by_card(card_number: str):
    """Look up a customer by their Aronium loyalty card number (barcode/RFID/etc)."""
    customer = aronium_db.get_customer_by_loyalty_card(card_number)
    if not customer:
        raise HTTPException(status_code=404, detail="No customer found for that card number")
    return customer


@router.get("/{customer_id}/purchases", response_model=list[DocumentOut])
def get_customer_purchases(customer_id: int, limit: int = Query(default=50, le=200)):
    return aronium_db.list_customer_documents(customer_id, limit=limit)
