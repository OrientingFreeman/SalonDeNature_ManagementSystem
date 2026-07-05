from datetime import datetime, date, time, timedelta
from sqlalchemy import func

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file,
    flash,
    jsonify,
    current_app
)

from functools import wraps
from openpyxl import Workbook
from io import BytesIO

from dashboard.models import ShopSettings, AdminUser, AdminNotification
from extensions import db
from bookings.models import Booking, Service, StaffService, BookingEvent
from bookings.services import (
    create_booking,
    find_available_staff_for_service,
    get_available_slots_any_staff,
    reschedule_booking,
    admin_update_booking_assignment
)
from staff.models import Staff, StaffSchedule, StaffTimeOff
from customers.models import Customer
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import os

from dashboard.notifications import (
    admin_notification_filter_query,
    cleanup_old_admin_notifications,
    delete_admin_notifications_by_ids,
    get_admin_notification_stats,
    mark_admin_notifications_read_by_ids,
    mark_notification_read,
    notify_booking_changed,
    notify_booking_status_changed,
    notify_deposit_paid,
    serialize_admin_notification,
)
from sms.models import SmsLog
from sms.service import (
    send_booking_cancelled_sms,
    send_booking_changed_sms,
    send_deposit_paid_sms,
    send_test_sms,
)

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(url_for("dashboard.admin_login"))

        return func(*args, **kwargs)

    return wrapper

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.context_processor
def inject_admin_notification_context():
    if not session.get("admin_logged_in"):
        return {}

    unread_count = AdminNotification.query.filter_by(is_read=False).count()
    recent_notifications = (
        AdminNotification.query
        .order_by(AdminNotification.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "admin_unread_notification_count": unread_count,
        "admin_recent_notifications": recent_notifications,
    }


@dashboard_bp.route("/admin")
@admin_required
def dashboard_home():
    today = date.today()

    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)

    today_booking_count = Booking.query.filter(
        Booking.start_time >= day_start,
        Booking.start_time <= day_end
    ).count()

    pending_count = Booking.query.filter_by(
        status="pending"
    ).count()

    completed_today = Booking.query.filter(
        Booking.status == "completed",
        Booking.start_time >= day_start,
        Booking.start_time <= day_end
    ).all()

    today_revenue = sum(
        booking.service.price
        for booking in completed_today
    )

    return redirect(url_for("dashboard.admin_timeline"))


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

        flash("관리자 로그인에 실패했습니다. 아이디와 비밀번호를 확인해주세요.")
        return redirect(url_for("dashboard.admin_login"))

    return render_template("admin_login.html")

@dashboard_bp.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)

    return redirect("/admin/login")


