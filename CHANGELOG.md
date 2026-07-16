# Salon De Nature Management System Changelog

## v0.12.0 - Phase11-7 Customer My Booking Hub

Added
- Status-filtered My Reservations view for upcoming, completed, cancelled, and no-show bookings.
- Customer-owned reservation detail page with schedule, service, staff, price, deposit, and memo information.
- Customer-facing chronological BookingEvent history.
- Direct View details navigation from each reservation card.

Changed
- My Reservations now groups bookings by operational state while preserving existing cancellation, rescheduling, and late-notice actions.
- Reservation detail access is constrained by the authenticated customer ID.

Notes
- No database migration is required.
- Existing customer cancellation and rescheduling API ownership checks remain active.

## v0.11.9 - Phase11-6 Unified Booking Timeline

Added
- Unified administrator booking timeline combining `BookingEvent` records and booking-specific SMS logs.
- Chronological event rail with event-specific markers for status, schedule, deposit, payment, and SMS activity.
- Human-readable labels, source classification, timestamps, processing memo, SMS recipient, delivery status, and error details.
- Responsive timeline layout for desktop and mobile booking detail views.

Changed
- The separate booking event history and SMS history panels are replaced by one operational history view.
- Timeline entries are ordered oldest to newest so the full booking lifecycle reads from top to bottom.

Notes
- Existing `BookingEvent` does not contain an administrator/user foreign key, so Phase11-6 displays a factual workflow source rather than inventing a handler name.
- No database migration is required.

## v0.11.8 - Phase11-5B Controlled Admin Status Processing

Added
- Status-specific administrator actions on the booking detail page.
- Pending bookings can be confirmed or cancelled.
- Confirmed bookings can be completed, marked as no-show, or cancelled.
- Confirmation modal before each booking detail status action.
- Required cancellation and no-show reason validation in both the UI and service layer.

Changed
- Completed, no-show, and cancelled bookings no longer expose further status actions.
- BookingEvent now records the previous status, next status, and supplied processing reason.
- Timeline status processing now uses the same service-layer transition policy and reason validation.
- Existing customer and administrator cancellation SMS delivery remains active.
- Completed and no-show processing does not trigger automatic SMS.

Notes
- No new database columns or migration are required for Phase11-5B.

## v0.11.7 - Phase11-5A Admin Booking Detail Hub

Added
- Dedicated administrator booking detail page at `/admin/bookings/<booking_id>`.
- Unified booking, customer, service, staff, schedule, deposit, and memo information.
- Booking event history ordered newest first.
- Booking-specific customer and administrator SMS history, including reminder delivery status.
- Manual status management form with an operational reason/memo saved to `BookingEvent`.
- Full Details navigation from the administrator timeline booking modal.

Changed
- Manual cancellation continues to use the existing status-transition policy and customer cancellation SMS flow.
- No new database columns or migration are required for Phase11-5A.

## v0.11.6 - Phase11-4B Same-Day 9 AM Reminder Update

Changed
- Automatic reminder target changed from the next day to the booking date itself.
- Default CLI and admin manual runs now process today in the `Asia/Seoul` timezone.
- Recommended systemd timer changed to 09:00 Asia/Seoul.
- Customer and administrator default reminder wording changed from “tomorrow” to “today”.
- `create_sms_tables.py` migrates the legacy default reminder wording without overwriting unrelated template edits.

Notes
- Existing deduplication remains based on booking ID, template, recipient, and booking start datetime.
- A changed booking schedule can therefore be evaluated and reminded again for its new schedule.

## v0.11.5 - Phase11-4B Booking Reminder Scheduler

Added
- Dedicated Flask CLI reminder job: `flask --app app reminders run`.
- Optional `--date YYYY-MM-DD` processing for manual verification and recovery runs.
- Customer `booking_reminder` and admin `admin_booking_reminder` editable SMS templates.
- Admin setting toggle for one-day-before reminder notifications.
- Admin Notification Center action to run reminders manually.
- SMS reminder history fields: `scheduled_for`, `reminder_date`, and `dedupe_key`.
- Database-level unique reminder claim to prevent duplicate sends across concurrent or repeated runs.
- `REMINDER_SCHEDULER.md` with systemd timer and disabled-SMS verification instructions.

Changed
- Reminder processing targets only `confirmed` bookings on the selected date.
- Cancelled, completed, no-show, and pending bookings are excluded by the query.
- Booking schedule changes produce a new dedupe key, so the changed schedule can receive a new reminder.
- `create_sms_tables.py` now upgrades Phase11-4B columns, settings, index, and templates idempotently.

Architecture
- The production recommendation is a dedicated Flask CLI job triggered by systemd timer or cron, not an in-process APScheduler. This avoids Flask reloader and multi-worker duplicate scheduler execution.
- With `SMS_ENABLED=false`, eligible attempts are stored as `skipped`, allowing end-to-end verification without a Solapi account.


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
