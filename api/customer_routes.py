from datetime import datetime
from functools import wraps

from flask import request, session

from api import api_v1_bp
from api.responses import error_response, success_response
from bookings.models import Booking, BookingEvent
from bookings.services import (
    cancel_booking_by_customer,
    create_booking,
    find_available_staff_for_service,
    reschedule_booking,
)
from customers.models import Customer


ACTIVE_BOOKING_STATUSES = {"pending", "confirmed"}
VALID_BOOKING_FILTERS = {"all", "upcoming", "completed", "closed"}


def _current_customer():
    customer_id = session.get("customer_id")
    if not customer_id:
        return None
    customer = Customer.query.get(customer_id)
    if not customer:
        session.pop("customer_id", None)
    return customer


def customer_api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        customer = _current_customer()
        if not customer:
            return error_response(
                "AUTHENTICATION_REQUIRED",
                "Customer login is required.",
                status=401,
            )
        return view(customer, *args, **kwargs)

    return wrapped


def _parse_positive_int(value, field_name):
    if isinstance(value, bool):
        return None, error_response(
            "INVALID_FIELD",
            f"{field_name} must be a positive integer.",
            status=422,
            details={"field": field_name},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, error_response(
            "INVALID_FIELD",
            f"{field_name} must be a positive integer.",
            status=422,
            details={"field": field_name},
        )
    if parsed <= 0:
        return None, error_response(
            "INVALID_FIELD",
            f"{field_name} must be a positive integer.",
            status=422,
            details={"field": field_name},
        )
    return parsed, None


def _parse_iso_minute(value, field_name):
    if not isinstance(value, str) or not value.strip():
        return None, error_response(
            "INVALID_FIELD",
            f"{field_name} is required and must use YYYY-MM-DDTHH:MM format.",
            status=422,
            details={"field": field_name},
        )
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M"), None
    except ValueError:
        return None, error_response(
            "INVALID_DATETIME_FORMAT",
            f"{field_name} must use YYYY-MM-DDTHH:MM format.",
            status=422,
            details={"field": field_name},
        )


def _booking_payload(booking, *, include_events=False):
    payload = {
        "id": booking.id,
        "status": booking.status,
        "previous_status": booking.previous_status,
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
        "service": {
            "id": booking.service.id,
            "name_ko": booking.service.name_ko,
            "name_en": booking.service.name_en,
            "category": booking.service.category,
            "duration_minutes": booking.service.duration_minutes,
            "price": booking.service.price,
        },
        "staff": {
            "id": booking.staff.id,
            "name": booking.staff.name,
            "position": booking.staff.position,
        },
        "deposit": {
            "paid": bool(booking.deposit_paid),
            "status": booking.deposit_payment_status or "none",
            "amount": booking.service.deposit_amount or 0,
            "payment_link": booking.deposit_payment_link,
            "note": booking.deposit_note,
        },
        "memo": booking.memo,
        "late_notice_minutes": booking.late_notice_minutes,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
        "actions": {
            "cancel": booking.status in ACTIVE_BOOKING_STATUSES,
            "reschedule": booking.status in ACTIVE_BOOKING_STATUSES,
        },
    }
    if include_events:
        events = BookingEvent.query.filter_by(booking_id=booking.id).order_by(
            BookingEvent.created_at.asc(), BookingEvent.id.asc()
        ).all()
        payload["events"] = [
            {
                "id": event.id,
                "type": event.event_type,
                "memo": event.memo,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ]
    return payload


def _owned_booking(customer_id, booking_id):
    return Booking.query.filter_by(id=booking_id, customer_id=customer_id).first()


def _service_error_response(result):
    code = result.get("error", "BOOKING_OPERATION_FAILED")
    message = result.get("message", "The booking operation failed.")
    status_by_code = {
        "CUSTOMER_NOT_FOUND": 404,
        "BOOKING_NOT_FOUND": 404,
        "STAFF_NOT_FOUND_OR_INACTIVE": 404,
        "SERVICE_NOT_FOUND_OR_INACTIVE": 404,
        "CUSTOMER_BOOKING_RESTRICTED": 403,
        "BOOKING_TIME_OVERLAPPED": 409,
        "NEW_TIME_NOT_AVAILABLE": 409,
        "BOOKING_NOT_CANCELABLE": 409,
        "BOOKING_NOT_RESCHEDULABLE": 409,
        "PAST_BOOKING_NOT_ALLOWED": 422,
        "INVALID_SERVICE_DURATION": 422,
        "STAFF_CANNOT_DO_SERVICE": 422,
        "STAFF_NOT_WORKING": 422,
        "OUTSIDE_WORKING_HOURS": 422,
        "DURING_BREAK_TIME": 422,
        "STAFF_TIME_OFF": 422,
        "SAME_DAY_CANCEL_BLOCKED": 422,
        "SAME_DAY_RESCHEDULE_BLOCKED": 422,
    }
    return error_response(code, message, status=status_by_code.get(code, 400))


@api_v1_bp.get("/me/bookings")
@customer_api_login_required
def list_my_bookings(customer):
    status_filter = (request.args.get("status") or "all").strip().lower()
    if status_filter not in VALID_BOOKING_FILTERS:
        return error_response(
            "INVALID_STATUS_FILTER",
            "status must be one of: all, upcoming, completed, closed.",
            status=400,
            details={"parameter": "status"},
        )

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)
    if page is None or page < 1 or per_page is None or per_page < 1 or per_page > 100:
        return error_response(
            "INVALID_PAGINATION",
            "page must be at least 1 and per_page must be between 1 and 100.",
            status=400,
        )

    query = Booking.query.filter_by(customer_id=customer.id)
    if status_filter == "upcoming":
        query = query.filter(Booking.status.in_(["pending", "confirmed"]))
    elif status_filter == "completed":
        query = query.filter(Booking.status == "completed")
    elif status_filter == "closed":
        query = query.filter(Booking.status.in_(["cancelled", "no_show"]))

    total = query.count()
    bookings = query.order_by(Booking.start_time.desc(), Booking.id.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if total else 0

    return success_response(
        [_booking_payload(booking) for booking in bookings],
        meta={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "status": status_filter,
        },
    )


@api_v1_bp.get("/me/bookings/<int:booking_id>")
@customer_api_login_required
def get_my_booking(customer, booking_id):
    booking = _owned_booking(customer.id, booking_id)
    if not booking:
        return error_response(
            "BOOKING_NOT_FOUND",
            "The requested booking was not found.",
            status=404,
        )
    return success_response(_booking_payload(booking, include_events=True))


@api_v1_bp.post("/me/bookings")
@customer_api_login_required
def create_my_booking(customer):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response(
            "JSON_BODY_REQUIRED",
            "A JSON request body is required.",
            status=400,
        )

    if not customer.name or not customer.phone or customer.phone.startswith(("kakao_", "google_")):
        return error_response(
            "CUSTOMER_PROFILE_INCOMPLETE",
            "Complete the customer name and phone number before booking.",
            status=422,
        )

    service_id, invalid = _parse_positive_int(data.get("service_id"), "service_id")
    if invalid:
        return invalid
    start_time, invalid = _parse_iso_minute(data.get("start_time"), "start_time")
    if invalid:
        return invalid

    staff_value = data.get("staff_id")
    if staff_value in (None, "any"):
        staff = find_available_staff_for_service(service_id=service_id, start_time=start_time)
        if not staff:
            return error_response(
                "NO_AVAILABLE_STAFF",
                "No eligible staff member is available at the selected time.",
                status=409,
            )
        staff_id = staff.id
    else:
        staff_id, invalid = _parse_positive_int(staff_value, "staff_id")
        if invalid:
            return invalid

    result = create_booking(
        customer_id=customer.id,
        staff_id=staff_id,
        service_id=service_id,
        start_time=start_time,
    )
    if not result.get("ok"):
        return _service_error_response(result)

    booking = _owned_booking(customer.id, result["booking"]["id"])
    return success_response(_booking_payload(booking, include_events=True), status=201)


@api_v1_bp.post("/me/bookings/<int:booking_id>/cancel")
@customer_api_login_required
def cancel_my_booking(customer, booking_id):
    booking = _owned_booking(customer.id, booking_id)
    if not booking:
        return error_response(
            "BOOKING_NOT_FOUND",
            "The requested booking was not found.",
            status=404,
        )

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return error_response("INVALID_JSON_BODY", "The JSON body must be an object.", status=400)
    reason = (data.get("reason") or "").strip()
    if not reason:
        return error_response(
            "CANCELLATION_REASON_REQUIRED",
            "A cancellation reason is required.",
            status=422,
            details={"field": "reason"},
        )

    result = cancel_booking_by_customer(booking.id, reason=reason)
    if not result.get("ok"):
        return _service_error_response(result)
    return success_response(_booking_payload(booking, include_events=True))


@api_v1_bp.post("/me/bookings/<int:booking_id>/reschedule")
@customer_api_login_required
def reschedule_my_booking(customer, booking_id):
    booking = _owned_booking(customer.id, booking_id)
    if not booking:
        return error_response(
            "BOOKING_NOT_FOUND",
            "The requested booking was not found.",
            status=404,
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response(
            "JSON_BODY_REQUIRED",
            "A JSON request body is required.",
            status=400,
        )
    new_start_time, invalid = _parse_iso_minute(data.get("new_start_time"), "new_start_time")
    if invalid:
        return invalid

    result = reschedule_booking(booking.id, new_start_time)
    if not result.get("ok"):
        return _service_error_response(result)
    return success_response(_booking_payload(booking, include_events=True))
