from datetime import datetime, timedelta
from functools import wraps

from flask import request, session

from api import api_v1_bp
from api.responses import error_response, success_response
from api.security import rate_limit, require_api_csrf
from bookings.models import Booking, BookingEvent
from bookings.services import ALLOWED_STATUS_TRANSITIONS, update_booking_status
from dashboard.analytics import build_revenue_analytics
from dashboard.models import AdminUser
from dashboard.notifications import notify_booking_status_changed
from extensions import db
from sms.service import send_booking_cancelled_sms


def admin_api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return error_response("ADMIN_AUTHENTICATION_REQUIRED", "Administrator login is required.", status=401)
        admin_id = session.get("admin_user_id")
        admin = AdminUser.query.get(admin_id) if admin_id else None
        if not admin or not admin.is_active:
            session.pop("admin_logged_in", None)
            session.pop("admin_user_id", None)
            return error_response("ADMIN_AUTHENTICATION_REQUIRED", "Administrator login is required.", status=401)
        return view(admin, *args, **kwargs)
    return wrapped


def _booking_payload(booking, include_events=False):
    payload = {
        "id": booking.id,
        "status": booking.status,
        "previous_status": booking.previous_status,
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
        "customer": {"id": booking.customer.id, "name": booking.customer.name, "phone": booking.customer.phone, "email": booking.customer.email},
        "service": {"id": booking.service.id, "name_ko": booking.service.name_ko, "name_en": booking.service.name_en, "category": booking.service.category, "price": booking.service.price, "duration_minutes": booking.service.duration_minutes},
        "staff": {"id": booking.staff.id, "name": booking.staff.name, "position": booking.staff.position},
        "deposit": {"paid": bool(booking.deposit_paid), "status": booking.deposit_payment_status or "none", "amount": booking.service.deposit_amount or 0, "payment_link": booking.deposit_payment_link, "note": booking.deposit_note},
        "memo": booking.memo,
        "late_notice_minutes": booking.late_notice_minutes,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
        "allowed_status_transitions": ALLOWED_STATUS_TRANSITIONS.get(booking.status, []),
    }
    if include_events:
        events = BookingEvent.query.filter_by(booking_id=booking.id).order_by(BookingEvent.created_at.asc(), BookingEvent.id.asc()).all()
        payload["events"] = [{"id": e.id, "type": e.event_type, "memo": e.memo, "created_at": e.created_at.isoformat() if e.created_at else None} for e in events]
    return payload


@api_v1_bp.get("/admin/bookings")
@rate_limit()
@admin_api_login_required
def list_admin_bookings(_admin):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    if page < 1 or per_page < 1 or per_page > 100:
        return error_response("INVALID_PAGINATION", "page must be at least 1 and per_page must be between 1 and 100.", status=400)
    query = Booking.query
    status = (request.args.get("status") or "").strip()
    if status:
        if status not in ALLOWED_STATUS_TRANSITIONS:
            return error_response("INVALID_STATUS_FILTER", "Unknown booking status.", status=400)
        query = query.filter(Booking.status == status)
    for name, column in (("staff_id", Booking.staff_id), ("service_id", Booking.service_id), ("customer_id", Booking.customer_id)):
        raw = request.args.get(name)
        if raw:
            try:
                value = int(raw)
                if value <= 0: raise ValueError
            except ValueError:
                return error_response("INVALID_QUERY_PARAMETER", f"{name} must be a positive integer.", status=400)
            query = query.filter(column == value)
    for name, op in (("date_from", "from"), ("date_to", "to")):
        raw = (request.args.get(name) or "").strip()
        if raw:
            try: parsed = datetime.strptime(raw, "%Y-%m-%d")
            except ValueError: return error_response("INVALID_DATE_FORMAT", f"{name} must use YYYY-MM-DD format.", status=400)
            query = query.filter(Booking.start_time >= parsed if op == "from" else Booking.start_time < parsed + timedelta(days=1))
    total = query.count()
    bookings = query.order_by(Booking.start_time.desc(), Booking.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    return success_response([_booking_payload(b) for b in bookings], meta={"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1)//per_page if total else 0})


@api_v1_bp.get("/admin/bookings/<int:booking_id>")
@rate_limit()
@admin_api_login_required
def get_admin_booking(_admin, booking_id):
    booking = Booking.query.get(booking_id)
    if not booking:
        return error_response("BOOKING_NOT_FOUND", "The requested booking was not found.", status=404)
    return success_response(_booking_payload(booking, include_events=True))


@api_v1_bp.get("/admin/bookings/<int:booking_id>/events")
@rate_limit()
@admin_api_login_required
def get_admin_booking_events(_admin, booking_id):
    if not Booking.query.get(booking_id):
        return error_response("BOOKING_NOT_FOUND", "The requested booking was not found.", status=404)
    events = BookingEvent.query.filter_by(booking_id=booking_id).order_by(BookingEvent.created_at.asc(), BookingEvent.id.asc()).all()
    return success_response([{"id": e.id, "type": e.event_type, "memo": e.memo, "created_at": e.created_at.isoformat() if e.created_at else None} for e in events])


@api_v1_bp.patch("/admin/bookings/<int:booking_id>/status")
@rate_limit(limit=30, window_seconds=60)
@require_api_csrf
@admin_api_login_required
def change_admin_booking_status(_admin, booking_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("JSON_BODY_REQUIRED", "A JSON request body is required.", status=400)
    new_status = (data.get("status") or "").strip()
    reason = (data.get("reason") or data.get("memo") or "").strip() or None
    booking = Booking.query.get(booking_id)
    if not booking:
        return error_response("BOOKING_NOT_FOUND", "The requested booking was not found.", status=404)
    old_status = booking.status
    result = update_booking_status(booking_id, new_status, memo=reason)
    if not result.get("ok"):
        status = 422 if result.get("error") == "STATUS_REASON_REQUIRED" else 409
        return error_response(result.get("error", "STATUS_UPDATE_FAILED"), result.get("message", "Status update failed."), status=status)
    booking = Booking.query.get(booking_id)
    notify_booking_status_changed(booking, old_status, new_status)
    if new_status == "cancelled":
        send_booking_cancelled_sms(booking)
    db.session.commit()
    return success_response({"previous_status": old_status, "booking": _booking_payload(booking, include_events=True)})


@api_v1_bp.get("/admin/analytics/revenue")
@rate_limit()
@admin_api_login_required
def admin_revenue_analytics(_admin):
    start_raw = (request.args.get("start_date") or "").strip()
    end_raw = (request.args.get("end_date") or "").strip()
    try:
        start_date = datetime.strptime(start_raw, "%Y-%m-%d").date() if start_raw else None
        end_date = datetime.strptime(end_raw, "%Y-%m-%d").date() if end_raw else None
    except ValueError:
        return error_response("INVALID_DATE_FORMAT", "start_date and end_date must use YYYY-MM-DD format.", status=400)
    return success_response(build_revenue_analytics(start_date, end_date))
