from fastapi import APIRouter, Depends, Query

from app import general_client
from app.auth import require_mobile_api_key
from app.schemas import CustomerOut, DocumentOut

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(require_mobile_api_key)],
)

@router.get("", response_model=list[CustomerOut])
def list_customers(search: str | None = Query(default=None)):
    return general_client.list_customers(search=search)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int):
    return general_client.get_customer(customer_id)


@router.get("/by-card/{card_number}", response_model=CustomerOut)
def get_customer_by_card(card_number: str):
    return general_client.get_customer_by_card(card_number)


@router.get("/{customer_id}/purchases", response_model=list[DocumentOut])
def get_customer_purchases(customer_id: int, limit: int = Query(default=50, le=200)):
    return general_client.get_customer_purchases(customer_id, limit=limit)
