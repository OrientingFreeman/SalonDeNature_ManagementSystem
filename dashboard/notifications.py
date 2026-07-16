from datetime import datetime, timedelta

from extensions import db
from dashboard.models import AdminNotification


def _format_booking_time(booking):
    if not booking or not booking.start_time:
        return ""

    return booking.start_time.strftime("%Y-%m-%d %H:%M")


def _booking_target_url(booking):
    if not booking or not booking.start_time:
        return "/admin/timeline"

    return f"/admin/timeline?date={booking.start_time.strftime('%Y-%m-%d')}&booking_id={booking.id}"


def _booking_customer_name(booking):
    if booking and booking.customer and booking.customer.name:
        return booking.customer.name

    return "고객"


def _booking_service_name(booking):
    if booking and booking.service:
        return booking.service.name_ko or booking.service.name_en or "서비스"

    return "서비스"



def _status_label(status):
    return {
        "pending": "대기",
        "confirmed": "확정",
        "completed": "완료",
        "cancelled": "취소",
        "no_show": "노쇼",
    }.get(status, status)


def create_admin_notification(notification_type, title, message, booking=None, target_url=None):
    notification = AdminNotification(
        notification_type=notification_type,
        title=title,
        message=message,
        booking_id=booking.id if booking else None,
        target_url=target_url or _booking_target_url(booking),
    )

    db.session.add(notification)
    return notification


def notify_booking_created(booking):
    customer_name = _booking_customer_name(booking)
    service_name = _booking_service_name(booking)
    booking_time = _format_booking_time(booking)

    title = "새 예약"
    message = f"{customer_name} 고객이 {booking_time}에 {service_name} 예약을 등록했습니다."

    if booking.deposit_payment_status == "required":
        title = "새 예약 · 예약금 필요"
        message = f"{customer_name} 고객이 {booking_time}에 {service_name} 예약을 등록했습니다. 예약금 입금이 필요합니다."

    return create_admin_notification(
        notification_type="booking_created",
        title=title,
        message=message,
        booking=booking,
    )


def notify_booking_cancelled(booking):
    customer_name = _booking_customer_name(booking)
    service_name = _booking_service_name(booking)
    booking_time = _format_booking_time(booking)

    return create_admin_notification(
        notification_type="booking_cancelled",
        title="예약 취소",
        message=f"{customer_name} 고객의 {booking_time} {service_name} 예약이 취소되었습니다.",
        booking=booking,
    )


def notify_booking_changed(booking, change_summary=None):
    customer_name = _booking_customer_name(booking)
    service_name = _booking_service_name(booking)
    booking_time = _format_booking_time(booking)
    detail = f" ({change_summary})" if change_summary else ""

    return create_admin_notification(
        notification_type="booking_changed",
        title="예약 변경",
        message=f"{customer_name} 고객의 {service_name} 예약이 {booking_time}으로 변경되었습니다.{detail}",
        booking=booking,
    )


def notify_deposit_paid(booking, source="관리자"):
    customer_name = _booking_customer_name(booking)
    service_name = _booking_service_name(booking)
    booking_time = _format_booking_time(booking)

    return create_admin_notification(
        notification_type="deposit_paid",
        title="예약금 입금 확인",
        message=f"{source}: {customer_name} 고객의 {booking_time} {service_name} 예약금이 입금 완료 처리되었습니다.",
        booking=booking,
    )


def notify_booking_status_changed(booking, old_status, new_status):
    customer_name = _booking_customer_name(booking)
    service_name = _booking_service_name(booking)

    return create_admin_notification(
        notification_type="booking_status_changed",
        title="예약 상태 변경",
        message=f"{customer_name} 고객의 {service_name} 예약 상태가 {_status_label(old_status)}에서 {_status_label(new_status)}(으)로 변경되었습니다.",
        booking=booking,
    )


