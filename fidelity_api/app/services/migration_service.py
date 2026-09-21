"""
Bring customers that already exist in Aronium into the loyalty system.

The problem
-----------
The API is being plugged into a store that has been running Aronium for a
while, so it already has real customers. Those customers never went through
POST /auth/register, so they have no loyalty account and no login.

What "migrating" a customer does here
-------------------------------------
* Creates their LoyaltyAccount with a balance of exactly 0 and NO points
  transaction. Nothing they bought before today earns points - the loyalty
  programme starts for them at migration time. (The sync cursor is also
  started at "now" on a fresh install - see routers/sync.py - otherwise the
  background sync would award that history anyway.)
* Records them in `legacy_customers` with a single-use ACTIVATION CODE.

Why an activation code and not a password
-----------------------------------------
Aronium's Customer table has no password column, so there is nothing to
migrate credentials from. We must not invent a password for someone else, and
we must not let "whoever types the name first" take over an existing
customer's account. So each migrated customer gets a random one-time code
(handed out by the shop, e.g. from the CSV the CLI writes). They redeem it at
POST /auth/claim and choose their own password - and, if necessary, a
different username. Only the code's hash is stored, so a leaked loyalty.db
does not leak usable codes.

Username clashes
----------------
Login is by name and CustomerCredential.name is unique. If an old customer's
Aronium name is already an app username, or is shared with another old
customer, or is blank, they can't simply keep it:
* the migration report flags them up front (`username_conflict`), so the shop
  can warn them; and
* claim_account() refuses a taken name with UsernameTakenError (HTTP 409), which
  tells the customer to choose a different one. Whoever already holds a
  name keeps it; the old customer is the one asked to change.
The customer's Aronium record is never renamed - the till keeps showing the
name staff know them by, and only the app username differs.

Safe to run more than once: customers already registered, or already
migrated, are skipped.
"""

import hashlib
import re
import secrets
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import general_client
from app.models import (
    CustomerCredential,
    LegacyCustomer,
    LoyaltyAccount,
    PointsTransaction,
)
from app.security import hash_password
from app.services.points_service import get_or_create_account

# Aronium ships with a built-in "Walk-in customer" (Id 1) used for anonymous
# sales. It is not a real person, so it never gets an account.
WALK_IN_CUSTOMER_ID = 1
WALK_IN_CUSTOMER_NAME = "walk-in customer"

# 32 symbols, no 0/O/1/I, so a code read out over the counter isn't misheard.
# 12 symbols = 60 bits, comfortably unguessable for a single-use code.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 12


class InvalidClaimCodeError(Exception):
    pass


class UsernameRequiredError(Exception):
    pass


class UsernameTakenError(Exception):
    pass


class NotMigratedError(Exception):
    pass


class AlreadyClaimedError(Exception):
    pass


# ---------- small helpers ----------

def _normalize_username(name: str | None) -> str:
    # casefold + strip: "Amine", "amine " and "AMINE" are the same person as far
    # as a username clash goes, which avoids look-alike accounts.
    return (name or "").strip().casefold()


