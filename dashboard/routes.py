from datetime import datetime, date, time, timedelta
from sqlalchemy import func

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

from functools import wraps
from openpyxl import Workbook
from io import BytesIO

from dashboard.models import ShopSettings, AdminUser
from extensions import db
from bookings.models import Booking, Service, StaffService
from bookings.services import (
    create_booking,
    find_available_staff_for_service,
    get_available_slots_any_staff
)
from staff.models import Staff, StaffSchedule
from customers.models import Customer
from werkzeug.security import check_password_hash, generate_password_hash


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(url_for("dashboard.admin_login"))

        return func(*args, **kwargs)

    return wrapper

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/admin")
@admin_required
def dashboard_home():
    return render_template("admin_home.html")


@dashboard_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        admin = AdminUser.query.filter_by(username=username).first()

        if admin and admin.is_active and check_password_hash(admin.password_hash, password):
            admin.last_login_at = datetime.utcnow()
            db.session.commit()

            session["admin_logged_in"] = True
            session["admin_user_id"] = admin.id

            return redirect("/admin")

        return "관리자 로그인 실패", 400

    return render_template("admin_login.html")

@dashboard_bp.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)

    return redirect("/admin/login")


@dashboard_bp.route("/admin/calendar")
@admin_required
def admin_calendar():
    date_str = request.args.get("date")

    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        target_date = date.today()

    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    bookings = Booking.query.filter(
        Booking.start_time >= day_start,
        Booking.start_time <= day_end
    ).order_by(Booking.start_time.asc()).all()

    return render_template(
        "admin_calendar.html",
        target_date=target_date,
        bookings=bookings
    )


@dashboard_bp.route("/admin/settings")
@admin_required
def admin_settings():
    settings = ShopSettings.query.first()

    return render_template(
        "admin_settings.html",
        settings=settings
    )


@dashboard_bp.route(
    "/admin/settings/update",
    methods=["POST"]
)
@admin_required
def update_settings():
    settings = ShopSettings.query.first()

    settings.no_show_limit_count = int(
        request.form["no_show_limit_count"]
    )

    settings.deposit_enabled = (
        request.form.get("deposit_enabled") == "on"
    )

    settings.booking_approval_mode = (
        request.form["booking_approval_mode"]
    )

    db.session.commit()

    return redirect(
        url_for("dashboard.admin_settings")
    )


@dashboard_bp.route("/admin/staff")
@admin_required
def admin_staff():
    staff_list = Staff.query.order_by(Staff.id.asc()).all()

    return render_template(
        "admin_staff.html",
        staff_list=staff_list
    )


@dashboard_bp.route("/admin/staff/create", methods=["POST"])
@admin_required
def create_staff_admin():
    name = request.form["name"]
    username = request.form["username"]
    password = request.form["password"]
    role = request.form.get("role", "staff")
    phone = request.form.get("phone")

    existing_staff = Staff.query.filter_by(username=username).first()

    if existing_staff:
        return "이미 사용 중인 직원 아이디입니다.", 400

    staff = Staff(
        name=name,
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        phone=phone,
        is_active=True
    )

    db.session.add(staff)
    db.session.commit()

    return redirect(url_for("dashboard.admin_staff"))


@dashboard_bp.route("/admin/staff/<int:staff_id>/toggle", methods=["POST"])
@admin_required
def toggle_staff_active(staff_id):
    staff = Staff.query.get(staff_id)

    if not staff:
        return redirect(url_for("dashboard.admin_staff"))

    staff.is_active = not staff.is_active

    db.session.commit()

    return redirect(url_for("dashboard.admin_staff"))



@dashboard_bp.route("/admin/staff/<int:staff_id>/schedule")
@admin_required
def staff_schedule_page(staff_id):
    staff = Staff.query.get(staff_id)

    if not staff:
        return redirect(url_for("dashboard.admin_staff"))

    schedules = StaffSchedule.query.filter_by(
        staff_id=staff_id
    ).order_by(StaffSchedule.day_of_week.asc()).all()

    schedule_map = {
        schedule.day_of_week: schedule
        for schedule in schedules
    }

    return render_template(
        "staff_schedule.html",
        staff=staff,
        schedule_map=schedule_map
    )


