"""Create/update SMS-related tables and seed default SMS templates.

Run after deploying Phase11-4B / v0.11.6:
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


def _create_index_if_missing(index_name, sql):
    inspector = inspect(db.engine)
    existing = {index["name"] for index in inspector.get_indexes("sms_logs")}
    if index_name in existing:
        return False
    db.session.execute(text(sql))
    db.session.commit()
    return True


with app.app_context():
    db.create_all()

    added_columns = []
    created_indexes = []

    for column_name, column_sql in [
        ("template_key", "template_key VARCHAR(50)"),
        ("recipient_type", "recipient_type VARCHAR(20) NOT NULL DEFAULT 'customer'"),
        ("scheduled_for", "scheduled_for DATETIME"),
        ("reminder_date", "reminder_date DATE"),
        ("dedupe_key", "dedupe_key VARCHAR(255)"),
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
        ("admin_sms_booking_reminder_enabled", "admin_sms_booking_reminder_enabled BOOLEAN DEFAULT 1"),
    ]:
        if _add_column_if_missing("shop_settings", column_name, column_sql):
            added_columns.append(f"shop_settings.{column_name}")

    if _create_index_if_missing(
        "uq_sms_logs_dedupe_key",
        "CREATE UNIQUE INDEX uq_sms_logs_dedupe_key ON sms_logs (dedupe_key) WHERE dedupe_key IS NOT NULL",
    ):
        created_indexes.append("uq_sms_logs_dedupe_key")

    created = ensure_default_sms_templates()

    migrated_template_phrases = 0
    reminder_replacements = {
        "This is a reminder for your booking tomorrow.": "This is a reminder for your booking today.",
        "Tomorrow's confirmed booking": "Today's confirmed booking",
    }
    for template_key in ("booking_reminder", "admin_booking_reminder"):
        template = SmsTemplate.query.filter_by(template_key=template_key).first()
        if not template:
            continue
        updated_content = template.content
        for old_text, new_text in reminder_replacements.items():
            if old_text in updated_content:
                updated_content = updated_content.replace(old_text, new_text)
                migrated_template_phrases += 1
        if updated_content != template.content:
            template.content = updated_content
    if migrated_template_phrases:
        db.session.commit()

    print("SMS tables/settings are ready for Phase11-4B v0.11.6.")
    print(f"Columns added: {', '.join(added_columns) if added_columns else 'none'}")
    print(f"Indexes created: {', '.join(created_indexes) if created_indexes else 'none'}")
    print(f"Default templates created: {created}")
    print(f"Legacy reminder phrases migrated: {migrated_template_phrases}")
