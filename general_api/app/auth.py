from fastapi import Header, HTTPException, status

from app.config import settings


def require_internal_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.general_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key",
        )
