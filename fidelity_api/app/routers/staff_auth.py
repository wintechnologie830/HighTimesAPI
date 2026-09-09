from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_mobile_api_key
from app.database import get_db
from app.schemas import StaffAuthOut, StaffLoginIn, StaffRegisterIn
from app.services import staff_auth_service

router = APIRouter(
    prefix="/staff/auth",
    tags=["staff"],
    dependencies=[Depends(require_mobile_api_key)],
)


@router.post("/register", response_model=StaffAuthOut, status_code=201)
def staff_register(payload: StaffRegisterIn, db: Session = Depends(get_db)):
    try:
        return staff_auth_service.register(
            db, username=payload.username, name=payload.name, password=payload.password
        )
    except staff_auth_service.UsernameAlreadyRegisteredError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/login", response_model=StaffAuthOut)
def staff_login(payload: StaffLoginIn, db: Session = Depends(get_db)):
    try:
        return staff_auth_service.login(db, username=payload.username, password=payload.password)
    except staff_auth_service.InvalidStaffCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout", status_code=204)
def staff_logout(x_staff_token: str = Header(...), db: Session = Depends(get_db)):
    staff_auth_service.logout(db, x_staff_token)
