from __future__ import annotations

import json
from datetime import date

from sqlalchemy.exc import IntegrityError

from flask import current_app, has_app_context

from dashboard.models import ShopSettings
from extensions import db
from sms.default_templates import DEFAULT_SMS_TEMPLATES
from sms.models import SmsLog, SmsTemplate
from sms.provider import SolapiSmsProvider, SmsProviderError, normalize_phone
from sms.renderer import build_booking_context, render_template_content


class SmsEventType:
    BOOKING_CREATED = "booking_created"
    BOOKING_CHANGED = "booking_changed"
    BOOKING_CANCELLED = "booking_cancelled"
    DEPOSIT_REQUEST = "deposit_request"
    DEPOSIT_PAID = "deposit_paid"
    TEST = "test"
    BOOKING_REMINDER = "booking_reminder"


ADMIN_TEMPLATE_BY_EVENT = {
    SmsEventType.BOOKING_CREATED: "admin_booking_created",
    SmsEventType.BOOKING_CHANGED: "admin_booking_changed",
    SmsEventType.BOOKING_CANCELLED: "admin_booking_cancelled",
    SmsEventType.DEPOSIT_REQUEST: "admin_deposit_request",
    SmsEventType.DEPOSIT_PAID: "admin_deposit_paid",
    SmsEventType.BOOKING_REMINDER: "admin_booking_reminder",
}

ADMIN_SETTING_FLAG_BY_EVENT = {
    SmsEventType.BOOKING_CREATED: "admin_sms_booking_created_enabled",
    SmsEventType.BOOKING_CHANGED: "admin_sms_booking_changed_enabled",
    SmsEventType.BOOKING_CANCELLED: "admin_sms_booking_cancelled_enabled",
    SmsEventType.DEPOSIT_REQUEST: "admin_sms_deposit_request_enabled",
    SmsEventType.DEPOSIT_PAID: "admin_sms_deposit_paid_enabled",
    SmsEventType.BOOKING_REMINDER: "admin_sms_booking_reminder_enabled",
}


def ensure_default_sms_templates():
    """Create missing default templates without overwriting admin-edited content."""
    created_count = 0
    for item in DEFAULT_SMS_TEMPLATES:
        existing = SmsTemplate.query.filter_by(template_key=item["template_key"]).first()
        if existing:
            continue
        db.session.add(SmsTemplate(**item))
        created_count += 1

    if created_count:
        db.session.commit()
    return created_count


def get_sms_template(template_key):
    ensure_default_sms_templates()
    return SmsTemplate.query.filter_by(template_key=template_key).first()


def render_sms_template(template_key, booking):
    template = get_sms_template(template_key)
    if not template:
        return None, "missing_template"
    if not template.is_enabled:
        return None, "template_disabled"

    context = build_booking_context(booking)
    return render_template_content(template.content, context), None


def send_booking_sms(booking, event_type):
    """Send customer SMS and configured admin SMS for a booking event.

    SMS failures are logged and returned, but they do not roll back bookings/payments.
    """
    if not booking:
        return {"ok": False, "skipped": True, "reason": "missing_booking"}

    customer_result = send_customer_booking_sms(booking, event_type)
    admin_results = send_admin_booking_sms(booking, event_type)

    return {
        "ok": bool(customer_result.get("ok")) or any(result.get("ok") for result in admin_results),
        "customer": customer_result,
        "admin": admin_results,
    }


def send_customer_booking_sms(booking, event_type):
    message, error = render_sms_template(event_type, booking)
    if error:
        return {"ok": False, "skipped": True, "reason": error, "recipient_type": "customer"}

    customer = getattr(booking, "customer", None)
    recipient = getattr(customer, "phone", None)

    return _send_and_log(
        recipient=recipient,
        message=message,
        event_type=event_type,
        template_key=event_type,
        recipient_type="customer",
        booking_id=getattr(booking, "id", None),
    )


def send_admin_booking_sms(booking, event_type):
    settings = ShopSettings.query.first() if has_app_context() else None
    if not settings:
        return []

    flag_name = ADMIN_SETTING_FLAG_BY_EVENT.get(event_type)
    if flag_name and getattr(settings, flag_name, True) is False:
        return []

    recipients = _parse_admin_recipients(getattr(settings, "admin_sms_recipients", None))
    if not recipients:
        return []

    admin_template_key = ADMIN_TEMPLATE_BY_EVENT.get(event_type)
    if not admin_template_key:
        return []

    message, error = render_sms_template(admin_template_key, booking)
    if error:
        return [{"ok": False, "skipped": True, "reason": error, "recipient_type": "admin"}]

    results = []
    for recipient in recipients:
        results.append(_send_and_log(
            recipient=recipient,
            message=message,
            event_type=event_type,
            template_key=admin_template_key,
            recipient_type="admin",
            booking_id=getattr(booking, "id", None),
        ))
    return results



