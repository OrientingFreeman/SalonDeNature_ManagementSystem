"""Create SMS log/template tables and seed default SMS templates.

Run once after deploying Phase11-3:
    python create_sms_tables.py
"""

from app import app
from extensions import db
from sms.models import SmsLog, SmsTemplate  # noqa: F401
from sms.service import ensure_default_sms_templates


with app.app_context():
    db.create_all()
    created = ensure_default_sms_templates()
    print("SMS tables are ready.")
    print(f"Default templates created: {created}")
