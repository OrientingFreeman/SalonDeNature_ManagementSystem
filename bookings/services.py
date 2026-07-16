from datetime import datetime, date, time, timedelta

from bookings.models import Booking, BookingEvent, Service, StaffService
from staff.models import StaffSchedule, Staff, StaffTimeOff
from customers.models import Customer
from extensions import db
from dashboard.models import ShopSettings
from dashboard.notifications import (
    notify_booking_cancelled,
    notify_booking_changed,
    notify_booking_created,
    notify_deposit_paid,
)
from sms.service import (
    send_booking_cancelled_sms,
    send_booking_changed_sms,
    send_booking_created_sms,
    send_deposit_paid_sms,
    send_deposit_request_sms,
)


SLOT_MINUTES = 30

RESERVATION_STATUSES = {
    "pending": "예약 접수",
    "confirmed": "예약 확정",
    "completed": "시술 완료",
    "cancelled": "취소",
    "no_show": "노쇼",
}

ALLOWED_STATUS_TRANSITIONS = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["completed", "cancelled", "no_show"],
    "completed": [],
    "cancelled": [],
    "no_show": [],
}


def can_change_reservation_status(current_status, new_status):
    if new_status not in RESERVATION_STATUSES:
        return False

    return new_status in ALLOWED_STATUS_TRANSITIONS.get(current_status, [])


def is_valid_service_duration(duration_minutes):
    return duration_minutes in [30, 60, 90, 120]


def has_time_overlap(new_start, new_end, existing_start, existing_end):
    return new_start < existing_end and new_end > existing_start


def is_during_break(slot_start, slot_end, schedule):
    if not schedule.break_start_time or not schedule.break_end_time:
        return False

    break_start = datetime.combine(slot_start.date(), schedule.break_start_time)
    break_end = datetime.combine(slot_start.date(), schedule.break_end_time)

    return has_time_overlap(slot_start, slot_end, break_start, break_end)


def is_during_time_off(slot_start, slot_end, staff_id):
    time_off = StaffTimeOff.query.filter(
        StaffTimeOff.staff_id == staff_id,
        StaffTimeOff.start_time < slot_end,
        StaffTimeOff.end_time > slot_start
    ).first()

    return time_off is not None


def generate_time_slots(work_start, work_end, service_duration):
    slots = []

    current = work_start
    while current + timedelta(minutes=service_duration) <= work_end:
        slots.append(current)
        current += timedelta(minutes=SLOT_MINUTES)

    return slots


def update_booking_status(booking_id, new_status, memo=None):
    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "error": "BOOKING_NOT_FOUND",
            "message": "예약을 찾을 수 없습니다."
        }

    new_status = (new_status or "").strip()
    memo = (memo or "").strip()

    if not can_change_reservation_status(booking.status, new_status):
        return {
            "ok": False,
            "error": "INVALID_STATUS_TRANSITION",
            "message": f"{booking.status} 상태에서 {new_status} 상태로는 변경할 수 없습니다."
        }

    if new_status in {"cancelled", "no_show"} and not memo:
        return {
            "ok": False,
            "error": "STATUS_REASON_REQUIRED",
            "message": "취소 및 노쇼 처리에는 사유가 필요합니다."
        }

    old_status = booking.status

    if new_status == "no_show":
        booking.previous_status = old_status

    booking.status = new_status

    event_memo = f"예약 상태 변경: {old_status} -> {new_status}"
    if memo:
        event_memo += f"\n처리 사유: {memo}"

    event = BookingEvent(
        booking_id=booking.id,
        event_type=new_status,
        memo=event_memo
    )

    db.session.add(event)

    if new_status == "completed":
        booking.customer.visit_count += 1
        booking.customer.total_revenue += booking.service.price

    if new_status == "no_show":
        booking.customer.no_show_count += 1

        settings = ShopSettings.query.first()
        no_show_limit = settings.no_show_limit_count if settings else 3

        if booking.customer.no_show_count >= no_show_limit:
            booking.customer.booking_restricted = True

    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "new_status": booking.status
    }


