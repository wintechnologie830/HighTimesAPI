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
