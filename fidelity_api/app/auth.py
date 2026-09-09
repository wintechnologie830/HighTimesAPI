from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import StaffCredential
from app.services import staff_auth_service


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


def require_staff_auth(
    x_staff_token: str = Header(...), db: Session = Depends(get_db)
) -> StaffCredential:
    """
    Identifies *which* staff member is acting, on top of require_staff_pin
    (which only proves "someone allowed in the back room"). Used on the
    fulfill endpoint so a redemption's staff_id records a real individual,
    not just "the pickup desk was unlocked." Returns the StaffCredential
    so the endpoint can read staff.id / staff.name.
    """
    staff = staff_auth_service.get_staff_by_token(db, x_staff_token)
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff session expired or invalid - please sign in again",
        )
    return staff