def serialize_admin_notification(notification):
    return {
        "id": notification.id,
        "type": notification.notification_type,
        "title": notification.title,
        "message": notification.message,
        "target_url": notification.target_url or "/admin/timeline",
        "is_read": bool(notification.is_read),
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "created_at_display": notification.created_at.strftime("%Y-%m-%d %H:%M") if notification.created_at else "",
    }


def mark_notification_read(notification):
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()

def cleanup_old_admin_notifications(
    read_retention_days=30,
    unread_retention_days=90
):
    """
    Delete old admin notifications.

    Policy:
    - Read notifications are deleted after 30 days by default.
    - Unread notifications are deleted after 90 days by default.

    Booking history itself remains in BookingEvent / Booking tables.
    AdminNotification is treated as a short-lived UI notification table.
    """
    now = datetime.utcnow()
    read_cutoff = now - timedelta(days=read_retention_days)
    unread_cutoff = now - timedelta(days=unread_retention_days)

    old_read_notifications = AdminNotification.query.filter(
        AdminNotification.is_read == True,
        AdminNotification.created_at < read_cutoff
    )

    old_unread_notifications = AdminNotification.query.filter(
        AdminNotification.is_read == False,
        AdminNotification.created_at < unread_cutoff
    )

    read_deleted_count = old_read_notifications.count()
    unread_deleted_count = old_unread_notifications.count()

    old_read_notifications.delete(synchronize_session=False)
    old_unread_notifications.delete(synchronize_session=False)

    return {
        "read_deleted_count": read_deleted_count,
        "unread_deleted_count": unread_deleted_count,
        "total_deleted_count": read_deleted_count + unread_deleted_count,
        "read_retention_days": read_retention_days,
        "unread_retention_days": unread_retention_days,
    }

def admin_notification_filter_query(base_query, filter_key=None, search_query=None):
    """
    Apply Notification Center filters/search.

    Supported filter_key:
    - all
    - unread
    - booking
    - deposit
    - status
    - cancelled
    """
    filter_key = (filter_key or "all").strip().lower()
    search_query = (search_query or "").strip()

    if filter_key == "unread":
        base_query = base_query.filter(AdminNotification.is_read == False)
    elif filter_key == "booking":
        base_query = base_query.filter(
            AdminNotification.notification_type.in_([
                "booking_created",
                "booking_changed",
            ])
        )
    elif filter_key == "deposit":
        base_query = base_query.filter(
            AdminNotification.notification_type.in_([
                "deposit_paid",
            ])
        )
    elif filter_key == "status":
        base_query = base_query.filter(
            AdminNotification.notification_type == "booking_status_changed"
        )
    elif filter_key == "cancelled":
        base_query = base_query.filter(
            AdminNotification.notification_type == "booking_cancelled"
        )

    if search_query:
        like_term = f"%{search_query}%"
        base_query = base_query.filter(
            db.or_(
                AdminNotification.title.ilike(like_term),
                AdminNotification.message.ilike(like_term),
                AdminNotification.notification_type.ilike(like_term),
            )
        )

    return base_query


def get_admin_notification_stats():
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    return {
        "total_count": AdminNotification.query.count(),
        "unread_count": AdminNotification.query.filter_by(is_read=False).count(),
        "today_count": AdminNotification.query.filter(
            AdminNotification.created_at >= today_start
        ).count(),
    }


def mark_admin_notifications_read_by_ids(notification_ids):
    if not notification_ids:
        return 0

    now = datetime.utcnow()
    notifications = AdminNotification.query.filter(
        AdminNotification.id.in_(notification_ids)
    ).all()

    updated_count = 0

    for notification in notifications:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = now
            updated_count += 1

    return updated_count


def delete_admin_notifications_by_ids(notification_ids):
    if not notification_ids:
        return 0

    query = AdminNotification.query.filter(
        AdminNotification.id.in_(notification_ids)
    )

    deleted_count = query.count()
    query.delete(synchronize_session=False)

    return deleted_count