@dashboard_bp.route("/admin/staff/<int:staff_id>/schedule/update", methods=["POST"])
@admin_required
def update_staff_schedule(staff_id):
    staff = Staff.query.get(staff_id)

    if not staff:
        return redirect(url_for("dashboard.admin_staff"))

    for day in range(7):
        is_working = request.form.get(f"is_working_{day}") == "on"

        start_time_str = request.form.get(f"start_time_{day}")
        end_time_str = request.form.get(f"end_time_{day}")
        break_start_str = request.form.get(f"break_start_time_{day}")
        break_end_str = request.form.get(f"break_end_time_{day}")

        schedule = StaffSchedule.query.filter_by(
            staff_id=staff_id,
            day_of_week=day
        ).first()

        if not schedule:
            schedule = StaffSchedule(
                staff_id=staff_id,
                day_of_week=day
            )
            db.session.add(schedule)

        schedule.is_working = is_working

        if is_working:
            schedule.start_time = datetime.strptime(start_time_str, "%H:%M").time()
            schedule.end_time = datetime.strptime(end_time_str, "%H:%M").time()

            schedule.break_start_time = (
                datetime.strptime(break_start_str, "%H:%M").time()
                if break_start_str else None
            )

            schedule.break_end_time = (
                datetime.strptime(break_end_str, "%H:%M").time()
                if break_end_str else None
            )
        else:
            schedule.start_time = time(0, 0)
            schedule.end_time = time(0, 0)
            schedule.break_start_time = None
            schedule.break_end_time = None

    db.session.commit()

    return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))


@dashboard_bp.route("/admin/services")
@admin_required
def admin_services():
    services = Service.query.order_by(Service.id.asc()).all()

    return render_template(
        "admin_services.html",
        services=services
    )


@dashboard_bp.route("/admin/services/create", methods=["POST"])
@admin_required
def create_service_admin():
    category = request.form["category"]
    name_ko = request.form["name_ko"]
    name_en = request.form.get("name_en")
    duration_minutes = int(request.form["duration_minutes"])
    price = int(request.form["price"])

    deposit_required = request.form.get("deposit_required") == "on"
    deposit_amount = int(request.form.get("deposit_amount") or 0)

    service = Service(
        category=category,
        name_ko=name_ko,
        name_en=name_en,
        duration_minutes=duration_minutes,
        price=price,
        deposit_required=deposit_required,
        deposit_amount=deposit_amount,
        is_active=True
    )

    db.session.add(service)
    db.session.commit()

    return redirect(url_for("dashboard.admin_services"))


@dashboard_bp.route("/admin/services/<int:service_id>/toggle", methods=["POST"])
@admin_required
def toggle_service_active(service_id):
    service = Service.query.get(service_id)

    if service:
        service.is_active = not service.is_active
        db.session.commit()

    return redirect(url_for("dashboard.admin_services"))


@dashboard_bp.route("/admin/services/<int:service_id>/edit")
@admin_required
def edit_service_page(service_id):
    service = Service.query.get(service_id)

    if not service:
        return redirect(url_for("dashboard.admin_services"))

    return render_template(
        "edit_service.html",
        service=service
    )


@dashboard_bp.route("/admin/services/<int:service_id>/update", methods=["POST"])
@admin_required
def update_service_admin(service_id):
    service = Service.query.get(service_id)

    if not service:
        return redirect(url_for("dashboard.admin_services"))

    service.category = request.form["category"]
    service.name_ko = request.form["name_ko"]
    service.name_en = request.form.get("name_en")
    service.duration_minutes = int(request.form["duration_minutes"])
    service.price = int(request.form["price"])
    service.deposit_required = request.form.get("deposit_required") == "on"
    service.deposit_amount = int(request.form.get("deposit_amount") or 0)

    db.session.commit()

    return redirect(url_for("dashboard.admin_services"))



@dashboard_bp.route("/admin/services/<int:service_id>/delete", methods=["POST"])
@admin_required
def delete_service_admin(service_id):
    service = Service.query.get(service_id)

    if not service:
        return redirect(url_for("dashboard.admin_services"))

    has_booking = Booking.query.filter_by(
        service_id=service_id
    ).first()

    if has_booking:
        service.is_active = False
        db.session.commit()
        return redirect(url_for("dashboard.admin_services"))

    db.session.delete(service)
    db.session.commit()

    return redirect(url_for("dashboard.admin_services"))


@dashboard_bp.route("/admin/staff/<int:staff_id>/services")
@admin_required
def staff_services_page(staff_id):
    staff = Staff.query.get(staff_id)

    if not staff:
        return redirect(url_for("dashboard.admin_staff"))

    services = Service.query.order_by(Service.id.asc()).all()

    linked_service_ids = [
        item.service_id
        for item in StaffService.query.filter_by(staff_id=staff_id).all()
    ]

    return render_template(
        "staff_services.html",
        staff=staff,
        services=services,
        linked_service_ids=linked_service_ids
    )


