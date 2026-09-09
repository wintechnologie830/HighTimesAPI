"""
One-off migration: adds staff login support to an EXISTING loyalty.db.
Safe to run more than once - it checks before creating/altering anything.

Run ONCE after deploying this version (from the fidelity_api/ directory,
with your venv active), before starting uvicorn:

    python migrate_staff_login.py

What it does:
1. Creates the two brand-new tables staff_credentials and staff_sessions
   (Base.metadata.create_all only ever creates *missing* tables, so this
   part would also happen automatically on next startup - doing it here
   just makes it happen up front, alongside step 2).
2. Adds a staff_id column to the existing redemptions table. This one
   step create_all() can NOT do on its own - it never alters a table
   that already exists, so without this script every existing
   loyalty.db would be missing the column and fulfill() would fail.

After running this, use manage_staff.py to create staff accounts.
"""
import sqlite3

from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401  (ensures models are registered)


def main():
    # 1. Create staff_credentials / staff_sessions if they don't exist yet.
    Base.metadata.create_all(bind=engine)

    # 2. Add redemptions.staff_id if the column isn't there already.
    conn = sqlite3.connect(settings.loyalty_db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(redemptions)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "staff_id" in existing_columns:
            print("redemptions.staff_id already exists - nothing to migrate.")
            return
        cur.execute(
            "ALTER TABLE redemptions ADD COLUMN staff_id INTEGER "
            "REFERENCES staff_credentials(id)"
        )
        conn.commit()
        print("Added redemptions.staff_id.")
    finally:
        conn.close()

    print("Migration complete. Existing redemptions have staff_id = NULL, "
          "which is expected - they predate staff attribution.")


if __name__ == "__main__":
    main()