@dashboard_bp.route("/admin/notifications")
@admin_required
def admin_notifications_page():
    page = request.args.get("page", 1, type=int)
    filter_key = request.args.get("filter", "all")
    search_query = request.args.get("q", "").strip()

    try:
        per_page = int(request.args.get("per_page", 20))
    except (TypeError, ValueError):
        per_page = 20

    if per_page not in [10, 20, 30, 50]:
        per_page = 20

    base_query = AdminNotification.query
    filtered_query = admin_notification_filter_query(
        base_query,
        filter_key=filter_key,
        search_query=search_query,
    )

    notifications = (
        filtered_query
        .order_by(AdminNotification.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    stats = get_admin_notification_stats()

    filter_counts = {
        "all": AdminNotification.query.count(),
        "unread": AdminNotification.query.filter_by(is_read=False).count(),
        "booking": AdminNotification.query.filter(
            AdminNotification.notification_type.in_([
                "booking_created",
                "booking_changed",
            ])
        ).count(),
        "deposit": AdminNotification.query.filter(
            AdminNotification.notification_type.in_([
                "deposit_paid",
            ])
        ).count(),
        "status": AdminNotification.query.filter(
            AdminNotification.notification_type == "booking_status_changed"
        ).count(),
        "cancelled": AdminNotification.query.filter(
            AdminNotification.notification_type == "booking_cancelled"
        ).count(),
    }

    filter_tabs = [
        ("all", "All"),
        ("unread", "Unread"),
        ("booking", "Booking"),
        ("deposit", "Deposit"),
        ("status", "Status"),
        ("cancelled", "Cancelled"),
    ]

    sms_logs = (
        SmsLog.query
        .order_by(SmsLog.created_at.desc())
        .limit(10)
        .all()
    )

    sms_stats = {
        "sent": SmsLog.query.filter_by(status="sent").count(),
        "skipped": SmsLog.query.filter_by(status="skipped").count(),
        "failed": SmsLog.query.filter_by(status="failed").count(),
        "total": SmsLog.query.count(),
    }

    return render_template(
        "admin_notifications.html",
        notifications=notifications,
        unread_count=stats["unread_count"],
        stats=stats,
        filter_counts=filter_counts,
        filter_key=filter_key,
        search_query=search_query,
        filter_tabs=filter_tabs,
        per_page=per_page,
        sms_enabled=current_app.config.get("SMS_ENABLED"),
        solapi_from_number=current_app.config.get("SOLAPI_FROM_NUMBER"),
        sms_logs=sms_logs,
        sms_stats=sms_stats,
    )


@dashboard_bp.route("/admin/notifications/sms-test", methods=["POST"])
@admin_required
def admin_notifications_sms_test():
    recipient = request.form.get("recipient_phone", "").strip()
    message = request.form.get("message", "").strip()

    if not recipient:
        flash("Please enter a recipient phone number.", "error")
        return redirect(url_for("dashboard.admin_notifications_page"))

    result = send_test_sms(recipient, message or None)

    if result.get("ok") and not result.get("skipped"):
        flash("Test SMS sent successfully.", "success")
    elif result.get("skipped"):
        flash(f"Test SMS skipped: {result.get('reason')}", "warning")
    else:
        flash(f"Test SMS failed: {result.get('reason')}", "error")

    return redirect(url_for("dashboard.admin_notifications_page"))


@dashboard_bp.route("/admin/notifications/<int:notification_id>/read", methods=["POST"])
@admin_required
def admin_notification_mark_read(notification_id):
    notification = AdminNotification.query.get_or_404(notification_id)
    mark_notification_read(notification)
    db.session.commit()

    return jsonify({
        "ok": True,
        "notification": serialize_admin_notification(notification),
        "unread_count": AdminNotification.query.filter_by(is_read=False).count(),
    })



@dashboard_bp.route("/admin/notifications/<int:notification_id>/delete", methods=["POST"])
@admin_required
def admin_notification_delete(notification_id):
    notification = AdminNotification.query.get_or_404(notification_id)
    db.session.delete(notification)
    db.session.commit()

    flash("Notification deleted.", "success")
    return redirect(url_for(
        "dashboard.admin_notifications_page",
        page=request.args.get("page", 1),
        filter=request.args.get("filter", "all"),
        q=request.args.get("q", ""),
        per_page=request.args.get("per_page", 20),
    ))


@dashboard_bp.route("/admin/notifications/mark-all-read", methods=["POST"])
@admin_required
def admin_notifications_mark_all_read():
    now = datetime.utcnow()
    unread_notifications = AdminNotification.query.filter_by(is_read=False).all()

    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = now

    db.session.commit()

    return jsonify({
        "ok": True,
        "updated_count": len(unread_notifications),
        "unread_count": 0,
    })




@dashboard_bp.route("/admin/notifications/bulk-action", methods=["POST"])
@admin_required
def admin_notifications_bulk_action():
    action = request.form.get("action")
    notification_ids = [
        int(notification_id)
        for notification_id in request.form.getlist("notification_ids")
        if notification_id.isdigit()
    ]

    if not notification_ids:
        flash("Please select at least one notification.", "error")
        return redirect(url_for(
            "dashboard.admin_notifications_page",
            page=request.form.get("page", 1),
            filter=request.form.get("filter", "all"),
            q=request.form.get("q", ""),
            per_page=request.form.get("per_page", 20),
        ))

    if action == "mark_read":
        updated_count = mark_admin_notifications_read_by_ids(notification_ids)
        db.session.commit()
        flash(f"{updated_count} notification(s) marked as read.", "success")
    elif action == "delete":
        deleted_count = delete_admin_notifications_by_ids(notification_ids)
        db.session.commit()
        flash(f"{deleted_count} notification(s) deleted.", "success")
    else:
        flash("Invalid bulk action.", "error")

    return redirect(url_for(
        "dashboard.admin_notifications_page",
        page=request.form.get("page", 1),
        filter=request.form.get("filter", "all"),
        q=request.form.get("q", ""),
        per_page=request.form.get("per_page", 20),
    ))


@dashboard_bp.route("/admin/notifications/cleanup", methods=["POST"])
@admin_required
def admin_notifications_cleanup():
    result = cleanup_old_admin_notifications()
    db.session.commit()

    flash(
        (
            f"Notification cleanup completed. "
            f"{result['total_deleted_count']} old notification(s) deleted."
        ),
        "success"
    )

    return redirect(url_for("dashboard.admin_notifications_page"))


@dashboard_bp.route("/admin/api/notifications/summary")
@admin_required
def admin_notifications_summary_api():
    recent_notifications = (
        AdminNotification.query
        .order_by(AdminNotification.created_at.desc())
        .limit(5)
        .all()
    )

    return jsonify({
        "ok": True,
        "unread_count": AdminNotification.query.filter_by(is_read=False).count(),
        "notifications": [
            serialize_admin_notification(notification)
            for notification in recent_notifications
        ],
    })


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

    staff_list = Staff.query.filter_by(is_active=True).all()
    services = Service.query.filter_by(is_active=True).all()

    return render_template(
        "admin_calendar.html",
        target_date=target_date,
        bookings=bookings,
        staff_list=staff_list,
        services=services
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

    if not settings:
        settings = ShopSettings()
        db.session.add(settings)

    settings.no_show_limit_count = int(
        request.form["no_show_limit_count"]
    )

    deposit_enabled = request.form.get("deposit_enabled") == "on"
    settings.deposit_enabled = deposit_enabled

    settings.booking_approval_mode = (
        request.form["booking_approval_mode"]
    )

    settings.deposit_bank_name = request.form.get("deposit_bank_name") or None
    settings.deposit_account_number = request.form.get("deposit_account_number") or None
    settings.deposit_account_holder = request.form.get("deposit_account_holder") or None
    settings.deposit_notice = request.form.get("deposit_notice") or None

    deposit_due_minutes_raw = request.form.get("deposit_due_minutes")
    try:
        settings.deposit_due_minutes = int(deposit_due_minutes_raw or 30)
    except ValueError:
        settings.deposit_due_minutes = 30

    if settings.deposit_due_minutes < 0:
        settings.deposit_due_minutes = 0

    if not deposit_enabled:
        services = Service.query.all()

        for service in services:
            service.deposit_required = False
            service.deposit_amount = 0

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
    position = request.form.get("position")
    introduction = request.form.get("introduction")
    specialties = request.form.get("specialties")

    career_years = request.form.get("career_years")
    display_order = request.form.get("display_order", 0)

    career_years = int(career_years) if career_years else None
    display_order = int(display_order) if display_order else 0

    
    profile_image_url = None
    file = request.files.get("profile_image")
    if file and file.filename:
        if allowed_image(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{timestamp}_{filename}"
            upload_folder = os.path.join(
                current_app.root_path,
                "static",
                "uploads",
                "staff"
            )
            os.makedirs(upload_folder, exist_ok=True)
            save_path = os.path.join(upload_folder, filename)
            file.save(save_path)
            profile_image_url = f"/static/uploads/staff/{filename}"
        else:
            flash("Only image files are allowed.", "error")
            return redirect(url_for("dashboard.admin_staff"))

    profile_image_url=profile_image_url

    existing_staff = Staff.query.filter_by(username=username).first()

    if existing_staff:
        return "이미 사용 중인 직원 아이디입니다.", 400

    staff = Staff(
        name=name,
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        phone=phone,
        is_active=True,
        position = position,
        introduction = introduction,
        specialties = specialties,
        career_years = career_years,
        profile_image=profile_image_url,
        display_order = display_order
    )

    db.session.add(staff)
    db.session.commit()

    return redirect(url_for("dashboard.admin_staff"))


@dashboard_bp.route("/admin/staff/<int:staff_id>/edit")
@admin_required
def edit_staff_page(staff_id):
    staff = Staff.query.get_or_404(staff_id)

    return render_template(
        "edit_staff.html",
        staff=staff
    )


@dashboard_bp.route("/admin/staff/<int:staff_id>/update", methods=["POST"])
@admin_required
def update_staff_admin(staff_id):
    staff = Staff.query.get_or_404(staff_id)

    staff.name = request.form["name"]
    staff.username = request.form.get("username")
    staff.role = request.form.get("role", "staff")
    staff.phone = request.form.get("phone")

    staff.position = request.form.get("position")
    staff.introduction = request.form.get("introduction")
    staff.specialties = request.form.get("specialties")

    profile_image_url = staff.profile_image
    delete_profile_image = request.form.get("delete_profile_image") == "on"

    if delete_profile_image:
        profile_image_url = None


    file = request.files.get("profile_image")

    if file and file.filename:
        if not allowed_image(file.filename):
            flash("Only image files are allowed.", "error")
            return redirect(
                url_for(
                    "dashboard.edit_staff_page",
                    staff_id=staff.id
                )
            )

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{filename}"

        upload_folder = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            "staff"
        )
        os.makedirs(upload_folder, exist_ok=True)

        save_path = os.path.join(upload_folder, filename)
        file.save(save_path)

        profile_image_url = f"/static/uploads/staff/{filename}"

    career_years = request.form.get("career_years")
    display_order = request.form.get("display_order")

    staff.career_years = int(career_years) if career_years else None
    staff.display_order = int(display_order) if display_order else 0
    staff.profile_image = profile_image_url
    
    new_password = request.form.get("password")
    if new_password:
        staff.password_hash = generate_password_hash(new_password)

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

@dashboard_bp.route("/admin/staff/<int:staff_id>/image/delete", methods=["POST"])
@admin_required
def delete_staff_image(staff_id):
    staff = Staff.query.get_or_404(staff_id)

    if staff.profile_image:
        image_path = staff.profile_image.lstrip("/")

        full_path = os.path.join(
            current_app.root_path,
            image_path
        )

        if os.path.exists(full_path):
            os.remove(full_path)

        staff.profile_image = None
        db.session.commit()

    return redirect(
        url_for("dashboard.edit_staff_page", staff_id=staff.id)
    )



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
    time_offs = StaffTimeOff.query.filter_by(
        staff_id=staff_id).order_by(StaffTimeOff.start_time.desc()).all()

    # Then pass it to the template:
    return render_template(
        "staff_schedule.html",
        staff=staff,
        schedule_map=schedule_map,
        time_offs=time_offs
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
    settings = ShopSettings.query.first()

    return render_template(
        "admin_services.html",
        services=services,
        settings=settings
    )


@dashboard_bp.route("/admin/services/create", methods=["POST"])
@admin_required
def create_service_admin():
    category = request.form["category"]
    name_ko = request.form["name_ko"]
    name_en = request.form.get("name_en")
    duration_minutes = int(request.form["duration_minutes"])
    price = int(request.form["price"])

    settings = ShopSettings.query.first()
    deposit_enabled = settings.deposit_enabled if settings else False

    if deposit_enabled:
        deposit_required = request.form.get("deposit_required") == "on"
        deposit_amount = int(request.form.get("deposit_amount") or 0) if deposit_required else 0

        if deposit_required and deposit_amount <= 0:
            flash("Deposit amount must be greater than 0 when deposit is required.", "error")
            return redirect(url_for("dashboard.admin_services"))
    else:
        deposit_required = False
        deposit_amount = 0


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
    settings = ShopSettings.query.first()

    return render_template(
        "edit_service.html",
        service=service,
        settings=settings
    )


@dashboard_bp.route("/admin/services/<int:service_id>/update", methods=["POST"])
@admin_required
def update_service_admin(service_id):
    service = Service.query.get(service_id)

    if not service:
        return redirect(url_for("dashboard.admin_services"))

    settings = ShopSettings.query.first()
    deposit_enabled = settings.deposit_enabled if settings else False

    service.category = request.form["category"]
    service.name_ko = request.form["name_ko"]
    service.name_en = request.form.get("name_en")
    service.duration_minutes = int(request.form["duration_minutes"])
    service.price = int(request.form["price"])

    if deposit_enabled:
        deposit_required = request.form.get("deposit_required") == "on"
        deposit_amount = int(request.form.get("deposit_amount") or 0) if deposit_required else 0

        if deposit_required and deposit_amount <= 0:
            flash("Deposit amount must be greater than 0 when deposit is required.", "error")
            return redirect(url_for("dashboard.edit_service_page", service_id=service.id))

        service.deposit_required = deposit_required
        service.deposit_amount = deposit_amount
    else:
        service.deposit_required = False
        service.deposit_amount = 0

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

    if request.args.get("embed") == "1":
        return redirect(url_for("dashboard.admin_calendar", date=start_time.date(), embed=1))

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


@dashboard_bp.route("/admin/staff/<int:staff_id>/time-off/create", methods=["POST"])
@admin_required
def create_staff_time_off(staff_id):
    staff = Staff.query.get(staff_id)

    if not staff:
        flash("Staff member not found.")
        return redirect(url_for("dashboard.admin_staff"))

    off_date_str = request.form.get("off_date")
    start_time_str = request.form.get("start_time")
    end_time_str = request.form.get("end_time")
    reason = request.form.get("reason")
    is_full_day = request.form.get("is_full_day") == "on"

    if not off_date_str:
        flash("Please select a date.")
        return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))

    off_date = datetime.strptime(off_date_str, "%Y-%m-%d").date()

    if is_full_day:
        time_off_start = datetime.combine(off_date, time.min)
        time_off_end = datetime.combine(off_date, time.max)
    else:
        if not start_time_str or not end_time_str:
            flash("Please enter both start and end times.")
            return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))

        time_off_start = datetime.combine(off_date, datetime.strptime(start_time_str, "%H:%M").time())
        time_off_end = datetime.combine(off_date, datetime.strptime(end_time_str, "%H:%M").time())

    if time_off_end <= time_off_start:
        flash("End time must be later than start time.")
        return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))

    conflicting_booking = Booking.query.filter(
        Booking.staff_id == staff_id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.start_time < time_off_end,
        Booking.end_time > time_off_start
    ).first()

    if conflicting_booking:
        flash("This staff member already has a booking during the selected time off period. Please cancel or reschedule that booking first.")
        return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))

    overlapping_time_off = StaffTimeOff.query.filter(
        StaffTimeOff.staff_id == staff_id,
        StaffTimeOff.start_time < time_off_end,
        StaffTimeOff.end_time > time_off_start
    ).first()

    if overlapping_time_off:
        flash("This time off period overlaps with an existing time off entry.")
        return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))

    time_off = StaffTimeOff(
        staff_id=staff_id,
        start_time=time_off_start,
        end_time=time_off_end,
        reason=reason
    )

    db.session.add(time_off)
    db.session.commit()

    flash("Staff time off has been registered.")
    return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))


