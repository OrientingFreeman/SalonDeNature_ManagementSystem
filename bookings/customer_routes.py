from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from extensions import db
from customers.models import Customer
from staff.models import Staff
from bookings.models import Service, Booking
from dashboard.models import ShopSettings
from bookings.services import (
    create_booking,
    find_available_staff_for_service
)

from translations import get_text, normalize_lang
from staff.models import Staff

def get_lang():
    lang = normalize_lang(request.args.get("lang", session.get("lang", "en")))
    session["lang"] = lang
    return lang


customer_booking_bp = Blueprint(
    "customer_booking",
    __name__
)



@customer_booking_bp.route("/")
def customer_home():
    lang = get_lang()

    staffs = (
       Staff.query
        .filter_by(is_active=True)
        .order_by(Staff.display_order.asc())
        .limit(3)
        .all()
    )

    return render_template(
        "customer_home.html",
        lang=lang,
        text=get_text(lang),
        staffs=staffs
    )


@customer_booking_bp.route("/booking")
def customer_booking_page():
    if not session.get("customer_id"):
        return redirect(url_for("auth.login"))
    
    current_customer = Customer.query.get(session["customer_id"])
    
    staff_list = Staff.query.filter_by(is_active=True).order_by(Staff.name.asc()).all()
    services = Service.query.filter_by(is_active=True).order_by(Service.name_ko.asc()).all()
    lang = get_lang()
    
    
    if session.get("customer_id"):
        current_customer = Customer.query.get(session["customer_id"])
    
    selected_staff_id = request.args.get("staff_id", type=int)

    return render_template(
        "customer_booking.html",
        staff_list=staff_list,
        services=services,
        lang=lang,
        text=get_text(lang),
        current_customer=current_customer,
        selected_staff_id=selected_staff_id
    )


@customer_booking_bp.route("/booking", methods=["POST"])
def customer_booking_submit():

    if not session.get("customer_id"):
        return redirect(url_for("auth.login"))

    lang = get_lang()
    
    
    staff_id_raw = request.form["staff_id"]
    service_id = int(request.form["service_id"])

    start_time_str = request.form["start_time"]
    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")

    if session.get("customer_id"):
        customer = Customer.query.get(session["customer_id"])
    
        if not customer:
            session.pop("customer_id", None)
            return redirect(url_for("auth.login"))
    

    needs_profile_completion = (
        customer.login_provider in ["kakao", "google"]
        and (
            not customer.name
            or customer.phone.startswith("kakao_")
            or customer.phone.startswith("google_")
        )
    )

    if needs_profile_completion:
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        consent = request.form.get("booking_info_consent")

        if not name or not phone or consent != "on":
            return "Name, phone number, and consent are required for booking.", 400

        customer.name = name
        customer.phone = phone
        customer.booking_info_consent_at = datetime.utcnow()

    
    db.session.add(customer)
    db.session.commit()

    if staff_id_raw == "any":
        staff = find_available_staff_for_service(
            service_id=service_id,
            start_time=start_time
        )

        if not staff:
            return "선택한 시간은 방금 마감되었습니다. 다른 시간을 선택해주세요.", 400

        staff_id = staff.id
    else:
        staff_id = int(staff_id_raw)

    result = create_booking(
        customer_id=customer.id,
        staff_id=staff_id,
        service_id=service_id,
        start_time=start_time
    )

    if not result.get("ok"):
        return result.get("message", "예약 생성 실패"), 400

    booking_id = result["booking"]["id"]

    return redirect(
        url_for(
            "customer_booking.customer_booking_success",
            booking_id=booking_id,
            lang=lang
        )
    )


@customer_booking_bp.route("/booking/success/<int:booking_id>")
def customer_booking_success(booking_id):
    lang=get_lang()
    booking = Booking.query.get(booking_id)

    if not booking:
        return "예약 정보를 찾을 수 없습니다.", 404

    return render_template(
        "customer_booking_success.html",
        booking=booking,
        lang=lang,
        text=get_text(lang),
        settings=ShopSettings.query.first()
    )

@customer_booking_bp.route("/my-bookings")
def my_bookings():
    if not session.get("customer_id"):
        return redirect(url_for("auth.login"))

    lang = get_lang()

    customer = Customer.query.get(session["customer_id"])

    if not customer:
        session.pop("customer_id", None)
        return redirect(url_for("auth.login"))

    bookings = Booking.query.filter_by(
        customer_id=customer.id
    ).order_by(Booking.start_time.desc()).all()

    return render_template(
        "my_bookings.html",
        bookings=bookings,
        customer=customer,
        lang=lang,
        text=get_text(lang),
        today=date.today(),
        now=datetime.now(),
        settings=ShopSettings.query.first()
    )


@customer_booking_bp.route("/staff/<int:staff_id>")
def staff_profile(staff_id):
    lang = get_lang()

    staff = Staff.query.get_or_404(staff_id)

    return render_template(
        "staff_profile.html",
        staff=staff,
        lang=lang,
        text=get_text(lang)
    )

@customer_booking_bp.route("/contact")
def contact_page():
    return render_template("contact.html")


@customer_booking_bp.route("/privacy")
def privacy_page():
    return render_template("privacy.html")


@customer_booking_bp.route("/terms")
def terms_page():
    return render_template("terms.html")

