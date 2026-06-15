from datetime import datetime
from extensions import db


class Staff(db.Model):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


    username = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    
    last_login_at = db.Column(db.DateTime, nullable=True)

    role = db.Column(db.String(30), default="staff")  # owner / staff
    phone = db.Column(db.String(50), nullable=True)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class StaffSchedule(db.Model):
    __tablename__ = "staff_schedules"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)

    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Mon, 6=Sun
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    break_start_time = db.Column(db.Time, nullable=True)
    break_end_time = db.Column(db.Time, nullable=True)

    is_working = db.Column(db.Boolean, default=True)

    staff = db.relationship("Staff", backref="schedules")
