from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from flask import current_app


class SmsProviderError(Exception):
    """Raised when the SMS provider request fails."""


@dataclass
class SmsSendResult:
    ok: bool
    skipped: bool = False
    reason: Optional[str] = None
    provider: str = "solapi"
    response: Optional[Dict[str, Any]] = None


class SolapiSmsProvider:
    """Minimal SOLAPI REST provider.

    Uses SOLAPI HMAC-SHA256 authentication and the single-message endpoint.
    Required Flask config:
    - SOLAPI_API_KEY
    - SOLAPI_API_SECRET
    - SOLAPI_FROM_NUMBER
    Optional Flask config:
    - SMS_ENABLED: must be true for real sending
    - SOLAPI_API_BASE_URL: default https://api.solapi.com
    - SOLAPI_TIMEOUT_SECONDS: default 10
    """

    def __init__(self, app_config=None):
        self.config = app_config or current_app.config
        self.api_key = self.config.get("SOLAPI_API_KEY")
        self.api_secret = self.config.get("SOLAPI_API_SECRET")
        self.from_number = normalize_phone(self.config.get("SOLAPI_FROM_NUMBER"))
        self.base_url = (self.config.get("SOLAPI_API_BASE_URL") or "https://api.solapi.com").rstrip("/")
        self.timeout = int(self.config.get("SOLAPI_TIMEOUT_SECONDS") or 10)
        self.enabled = bool(self.config.get("SMS_ENABLED"))

    def send_sms(self, to: str, text: str) -> SmsSendResult:
        to_number = normalize_phone(to)
        text = (text or "").strip()

        if not to_number:
            return SmsSendResult(ok=False, skipped=True, reason="missing_recipient_phone")

        if not text:
            return SmsSendResult(ok=False, skipped=True, reason="empty_message")

        if not self.enabled:
            current_app.logger.info("SMS skipped because SMS_ENABLED is false. to=%s text=%s", to_number, text)
            return SmsSendResult(ok=True, skipped=True, reason="sms_disabled")

        missing_config = []
        if not self.api_key:
            missing_config.append("SOLAPI_API_KEY")
        if not self.api_secret:
            missing_config.append("SOLAPI_API_SECRET")
        if not self.from_number:
            missing_config.append("SOLAPI_FROM_NUMBER")

        if missing_config:
            reason = "missing_config:" + ",".join(missing_config)
            current_app.logger.warning("SMS skipped because config is incomplete. %s", reason)
            return SmsSendResult(ok=False, skipped=True, reason=reason)

        payload = {
            "message": {
                "from": self.from_number,
                "to": to_number,
                "text": text,
            }
        }

        response = requests.post(
            f"{self.base_url}/messages/v4/send",
            headers={
                "Authorization": self._authorization_header(),
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )

        try:
            response_data = response.json()
        except ValueError:
            response_data = {"raw": response.text}

        if response.status_code >= 400:
            raise SmsProviderError(f"SOLAPI SMS failed: {response.status_code} {response_data}")

        return SmsSendResult(ok=True, response=response_data)

    def _authorization_header(self) -> str:
        date_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        salt = secrets.token_hex(16)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            f"{date_time}{salt}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return (
            "HMAC-SHA256 "
            f"apiKey={self.api_key}, "
            f"date={date_time}, "
            f"salt={salt}, "
            f"signature={signature}"
        )


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None

    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return None

    return digits