@dashboard_bp.route("/admin/staff/<int:staff_id>/time-off/<int:time_off_id>/delete", methods=["POST"])
@admin_required
def delete_staff_time_off(staff_id, time_off_id):
    time_off = StaffTimeOff.query.filter_by(id=time_off_id, staff_id=staff_id).first()

    if not time_off:
        flash("Time off entry not found.")
        return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))

    db.session.delete(time_off)
    db.session.commit()

    flash("Staff time off has been deleted.")
    return redirect(url_for("dashboard.staff_schedule_page", staff_id=staff_id))


@dashboard_bp.route("/admin/bookings/<int:booking_id>/reschedule", methods=["POST"])
@admin_required
def admin_reschedule_booking(booking_id):
    data = request.get_json() or {}
    new_start_time_str = data.get("new_start_time")

    if not new_start_time_str:
        return jsonify({
            "ok": False,
            "message": "Please select a new date and time."
        }), 400

    try:
        new_start_time = datetime.fromisoformat(new_start_time_str)
    except ValueError:
        return jsonify({
            "ok": False,
            "message": "Invalid date/time format."
        }), 400

    if not _is_quarter_hour(new_start_time):
        return jsonify({
            "ok": False,
            "message": "Bookings can only be rescheduled in 15-minute increments."
        }), 400

    result = reschedule_booking(
        booking_id=booking_id,
        new_start_time=new_start_time
    )

    if not result.get("ok"):
        return jsonify(result), 400

    booking = Booking.query.get(booking_id)

    if not booking:
        return jsonify({
            "ok": False,
            "message": "Booking not found after reschedule."
        }), 404

    payload = _timeline_booking_payload(booking)
    payload["message"] = result.get("message", "Booking rescheduled successfully.")
    return jsonify(payload), 200


