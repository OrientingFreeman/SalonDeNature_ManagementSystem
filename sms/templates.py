from __future__ import annotations

from dashboard.models import ShopSettings


def _customer_name(booking):
    return booking.customer.name if booking and booking.customer and booking.customer.name else "고객"


def _service_name(booking):
    if booking and booking.service:
        return booking.service.name_ko or booking.service.name_en or "예약 서비스"
    return "예약 서비스"


def _staff_name(booking):
    return booking.staff.name if booking and booking.staff and booking.staff.name else "담당자"


def _time_display(booking):
    if not booking or not booking.start_time:
        return "예약 시간 미정"
    return booking.start_time.strftime("%Y-%m-%d %H:%M")


def _shop_name():
    return "Salon De Nature"


def booking_created_message(booking):
    return (
        f"[{_shop_name()}] {_customer_name(booking)}님, 예약이 접수되었습니다.\n"
        f"- 시술: {_service_name(booking)}\n"
        f"- 담당: {_staff_name(booking)}\n"
        f"- 일시: {_time_display(booking)}"
    )


def booking_changed_message(booking):
    return (
        f"[{_shop_name()}] 예약 정보가 변경되었습니다.\n"
        f"- 시술: {_service_name(booking)}\n"
        f"- 담당: {_staff_name(booking)}\n"
        f"- 변경 일시: {_time_display(booking)}"
    )


def booking_cancelled_message(booking):
    return (
        f"[{_shop_name()}] 예약이 취소되었습니다.\n"
        f"- 시술: {_service_name(booking)}\n"
        f"- 일시: {_time_display(booking)}"
    )


def deposit_request_message(booking):
    settings = ShopSettings.query.first()
    amount = booking.service.deposit_amount if booking and booking.service else 0

    lines = [
        f"[{_shop_name()}] 예약금 입금 안내입니다.",
        f"- 시술: {_service_name(booking)}",
        f"- 일시: {_time_display(booking)}",
    ]

    if amount:
        lines.append(f"- 예약금: {amount:,}원")

    if settings:
        account_parts = [
            settings.deposit_bank_name,
            settings.deposit_account_number,
            settings.deposit_account_holder,
        ]
        account_text = " ".join([part for part in account_parts if part])
        if account_text:
            lines.append(f"- 입금계좌: {account_text}")
        if settings.deposit_due_minutes:
            lines.append(f"- 입금기한: 예약 후 {settings.deposit_due_minutes}분 이내")
        if settings.deposit_notice:
            lines.append(settings.deposit_notice.strip())

    return "\n".join(lines)


def deposit_paid_message(booking):
    return (
        f"[{_shop_name()}] 예약금 입금이 확인되었습니다.\n"
        f"- 시술: {_service_name(booking)}\n"
        f"- 일시: {_time_display(booking)}"
    )
