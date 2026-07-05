"""Create/update SMS-related tables and seed default SMS templates.

Run after deploying Phase11-4A:
    python create_sms_tables.py

This script is intentionally idempotent for SQLite deployments.
"""

from sqlalchemy import inspect, text

from app import app
from extensions import db
from dashboard.models import ShopSettings  # noqa: F401
from sms.models import SmsLog, SmsTemplate  # noqa: F401
from sms.service import ensure_default_sms_templates


def _add_column_if_missing(table_name, column_name, column_sql):
    inspector = inspect(db.engine)
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return False

    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
    db.session.commit()
    return True


with app.app_context():
    db.create_all()

    added_columns = []

    for column_name, column_sql in [
        ("template_key", "template_key VARCHAR(50)"),
        ("recipient_type", "recipient_type VARCHAR(20) NOT NULL DEFAULT 'customer'"),
    ]:
        if _add_column_if_missing("sms_logs", column_name, column_sql):
            added_columns.append(f"sms_logs.{column_name}")

    for column_name, column_sql in [
        ("admin_sms_recipients", "admin_sms_recipients TEXT"),
        ("admin_sms_booking_created_enabled", "admin_sms_booking_created_enabled BOOLEAN DEFAULT 1"),
        ("admin_sms_booking_changed_enabled", "admin_sms_booking_changed_enabled BOOLEAN DEFAULT 1"),
        ("admin_sms_booking_cancelled_enabled", "admin_sms_booking_cancelled_enabled BOOLEAN DEFAULT 1"),
        ("admin_sms_deposit_request_enabled", "admin_sms_deposit_request_enabled BOOLEAN DEFAULT 1"),
        ("admin_sms_deposit_paid_enabled", "admin_sms_deposit_paid_enabled BOOLEAN DEFAULT 1"),
    ]:
        if _add_column_if_missing("shop_settings", column_name, column_sql):
            added_columns.append(f"shop_settings.{column_name}")

    created = ensure_default_sms_templates()

    print("SMS tables/settings are ready.")
    print(f"Columns added: {', '.join(added_columns) if added_columns else 'none'}")
    print(f"Default templates created: {created}")
