# Salon De Nature Management System Changelog

## v0.16.2 - Final Handover Data Cleanup

Added
- Safe dry-run-first `prepare_handover.py` utility for removing test customers, staff, bookings, payment records, SMS logs, notifications, schedules, time off, and linked staff profile images.
- Automatic timestamped SQLite backup before executed cleanup.
- Administrator selection and preservation while retaining services, shop settings, SMS templates, and migration state.
- Korean handover cleanup guide.

Notes
- No database migration is required.
- The cleanup must be reviewed in dry-run mode before using `--execute`.

## v0.16.1 - Internal Korean UI / Customer Bilingual UI

Added
- Korean-only navigation, labels, forms, dialogs, alerts, and operational notifications for administrator and staff pages.
- Customer navigation and PWA installation text now follow the existing English/Korean language selection.

Changed
- Customer pages continue to use English as the default language and preserve Korean switching through `lang=ko`.
- Administrator and staff sessions force the document language and shared operational UI to Korean.

Notes
- No database migration or environment variable change is required.

## v0.16.0 - Phase16 Progressive Web App

Added
- Installable PWA manifest, app icons, maskable icon, and root-scoped service worker.
- Android/Chromium install prompt and iOS Add to Home Screen guidance.
- Generic offline fallback page and PWA deployment/verification documentation.
- PWA contract tests for manifest structure, route syntax, and sensitive-cache exclusions.

Changed
- Base layout now includes mobile viewport, theme color, Apple web app metadata, manifest, and service-worker registration.
- Static same-origin assets use cache-first refresh while navigated HTML, API responses, administrator, staff, and customer booking data are not cached.

Notes
- HTTPS is required and is already present in the production deployment.
- No database migration or additional environment variable is required.
- Increment the service-worker cache version when changing precached assets.

## v0.15.3 - Phase15-A3 Automated CRM Segmentation

Added
- Mutually exclusive New, Returning, Potential VIP, VIP, Dormant, and At-risk customer segments.
- Segment reason text on CRM list and customer detail views.
- Potential VIP and At-risk CRM summary cards, filters, and operational-risk sorting.

Changed
- CRM list and detail now share one centralized segmentation policy and precedence order.
- Segments are recalculated from completed visits, completed-booking revenue, recent activity, upcoming bookings, cancellation/no-show rates, and booking restriction.

Notes
- VIP: at least five completed visits or KRW 300,000 in completed-booking revenue.
- At risk: booking restricted, no-show rate at least 20%, or cancellation rate at least 40%.
- Dormant: last completed visit more than 90 days ago with no upcoming pending/confirmed booking.
- Potential VIP: at least three completed visits, KRW 180,000 revenue, or a recent repeat customer with an upcoming booking.
- No database migration is required.

## v0.15.2 - Phase15-A2 Customer CRM Detail

Added
- CRM customer detail dashboard with live booking-derived KPIs.
- Preferred service, preferred staff, typical appointment hour, and average visit-cycle analysis.
- Operational risk classification based on cancellation, no-show, and booking restriction data.
- Administrator-only customer notes and direct navigation to each booking detail.

Changed
- Customer detail metrics now use actual booking records rather than stored aggregate counters.
- Existing profile, preference, caution, memo, and password reset workflows remain available.

Notes
- No database migration is required.
- Risk classification is an operational heuristic and not a predictive model.

## v0.15.0 - Phase15-A1 Customer CRM Portfolio

Added
- Customer CRM portfolio with booking-derived revenue, completed visits, last visit, next booking, cancellation, and no-show metrics.
- New, returning, VIP, and dormant customer segmentation without adding database columns.
- Customer search by name, phone, or email, plus segment, restriction, and sorting controls.
- Preferred completed service and staff indicators.
- CRM summary cards for customer count, returning/VIP/dormant customers, completed-booking revenue, and average customer value.

Changed
- Customer Management now recalculates operational metrics from actual booking records instead of relying on legacy stored counters.
- Existing customer creation and customer detail navigation remain available.

Notes
- VIP means at least five completed visits or at least KRW 300,000 in completed-booking revenue.
- Dormant means the last completed visit was more than 90 days ago and there is no upcoming pending or confirmed booking.
- No database migration is required.

## v0.14.3 - Phase14-4 API Operations and Security

Added
- Session API CSRF token endpoint and X-CSRF-Token enforcement for POST/PATCH requests.
- Configurable restricted CORS, in-process rate limiting, API request IDs, security headers, and structured request logging.
- API operations and security deployment documentation.

Changed
- Public and authenticated API endpoints now apply endpoint-specific request limits.
- API responses include X-Request-ID and no-store/nosniff headers.

Notes
- No database migration is required.
- The in-memory limiter is per Gunicorn worker; Nginx or Redis is recommended for strict distributed enforcement.

## v0.14.2 - Phase14-3 Administrator REST API

Added
- Session-authenticated administrator booking list, detail, BookingEvent, controlled status transition, and revenue analytics endpoints.
- Administrator filters for status, staff, service, customer, date range, and pagination.
- OpenAPI documentation for administrator APIs.

Changed
- Revenue web dashboard and REST API now share `dashboard.analytics.build_revenue_analytics`.
- Administrator status API reuses existing transition, notification, BookingEvent, and cancellation SMS workflows.

Notes
- No database migration is required.
- Administrator API authentication uses the existing Flask admin session.

## v0.14.1 - Phase14-2 Customer Booking REST API

Added
- Session-authenticated customer booking endpoints under `/api/v1/me/bookings`.
- Paginated customer-owned booking list with operational status filters.
- Customer booking detail response including chronological `BookingEvent` history.
- Customer booking creation with explicit or automatic eligible staff assignment.
- Customer cancellation API with a required reason.
- Customer rescheduling API using the existing availability rules.
- OpenAPI documentation for all Phase14-2 endpoints and request schemas.

Changed
- Customer cancellation service accepts an optional reason and records it in `BookingEvent` while preserving existing web compatibility and cancellation SMS delivery.
- API ownership checks return `404` for missing or non-owned bookings.

Notes
- Authentication reuses the existing Flask customer session; no token or database migration is introduced.
- Existing booking creation, cancellation, rescheduling, SMS, and event services are reused rather than duplicated.

## v0.14.0 - Phase14-1 REST API Foundation

Added
- Versioned public API Blueprint at `/api/v1`.
- Standard success and error JSON envelopes.
- Public health, active service, active staff, and booking availability endpoints.
- Optional staff filtering by service and availability lookup across one or all eligible staff members.
- OpenAPI 3.0 document at `/api/openapi.json` and Swagger UI at `/api/docs`.
- Basic API contract tests for health, documentation, and validation behavior.

Changed
- Existing `/api/bookings` web AJAX endpoints remain unchanged for backward compatibility.
- Public availability calls reuse the existing booking service-layer slot calculation.

Notes
- No database migration is required.
- Swagger UI assets load from jsDelivr; `/api/openapi.json` remains available without the CDN.

## v0.13.0 - Phase13 Revenue and Operations Analytics

Added
- Selected-period KPI cards for revenue, average ticket, completion conversion, cancellation rate, no-show rate, and returning-customer rate.
- Booking status, weekday, and start-time operating charts.
- Service and staff performance tables with completed counts and revenue.
- Explicit metric definitions separating completed-booking revenue from all-booking operating rates.

Changed
- Existing Revenue Dashboard expanded into a combined revenue and operating analytics workspace.
- Existing date filtering and Excel export remain available.

Notes
- No database migration is required.
- Revenue continues to use service price on completed bookings; refunds and discounts are not modeled by the current schema.

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
