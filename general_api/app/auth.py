from fastapi import Header, HTTPException, status

from app.config import settings


def require_internal_api_key(x_api_key: str = Header(...)):
    """
    This key is known ONLY to fidelityAPI. It is never issued to the mobile
    app, and generalAPI itself should never be exposed outside 127.0.0.1.
    This check is a second layer of defense on top of that network isolation.
    """
    if x_api_key != settings.general_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key",
        )
