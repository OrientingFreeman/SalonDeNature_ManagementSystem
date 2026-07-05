"""Backward-compatible SMS table setup script.

Phase11-3 now creates both sms_logs and sms_templates.
Prefer: python create_sms_tables.py
"""

from create_sms_tables import *  # noqa
