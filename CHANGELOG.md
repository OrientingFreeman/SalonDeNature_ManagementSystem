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
