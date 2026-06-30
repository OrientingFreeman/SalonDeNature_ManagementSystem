from flask import url_for

from dashboard.models import AdminNotification
from extensions import db


def _booking_label(booking):
    customer_name = getattr(getattr(booking, "customer", None), "name", None) or "Customer"
    service = getattr(booking, "service", None)
    service_name = getattr(service, "name_en", None) or getattr(service, "name_ko", None) or "Service"
    start_text = booking.start_time.strftime("%Y-%m-%d %H:%M") if booking.start_time else "No time"
    return customer_name, service_name, start_text


def create_admin_notification(notification_type, title, message=None, booking=None, target_url=None):
    notification = AdminNotification(
        notification_type=notification_type,
        title=title,
        message=message,
        booking_id=booking.id if booking else None,
        target_url=target_url,
    )
    db.session.add(notification)
    return notification


def notify_booking_created(booking):
    customer_name, service_name, start_text = _booking_label(booking)

    if booking.deposit_payment_status == "required":
        title = "예약금 확인 필요"
        message = f"{customer_name} / {service_name} / {start_text} 예약이 생성되었습니다. 예약금 입금 확인이 필요합니다."
        notification_type = "DEPOSIT_REQUIRED"
    else:
        title = "새 예약 생성"
        message = f"{customer_name} / {service_name} / {start_text} 예약이 생성되었습니다."
        notification_type = "BOOKING_CREATED"

    return create_admin_notification(
        notification_type=notification_type,
        title=title,
        message=message,
        booking=booking,
        target_url=f"/admin/timeline?date={booking.start_time.date().isoformat()}" if booking.start_time else "/admin/timeline",
    )


def notify_booking_cancelled_by_customer(booking):
    customer_name, service_name, start_text = _booking_label(booking)
    return create_admin_notification(
        notification_type="BOOKING_CANCELLED_BY_CUSTOMER",
        title="고객 예약 취소",
        message=f"{customer_name} / {service_name} / {start_text} 예약이 고객에 의해 취소되었습니다.",
        booking=booking,
        target_url=f"/admin/timeline?date={booking.start_time.date().isoformat()}" if booking.start_time else "/admin/timeline",
    )


def notify_booking_rescheduled(booking, old_start=None, old_end=None):
    customer_name, service_name, start_text = _booking_label(booking)
    old_text = old_start.strftime("%Y-%m-%d %H:%M") if old_start else "previous time"
    return create_admin_notification(
        notification_type="BOOKING_RESCHEDULED",
        title="예약 시간 변경",
        message=f"{customer_name} / {service_name} 예약 시간이 {old_text}에서 {start_text}로 변경되었습니다.",
        booking=booking,
        target_url=f"/admin/timeline?date={booking.start_time.date().isoformat()}" if booking.start_time else "/admin/timeline",
    )


def notify_booking_assignment_changed(booking):
    customer_name, service_name, start_text = _booking_label(booking)
    staff_name = getattr(getattr(booking, "staff", None), "name", None) or "Staff"
    return create_admin_notification(
        notification_type="BOOKING_ASSIGNMENT_CHANGED",
        title="예약 배정 변경",
        message=f"{customer_name} / {service_name} / {start_text} 예약이 {staff_name}에게 배정되었습니다.",
        booking=booking,
        target_url=f"/admin/timeline?date={booking.start_time.date().isoformat()}" if booking.start_time else "/admin/timeline",
    )


def notify_deposit_marked_paid(booking, status_auto_confirmed=False):
    customer_name, service_name, start_text = _booking_label(booking)
    suffix = " 예약도 자동 확정되었습니다." if status_auto_confirmed else ""
    return create_admin_notification(
        notification_type="DEPOSIT_MARKED_PAID",
        title="예약금 입금 확인 완료",
        message=f"{customer_name} / {service_name} / {start_text} 예약금이 입금 확인 처리되었습니다.{suffix}",
        booking=booking,
        target_url=f"/admin/timeline?date={booking.start_time.date().isoformat()}" if booking.start_time else "/admin/timeline",
    )


def notify_booking_status_changed(booking, old_status, new_status):
    customer_name, service_name, start_text = _booking_label(booking)
    return create_admin_notification(
        notification_type="BOOKING_STATUS_CHANGED",
        title="예약 상태 변경",
        message=f"{customer_name} / {service_name} / {start_text} 상태가 {old_status}에서 {new_status}로 변경되었습니다.",
        booking=booking,
        target_url=f"/admin/timeline?date={booking.start_time.date().isoformat()}" if booking.start_time else "/admin/timeline",
    )
