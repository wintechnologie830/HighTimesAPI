from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_mobile_api_key
from app.database import get_db
from app.schemas import AuthOut, LoginIn, RegisterIn
from app.services import auth_service

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(require_mobile_api_key)],
)


@router.post("/register", response_model=AuthOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    try:
        return auth_service.register(
            db,
            name=payload.name,
            password=payload.password,
            phone=payload.phone,
        )
    except auth_service.NameAlreadyRegisteredError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    try:
        return auth_service.login(db, name=payload.name, password=payload.password)
    except auth_service.InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e))