@dashboard_bp.route("/admin/staff/<int:staff_id>/services/update", methods=["POST"])
@admin_required
def update_staff_services(staff_id):
    staff = Staff.query.get(staff_id)

    if not staff:
        return redirect(url_for("dashboard.admin_staff"))

    selected_service_ids = request.form.getlist("service_ids")
    selected_service_ids = [int(service_id) for service_id in selected_service_ids]

    StaffService.query.filter_by(staff_id=staff_id).delete()

    for service_id in selected_service_ids:
        staff_service = StaffService(
            staff_id=staff_id,
            service_id=service_id
        )
        db.session.add(staff_service)

    db.session.commit()

    return redirect(url_for("dashboard.staff_services_page", staff_id=staff_id))



@dashboard_bp.route("/admin/customers")
@admin_required
def admin_customers():
    customers = Customer.query.order_by(Customer.id.asc()).all()

    return render_template(
        "admin_customers.html",
        customers=customers
    )


@dashboard_bp.route("/admin/customers/create", methods=["POST"])
@admin_required
def create_customer_admin():
    customer = Customer(
        name=request.form["name"],
        phone=request.form["phone"],
        email=request.form.get("email"),
        memo=request.form.get("memo"),
        preferred_style=request.form.get("preferred_style"),
        skin_sensitivity=request.form.get("skin_sensitivity"),
        complaint_note=request.form.get("complaint_note")
    )

    db.session.add(customer)
    db.session.commit()

    return redirect(url_for("dashboard.admin_customers"))


@dashboard_bp.route("/admin/customers/<int:customer_id>")
@admin_required
def customer_detail(customer_id):
    customer = Customer.query.get(customer_id)

    if not customer:
        return redirect(url_for("dashboard.admin_customers"))

    bookings = Booking.query.filter_by(
        customer_id=customer_id
    ).order_by(Booking.start_time.desc()).all()

    return render_template(
        "customer_detail.html",
        customer=customer,
        bookings=bookings
    )


@dashboard_bp.route("/admin/customers/<int:customer_id>/update", methods=["POST"])
@admin_required
def update_customer(customer_id):
    customer = Customer.query.get(customer_id)

    if not customer:
        return redirect(url_for("dashboard.admin_customers"))

    customer.name = request.form["name"]
    customer.phone = request.form["phone"]
    customer.email = request.form.get("email")
    customer.preferred_style = request.form.get("preferred_style")
    customer.skin_sensitivity = request.form.get("skin_sensitivity")
    customer.complaint_note = request.form.get("complaint_note")
    customer.memo = request.form.get("memo")

    db.session.commit()

    return redirect(url_for("dashboard.customer_detail", customer_id=customer.id))



@dashboard_bp.route("/admin/bookings/create")
@admin_required
def admin_create_booking_page():
    customers = Customer.query.order_by(Customer.name.asc()).all()
    staff_list = Staff.query.filter_by(is_active=True).order_by(Staff.name.asc()).all()
    services = Service.query.filter_by(is_active=True).order_by(Service.name_ko.asc()).all()

    return render_template(
        "admin_create_booking.html",
        customers=customers,
        staff_list=staff_list,
        services=services
    )


@dashboard_bp.route("/admin/bookings/create", methods=["POST"])
@admin_required
def admin_create_booking_submit():
    from bookings.services import create_booking

    customer_id_raw = request.form.get("customer_id")
    new_customer_name = request.form.get("new_customer_name")
    new_customer_phone = request.form.get("new_customer_phone")

    if customer_id_raw:
        customer_id = int(customer_id_raw)
    else:
        if not new_customer_name:
            return "신규 고객 이름은 필수입니다.", 400

        customer = Customer(
            name=new_customer_name,
            phone=new_customer_phone or "",
        )
    
        db.session.add(customer)
        db.session.commit()
    
        customer_id = customer.id
    
    staff_id_raw = request.form["staff_id"]
    service_id = int(request.form["service_id"])

    start_time_str = request.form["start_time"]
    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")

    if staff_id_raw == "any":
        staff = find_available_staff_for_service(
            service_id=service_id,
            start_time=start_time
        )
    
        if not staff:
            return "가능한 직원이 없습니다.", 400
        
        staff_id = staff.id
    else:
        staff_id = int(staff_id_raw)
    
    result = create_booking(
        customer_id=customer_id,
        staff_id=staff_id,
        service_id=service_id,
        start_time=start_time
    )

    if not result.get("ok"):
        return result.get("message", "예약 생성 실패"), 400

    return redirect(url_for("dashboard.admin_calendar", date=start_time.date()))


@dashboard_bp.route("/admin/users")
@admin_required
def admin_users():

    users = AdminUser.query.order_by(
        AdminUser.id.asc()
    ).all()

    return render_template(
        "admin_users.html",
        users=users
    )

