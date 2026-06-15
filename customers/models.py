from datetime import datetime
from extensions import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=True)

    social_provider = db.Column(db.String(30), nullable=True)
    social_id = db.Column(db.String(255), nullable=True)

    login_provider = db.Column(db.String(30), nullable=True)
    provider_user_id = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    

    no_show_count = db.Column(db.Integer, default=0)
    booking_restricted = db.Column(db.Boolean, default=False)

    memo = db.Column(db.Text, nullable=True)
    preferred_style = db.Column(db.Text, nullable=True)
    skin_sensitivity = db.Column(db.Text, nullable=True)
    complaint_note = db.Column(db.Text, nullable=True)

    
    visit_count = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
