from fastapi import Header, HTTPException, status

from app.config import settings


def require_mobile_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.fidelity_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