@dashboard_bp.route("/admin/bookings/<int:booking_id>/assignment", methods=["POST"])
@admin_required
def admin_update_booking_assignment_route(booking_id):
    data = request.get_json() or {}

    staff_id_raw = data.get("staff_id")
    service_id_raw = data.get("service_id")
    new_start_time_str = data.get("new_start_time")

    if not staff_id_raw or not service_id_raw or not new_start_time_str:
        return jsonify({
            "ok": False,
            "message": "Please select staff, service, date, and time."
        }), 400

    try:
        staff_id = int(staff_id_raw)
        service_id = int(service_id_raw)
        new_start_time = datetime.fromisoformat(new_start_time_str)
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "message": "Invalid request data."
        }), 400

    if not _is_quarter_hour(new_start_time):
        return jsonify({
            "ok": False,
            "message": "Bookings can only be assigned in 15-minute increments."
        }), 400

    result = admin_update_booking_assignment(
        booking_id=booking_id,
        staff_id=staff_id,
        service_id=service_id,
        new_start_time=new_start_time
    )

    if not result.get("ok"):
        return jsonify(result), 400

    booking = Booking.query.get(booking_id)

    if not booking:
        return jsonify({
            "ok": False,
            "message": "Booking not found after assignment update."
        }), 404

    payload = _timeline_booking_payload(booking)
    payload["message"] = result.get("message", "Booking assignment updated successfully.")
    return jsonify(payload), 200