def update_deposit_request_info(booking_id, payment_link, deposit_note):
    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "message": "예약을 찾을 수 없습니다."
        }

    booking.deposit_payment_link = payment_link
    booking.deposit_note = deposit_note

    event = BookingEvent(
        booking_id=booking.id,
        event_type="deposit_request_info_updated",
        memo="예약금 결제 요청 정보 수정"
    )

    db.session.add(event)
    send_deposit_request_sms(booking)
    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "deposit_payment_link": booking.deposit_payment_link,
        "deposit_note": booking.deposit_note
    }



def revert_no_show(booking_id):
    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "error": "BOOKING_NOT_FOUND",
            "message": "예약을 찾을 수 없습니다."
        }

    if booking.status != "no_show":
        return {
            "ok": False,
            "error": "NOT_NO_SHOW_BOOKING",
            "message": "노쇼 상태인 예약만 취소할 수 있습니다."
        }

    booking.status = booking.previous_status or "confirmed"
    booking.previous_status = None

    if booking.customer.no_show_count > 0:
        booking.customer.no_show_count -= 1

    settings = ShopSettings.query.first()
    no_show_limit = settings.no_show_limit_count if settings else 3

    if booking.customer.no_show_count < no_show_limit:
        booking.customer.booking_restricted = False

    event = BookingEvent(
        booking_id=booking.id,
        event_type="no_show_reverted",
        memo="노쇼 처리 취소"
    )

    db.session.add(event)
    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "status": booking.status,
        "no_show_count": booking.customer.no_show_count,
        "booking_restricted": booking.customer.booking_restricted
    }



def get_available_slots(staff_id, service_id, target_date):
    
    service = Service.query.get(service_id)
    staff = Staff.query.get(staff_id)

    if not staff or not staff.is_active:
        return {
            "ok": True,
            "available_slots": []
        }
    
    if not service:
        return {
            "ok": False,
            "error": "SERVICE_NOT_FOUND",
            "message": "해당 시술을 찾을 수 없습니다."
        }

    if not is_valid_service_duration(service.duration_minutes):
        return {
            "ok": False,
            "error": "INVALID_SERVICE_DURATION",
            "message": "시술 시간은 30, 60, 90, 120분 중 하나여야 합니다."
        }

    staff_service = StaffService.query.filter_by(
        staff_id=staff_id,
        service_id=service_id
    ).first()

    if not staff_service:
        return {
            "ok": False,
            "error": "STAFF_CANNOT_DO_SERVICE",
            "message": "해당 직원은 이 시술을 담당할 수 없습니다."
        }

    weekday = target_date.weekday()

    schedule = StaffSchedule.query.filter_by(
        staff_id=staff_id,
        day_of_week=weekday,
        is_working=True
    ).first()

    if not schedule:
        return {
            "ok": True,
            "available_slots": []
        }

    work_start = datetime.combine(target_date, schedule.start_time)
    work_end = datetime.combine(target_date, schedule.end_time)

    existing_bookings = Booking.query.filter(
        Booking.staff_id == staff_id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.start_time < work_end,
        Booking.end_time > work_start
    ).all()

    candidate_slots = generate_time_slots(
        work_start,
        work_end,
        service.duration_minutes
    )

    available_slots = []

    now = datetime.now()

    for slot_start in candidate_slots:
        if slot_start <= now:
            continue

        slot_end = slot_start + timedelta(minutes=service.duration_minutes)

        if is_during_break(slot_start, slot_end, schedule):
            continue

        if is_during_time_off(slot_start, slot_end, staff_id):
            continue

        is_overlapped = False

        for booking in existing_bookings:
            if has_time_overlap(
                slot_start,
                slot_end,
                booking.start_time,
                booking.end_time
            ):
                is_overlapped = True
                break

        if not is_overlapped:
            available_slots.append(slot_start.strftime("%H:%M"))

    return {
        "ok": True,
        "available_slots": available_slots
    }

