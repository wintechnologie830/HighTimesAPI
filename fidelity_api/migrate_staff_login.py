import sqlite3

from app.config import settings
from app.database import Base, engine
from app import models


def main():
    Base.metadata.create_all(bind=engine)

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
