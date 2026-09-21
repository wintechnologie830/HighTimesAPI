from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_mobile_api_key
from app.database import get_db
from app.schemas import AuthOut, ClaimIn, LoginIn, RegisterIn
from app.services import auth_service, migration_service

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


@router.post("/claim", response_model=AuthOut)
def claim(payload: ClaimIn, db: Session = Depends(get_db)):
    """
    Activate the account of a customer who already existed in Aronium before
    this app (see services/migration_service.py). They redeem the one-time
    activation code the store gave them and choose their own password.

    409 means the username is already taken - the customer must choose a
    different one and send the same request again with `username` set.
    """
    try:
        return migration_service.claim_account(
            db,
            claim_code=payload.claim_code,
            password=payload.password,
            username=payload.username,
        )
    except migration_service.InvalidClaimCodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except migration_service.UsernameRequiredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except migration_service.UsernameTakenError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    try:
        return auth_service.login(db, name=payload.name, password=payload.password)
    except auth_service.InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e))
