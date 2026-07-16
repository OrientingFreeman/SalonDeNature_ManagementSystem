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