@dashboard_bp.route("/admin/change-password", methods=["GET", "POST"])
@admin_required
def admin_change_password():

    admin = AdminUser.query.get(
        session["admin_user_id"]
    )

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if not check_password_hash(
            admin.password_hash,
            current_password
        ):
            flash("Current password is incorrect.")
            return redirect(url_for(
                "dashboard.admin_change_password"
            ))

        if new_password != confirm_password:
            flash("New passwords do not match.")
            return redirect(url_for(
                "dashboard.admin_change_password"
            ))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for(
                "dashboard.admin_change_password"
            ))

        admin.password_hash = generate_password_hash(
            new_password
        )

        db.session.commit()

        flash("Password updated successfully.")

        return redirect("/admin")

    return render_template(
        "admin_change_password.html"
    )


@dashboard_bp.route("/admin/customers/<int:customer_id>/reset-password", methods=["POST"])
@admin_required
def reset_customer_password(customer_id):
    customer = Customer.query.get(customer_id)

    if not customer:
        flash("Customer not found.")
        return redirect(url_for("dashboard.admin_customers"))

    if customer.login_provider != "local":
        flash("Password reset is only available for local accounts.")
        return redirect(url_for("dashboard.customer_detail", customer_id=customer_id))

    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not new_password or not confirm_password:
        flash("Please enter and confirm the new password.")
        return redirect(url_for("dashboard.customer_detail", customer_id=customer_id))

    if new_password != confirm_password:
        flash("Passwords do not match.")
        return redirect(url_for("dashboard.customer_detail", customer_id=customer_id))

    if len(new_password) < 8:
        flash("Password must be at least 8 characters.")
        return redirect(url_for("dashboard.customer_detail", customer_id=customer_id))

    customer.password_hash = generate_password_hash(new_password)
    db.session.commit()

    flash("Customer password has been reset.")
    return redirect(url_for("dashboard.customer_detail", customer_id=customer_id))



