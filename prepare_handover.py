#!/usr/bin/env python3
"""Prepare the Salon De Nature SQLite database for production handover.

Preserved:
- One administrator account selected by --admin-username (or the only admin account)
- Service catalog
- Shop settings
- SMS templates
- Alembic migration version

Removed:
- Other administrator accounts
- Customers and customer login data
- Staff accounts and profiles
- Staff schedules, time off and staff-service assignments
- Bookings, booking events and payment records
- SMS logs and administrator notifications
- Uploaded staff profile image files referenced by removed staff records

The command is dry-run by default. Use --execute to perform deletion.
A timestamped SQLite backup is always created before an executed cleanup.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB = PROJECT_ROOT / "beauty_shop.db"

DELETE_ORDER = [
    "sms_logs",
    "payments",
    "booking_events",
    "admin_notifications",
    "bookings",
    "staff_time_offs",
    "staff_schedules",
    "staff_services",
    "customers",
    "staff",
]

PRESERVED_TABLES = [
    "services",
    "shop_settings",
    "sms_templates",
    "alembic_version",
]


def load_database_path(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("sqlite:"):
        parsed = urlparse(database_url)
        raw_path = unquote(parsed.path)
        if raw_path:
            path = Path(raw_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return path.resolve()

    return DEFAULT_DB.resolve()


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def choose_admin(connection: sqlite3.Connection, username: str | None) -> tuple[int, str]:
    admins = connection.execute(
        "SELECT id, username, is_active FROM admin_users ORDER BY id"
    ).fetchall()

    if not admins:
        raise RuntimeError("No administrator account exists. Cleanup was stopped.")

    if username:
        matches = [row for row in admins if row[1] == username]
        if not matches:
            available = ", ".join(row[1] for row in admins)
            raise RuntimeError(
                f"Administrator '{username}' was not found. Available: {available}"
            )
        return int(matches[0][0]), str(matches[0][1])

    if len(admins) == 1:
        return int(admins[0][0]), str(admins[0][1])

    available = ", ".join(row[1] for row in admins)
    raise RuntimeError(
        "Multiple administrator accounts exist. "
        "Run again with --admin-username. Available: " + available
    )


def referenced_staff_images(connection: sqlite3.Connection, tables: set[str]) -> list[Path]:
    if "staff" not in tables:
        return []

    images: list[Path] = []
    for (profile_image,) in connection.execute(
        "SELECT profile_image FROM staff WHERE profile_image IS NOT NULL AND profile_image <> ''"
    ).fetchall():
        relative = str(profile_image).lstrip("/")
        candidate = (PROJECT_ROOT / relative).resolve()
        uploads_root = (PROJECT_ROOT / "static" / "uploads" / "staff").resolve()
        try:
            candidate.relative_to(uploads_root)
        except ValueError:
            continue
        images.append(candidate)
    return images


def reset_sqlite_sequences(connection: sqlite3.Connection, tables: set[str]) -> None:
    if "sqlite_sequence" not in tables:
        return
    targets = DELETE_ORDER + ["admin_notifications"]
    placeholders = ",".join("?" for _ in targets)
    connection.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
        targets,
    )


def print_plan(
    connection: sqlite3.Connection,
    tables: set[str],
    admin_username: str,
    image_paths: list[Path],
) -> None:
    print("\n=== Salon De Nature handover cleanup plan ===")
    print(f"Administrator preserved: {admin_username}")
    print("\nRows to remove:")
    for table in DELETE_ORDER:
        if table in tables:
            print(f"  - {table}: {count_rows(connection, table)}")
    if "admin_users" in tables:
        admin_count = count_rows(connection, "admin_users")
        print(f"  - additional admin_users: {max(0, admin_count - 1)}")

    print("\nTables/data preserved:")
    print("  - selected administrator account")
    for table in PRESERVED_TABLES:
        if table in tables:
            print(f"  - {table}: {count_rows(connection, table)}")

    print(f"\nReferenced staff profile images to remove: {len(image_paths)}")
    for path in image_paths:
        print(f"  - {path.relative_to(PROJECT_ROOT)}")


def run_cleanup(database_path: Path, admin_username: str | None, execute: bool) -> int:
    if not database_path.exists():
        print(f"Database not found: {database_path}", file=sys.stderr)
        return 2

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        tables = table_names(connection)
        required = {"admin_users", "customers", "staff", "bookings"}
        missing = required - tables
        if missing:
            raise RuntimeError("Unexpected database schema. Missing: " + ", ".join(sorted(missing)))

        admin_id, selected_username = choose_admin(connection, admin_username)
        images = referenced_staff_images(connection, tables)
        print(f"Database: {database_path}")
        print_plan(connection, tables, selected_username, images)

        if not execute:
            print("\nDRY RUN ONLY: no data was changed.")
            print("Run with --execute after reviewing the plan.")
            return 0

        backup_dir = PROJECT_ROOT / "handover_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"beauty_shop_before_handover_{timestamp}.db"

        backup_connection = sqlite3.connect(backup_path)
        try:
            connection.backup(backup_connection)
        finally:
            backup_connection.close()

        print(f"\nBackup created: {backup_path}")

        try:
            connection.execute("BEGIN IMMEDIATE")
            for table in DELETE_ORDER:
                if table in tables:
                    connection.execute(f'DELETE FROM "{table}"')

            connection.execute("DELETE FROM admin_users WHERE id <> ?", (admin_id,))
            reset_sqlite_sequences(connection, tables)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        removed_images = 0
        for image_path in images:
            try:
                if image_path.exists() and image_path.is_file():
                    image_path.unlink()
                    removed_images += 1
            except OSError as exc:
                print(f"Warning: could not remove {image_path}: {exc}", file=sys.stderr)

        print("\nCleanup completed.")
        print(f"Administrator preserved: {selected_username}")
        print(f"Staff profile images removed: {removed_images}")
        print("Customers, staff, bookings and operational history are now empty.")
        return 0
    except (RuntimeError, sqlite3.DatabaseError) as exc:
        print(f"Cleanup stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely remove test operational data before salon handover."
    )
    parser.add_argument(
        "--database",
        help="SQLite database path. Defaults to DATABASE_URL or beauty_shop.db.",
    )
    parser.add_argument(
        "--admin-username",
        help="Administrator username to preserve. Required when multiple admins exist.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform cleanup. Without this option the command is a dry run.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run_cleanup(
            database_path=load_database_path(args.database),
            admin_username=args.admin_username,
            execute=args.execute,
        )
    )
