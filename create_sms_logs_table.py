from app import app
from extensions import db
from sms.models import SmsLog


with app.app_context():
    db.create_all()
    print("sms_logs table is ready.")
