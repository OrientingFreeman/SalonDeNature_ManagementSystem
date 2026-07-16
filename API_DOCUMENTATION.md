# Salon De Nature REST API

Phase14-1 adds a versioned public read API without changing the existing web AJAX endpoints under `/api/bookings`.

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/services`
- `GET /api/v1/staff`
- `GET /api/v1/availability`
- `GET /api/openapi.json`
- `GET /api/docs`

## Examples

```bash
curl https://salondenature.shop/api/v1/health
curl https://salondenature.shop/api/v1/services
curl "https://salondenature.shop/api/v1/staff?service_id=1"
curl "https://salondenature.shop/api/v1/availability?date=2026-08-01&service_id=1&staff_id=1"
```

Omit `staff_id` from the availability request to combine available start times across all active staff assigned to the service.

## Response envelope

Success:

```json
{
  "success": true,
  "data": {}
}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_DATE_FORMAT",
    "message": "date must use YYYY-MM-DD format."
  }
}
```

## Server verification

After deployment and service restart:

```bash
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/openapi.json
```

Use the actual Gunicorn bind port when it differs from `8000`. Open `/api/docs` in a browser to use Swagger UI. Swagger UI assets are loaded from jsDelivr, while the OpenAPI JSON endpoint itself has no CDN dependency.

## Tests

With the project environment activated and dependencies installed:

```bash
python -m unittest tests.test_api_v1 -v
```

## Phase14-2 customer booking API

These endpoints reuse the existing Flask customer login session. Log in through the website first, then call the API from the same browser/session. A customer ID is never accepted from the request body.

- `GET /api/v1/me/bookings?status=all&page=1&per_page=20`
- `GET /api/v1/me/bookings/<booking_id>`
- `POST /api/v1/me/bookings`
- `POST /api/v1/me/bookings/<booking_id>/cancel`
- `POST /api/v1/me/bookings/<booking_id>/reschedule`

Booking ownership is checked server-side. A missing or non-owned booking returns `404` so another customer's booking existence is not disclosed.

Create request example:

```json
{
  "service_id": 1,
  "staff_id": "any",
  "start_time": "2026-08-01T14:00"
}
```

Cancellation requires a reason. The existing cancellation SMS and BookingEvent workflow remains active:

```json
{
  "reason": "Schedule conflict"
}
```

Reschedule request example:

```json
{
  "new_start_time": "2026-08-02T15:30"
}
```

## Phase14-3 administrator API

Administrator endpoints reuse the existing Flask administrator session. Log in through `/admin/login` before using Swagger `Try it out` in the same browser.

- `GET /api/v1/admin/bookings`
- `GET /api/v1/admin/bookings/<booking_id>`
- `GET /api/v1/admin/bookings/<booking_id>/events`
- `PATCH /api/v1/admin/bookings/<booking_id>/status`
- `GET /api/v1/admin/analytics/revenue`

Status changes reuse the controlled transition service. Cancellation and no-show require a reason. Cancellation continues to trigger the existing customer and administrator cancellation SMS workflow; completion and no-show do not send automatic SMS.