def create_booking(customer_id, staff_id, service_id, start_time):

    if start_time <= datetime.now():
        return {
            "ok": False,
            "error": "PAST_BOOKING_NOT_ALLOWED",
            "message": "현재 시간보다 이전 시간은 예약할 수 없습니다."
        }

    customer = Customer.query.get(customer_id)
    if not customer:
        return {
            "ok": False,
            "error": "CUSTOMER_NOT_FOUND",
            "message": "고객을 찾을 수 없습니다."
        }

    if customer.booking_restricted:
        return {
            "ok": False,
            "error": "CUSTOMER_BOOKING_RESTRICTED",
            "message": "온라인 예약이 제한된 고객입니다. 전화 문의가 필요합니다."
        }

    staff = Staff.query.get(staff_id)
    if not staff or not staff.is_active:
        return {
            "ok": False,
            "error": "STAFF_NOT_FOUND_OR_INACTIVE",
            "message": "직원을 찾을 수 없거나 비활성화 상태입니다."
        }

    service = Service.query.get(service_id)
    if not service or not service.is_active:
        return {
            "ok": False,
            "error": "SERVICE_NOT_FOUND_OR_INACTIVE",
            "message": "시술을 찾을 수 없거나 비활성화 상태입니다."
        }

    if not is_valid_service_duration(service.duration_minutes):
        return {
            "ok": False,
            "error": "INVALID_SERVICE_DURATION",
            "message": "시술 시간은 30, 60, 90, 120분 중 하나여야 합니다."
        }

    staff_service = StaffService.query.filter_by(
        staff_id=staff_id,
        service_id=service_id
    ).first()

    if not staff_service:
        return {
            "ok": False,
            "error": "STAFF_CANNOT_DO_SERVICE",
            "message": "해당 직원은 이 시술을 담당할 수 없습니다."
        }

    end_time = start_time + timedelta(minutes=service.duration_minutes)

    weekday = start_time.date().weekday()

    schedule = StaffSchedule.query.filter_by(
        staff_id=staff_id,
        day_of_week=weekday,
        is_working=True
    ).first()

    if not schedule:
        return {
            "ok": False,
            "error": "STAFF_NOT_WORKING",
            "message": "해당 날짜에는 직원이 근무하지 않습니다."
        }

    work_start = datetime.combine(start_time.date(), schedule.start_time)
    work_end = datetime.combine(start_time.date(), schedule.end_time)

    if start_time < work_start or end_time > work_end:
        return {
            "ok": False,
            "error": "OUTSIDE_WORKING_HOURS",
            "message": "직원 근무시간 밖의 예약입니다."
        }

    if is_during_break(start_time, end_time, schedule):
        return {
            "ok": False,
            "error": "DURING_BREAK_TIME",
            "message": "직원 휴게시간과 겹치는 예약입니다."
        }

    if is_during_time_off(start_time, end_time, staff_id):
        return {
            "ok": False,
            "error": "STAFF_TIME_OFF",
            "message": "This time is blocked by staff time off."
        }

    overlapped_booking = Booking.query.filter(
        Booking.staff_id == staff_id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.start_time < end_time,
        Booking.end_time > start_time
    ).first()

    if overlapped_booking:
        return {
            "ok": False,
            "error": "BOOKING_TIME_OVERLAPPED",
            "message": "이미 해당 시간대에 예약이 있습니다."
        }


    settings = ShopSettings.query.first()
    deposit_enabled = settings.deposit_enabled if settings else False

    '''
    deposit_payment_status = (
        "required"
        if deposit_enabled and service.deposit_required
        else "none"
    )
    '''
    
    requires_deposit = deposit_enabled and service.deposit_required and service.deposit_amount > 0

    booking_approval_mode = settings.booking_approval_mode if settings else "auto"

    if booking_approval_mode == "manual":
        booking_status = "pending"
    else:
        booking_status = "pending" if requires_deposit else "confirmed"

    booking = Booking(
        customer_id=customer_id,
        staff_id=staff_id,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
        status=booking_status,
        deposit_paid=False,
        deposit_payment_status="required" if requires_deposit else "none"
    )
    db.session.add(booking)
    db.session.flush()

    event = BookingEvent(
        booking_id=booking.id,
        event_type="created",
        memo="예약 생성"
    )

    db.session.add(event)
    notify_booking_created(booking)

    if booking.deposit_payment_status == "required":
        send_deposit_request_sms(booking)
    else:
        send_booking_created_sms(booking)

    db.session.commit()

    return {
        "ok": True,
        "booking": {
            "id": booking.id,
            "customer_id": booking.customer_id,
            "staff_id": booking.staff_id,
            "service_id": booking.service_id,
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
            "status": booking.status,
            "deposit_payment_status": booking.deposit_payment_status
        }
    }