def send_booking_reminder_sms(booking, reminder_date: date):
    """Send customer/admin reminder once per booking schedule and recipient.

    The dedupe key includes the booking start datetime. A rescheduled booking therefore
    becomes eligible again for its new schedule, while repeated scheduler/manual runs
    for the same schedule are ignored.
    """
    if not booking or getattr(booking, "status", None) != "confirmed":
        return {"ok": False, "skipped": True, "reason": "booking_not_confirmed", "customer": {}, "admin": []}

    scheduled_for = getattr(booking, "start_time", None)
    customer_message, customer_error = render_sms_template("booking_reminder", booking)
    if customer_error:
        customer_result = {"ok": False, "skipped": True, "reason": customer_error, "recipient_type": "customer"}
    else:
        customer = getattr(booking, "customer", None)
        recipient = getattr(customer, "phone", None)
        customer_result = _send_and_log(
            recipient=recipient,
            message=customer_message,
            event_type=SmsEventType.BOOKING_REMINDER,
            template_key="booking_reminder",
            recipient_type="customer",
            booking_id=getattr(booking, "id", None),
            scheduled_for=scheduled_for,
            reminder_date=reminder_date,
            dedupe_key=_build_reminder_dedupe_key(booking, "booking_reminder", "customer", recipient),
        )

    admin_results = send_admin_booking_reminder_sms(booking, reminder_date)
    return {
        "ok": bool(customer_result.get("ok")) or any(item.get("ok") for item in admin_results),
        "customer": customer_result,
        "admin": admin_results,
    }


def send_admin_booking_reminder_sms(booking, reminder_date: date):
    settings = ShopSettings.query.first() if has_app_context() else None
    if not settings or getattr(settings, "admin_sms_booking_reminder_enabled", True) is False:
        return []

    recipients = _parse_admin_recipients(getattr(settings, "admin_sms_recipients", None))
    if not recipients:
        return []

    message, error = render_sms_template("admin_booking_reminder", booking)
    if error:
        return [{"ok": False, "skipped": True, "reason": error, "recipient_type": "admin"}]

    results = []
    for recipient in recipients:
        results.append(_send_and_log(
            recipient=recipient,
            message=message,
            event_type=SmsEventType.BOOKING_REMINDER,
            template_key="admin_booking_reminder",
            recipient_type="admin",
            booking_id=getattr(booking, "id", None),
            scheduled_for=getattr(booking, "start_time", None),
            reminder_date=reminder_date,
            dedupe_key=_build_reminder_dedupe_key(booking, "admin_booking_reminder", "admin", recipient),
        ))
    return results


def _build_reminder_dedupe_key(booking, template_key, recipient_type, recipient):
    scheduled_for = getattr(booking, "start_time", None)
    schedule_token = scheduled_for.isoformat(timespec="minutes") if scheduled_for else "missing"
    phone = normalize_phone(recipient) or "missing"
    return f"booking-reminder:{getattr(booking, 'id', 'missing')}:{template_key}:{recipient_type}:{phone}:{schedule_token}"

def send_test_sms(recipient, message=None):
    text = (message or "[Salon De Nature] SMS test message. If you received this, Solapi connection is working.").strip()
    return _send_and_log(
        recipient=recipient,
        message=text,
        event_type=SmsEventType.TEST,
        template_key=SmsEventType.TEST,
        recipient_type="test",
        booking_id=None,
    )


def _parse_admin_recipients(value):
    if not value:
        return []
    normalized = value.replace("\n", ",").replace(";", ",")
    recipients = []
    for item in normalized.split(","):
        phone = normalize_phone(item.strip())
        if phone and phone not in recipients:
            recipients.append(phone)
    return recipients


