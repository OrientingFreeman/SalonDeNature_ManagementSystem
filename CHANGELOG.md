
## v0.11.4 - Phase11-4A Admin SMS Notifications

Added
- Admin SMS recipient settings in Shop Settings.
- Event-level admin SMS toggles for booking created, booking updated, booking cancelled, deposit requested, and deposit confirmed.
- Admin-only SMS templates: `admin_booking_created`, `admin_booking_changed`, `admin_booking_cancelled`, `admin_deposit_request`, `admin_deposit_paid`.
- SMS log recipient classification via `recipient_type` and `template_key`.

Changed
- Booking SMS service now sends both customer SMS and configured admin SMS for booking/deposit events.
- Default customer SMS templates are now English for newly seeded templates.
- SMS log table in Notification Center now shows recipient type and template key.
- `create_sms_tables.py` now performs idempotent SQLite column updates for Phase11-4A.

Notes
- Existing edited customer templates in the database are not overwritten. Admin templates are inserted when `python create_sms_tables.py` runs.
- Real SMS is still controlled by `SMS_ENABLED`; with `SMS_ENABLED=false`, logs are created as skipped.
# Salon De Nature Management System Changelog

## v0.11.3 - Phase11-3 SMS Template Manager

### Added
- SMS template database model (`SmsTemplate`).
- Default SMS templates for:
  - booking created
  - booking changed
  - booking cancelled
  - deposit request
  - deposit paid
- SMS template renderer with placeholder replacement.
- Admin SMS Template Manager page at `/admin/sms-templates`.
- Template enable/disable switch.
- Template preview using sample booking data.
- Placeholder chips for inserting supported variables.
- `create_sms_tables.py` setup script for SMS logs and templates.

### Changed
- SMS sending service now renders messages from DB templates instead of hard-coded functions.
- `create_sms_logs_table.py` remains as a backward-compatible wrapper.
- Admin Notification Center links to SMS Template Manager.

### Notes
- Run `python create_sms_tables.py` once after deployment.
- Existing templates are not overwritten by default sync.
- `SMS_ENABLED=false` still prevents real outbound Solapi sends while logging skipped attempts.
