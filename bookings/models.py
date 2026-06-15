from datetime import datetime
from extensions import db


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)

    category = db.Column(db.String(30), nullable=False)  # nail / waxing
    name_ko = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100), nullable=True)

    duration_minutes = db.Column(db.Integer, nullable=False)  # 30 / 60 / 90 / 120
    price = db.Column(db.Integer, nullable=False)

    deposit_required = db.Column(db.Boolean, default=False)
    deposit_amount = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True)


class StaffService(db.Model):
    __tablename__ = "staff_services"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)

    staff = db.relationship("Staff", backref="staff_services")
    service = db.relationship("Service", backref="staff_services")


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.String(30), default="pending")
    # pending / confirmed / completed / cancelled / no_show
    previous_status = db.Column(db.String(30), nullable=True)

    deposit_paid = db.Column(db.Boolean, default=False)
    deposit_payment_status = db.Column(db.String(30), default="none")
    deposit_payment_link = db.Column(db.String(500), nullable=True)
    deposit_note = db.Column(db.Text, nullable=True)
    # none / required / paid / refunded / failed

    late_notice_minutes = db.Column(db.Integer, nullable=True)

    memo = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship("Customer", backref="bookings")
    staff = db.relationship("Staff", backref="bookings")
    service = db.relationship("Service", backref="bookings")


class BookingEvent(db.Model):
    __tablename__ = "booking_events"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)

    event_type = db.Column(db.String(50), nullable=False)
    # created / confirmed / cancelled / changed / completed / no_show / late_notice

    memo = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship("Booking", backref="events")