def cancel_booking_by_customer(booking_id):
    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "error": "BOOKING_NOT_FOUND",
            "message": "예약을 찾을 수 없습니다."
        }

    if booking.status not in ["pending", "confirmed"]:
        return {
            "ok": False,
            "error": "BOOKING_NOT_CANCELABLE",
            "message": "취소할 수 없는 예약 상태입니다."
        }

    today = date.today()
    booking_date = booking.start_time.date()

    if booking_date <= today:
        return {
            "ok": False,
            "error": "SAME_DAY_CANCEL_BLOCKED",
            "message": "당일 취소/변경은 앱에서 불가능합니다. 샵으로 전화 문의해주세요."
        }

    booking.status = "cancelled"

    event = BookingEvent(
        booking_id=booking.id,
        event_type="cancelled_by_customer",
        memo="고객 앱 취소"
    )

    db.session.add(event)
    notify_booking_cancelled(booking)
    send_booking_cancelled_sms(booking)
    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "status": booking.status
    }


def create_booking_check_only(staff_id, service_id, start_time):
    service = Service.query.get(service_id)

    if not service or not service.is_active:
        return {"ok": False}

    end_time = start_time + timedelta(minutes=service.duration_minutes)

    weekday = start_time.date().weekday()

    schedule = StaffSchedule.query.filter_by(
        staff_id=staff_id,
        day_of_week=weekday,
        is_working=True
    ).first()

    if not schedule:
        return {"ok": False}

    work_start = datetime.combine(start_time.date(), schedule.start_time)
    work_end = datetime.combine(start_time.date(), schedule.end_time)

    if start_time < work_start or end_time > work_end:
        return {"ok": False}

    if is_during_break(start_time, end_time, schedule):
        return {"ok": False}

    if is_during_time_off(start_time, end_time, staff_id):
        return {"ok": False}

    overlapped_booking = Booking.query.filter(
        Booking.staff_id == staff_id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.start_time < end_time,
        Booking.end_time > start_time
    ).first()

    if overlapped_booking:
        return {"ok": False}

    return {"ok": True}



def find_available_staff_for_service(service_id, start_time):
    service = Service.query.get(service_id)

    if not service:
        return None

    staff_services = StaffService.query.filter_by(
        service_id=service_id
    ).all()

    for staff_service in staff_services:
        staff = Staff.query.get(staff_service.staff_id)

        if not staff or not staff.is_active:
            continue

        result = create_booking_check_only(
            staff_id=staff.id,
            service_id=service_id,
            start_time=start_time
        )

        if result.get("ok"):
            return staff

    return None



def get_available_slots_any_staff(
    service_id,
    target_date
):
    service = Service.query.get(service_id)

    if not service:
        return {
            "ok": False,
            "message": "시술을 찾을 수 없습니다."
        }

    staff_services = StaffService.query.filter_by(
        service_id=service_id
    ).all()

    all_slots = set()

    for staff_service in staff_services:

        result = get_available_slots(
            staff_id=staff_service.staff_id,
            service_id=service_id,
            target_date=target_date
        )

        if result.get("ok"):
            all_slots.update(
                result.get("available_slots", [])
            )

    return {
        "ok": True,
        "available_slots": sorted(list(all_slots))
    }