@dashboard_bp.route(
    "/admin/users/create",
    methods=["POST"]
)
@admin_required
def create_admin_user():

    username = request.form["username"]
    password = request.form["password"]

    existing = AdminUser.query.filter_by(
        username=username
    ).first()

    if existing:
        return "이미 존재하는 관리자입니다.", 400

    admin = AdminUser(
        username=username,
        password_hash=generate_password_hash(password),
        is_active=True
    )

    db.session.add(admin)
    db.session.commit()

    return redirect("/admin/users")


@dashboard_bp.route("/admin/revenue")
@admin_required
def admin_revenue():
    today = date.today()

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if start_date_str and end_date_str:
        filter_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        filter_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    else:
        filter_start_date = today.replace(day=1)
        filter_end_date = today

    filter_start = datetime.combine(filter_start_date, time.min)
    filter_end = datetime.combine(filter_end_date, time.max)

    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)

    week_start_date = today - timedelta(days=today.weekday())
    week_start = datetime.combine(week_start_date, time.min)

    month_start_date = today.replace(day=1)
    month_start = datetime.combine(month_start_date, time.min)

    completed_bookings = Booking.query.filter(
        Booking.status == "completed"
    ).all()

    filtered_bookings = [
       booking for booking in completed_bookings
        if filter_start <= booking.start_time <= filter_end
    ]

    daily_revenue = {}

    for booking in filtered_bookings:
        day = booking.start_time.date().isoformat()

        if day not in daily_revenue:
            daily_revenue[day] = {
                "count": 0,
                "revenue": 0
            }

        daily_revenue[day]["count"] += 1
        daily_revenue[day]["revenue"] += booking.service.price

    today_revenue = sum(
        booking.service.price
        for booking in completed_bookings
        if day_start <= booking.start_time <= day_end
    )

    week_revenue = sum(
        booking.service.price
        for booking in completed_bookings
        if booking.start_time >= week_start
    )

    month_revenue = sum(
        booking.service.price
        for booking in completed_bookings
        if booking.start_time >= month_start
    )

    total_revenue = sum(
        booking.service.price
        for booking in completed_bookings
    )

    staff_revenue = {}
    category_revenue = {}

    for booking in filtered_bookings:
        staff_name = booking.staff.name
        category = booking.service.category

        staff_revenue[staff_name] = staff_revenue.get(staff_name, 0) + booking.service.price
        category_revenue[category] = category_revenue.get(category, 0) + booking.service.price

    staff_count = {}
    category_count = {}
    daily_revenue = dict(sorted(daily_revenue.items()))

    for booking in filtered_bookings:
        staff_name = booking.staff.name
        category = booking.service.category

        staff_count[staff_name] = staff_count.get(staff_name, 0) + 1
        category_count[category] = category_count.get(category, 0) + 1


    return render_template(
        "admin_revenue.html",
        today_revenue=today_revenue,
        week_revenue=week_revenue,
        month_revenue=month_revenue,
        total_revenue=total_revenue,
        staff_revenue=staff_revenue,
        category_revenue=category_revenue,
        completed_count=len(completed_bookings),
        filtered_bookings=filtered_bookings,
        filter_start_date=filter_start_date,
        filter_end_date=filter_end_date,
        filtered_revenue=sum(booking.service.price for booking in filtered_bookings),
        staff_count=staff_count,
        category_count=category_count,
        daily_revenue=daily_revenue,
        chart_labels=list(daily_revenue.keys()),
        chart_values=[
            data["revenue"]
            for data in daily_revenue.values()
        ],
        staff_chart_labels=list(staff_revenue.keys()),
        staff_chart_values=list(staff_revenue.values()),
        category_chart_labels=list(category_revenue.keys()),
        category_chart_values=list(category_revenue.values()),

    )

@dashboard_bp.route("/admin/revenue/export")
@admin_required
def export_revenue_excel():
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    else:
        today = date.today()
        start_date = today.replace(day=1)
        end_date = today

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    bookings = Booking.query.filter(
        Booking.status == "completed",
        Booking.start_time >= start_dt,
        Booking.start_time <= end_dt
    ).order_by(Booking.start_time.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Revenue"

    ws.append([
        "예약ID",
        "날짜",
        "시간",
        "고객",
        "직원",
        "시술",
        "파트",
        "가격",
        "상태"
    ])

    for booking in bookings:
        ws.append([
            booking.id,
            booking.start_time.strftime("%Y-%m-%d"),
            booking.start_time.strftime("%H:%M"),
            booking.customer.name,
            booking.staff.name,
            booking.service.name_ko,
            booking.service.category,
            booking.service.price,
            booking.status
        ])

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    filename = f"revenue_{start_date}_{end_date}.xlsx"

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )