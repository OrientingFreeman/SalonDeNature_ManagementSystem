from datetime import datetime, time
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import Staff, Booking
from bookings.services import update_booking_status


staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


def staff_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "staff_id" not in session:
            return redirect(url_for("staff.staff_login"))
        return func(*args, **kwargs)
    return wrapper


def staff_or_admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        if session.get("admin_id"):
            return func(*args, **kwargs)

        if session.get("staff_id"):
            return func(*args, **kwargs)

        return redirect("/staff/login")

    return wrapper


@staff_bp.route("/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        staff = Staff.query.filter_by(username=username).first()

        if not staff:
            flash("존재하지 않는 직원 계정입니다.")
            return redirect(url_for("staff.staff_login"))

        if not staff.is_active:
            flash("비활성화된 직원 계정입니다.")
            return redirect(url_for("staff.staff_login"))

        if not check_password_hash(staff.password_hash, password):
            flash("비밀번호가 올바르지 않습니다.")
            return redirect(url_for("staff.staff_login"))

        session.clear()
        session["staff_id"] = staff.id
        session["staff_name"] = staff.name
        session["staff_role"] = staff.role

        staff.last_login_at = datetime.utcnow()
        db.session.commit()

        return redirect(url_for("staff.staff_dashboard"))

    return render_template("staff_login.html")


@staff_bp.route("/dashboard")
@staff_required
def staff_dashboard():
    staff_id = session["staff_id"]

    today = datetime.today().date()

    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)

    today_bookings = (
        Booking.query
        .filter(
            Booking.staff_id == staff_id,
            Booking.start_time >= start_of_day,
            Booking.start_time <= end_of_day
        )
        .order_by(Booking.start_time)
        .all()
    )

    total_count = len(today_bookings)

    completed_count = len([
        booking for booking in today_bookings
        if booking.status == "completed"
    ])

    expected_revenue = sum([
        booking.service.price
        for booking in today_bookings
        if booking.status in ["confirmed", "completed"]
    ])

    return render_template(
        "staff_dashboard.html",
        bookings=today_bookings,
        total_count=total_count,
        completed_count=completed_count,
        expected_revenue=expected_revenue
)
    

@staff_bp.route("/calendar")
@staff_required
def staff_calendar():

    staff_id = session["staff_id"]

    target_date = request.args.get(
        "date",
        datetime.today().strftime("%Y-%m-%d")
    )

    selected_date = datetime.strptime(
        target_date,
        "%Y-%m-%d"
    ).date()

    start_of_day = datetime.combine(
        selected_date,
        time.min
    )

    end_of_day = datetime.combine(
        selected_date,
        time.max
    )

    bookings = (
        Booking.query
        .filter(
            Booking.staff_id == staff_id,
            Booking.start_time >= start_of_day,
            Booking.start_time <= end_of_day
        )
        .order_by(Booking.start_time)
        .all()
    )

    return render_template(
        "staff_calendar.html",
        bookings=bookings,
        target_date=target_date
    )


@staff_bp.route("/logout")
def staff_logout():
    session.clear()
    return redirect(url_for("staff.staff_login"))


@staff_bp.route("/booking/<int:booking_id>/complete", methods=["POST"])
@staff_required
def complete_booking(booking_id):

    booking = Booking.query.get_or_404(booking_id)

    if booking.staff_id != session["staff_id"]:
        return {"ok": False}, 403

    result = update_booking_status(
        booking.id,
        "completed",
        memo="직원 완료 처리"
    )

    if not result.get("ok"):
        return {"ok": False}, 400

    return {"ok": True}


@staff_bp.route(
    "/change-password",
    methods=["GET", "POST"]
)
@staff_required
def change_password():

    staff = Staff.query.get(
        session["staff_id"]
    )

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if not check_password_hash(
            staff.password_hash,
            current_password
        ):
            flash("Current password is incorrect.")
            return redirect(
                url_for("staff.change_password")
            )

        if new_password != confirm_password:
            flash("New passwords do not match.")
            return redirect(
                url_for("staff.change_password")
            )

        if len(new_password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(
                url_for("staff.change_password")
            )

        staff.password_hash = generate_password_hash(
            new_password
        )

        db.session.commit()

        flash("Password updated successfully.")

        return redirect("/staff/dashboard")

    return render_template(
        "staff_change_password.html"
    )