def _normalize_code(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", code or "").upper()


def _hash_code(code: str) -> str:
    # Plain SHA-256 is fine here (unlike passwords): the code is 60 random bits,
    # not something a person chose, and a deterministic hash lets us look it up.
    return hashlib.sha256(_normalize_code(code).encode("utf-8")).hexdigest()


def _new_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


def _is_system_customer(customer: dict) -> bool:
    return (
        customer["Id"] == WALK_IN_CUSTOMER_ID
        or _normalize_username(customer["Name"]) == WALK_IN_CUSTOMER_NAME
    )


# ---------- migration report ----------

@dataclass
class MigratedCustomer:
    aronium_customer_id: int
    name: str
    email: str | None
    phone: str | None
    # Plain-text activation code. Exists ONLY in this report (None on a dry
    # run) - the database keeps just a hash, so it cannot be recovered later.
    claim_code: str | None
    # None when the Aronium name is free to use as a username; otherwise why
    # this customer will have to choose a different one.
    username_conflict: str | None


@dataclass
class MigrationReport:
    dry_run: bool
    migrated: list[MigratedCustomer] = field(default_factory=list)
    skipped_already_registered: int = 0
    skipped_already_migrated: int = 0
    skipped_disabled: int = 0
    skipped_system: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def conflicts(self) -> list[MigratedCustomer]:
        return [m for m in self.migrated if m.username_conflict]


# ---------- migrate ----------

def migrate_aronium_customers(db: Session, dry_run: bool = False) -> MigrationReport:
    """
    Create a loyalty account (0 points, no history) and an activation code for
    every real, enabled Aronium customer that isn't in the loyalty system yet.

    dry_run=True computes the exact same report but writes nothing and
    generates no codes. Everything is written in ONE transaction: it either
    all happens or none of it does.
    """
    customers = general_client.list_customers()

    registered_ids = {r[0] for r in db.query(CustomerCredential.aronium_customer_id)}
    migrated_ids = {r[0] for r in db.query(LegacyCustomer.aronium_customer_id)}
    taken_usernames = {_normalize_username(r[0]) for r in db.query(CustomerCredential.name)}
    accounts = {a.aronium_customer_id: a for a in db.query(LoyaltyAccount)}
    accounts_with_history = {r[0] for r in db.query(PointsTransaction.account_id).distinct()}

    report = MigrationReport(dry_run=dry_run)

    candidates = []
    for c in customers:
        if _is_system_customer(c):
            report.skipped_system += 1
        elif not c.get("IsEnabled"):
            report.skipped_disabled += 1
        elif c["Id"] in registered_ids:
            report.skipped_already_registered += 1
        elif c["Id"] in migrated_ids:
            report.skipped_already_migrated += 1
        else:
            candidates.append(c)

    # Names shared by several customers still waiting to be migrated: only one
    # of them can ever hold that username.
    shared_count = Counter(_normalize_username(c["Name"]) for c in candidates)

    used_codes: set[str] = set()
    for c in candidates:
        name = (c["Name"] or "").strip()
        key = _normalize_username(name)

        conflict = None
        if not key:
            conflict = "Has no usable name in Aronium - must choose a username"
        elif key in taken_usernames:
            conflict = f"Username '{name}' is already used by an existing app account"
        elif shared_count[key] > 1:
            conflict = (
                f"Shares the name '{name}' with {shared_count[key] - 1} other "
                "Aronium customer(s); only one of them can keep it as a username"
            )

        code = None
        if not dry_run:
            code = _new_code()
            while _hash_code(code) in used_codes:  # 60 bits: practically never
                code = _new_code()
            used_codes.add(_hash_code(code))

            db.add(LegacyCustomer(aronium_customer_id=c["Id"], claim_code_hash=_hash_code(code)))

        # The account: balance 0 and deliberately NO PointsTransaction -
        # past purchases are not compensated.
        existing_account = accounts.get(c["Id"])
        if existing_account is None:
            if not dry_run:
                db.add(LoyaltyAccount(aronium_customer_id=c["Id"], points_balance=0.0))
        elif existing_account.id in accounts_with_history:
            report.warnings.append(
                f"Customer #{c['Id']} '{name}' already had a loyalty account with "
                f"{existing_account.points_balance:g} points (auto-sync ran before "
                "migration). Left untouched - review it if those are pre-migration sales."
            )

        report.migrated.append(
            MigratedCustomer(
                aronium_customer_id=c["Id"],
                name=name,
                email=c.get("Email"),
                phone=c.get("PhoneNumber"),
                claim_code=code,
                username_conflict=conflict,
            )
        )

    if not dry_run and report.migrated:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise
    return report


# ---------- claim (customer activates their account) ----------

def claim_account(
    db: Session, claim_code: str, password: str, username: str | None = None
) -> dict:
    legacy = (
        db.query(LegacyCustomer)
        .filter(LegacyCustomer.claim_code_hash == _hash_code(claim_code))
        .first()
    )
    if legacy is None or legacy.date_claimed is not None:
        raise InvalidClaimCodeError("Invalid or already used activation code")

    customer = general_client.get_customer(legacy.aronium_customer_id)
    if not customer.get("IsEnabled"):
        raise InvalidClaimCodeError(
            "This customer record is no longer active - please ask the store"
        )

    chosen = (username if username is not None else customer["Name"] or "").strip()
    if not chosen:
        raise UsernameRequiredError("Please choose a username")

    taken = {_normalize_username(r[0]) for r in db.query(CustomerCredential.name)}
    if _normalize_username(chosen) in taken:
        raise UsernameTakenError(
            f"The username '{chosen}' is already taken. Please choose a different username."
        )

    password_hash, salt = hash_password(password)
    db.add(
        CustomerCredential(
            aronium_customer_id=legacy.aronium_customer_id,
            name=chosen,
            password_hash=password_hash,
            password_salt=salt,
        )
    )
    legacy.date_claimed = datetime.now()
    try:
        # credential + "code used" land together, or not at all
        db.commit()
    except IntegrityError:
        # someone took the name between our check and the insert
        db.rollback()
        raise UsernameTakenError(
            f"The username '{chosen}' is already taken. Please choose a different username."
        )

    get_or_create_account(db, legacy.aronium_customer_id)
    return {"aronium_customer_id": customer["Id"], "name": customer["Name"]}


# ---------- reissue (lost / never-delivered code) ----------

def reissue_claim_code(db: Session, aronium_customer_id: int) -> str:
    """New activation code for a migrated customer who hasn't activated yet.
    The previous code stops working immediately."""
    legacy = (
        db.query(LegacyCustomer)
        .filter(LegacyCustomer.aronium_customer_id == aronium_customer_id)
        .first()
    )
    if legacy is None:
        raise NotMigratedError(f"Aronium customer #{aronium_customer_id} was not migrated")
    if legacy.date_claimed is not None:
        raise AlreadyClaimedError(
            f"Customer #{aronium_customer_id} has already activated their account"
        )

    code = _new_code()
    legacy.claim_code_hash = _hash_code(code)
    db.commit()
    return code