@dashboard_bp.route("/admin/timeline")
@admin_required
def admin_timeline():

    target_date_str = request.args.get("date")
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        target_date = date.today()

    day_start = datetime.combine(target_date, time(0, 0))
    day_end = day_start + timedelta(days=1)

    settings = ShopSettings.query.first()
    open_hour = 9
    close_hour = 21

    staffs = Staff.query.filter_by(is_active=True).order_by(Staff.display_order.asc()).all()
    services = Service.query.filter_by(is_active=True).order_by(Service.name_ko.asc()).all()

    bookings = (
        Booking.query
        .filter(
            Booking.start_time >= day_start,
            Booking.start_time < day_end,
            Booking.status.in_(["pending", "confirmed"])
        )
        .order_by(Booking.start_time.asc())
        .all()
    )

    timeline_start = datetime.combine(target_date, time(open_hour, 0))
    timeline_end = datetime.combine(target_date, time(close_hour, 0))
    total_minutes = int((timeline_end - timeline_start).total_seconds() / 60)

    time_slots = []
    current = timeline_start
    while current <= timeline_end:
        time_slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)

    weekday = target_date.weekday()

    staff_schedules = StaffSchedule.query.filter_by(
        day_of_week=weekday,
        is_working=True
    ).all()

    staff_time_offs = StaffTimeOff.query.filter(
        StaffTimeOff.start_time < day_end,
        StaffTimeOff.end_time > day_start
    ).all()

    return render_template(
        "admin_timeline.html",
        target_date=target_date,
        staffs=staffs,
        bookings=bookings,
        time_slots=time_slots,
        timeline_start=timeline_start,
        total_minutes=total_minutes,
        today=date.today(),
        prev_date=target_date - timedelta(days=1),
        next_date=target_date + timedelta(days=1),
        now=datetime.now(),
        staff_schedules=staff_schedules,
        staff_time_offs=staff_time_offs,
        services=services,
    )




