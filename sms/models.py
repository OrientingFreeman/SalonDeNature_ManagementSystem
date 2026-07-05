from datetime import datetime

from extensions import db


class SmsLog(db.Model):
    __tablename__ = "sms_logs"

    id = db.Column(db.Integer, primary_key=True)

    event_type = db.Column(db.String(50), nullable=False, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True, index=True)

    recipient_phone = db.Column(db.String(30), nullable=True)
    message = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    # sent / skipped / failed
    provider = db.Column(db.String(30), nullable=False, default="solapi")
    provider_message_id = db.Column(db.String(120), nullable=True)
    provider_response = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    booking = db.relationship("Booking", backref="sms_logs")
