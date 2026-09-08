from fastapi import APIRouter, Depends, HTTPException, Query

from app import aronium_db
from app.auth import require_internal_api_key
from app.schemas import CustomerCreateIn, CustomerOut, DocumentOut

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(require_internal_api_key)],
)


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreateIn):
    """Create a real Customer row in Aronium. Called once, at sign-up, from
    fidelityAPI's /auth/register - no password or credential of any kind is
    stored here, that lives entirely in fidelityAPI's own database."""
    return aronium_db.create_customer(payload.name, payload.email, payload.phone)


@router.get("", response_model=list[CustomerOut])
def list_customers(search: str | None = Query(default=None)):
    return aronium_db.list_customers(search=search)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int):
    customer = aronium_db.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/by-card/{card_number}", response_model=CustomerOut)
def get_customer_by_card(card_number: str):
    customer = aronium_db.get_customer_by_loyalty_card(card_number)
    if not customer:
        raise HTTPException(status_code=404, detail="No customer found for that card number")
    return customer


@router.get("/{customer_id}/purchases", response_model=list[DocumentOut])
def get_customer_purchases(customer_id: int, limit: int = Query(default=50, le=200)):
    return aronium_db.list_customer_documents(customer_id, limit=limit)
