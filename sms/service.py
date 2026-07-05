from __future__ import annotations

import json

from flask import current_app, has_app_context

from extensions import db
from sms.models import SmsLog
from sms.provider import SolapiSmsProvider, SmsProviderError, normalize_phone
from sms import templates


class SmsEventType:
    BOOKING_CREATED = "booking_created"
    BOOKING_CHANGED = "booking_changed"
    BOOKING_CANCELLED = "booking_cancelled"
    DEPOSIT_REQUEST = "deposit_request"
    DEPOSIT_PAID = "deposit_paid"
    TEST = "test"


TEMPLATE_BUILDERS = {
    SmsEventType.BOOKING_CREATED: templates.booking_created_message,
    SmsEventType.BOOKING_CHANGED: templates.booking_changed_message,
    SmsEventType.BOOKING_CANCELLED: templates.booking_cancelled_message,
    SmsEventType.DEPOSIT_REQUEST: templates.deposit_request_message,
    SmsEventType.DEPOSIT_PAID: templates.deposit_paid_message,
}


def send_booking_sms(booking, event_type):
    """Send a customer SMS for a booking event.

    SMS failures are logged and returned, but they do not roll back bookings/payments.
    """
    if not booking:
        return {"ok": False, "skipped": True, "reason": "missing_booking"}

    builder = TEMPLATE_BUILDERS.get(event_type)
    if not builder:
        return {"ok": False, "skipped": True, "reason": "unsupported_event_type"}

    customer = getattr(booking, "customer", None)
    recipient = getattr(customer, "phone", None)
    message = builder(booking)

    return _send_and_log(
        recipient=recipient,
        message=message,
        event_type=event_type,
        booking_id=getattr(booking, "id", None),
    )


def send_test_sms(recipient, message=None):
    text = (message or "[Salon De Nature] SMS test message. If you received this, Solapi connection is working.").strip()
    return _send_and_log(
        recipient=recipient,
        message=text,
        event_type=SmsEventType.TEST,
        booking_id=None,
    )


def _send_and_log(recipient, message, event_type, booking_id=None):
    recipient_phone = normalize_phone(recipient)
    log = _create_sms_log(
        event_type=event_type,
        booking_id=booking_id,
        recipient_phone=recipient_phone,
        message=message,
    )

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
            _log_info("SMS skipped. event=%s booking_id=%s reason=%s", event_type, booking_id, result.reason)
        else:
            _log_info("SMS sent. event=%s booking_id=%s", event_type, booking_id)

        return {
            "ok": result.ok,
            "skipped": result.skipped,
            "reason": result.reason,
            "provider": result.provider,
            "response": result.response,
            "log_id": getattr(log, "id", None),
        }
    except SmsProviderError as exc:
        _update_sms_log(log, status="failed", error_message=str(exc))
        _log_exception("SMS provider error. event=%s booking_id=%s error=%s", event_type, booking_id, exc)
        return {"ok": False, "skipped": False, "reason": str(exc), "log_id": getattr(log, "id", None)}
    except Exception as exc:
        _update_sms_log(log, status="failed", error_message=str(exc))
        _log_exception("SMS unexpected error. event=%s booking_id=%s error=%s", event_type, booking_id, exc)
        return {"ok": False, "skipped": False, "reason": str(exc), "log_id": getattr(log, "id", None)}


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


def _create_sms_log(event_type, booking_id, recipient_phone, message):
    if not has_app_context():
        return None

    try:
        log = SmsLog(
            event_type=event_type,
            booking_id=booking_id,
            recipient_phone=recipient_phone,
            message=message or "",
            status="pending",
            provider="solapi",
        )
        db.session.add(log)
        db.session.commit()
        return log
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

    # SOLAPI response shape can differ by endpoint/version. Keep this defensive.
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