def reschedule_booking(booking_id, new_start_time):
    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "error": "BOOKING_NOT_FOUND",
            "message": "예약을 찾을 수 없습니다."
        }

    if booking.status not in ["pending", "confirmed"]:
        return {
            "ok": False,
            "error": "BOOKING_NOT_RESCHEDULABLE",
            "message": "변경할 수 없는 예약 상태입니다."
        }

    if booking.start_time.date() <= date.today():
        return {
            "ok": False,
            "error": "SAME_DAY_RESCHEDULE_BLOCKED",
            "message": "당일 예약 변경은 앱에서 불가능합니다. 샵으로 전화 문의해주세요."
        }

    check_result = create_booking_check_only(
        staff_id=booking.staff_id,
        service_id=booking.service_id,
        start_time=new_start_time
    )

    if not check_result.get("ok"):
        return {
            "ok": False,
            "error": "NEW_TIME_NOT_AVAILABLE",
            "message": "선택한 시간에는 예약이 불가능합니다."
        }

    old_start = booking.start_time
    old_end = booking.end_time

    booking.start_time = new_start_time
    booking.end_time = new_start_time + timedelta(
        minutes=booking.service.duration_minutes
    )

    event = BookingEvent(
        booking_id=booking.id,
        event_type="rescheduled",
        memo=f"{old_start}~{old_end} -> {booking.start_time}~{booking.end_time}"
    )

    db.session.add(event)
    notify_booking_changed(booking, "Rescheduled by customer.")
    send_booking_changed_sms(booking)
    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat()
    }



def send_late_notice(booking_id, minutes):
    if minutes not in [5, 10]:
        return {
            "ok": False,
            "message": "5분 또는 10분만 선택할 수 있습니다."
        }

    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "message": "예약을 찾을 수 없습니다."
        }

    if booking.status not in ["pending", "confirmed"]:
        return {
            "ok": False,
            "message": "진행 중인 예약에만 늦음 알림을 보낼 수 있습니다."
        }

    if booking.start_time.date() != date.today():
        return {
            "ok": False,
            "message": "늦음 알림은 예약 당일에만 사용할 수 있습니다."
        }
    
    booking.late_notice_minutes = minutes

    event = BookingEvent(
        booking_id=booking.id,
        event_type="late_notice",
        memo=f"{minutes}분 늦음 알림"
    )

    db.session.add(event)
    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "late_notice_minutes": booking.late_notice_minutes
    }



def update_deposit_status(booking_id, deposit_status):
    allowed_statuses = ["none", "required", "paid", "refunded", "failed"]

    if deposit_status not in allowed_statuses:
        return {
            "ok": False,
            "message": "허용되지 않은 예약금 상태입니다."
        }

    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "message": "예약을 찾을 수 없습니다."
        }

    old_status = booking.status
    old_deposit_status = booking.deposit_payment_status or "none"

    booking.deposit_payment_status = deposit_status
    booking.deposit_paid = deposit_status == "paid"

    settings = ShopSettings.query.first()
    booking_approval_mode = settings.booking_approval_mode if settings else "auto"

    status_auto_confirmed = False

    if deposit_status == "paid" and booking_approval_mode == "auto" and booking.status == "pending":
        booking.status = "confirmed"
        status_auto_confirmed = True

    event = BookingEvent(
        booking_id=booking.id,
        event_type="deposit_status_changed",
        memo=(
            f"예약금 상태 변경: {old_deposit_status} -> {deposit_status}"
            + (
                f", 예약 상태 자동 변경: {old_status} -> confirmed"
                if status_auto_confirmed else ""
            )
        )
    )

    db.session.add(event)
    if deposit_status == "paid":
        notify_deposit_paid(booking, source="Admin")
        send_deposit_paid_sms(booking)
    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "deposit_payment_status": booking.deposit_payment_status,
        "deposit_paid": booking.deposit_paid,
        "status": booking.status,
        "status_auto_confirmed": status_auto_confirmed
    }



