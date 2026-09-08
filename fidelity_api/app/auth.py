from fastapi import Header, HTTPException, status

from app.config import settings


def require_mobile_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.fidelity_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def require_staff_pin(x_staff_pin: str = Header(...)):
    """
    Gates the staff-only redemption pickup screen (look up a code, browse
    pending pickups, mark fulfilled). Separate secret from the API key on
    purpose - see the comment on staff_pin in config.py.
    """
    if x_staff_pin != settings.staff_pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staff PIN",
        )