def _is_quarter_hour(dt):
    return (
        dt.minute % 15 == 0
        and dt.second == 0
        and dt.microsecond == 0
    )


def _has_time_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


def _validate_staff_booking_window(staff_id, service_id, start_time, end_time):
    staff = Staff.query.get(staff_id)

    if not staff or not staff.is_active:
        return "Selected staff member is not available."

    linked_service = StaffService.query.filter_by(
        staff_id=staff_id,
        service_id=service_id
    ).first()

    if not linked_service:
        return "Selected staff member cannot perform this service."

    weekday = start_time.weekday()

    schedule = StaffSchedule.query.filter_by(
        staff_id=staff_id,
        day_of_week=weekday,
        is_working=True
    ).first()

    if not schedule:
        return "Selected staff member is not working on this day."

    work_start = datetime.combine(start_time.date(), schedule.start_time)
    work_end = datetime.combine(start_time.date(), schedule.end_time)

    if start_time < work_start or end_time > work_end:
        return "Booking time is outside selected staff working hours."

    if schedule.break_start_time and schedule.break_end_time:
        break_start = datetime.combine(start_time.date(), schedule.break_start_time)
        break_end = datetime.combine(start_time.date(), schedule.break_end_time)

        if _has_time_overlap(start_time, end_time, break_start, break_end):
            return "Booking overlaps with selected staff break time."

    time_off = StaffTimeOff.query.filter(
        StaffTimeOff.staff_id == staff_id,
        StaffTimeOff.start_time < end_time,
        StaffTimeOff.end_time > start_time
    ).first()

    if time_off:
        return "Booking overlaps with selected staff time off."

    return None


def _timeline_booking_payload(booking):
    staff = Staff.query.get(booking.staff_id)
    service = Service.query.get(booking.service_id)
    duration_minutes = int(
        (booking.end_time - booking.start_time).total_seconds() / 60
    )

    return {
        "ok": True,
        "booking_id": booking.id,
        "new_staff_id": booking.staff_id,
        "staff_id": booking.staff_id,
        "staff_name": staff.name if staff else "Unassigned",
        "service_id": booking.service_id,
        "service_name": service.name_ko if service else "",
        "category": service.category if service else "etc",
        "duration_minutes": duration_minutes,
        "new_start_time": booking.start_time.isoformat(),
        "new_end_time": booking.end_time.isoformat(),
        "new_start_display": booking.start_time.strftime("%H:%M"),
        "new_end_display": booking.end_time.strftime("%H:%M"),
        "status": booking.status or "",
        "deposit_payment_status": booking.deposit_payment_status or "none",
        "deposit_paid": bool(booking.deposit_paid),
    }



