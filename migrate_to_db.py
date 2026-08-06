"""
migrate_to_db.py
================
One-time migration script.
Reads data/audit_results.csv and data/users.json and imports them
into the SQLite database (data/audit_system.db).

Run once:
    python migrate_to_db.py
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

from backend.database import init_db, migrate_from_csv, migrate_from_json, get_db_stats

CSV_PATH  = os.path.join(PROJECT_ROOT, "data", "audit_results.csv")
JSON_PATH = os.path.join(PROJECT_ROOT, "data", "users.json")


def main():
    print("=" * 55)
    print("  GenerativeAI Customer Support Auditor")
    print("  Database Migration: CSV/JSON -> SQLite")
    print("=" * 55)

    # 1. Initialise schema
    print("\n[1/3] Initialising database schema...")
    init_db()
    print("      [OK] Tables created (users, audit_sessions, audit_results)")

    # 2. Migrate audit CSV
    print(f"\n[2/3] Migrating audit data from: {CSV_PATH}")
    audit_count = migrate_from_csv(CSV_PATH)
    if audit_count:
        print(f"      [OK] {audit_count} audit rows imported")
    else:
        print("      [--] No CSV data found or file missing")

    # 3. Migrate users JSON
    print(f"\n[3/3] Migrating users from: {JSON_PATH}")
    user_count = migrate_from_json(JSON_PATH)
    if user_count:
        print(f"      [OK] {user_count} users imported")
    else:
        print("      [--] No users.json found or already migrated")

    # Final summary
    stats = get_db_stats()
    print("\n" + "=" * 55)
    print("  Migration Complete — Database Summary")
    print("=" * 55)
    print(f"  DB file       : {stats['db_file']}")
    print(f"  Total rows    : {stats['total_audit_rows']}")
    print(f"  Total users   : {stats['total_users']}")
    print(f"  Total sessions: {stats['total_sessions']}")
    print(f"  Status        : {stats['status'].upper()}")
    print("=" * 55)
    print("\nDone! The app will now read from SQLite instead of CSV.\n")


if __name__ == "__main__":
    main()
