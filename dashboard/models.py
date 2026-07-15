from datetime import datetime
from extensions import db


class ShopSettings(db.Model):
    __tablename__ = "shop_settings"

    id = db.Column(db.Integer, primary_key=True)

    no_show_limit_count = db.Column(db.Integer, default=3)
    same_day_cancel_block_enabled = db.Column(db.Boolean, default=True)
    deposit_enabled = db.Column(db.Boolean, default=False)
    deposit_bank_name = db.Column(db.String(100), nullable=True)
    deposit_account_number = db.Column(db.String(100), nullable=True)
    deposit_account_holder = db.Column(db.String(100), nullable=True)
    deposit_notice = db.Column(db.Text, nullable=True)
    deposit_due_minutes = db.Column(db.Integer, default=30)

    admin_sms_recipients = db.Column(db.Text, nullable=True)
    admin_sms_booking_created_enabled = db.Column(db.Boolean, default=True)
    admin_sms_booking_changed_enabled = db.Column(db.Boolean, default=True)
    admin_sms_booking_cancelled_enabled = db.Column(db.Boolean, default=True)
    admin_sms_deposit_request_enabled = db.Column(db.Boolean, default=True)
    admin_sms_deposit_paid_enabled = db.Column(db.Boolean, default=True)
    admin_sms_booking_reminder_enabled = db.Column(db.Boolean, default=True)

    booking_approval_mode = db.Column(db.String(30), default="auto")
    # auto / manual

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminUser(db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)


    



class AdminNotification(db.Model):
    __tablename__ = "admin_notifications"

    id = db.Column(db.Integer, primary_key=True)

    notification_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)

    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True)
    target_url = db.Column(db.String(500), nullable=True)

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    booking = db.relationship("Booking", backref="admin_notifications")