@dashboard_bp.route("/admin/timeline/move", methods=["POST"])
@admin_required
def admin_timeline_move():
    data = request.get_json() or {}

    booking_id = data.get("booking_id")
    new_staff_id_raw = data.get("staff_id")
    new_start_time_str = data.get("new_start_time")

    if not booking_id or not new_staff_id_raw or not new_start_time_str:
        return jsonify({
            "ok": False,
            "message": "booking_id, staff_id, and new_start_time are required."
        }), 400

    try:
        new_staff_id = int(new_staff_id_raw)
        new_start_time = datetime.fromisoformat(new_start_time_str)
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "message": "Invalid staff or date/time data."
        }), 400

    if not _is_quarter_hour(new_start_time):
        return jsonify({
            "ok": False,
            "message": "Bookings can only be moved in 15-minute increments."
        }), 400

    booking = Booking.query.get(booking_id)

    if not booking:
        return jsonify({
            "ok": False,
            "message": "Booking not found."
        }), 404

    if booking.status not in ["pending", "confirmed"]:
        return jsonify({
            "ok": False,
            "message": "Only pending or confirmed bookings can be moved."
        }), 400

    duration_minutes = int(
        (booking.end_time - booking.start_time).total_seconds() / 60
    )

    if duration_minutes <= 0:
        return jsonify({
            "ok": False,
            "message": "Invalid booking duration."
        }), 400

    new_end_time = new_start_time + timedelta(minutes=duration_minutes)

    validation_message = _validate_staff_booking_window(
        staff_id=new_staff_id,
        service_id=booking.service_id,
        start_time=new_start_time,
        end_time=new_end_time
    )

    if validation_message:
        return jsonify({
            "ok": False,
            "message": validation_message
        }), 400

    overlapped_booking = Booking.query.filter(
        Booking.id != booking.id,
        Booking.staff_id == new_staff_id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.start_time < new_end_time,
        Booking.end_time > new_start_time
    ).first()

    if overlapped_booking:
        return jsonify({
            "ok": False,
            "message": "This staff member already has a booking at this time."
        }), 400

    old_staff_id = booking.staff_id
    old_start_time = booking.start_time
    old_end_time = booking.end_time

    booking.staff_id = new_staff_id
    booking.start_time = new_start_time
    booking.end_time = new_end_time

    event = BookingEvent(
        booking_id=booking.id,
        event_type="timeline_drag_moved",
        memo=(
            f"staff {old_staff_id} -> {new_staff_id}, "
            f"time {old_start_time.strftime('%Y-%m-%d %H:%M')}~{old_end_time.strftime('%H:%M')} "
            f"-> {new_start_time.strftime('%Y-%m-%d %H:%M')}~{new_end_time.strftime('%H:%M')}"
        )
    )

    db.session.add(event)
    notify_booking_changed(booking, "Moved on admin timeline.")
    send_booking_changed_sms(booking)
    db.session.commit()

    payload = _timeline_booking_payload(booking)
    payload["old_staff_id"] = old_staff_id
    payload["old_start_time"] = old_start_time.isoformat()

    return jsonify(payload)



@dashboard_bp.route("/admin/timeline/bookings/<int:booking_id>/deposit-paid", methods=["POST"])
@admin_required
def admin_timeline_mark_deposit_paid(booking_id):
    booking = Booking.query.get(booking_id)

    if not booking:
        return jsonify({
            "ok": False,
            "message": "Booking not found."
        }), 404

    if booking.deposit_payment_status == "paid":
        payload = _timeline_booking_payload(booking)
        payload["message"] = "Deposit is already marked as paid."
        return jsonify(payload), 200

    old_deposit_status = booking.deposit_payment_status or "none"
    old_status = booking.status

    booking.deposit_payment_status = "paid"
    booking.deposit_paid = True

    settings = ShopSettings.query.first()
    booking_approval_mode = settings.booking_approval_mode if settings else "auto"

    status_auto_confirmed = False

    if booking_approval_mode == "auto" and booking.status == "pending":
        booking.status = "confirmed"
        status_auto_confirmed = True

    event = BookingEvent(
        booking_id=booking.id,
        event_type="deposit_marked_paid",
        memo=(
            f"deposit {old_deposit_status} -> paid"
            + (
                f", status {old_status} -> confirmed by auto approval"
                if status_auto_confirmed else ""
            )
        )
    )

    db.session.add(event)
    notify_deposit_paid(booking, source="Admin")
    send_deposit_paid_sms(booking)
    db.session.commit()

    payload = _timeline_booking_payload(booking)
    payload["old_deposit_payment_status"] = old_deposit_status
    payload["old_status"] = old_status
    payload["status_auto_confirmed"] = status_auto_confirmed
    payload["message"] = (
        "Deposit marked as paid and booking confirmed."
        if status_auto_confirmed
        else "Deposit marked as paid."
    )

    return jsonify(payload), 200


@dashboard_bp.route("/admin/timeline/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
def admin_timeline_update_booking_status(booking_id):
    data = request.get_json() or {}
    new_status = data.get("status")

    allowed_statuses = {"pending", "confirmed", "completed", "cancelled", "no_show"}

    if new_status not in allowed_statuses:
        return jsonify({
            "ok": False,
            "message": "Invalid booking status."
        }), 400

    booking = Booking.query.get(booking_id)

    if not booking:
        return jsonify({
            "ok": False,
            "message": "Booking not found."
        }), 404

    old_status = booking.status
    booking.status = new_status

    event = BookingEvent(
        booking_id=booking.id,
        event_type="timeline_status_changed",
        memo=f"status {old_status} -> {new_status}"
    )

    db.session.add(event)
    notify_booking_status_changed(booking, old_status, new_status)
    if new_status == "cancelled":
        send_booking_cancelled_sms(booking)
    db.session.commit()

    payload = _timeline_booking_payload(booking)
    payload["old_status"] = old_status
    return jsonify(payload), 200
