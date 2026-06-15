from datetime import datetime
from extensions import db


class ShopSettings(db.Model):
    __tablename__ = "shop_settings"

    id = db.Column(db.Integer, primary_key=True)

    no_show_limit_count = db.Column(db.Integer, default=3)
    same_day_cancel_block_enabled = db.Column(db.Boolean, default=True)
    deposit_enabled = db.Column(db.Boolean, default=False)

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


    
