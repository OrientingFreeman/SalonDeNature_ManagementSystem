from __future__ import annotations

import re
from datetime import datetime

from dashboard.models import ShopSettings

PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def render_template_content(content: str, context: dict) -> str:
    """Render a template by replacing {placeholder} tokens.

    Unknown placeholders are intentionally preserved so admins can see typos in preview.
    """
    content = content or ""

    def replace(match):
        key = match.group(1)
        if key not in context:
            return match.group(0)
        value = context.get(key)
        return "" if value is None else str(value)

    return PLACEHOLDER_PATTERN.sub(replace, content).strip()


def build_booking_context(booking) -> dict:
    settings = ShopSettings.query.first()
    customer = getattr(booking, "customer", None)
    staff = getattr(booking, "staff", None)
    service = getattr(booking, "service", None)
    start_time = getattr(booking, "start_time", None)

    service_name = "예약 서비스"
    if service:
        service_name = service.name_ko or service.name_en or service_name

    deposit_amount_value = 0
    if service and getattr(service, "deposit_amount", None):
        deposit_amount_value = service.deposit_amount

    account_text = ""
    deposit_due_minutes = ""
    deposit_notice = ""
    if settings:
        account_parts = [
            settings.deposit_bank_name,
            settings.deposit_account_number,
            settings.deposit_account_holder,
        ]
        account_text = " ".join([part for part in account_parts if part])
        deposit_due_minutes = settings.deposit_due_minutes or ""
        deposit_notice = (settings.deposit_notice or "").strip()

    return {
        "shop_name": "Salon De Nature",
        "customer_name": getattr(customer, "name", None) or "고객",
        "customer_phone": getattr(customer, "phone", None) or "",
        "staff_name": getattr(staff, "name", None) or "담당자",
        "service_name": service_name,
        "booking_date": _format_date(start_time),
        "booking_time": _format_time(start_time),
        "booking_datetime": _format_datetime(start_time),
        "deposit_amount": f"{deposit_amount_value:,}원" if deposit_amount_value else "",
        "deposit_account": account_text,
        "deposit_due_minutes": deposit_due_minutes,
        "deposit_notice": deposit_notice,
        "payment_link": getattr(booking, "deposit_payment_link", None) or "",
    }


def build_sample_context() -> dict:
    return {
        "shop_name": "Salon De Nature",
        "customer_name": "김민지",
        "customer_phone": "01012345678",
        "staff_name": "수진",
        "service_name": "젤네일",
        "booking_date": "2026-07-12",
        "booking_time": "14:00",
        "booking_datetime": "2026-07-12 14:00",
        "deposit_amount": "20,000원",
        "deposit_account": "국민은행 123456-78-901234 살롱드네이처",
        "deposit_due_minutes": "30",
        "deposit_notice": "예약 후 30분 이내 입금 부탁드립니다.",
        "payment_link": "https://salondenature.shop/pay/sample",
    }


def render_sample(content: str) -> str:
    return render_template_content(content, build_sample_context())


def _format_date(value):
    if not isinstance(value, datetime):
        return "예약일 미정"
    return value.strftime("%Y-%m-%d")


def _format_time(value):
    if not isinstance(value, datetime):
        return "예약시간 미정"
    return value.strftime("%H:%M")


def _format_datetime(value):
    if not isinstance(value, datetime):
        return "예약 시간 미정"
    return value.strftime("%Y-%m-%d %H:%M")
