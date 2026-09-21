"""
One-time import of the customers that already exist in Aronium.

    python migrate_aronium_customers.py run --dry-run
    python migrate_aronium_customers.py run --csv claim_codes.csv
    python migrate_aronium_customers.py reissue 42 --csv code_42.csv

Needs general_api to be running (this script reads Aronium's customers through
it, like the rest of fidelity_api). See app/services/migration_service.py for
what "migrating" means and why customers receive an activation code.
"""

import argparse
import csv
import os
import sys

from fastapi import HTTPException

from app.database import SessionLocal, init_db
from app.services import migration_service

CSV_COLUMNS = [
    "aronium_customer_id",
    "name",
    "email",
    "phone",
    "claim_code",
    "username_conflict",
]


def _open_new_csv(path: str):
    # 'x' = never overwrite: the codes in an earlier file can't be regenerated.
    # utf-8-sig so Excel on Windows reads accented / non-Latin names correctly.
    try:
        return open(path, "x", newline="", encoding="utf-8-sig")
    except FileExistsError:
        print(f"'{path}' already exists - refusing to overwrite it. Choose another file name.")
        sys.exit(1)


def cmd_run(args):
    if not args.dry_run and not args.csv:
        print("A real run needs --csv <file>: activation codes are only shown once and "
              "cannot be recovered afterwards.\nUse --dry-run to preview without writing anything.")
        sys.exit(2)

    # Open the CSV BEFORE touching the database, so a bad path fails early.
    csv_file = _open_new_csv(args.csv) if (args.csv and not args.dry_run) else None

    def discard_csv():
        if csv_file is not None:
            csv_file.close()
            os.remove(args.csv)  # nothing was migrated, so don't leave an empty file behind

    db = SessionLocal()
    try:
        report = migration_service.migrate_aronium_customers(db, dry_run=args.dry_run)
    except HTTPException as e:
        discard_csv()
        print(f"Could not read customers from Aronium: {e.detail}")
        sys.exit(1)
    except BaseException:
        discard_csv()
        raise
    finally:
        db.close()

    if csv_file is not None:
        try:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_COLUMNS)
            for m in report.migrated:
                writer.writerow([
                    m.aronium_customer_id, m.name, m.email or "", m.phone or "",
                    m.claim_code, m.username_conflict or "",
                ])
            csv_file.close()
        except OSError as e:
            print(f"The customers WERE migrated, but writing {args.csv} failed ({e}).\n"
                  "Use the 'reissue' command to create a new code for each customer.")
            sys.exit(1)

    mode = "DRY RUN - nothing was written" if report.dry_run else "Migration complete"
    print(f"{mode}\n")
    print(f"  customers to migrate ................ {len(report.migrated)}")
    print(f"  skipped: already have an app account  {report.skipped_already_registered}")
    print(f"  skipped: already migrated ........... {report.skipped_already_migrated}")
    print(f"  skipped: disabled in Aronium ........ {report.skipped_disabled}")
    print(f"  skipped: walk-in / system record .... {report.skipped_system}")
    print("\n  Migrated accounts start at 0 points; past purchases are NOT compensated.")

    if report.conflicts:
        print(f"\nUSERNAME CONFLICTS ({len(report.conflicts)}) - these customers must choose a "
              "new username when they activate:")
        for m in report.conflicts:
            print(f"  #{m.aronium_customer_id:<5} {m.name!r}: {m.username_conflict}")

    if report.warnings:
        print("\nWARNINGS:")
        for w in report.warnings:
            print(f"  - {w}")

    if csv_file is not None:
        print(f"\nActivation codes written to {args.csv}. Keep that file private and hand each "
              "code to its customer.\nA lost code can be replaced with the 'reissue' command.")


def cmd_reissue(args):
    csv_file = _open_new_csv(args.csv) if args.csv else None
    db = SessionLocal()
    try:
        try:
            code = migration_service.reissue_claim_code(db, args.aronium_customer_id)
        except (migration_service.NotMigratedError, migration_service.AlreadyClaimedError) as e:
            print(e)
            if csv_file is not None:
                csv_file.close()
            sys.exit(1)
    finally:
        db.close()

    if csv_file is not None:
        writer = csv.writer(csv_file)
        writer.writerow(["aronium_customer_id", "claim_code"])
        writer.writerow([args.aronium_customer_id, code])
        csv_file.close()
        print(f"New activation code for customer #{args.aronium_customer_id} written to {args.csv}. "
              "The previous code no longer works.")
    else:
        print(f"New activation code for customer #{args.aronium_customer_id}: {code}\n"
              "The previous code no longer works.")


def main():
    init_db()  # creates the legacy_customers table on an existing loyalty.db

    parser = argparse.ArgumentParser(description="Import existing Aronium customers into the loyalty system")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Migrate every Aronium customer not yet in the loyalty system")
    p_run.add_argument("--dry-run", action="store_true", help="Preview only: write nothing, create no codes")
    p_run.add_argument("--csv", help="Where to write the activation codes (required for a real run)")
    p_run.set_defaults(func=cmd_run)

    p_re = sub.add_parser("reissue", help="Give a not-yet-activated customer a new activation code")
    p_re.add_argument("aronium_customer_id", type=int)
    p_re.add_argument("--csv", help="Write the code to this file instead of printing it")
    p_re.set_defaults(func=cmd_reissue)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
