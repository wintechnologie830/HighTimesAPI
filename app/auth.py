from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str = Header(...)):
    """
    Simple shared-secret auth. The loyalty app must send:
        X-API-Key: <the value of API_KEY from your .env>
    Good enough for a small internal/mobile app; swap for OAuth2/JWT later
    if you need per-user login instead of a single shared key.
    """
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
