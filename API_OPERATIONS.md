# API Operations and Security

## Session authentication and CSRF
Customer and administrator APIs reuse the existing Flask login session. Before any POST or PATCH request, call `GET /api/v1/csrf-token` in the same session and send the returned value in `X-CSRF-Token`.

## CORS
Cross-origin credentialed access is denied unless the exact origin is listed in `API_CORS_ALLOWED_ORIGINS` as a comma-separated environment variable. Same-origin browser requests require no CORS configuration.

## Rate limiting
Defaults are 120 requests per 60 seconds per endpoint and session/IP. Mutation endpoints use 30 per minute and availability uses 60 per minute. Configure with `API_RATE_LIMIT` and `API_RATE_WINDOW_SECONDS`.

The limiter is in process memory. With multiple Gunicorn workers, each worker maintains its own bucket. For strict distributed enforcement, use Nginx rate limiting or a Redis-backed limiter later.

## Request tracing
Every API response includes `X-Request-ID`. Requests are logged with request ID, method, path, status, duration and remote address. Clients may supply their own `X-Request-ID`.

## Verification
```bash
curl -i https://salondenature.shop/api/v1/health
curl -i -c cookies.txt https://salondenature.shop/api/v1/csrf-token
```
