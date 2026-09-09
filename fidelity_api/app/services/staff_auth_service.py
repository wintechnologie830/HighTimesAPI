import secrets

from sqlalchemy.orm import Session

from app.models import StaffCredential, StaffSession
from app.security import hash_password, verify_password


class InvalidStaffCredentialsError(Exception):
    pass


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import StaffCredential, StaffSession
from app.security import hash_password, verify_password


class InvalidStaffCredentialsError(Exception):
    pass


class UsernameAlreadyRegisteredError(Exception):
    pass


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def register(db: Session, username: str, name: str, password: str) -> dict:
    """
    Self-service staff sign-up. Deliberately still has nothing to do with
    Aronium or CustomerCredential - it just writes a StaffCredential row
    in loyalty.db, same as it would if an admin had created the account
    by hand. Logs the new account straight in, same as customer register()
    does, so there's one less step before they can use the pickup desk.
    """
    username = username.strip()
    name = name.strip()
    existing = db.query(StaffCredential).filter(StaffCredential.username == username).first()
    if existing is not None:
        raise UsernameAlreadyRegisteredError(f"'{username}' is already taken")

    password_hash, salt = hash_password(password)
    staff = StaffCredential(
        username=username,
        name=name,
        password_hash=password_hash,
        password_salt=salt,
    )
    db.add(staff)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise UsernameAlreadyRegisteredError(f"'{username}' is already taken")
    db.refresh(staff)

    session = StaffSession(staff_id=staff.id, token=_generate_token())
    db.add(session)
    db.commit()

    return {"staff_id": staff.id, "name": staff.name, "token": session.token}


def login(db: Session, username: str, password: str) -> dict:
    """
    Verifies a staff member's own username/password (never Aronium, never
    the shared staff PIN) and hands back a session token. The token - not
    the staff id - is what the pickup desk sends back on every staff
    action from then on, so a customer poking at the network tab can't
    just guess a low integer and impersonate a staff member.
    """
    username = username.strip()
    staff = db.query(StaffCredential).filter(StaffCredential.username == username).first()
    if (
        staff is None
        or not staff.is_active
        or not verify_password(password, staff.password_salt, staff.password_hash)
    ):
        raise InvalidStaffCredentialsError("Incorrect username or password")

    session = StaffSession(staff_id=staff.id, token=_generate_token())
    db.add(session)
    db.commit()

    return {"staff_id": staff.id, "name": staff.name, "token": session.token}


def logout(db: Session, token: str) -> None:
    db.query(StaffSession).filter(StaffSession.token == token).delete()
    db.commit()


def get_staff_by_token(db: Session, token: str) -> StaffCredential | None:
    if not token:
        return None
    session = db.query(StaffSession).filter(StaffSession.token == token).first()
    if session is None:
        return None
    staff = db.query(StaffCredential).filter(StaffCredential.id == session.staff_id).first()
    if staff is None or not staff.is_active:
        return None
    return staff
