from datetime import datetime

from extensions import db


class SmsTemplate(db.Model):
    __tablename__ = "sms_templates"

    id = db.Column(db.Integer, primary_key=True)
    template_key = db.Column(db.String(50), nullable=False, unique=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SmsTemplate {self.template_key}>"


class SmsLog(db.Model):
    __tablename__ = "sms_logs"
    __table_args__ = (db.UniqueConstraint("dedupe_key", name="uq_sms_logs_dedupe_key"),)

    id = db.Column(db.Integer, primary_key=True)

    event_type = db.Column(db.String(50), nullable=False, index=True)
    template_key = db.Column(db.String(50), nullable=True, index=True)
    recipient_type = db.Column(db.String(20), nullable=False, default="customer", index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True, index=True)
    scheduled_for = db.Column(db.DateTime, nullable=True, index=True)
    reminder_date = db.Column(db.Date, nullable=True, index=True)
    dedupe_key = db.Column(db.String(255), nullable=True, index=True)

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
