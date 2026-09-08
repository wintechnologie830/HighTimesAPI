import hashlib
import hmac
import os

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import general_client
from app.models import CustomerCredential
from app.services.points_service import get_or_create_account

PBKDF2_ITERATIONS = 390_000


class NameAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def _verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    digest_hex, _ = _hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest_hex, expected_hash_hex)


def register(db: Session, name: str, password: str, phone: str | None = None) -> dict:
    """
    Create a brand new customer: a real Customer row in Aronium (via
    generalAPI, so the till/reports know them too), a local
    CustomerCredential so they can sign back in, and an empty
    LoyaltyAccount so their balance starts at 0.
    """
    name = name.strip()
    existing = db.query(CustomerCredential).filter(CustomerCredential.name == name).first()
    if existing is not None:
        raise NameAlreadyRegisteredError(f"'{name}' is already registered")

    # 1. Create the real Aronium customer first - if this fails (generalAPI
    # down, etc.) we haven't written anything locally yet.
    customer = general_client.create_customer(name=name, email=None, phone=phone)

    # 2. Store credentials locally, linked to that customer's Aronium id.
    password_hash, salt = _hash_password(password)
    credential = CustomerCredential(
        aronium_customer_id=customer["Id"],
        name=name,
        password_hash=password_hash,
        password_salt=salt,
    )
    db.add(credential)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise NameAlreadyRegisteredError(f"'{name}' is already registered")

    # 3. Give them a loyalty account, starting at 0 points.
    get_or_create_account(db, customer["Id"])

    return {"aronium_customer_id": customer["Id"], "name": customer["Name"]}


def login(db: Session, name: str, password: str) -> dict:
    name = name.strip()
    credential = db.query(CustomerCredential).filter(CustomerCredential.name == name).first()
    if credential is None or not _verify_password(password, credential.password_salt, credential.password_hash):
        raise InvalidCredentialsError("Incorrect name or password")

    customer = general_client.get_customer(credential.aronium_customer_id)
    return {"aronium_customer_id": customer["Id"], "name": customer["Name"]}
