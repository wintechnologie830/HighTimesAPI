import httpx
from fastapi import HTTPException

from app.config import settings

_HEADERS = {"X-API-Key": settings.general_api_key}


def _get(path: str, params: dict | None = None) -> httpx.Response:
    try:
        resp = httpx.get(
            f"{settings.general_api_base_url}{path}",
            headers=_HEADERS,
            params=params,
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"generalAPI is unreachable ({exc.__class__.__name__}). Is it running?",
        )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=resp.json().get("detail", "Not found"))
    resp.raise_for_status()
    return resp


def _post(path: str, json: dict | None = None) -> httpx.Response:
    try:
        resp = httpx.post(
            f"{settings.general_api_base_url}{path}",
            headers=_HEADERS,
            json=json,
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"generalAPI is unreachable ({exc.__class__.__name__}). Is it running?",
        )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=resp.json().get("detail", "Not found"))
    if resp.status_code not in (200, 409):
        resp.raise_for_status()
    return resp


def list_customers(search: str | None = None) -> list[dict]:
    return _get("/customers", params={"search": search} if search else None).json()


def get_customer(customer_id: int) -> dict:
    return _get(f"/customers/{customer_id}").json()


def get_customer_by_card(card_number: str) -> dict:
    return _get(f"/customers/by-card/{card_number}").json()


def get_customer_purchases(customer_id: int, limit: int = 50) -> list[dict]:
    return _get(f"/customers/{customer_id}/purchases", params={"limit": limit}).json()


def list_products(search: str | None = None, limit: int = 200) -> list[dict]:
    params = {"limit": limit}
    if search:
        params["search"] = search
    return _get("/products", params=params).json()


def get_product(product_id: int) -> dict:
    return _get(f"/products/{product_id}").json()


def list_recent_documents(since_id: int = 0, limit: int = 200) -> list[dict]:
    return _get("/documents/recent", params={"since_id": since_id, "limit": limit}).json()


def create_customer(name: str, email: str | None, phone: str | None) -> dict:
    return _post("/customers", json={"name": name, "email": email, "phone": phone}).json()


def record_sale(
    customer_id: int | None,
    product_id: int,
    quantity: int,
    unit_price: float,
    payment_type_id: int = 1,
) -> dict | None:
    resp = _post(
        "/sales",
        json={
            "customer_id": customer_id,
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "payment_type_id": payment_type_id,
        },
    )
    if resp.status_code == 409:
        return None
    return resp.json()


def reduce_stock(product_id: int, quantity: int) -> bool:
    resp = _post(f"/products/{product_id}/reduce-stock", json={"quantity": quantity})
    return resp.status_code == 200


def increase_stock(product_id: int, quantity: int) -> None:
    _post(f"/products/{product_id}/increase-stock", json={"quantity": quantity})
