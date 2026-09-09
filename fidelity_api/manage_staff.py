import argparse
import getpass
import sys

from app.database import SessionLocal, init_db
from app.models import StaffCredential
from app.security import hash_password


def _prompt_password() -> str | None:
    password = getpass.getpass("Password (min 8 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords didn't match.")
        return None
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return None
    return password


def cmd_add(args):
    db = SessionLocal()
    try:
        existing = db.query(StaffCredential).filter(StaffCredential.username == args.username).first()
        if existing is not None:
            print(f"'{args.username}' already exists.")
            sys.exit(1)

        password = _prompt_password()
        if password is None:
            sys.exit(1)

        password_hash, salt = hash_password(password)
        staff = StaffCredential(
            username=args.username,
            name=args.name,
            password_hash=password_hash,
            password_salt=salt,
        )
        db.add(staff)
        db.commit()
        db.refresh(staff)
        print(f"Created staff account: id={staff.id}  username={staff.username}  name={staff.name}")
    finally:
        db.close()


def cmd_list(args):
    db = SessionLocal()
    try:
        staff_rows = db.query(StaffCredential).order_by(StaffCredential.id).all()
        if not staff_rows:
            print("No staff accounts yet - use 'add' to create one.")
            return
        for s in staff_rows:
            status = "active" if s.is_active else "disabled"
            print(f"{s.id:>4}  {s.username:<20} {s.name:<25} {status}")
    finally:
        db.close()


def _set_active(username: str, active: bool):
    db = SessionLocal()
    try:
        staff = db.query(StaffCredential).filter(StaffCredential.username == username).first()
        if staff is None:
            print(f"No staff account '{username}'.")
            sys.exit(1)
        staff.is_active = active
        db.commit()
        print(f"{'Activated' if active else 'Deactivated'} '{username}'.")
    finally:
        db.close()


def cmd_deactivate(args):
    _set_active(args.username, False)


def cmd_activate(args):
    _set_active(args.username, True)


def cmd_reset_password(args):
    db = SessionLocal()
    try:
        staff = db.query(StaffCredential).filter(StaffCredential.username == args.username).first()
        if staff is None:
            print(f"No staff account '{args.username}'.")
            sys.exit(1)

        password = _prompt_password()
        if password is None:
            sys.exit(1)

        password_hash, salt = hash_password(password)
        staff.password_hash = password_hash
        staff.password_salt = salt
        db.commit()
        print(f"Password reset for '{args.username}'.")
    finally:
        db.close()


def main():
    init_db()

    parser = argparse.ArgumentParser(description="Manage fidelityAPI staff login accounts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_add = subparsers.add_parser("add", help="Create a new staff account")
    p_add.add_argument("username")
    p_add.add_argument("name", help="Full name, shown to other staff on the pickup desk")
    p_add.set_defaults(func=cmd_add)

    p_list = subparsers.add_parser("list", help="List all staff accounts")
    p_list.set_defaults(func=cmd_list)

    p_deactivate = subparsers.add_parser("deactivate", help="Disable a staff account's login")
    p_deactivate.add_argument("username")
    p_deactivate.set_defaults(func=cmd_deactivate)

    p_activate = subparsers.add_parser("activate", help="Re-enable a staff account's login")
    p_activate.add_argument("username")
    p_activate.set_defaults(func=cmd_activate)

    p_reset = subparsers.add_parser("reset-password", help="Set a new password for a staff account")
    p_reset.add_argument("username")
    p_reset.set_defaults(func=cmd_reset_password)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
