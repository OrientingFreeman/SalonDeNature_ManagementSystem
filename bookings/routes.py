from datetime import datetime

from flask import Blueprint, jsonify, request, session
from bookings.models import Booking
from bookings.services import (
    get_available_slots,
    create_booking,
    update_booking_status,
    revert_no_show,
    cancel_booking_by_customer,
    get_available_slots_any_staff,
    reschedule_booking,
    send_late_notice,
    update_deposit_status,
    update_deposit_request_info,
)

booking_bp = Blueprint("bookings", __name__, url_prefix="/api/bookings")


@booking_bp.route("/available-slots")
def available_slots():
    staff_id = request.args.get("staff_id", type=int)
    service_id = request.args.get("service_id", type=int)
    date_str = request.args.get("date")

    if not staff_id or not service_id or not date_str:
        return jsonify({
            "ok": False,
            "error": "MISSING_REQUIRED_PARAMS",
            "message": "staff_id, service_id, date는 필수입니다."
        }), 400

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "INVALID_DATE_FORMAT",
            "message": "date는 YYYY-MM-DD 형식이어야 합니다."
        }), 400

    result = get_available_slots(
        staff_id=staff_id,
        service_id=service_id,
        target_date=target_date
    )

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code





@booking_bp.route("", methods=["POST"])
def create_booking_route():
    data = request.get_json() or {}

    customer_id = data.get("customer_id")
    staff_id = data.get("staff_id")
    service_id = data.get("service_id")
    start_time_str = data.get("start_time")

    if not customer_id or not staff_id or not service_id or not start_time_str:
        return jsonify({
            "ok": False,
            "error": "MISSING_REQUIRED_FIELDS",
            "message": "customer_id, staff_id, service_id, start_time은 필수입니다."
        }), 400

    try:
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "INVALID_DATETIME_FORMAT",
            "message": "start_time은 YYYY-MM-DD HH:MM 형식이어야 합니다."
        }), 400

    result = create_booking(
        customer_id=customer_id,
        staff_id=staff_id,
        service_id=service_id,
        start_time=start_time
    )

    status_code = 201 if result.get("ok") else 400

    return jsonify(result), status_code


@booking_bp.route("/<int:booking_id>/status", methods=["POST"])
def update_booking_status_route(booking_id):
    data = request.get_json() or {}

    new_status = data.get("status")
    memo = data.get("memo")

    result = update_booking_status(
        booking_id=booking_id,
        new_status=new_status,
        memo=memo
    )

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code

@booking_bp.route("/<int:booking_id>/revert-no-show", methods=["POST"])
def revert_no_show_route(booking_id):
    result = revert_no_show(booking_id)

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code

@booking_bp.route("/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking_by_customer_route(booking_id):
    customer_id = session.get("customer_id")

    if not customer_id:
        return jsonify({
            "ok": False,
            "error": "LOGIN_REQUIRED",
            "message": "로그인이 필요합니다."
        }), 401

    booking = Booking.query.get(booking_id)

    if not booking:
        return jsonify({
            "ok": False,
            "error": "BOOKING_NOT_FOUND",
            "message": "예약을 찾을 수 없습니다."
        }), 404

    if booking.customer_id != customer_id:
        return jsonify({
            "ok": False,
            "error": "FORBIDDEN",
            "message": "본인 예약만 취소할 수 있습니다."
        }), 403

    result = cancel_booking_by_customer(booking_id)

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code


@booking_bp.route(
    "/available-slots-any"
)
def available_slots_any():
    service_id = request.args.get(
        "service_id",
        type=int
    )

    date_str = request.args.get("date")

    if not service_id or not date_str:
        return jsonify({
            "ok": False,
            "message": "service_id와 date는 필수입니다."
        }), 400

    target_date = datetime.strptime(
        date_str,
        "%Y-%m-%d"
    ).date()

    result = get_available_slots_any_staff(
        service_id=service_id,
        target_date=target_date
    )

    return jsonify(result)



@booking_bp.route("/<int:booking_id>/reschedule", methods=["POST"])
def reschedule_booking_route(booking_id):

    customer_id = session.get("customer_id")

    if not customer_id:
        return jsonify({
            "ok": False,
            "error": "LOGIN_REQUIRED",
            "message": "로그인이 필요합니다."
        }), 401

    booking = Booking.query.get(booking_id)

    if not booking:
        return jsonify({
            "ok": False,
            "error": "BOOKING_NOT_FOUND",
            "message": "예약을 찾을 수 없습니다."
        }), 404

    if booking.customer_id != customer_id:
        return jsonify({
            "ok": False,
            "error": "FORBIDDEN",
            "message": "본인 예약만 변경할 수 있습니다."
        }), 403

    data = request.get_json() or {}

    new_start_time_str = data.get("new_start_time")

    if not new_start_time_str:
        return jsonify({
            "ok": False,
            "error": "MISSING_NEW_START_TIME",
            "message": "new_start_time은 필수입니다."
        }), 400

    try:
        new_start_time = datetime.strptime(
            new_start_time_str,
            "%Y-%m-%dT%H:%M"
        )
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "INVALID_DATETIME_FORMAT",
            "message": "new_start_time은 YYYY-MM-DDTHH:MM 형식이어야 합니다."
        }), 400

    result = reschedule_booking(
        booking_id=booking_id,
        new_start_time=new_start_time
    )

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code


@booking_bp.route("/<int:booking_id>/late-notice", methods=["POST"])
def late_notice_route(booking_id):
    data = request.get_json() or {}
    minutes = data.get("minutes")

    result = send_late_notice(
        booking_id=booking_id,
        minutes=int(minutes)
    )

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code



@booking_bp.route("/<int:booking_id>/deposit-status", methods=["POST"])
def update_deposit_status_route(booking_id):
    data = request.get_json() or {}

    deposit_status = data.get("deposit_status")

    result = update_deposit_status(
        booking_id=booking_id,
        deposit_status=deposit_status
    )

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code


@booking_bp.route("/<int:booking_id>/deposit-request", methods=["POST"])
def update_deposit_request_route(booking_id):
    data = request.get_json() or {}

    result = update_deposit_request_info(
        booking_id=booking_id,
        payment_link=data.get("payment_link"),
        deposit_note=data.get("deposit_note")
    )

    status_code = 200 if result.get("ok") else 400

    return jsonify(result), status_code