def admin_update_booking_assignment(booking_id, staff_id, service_id, new_start_time):
    booking = Booking.query.get(booking_id)

    if not booking:
        return {
            "ok": False,
            "error": "BOOKING_NOT_FOUND",
            "message": "Booking not found."
        }

    if booking.status not in ["pending", "confirmed"]:
        return {
            "ok": False,
            "error": "BOOKING_NOT_EDITABLE",
            "message": "Only pending or confirmed bookings can be edited."
        }

    staff = Staff.query.get(staff_id)
    if not staff or not staff.is_active:
        return {
            "ok": False,
            "error": "STAFF_NOT_FOUND_OR_INACTIVE",
            "message": "Staff member not found or inactive."
        }

    service = Service.query.get(service_id)
    if not service or not service.is_active:
        return {
            "ok": False,
            "error": "SERVICE_NOT_FOUND_OR_INACTIVE",
            "message": "Service not found or inactive."
        }

    if not is_valid_service_duration(service.duration_minutes):
        return {
            "ok": False,
            "error": "INVALID_SERVICE_DURATION",
            "message": "Invalid service duration."
        }

    staff_service = StaffService.query.filter_by(
        staff_id=staff_id,
        service_id=service_id
    ).first()

    if not staff_service:
        return {
            "ok": False,
            "error": "STAFF_CANNOT_DO_SERVICE",
            "message": "This staff member cannot perform the selected service."
        }

    new_end_time = new_start_time + timedelta(minutes=service.duration_minutes)

    weekday = new_start_time.date().weekday()

    schedule = StaffSchedule.query.filter_by(
        staff_id=staff_id,
        day_of_week=weekday,
        is_working=True
    ).first()

    if not schedule:
        return {
            "ok": False,
            "error": "STAFF_NOT_WORKING",
            "message": "This staff member is not working on the selected date."
        }

    work_start = datetime.combine(new_start_time.date(), schedule.start_time)
    work_end = datetime.combine(new_start_time.date(), schedule.end_time)

    if new_start_time < work_start or new_end_time > work_end:
        return {
            "ok": False,
            "error": "OUTSIDE_WORKING_HOURS",
            "message": "The selected time is outside staff working hours."
        }

    if is_during_break(new_start_time, new_end_time, schedule):
        return {
            "ok": False,
            "error": "DURING_BREAK_TIME",
            "message": "The selected time overlaps with staff break time."
        }

    if is_during_time_off(new_start_time, new_end_time, staff_id):
        return {
            "ok": False,
            "error": "STAFF_TIME_OFF",
            "message": "The selected time is blocked by staff time off."
        }

    overlapped_booking = Booking.query.filter(
        Booking.id != booking_id,
        Booking.staff_id == staff_id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.start_time < new_end_time,
        Booking.end_time > new_start_time
    ).first()

    if overlapped_booking:
        return {
            "ok": False,
            "error": "BOOKING_TIME_OVERLAPPED",
            "message": "Another booking already exists during the selected time."
        }

    old_staff_id = booking.staff_id
    old_service_id = booking.service_id
    old_start = booking.start_time
    old_end = booking.end_time

    booking.staff_id = staff_id
    booking.service_id = service_id
    booking.start_time = new_start_time
    booking.end_time = new_end_time

    settings = ShopSettings.query.first()
    deposit_enabled = settings.deposit_enabled if settings else False

    if deposit_enabled and service.deposit_required:
        if booking.deposit_payment_status == "none":
            booking.deposit_payment_status = "required"
    else:
        booking.deposit_payment_status = "none"
        booking.deposit_paid = False
        booking.deposit_payment_link = None
        booking.deposit_note = None

    event = BookingEvent(
        booking_id=booking.id,
        event_type="assignment_changed",
        memo=(
            f"staff {old_staff_id}->{staff_id}, "
            f"service {old_service_id}->{service_id}, "
            f"time {old_start}~{old_end} -> {booking.start_time}~{booking.end_time}"
        )
    )

    db.session.add(event)
    notify_booking_changed(booking, "Assignment changed by admin.")

    if booking.deposit_payment_status == "required" and old_service_id != service_id:
        send_deposit_request_sms(booking)
    else:
        send_booking_changed_sms(booking)

    db.session.commit()

    return {
        "ok": True,
        "booking_id": booking.id,
        "staff_id": booking.staff_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat()
    }
