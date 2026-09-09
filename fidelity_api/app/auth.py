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
    if x_staff_pin != settings.staff_pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staff PIN",
        )


def require_staff_auth(
    x_staff_token: str = Header(...), db: Session = Depends(get_db)
) -> StaffCredential:
    staff = staff_auth_service.get_staff_by_token(db, x_staff_token)
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff session expired or invalid - please sign in again",
        )
    return staff