def _send_and_log(recipient, message, event_type, booking_id=None, template_key=None, recipient_type="customer", scheduled_for=None, reminder_date=None, dedupe_key=None):
    recipient_phone = normalize_phone(recipient)
    log = _create_sms_log(
        event_type=event_type,
        template_key=template_key,
        recipient_type=recipient_type,
        booking_id=booking_id,
        recipient_phone=recipient_phone,
        message=message,
        scheduled_for=scheduled_for,
        reminder_date=reminder_date,
        dedupe_key=dedupe_key,
    )

    if dedupe_key and log is None:
        return {
            "ok": False,
            "skipped": True,
            "reason": "duplicate_reminder",
            "recipient_type": recipient_type,
            "template_key": template_key,
        }

    try:
        result = SolapiSmsProvider().send_sms(recipient_phone, message)
        status = "skipped" if result.skipped else "sent"
        _update_sms_log(
            log,
            status=status,
            provider=result.provider,
            provider_response=result.response,
            error_message=result.reason,
        )

        if result.skipped:
            _log_info("SMS skipped. event=%s recipient_type=%s booking_id=%s reason=%s", event_type, recipient_type, booking_id, result.reason)
        else:
            _log_info("SMS sent. event=%s recipient_type=%s booking_id=%s", event_type, recipient_type, booking_id)

        return {
            "ok": result.ok,
            "skipped": result.skipped,
            "reason": result.reason,
            "provider": result.provider,
            "response": result.response,
            "recipient_type": recipient_type,
            "template_key": template_key,
            "log_id": getattr(log, "id", None),
        }
    except SmsProviderError as exc:
        _update_sms_log(log, status="failed", error_message=str(exc))
        _log_exception("SMS provider error. event=%s recipient_type=%s booking_id=%s error=%s", event_type, recipient_type, booking_id, exc)
        return {"ok": False, "skipped": False, "reason": str(exc), "recipient_type": recipient_type, "template_key": template_key, "log_id": getattr(log, "id", None)}
    except Exception as exc:
        _update_sms_log(log, status="failed", error_message=str(exc))
        _log_exception("SMS unexpected error. event=%s recipient_type=%s booking_id=%s error=%s", event_type, recipient_type, booking_id, exc)
        return {"ok": False, "skipped": False, "reason": str(exc), "recipient_type": recipient_type, "template_key": template_key, "log_id": getattr(log, "id", None)}


def send_booking_created_sms(booking):
    return send_booking_sms(booking, SmsEventType.BOOKING_CREATED)


def send_booking_changed_sms(booking):
    return send_booking_sms(booking, SmsEventType.BOOKING_CHANGED)


def send_booking_cancelled_sms(booking):
    return send_booking_sms(booking, SmsEventType.BOOKING_CANCELLED)


def send_deposit_request_sms(booking):
    return send_booking_sms(booking, SmsEventType.DEPOSIT_REQUEST)


def send_deposit_paid_sms(booking):
    return send_booking_sms(booking, SmsEventType.DEPOSIT_PAID)


def _create_sms_log(event_type, template_key, recipient_type, booking_id, recipient_phone, message, scheduled_for=None, reminder_date=None, dedupe_key=None):
    if not has_app_context():
        return None

    try:
        log = SmsLog(
            event_type=event_type,
            template_key=template_key,
            recipient_type=recipient_type,
            booking_id=booking_id,
            recipient_phone=recipient_phone,
            message=message or "",
            scheduled_for=scheduled_for,
            reminder_date=reminder_date,
            dedupe_key=dedupe_key,
            status="pending",
            provider="solapi",
        )
        db.session.add(log)
        db.session.commit()
        return log
    except IntegrityError as exc:
        db.session.rollback()
        if dedupe_key:
            _log_info("Duplicate SMS reminder claim skipped. dedupe_key=%s", dedupe_key)
            return None
        _log_exception("Failed to create SMS log. event=%s booking_id=%s error=%s", event_type, booking_id, exc)
        return None
    except Exception as exc:
        db.session.rollback()
        _log_exception("Failed to create SMS log. event=%s booking_id=%s error=%s", event_type, booking_id, exc)
        return None


def _update_sms_log(log, status, provider="solapi", provider_response=None, error_message=None):
    if not log or not has_app_context():
        return

    try:
        log.status = status
        log.provider = provider or "solapi"
        log.provider_response = _safe_json(provider_response)
        log.error_message = error_message
        log.provider_message_id = _extract_message_id(provider_response)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        _log_exception("Failed to update SMS log. log_id=%s error=%s", getattr(log, "id", None), exc)


def _safe_json(value):
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _extract_message_id(response):
    if not isinstance(response, dict):
        return None

    candidates = [
        response.get("messageId"),
        response.get("message_id"),
        response.get("groupId"),
        response.get("group_id"),
    ]

    message = response.get("message")
    if isinstance(message, dict):
        candidates.extend([message.get("messageId"), message.get("message_id")])

    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None


def _log_info(message, *args):
    if has_app_context():
        current_app.logger.info(message, *args)


def _log_exception(message, *args):
    if has_app_context():
        current_app.logger.exception(message, *args)
