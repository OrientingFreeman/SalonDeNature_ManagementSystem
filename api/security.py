import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, g, request, session
from werkzeug.exceptions import BadRequest, HTTPException

from api.responses import error_response

logger = logging.getLogger("salondenature.api")
_rate_buckets = defaultdict(deque)


def get_or_create_csrf_token():
    token = session.get("api_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["api_csrf_token"] = token
    return token


def require_api_csrf(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("customer_id") and not session.get("admin_logged_in"):
            return view(*args, **kwargs)
        expected = session.get("api_csrf_token")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            return error_response(
                "CSRF_TOKEN_INVALID",
                "A valid X-CSRF-Token header is required for this session-authenticated request.",
                status=403,
            )
        return view(*args, **kwargs)
    return wrapped


def rate_limit(limit=None, window_seconds=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            effective_limit = limit or current_app.config.get("API_RATE_LIMIT", 120)
            effective_window = window_seconds or current_app.config.get("API_RATE_WINDOW_SECONDS", 60)
            identity = session.get("admin_user_id") or session.get("customer_id") or request.remote_addr or "unknown"
            key = (request.endpoint, str(identity))
            now = time.monotonic()
            bucket = _rate_buckets[key]
            cutoff = now - effective_window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= effective_limit:
                retry_after = max(1, int(effective_window - (now - bucket[0])))
                response, status = error_response(
                    "RATE_LIMIT_EXCEEDED",
                    "Too many API requests. Try again later.",
                    status=429,
                    details={"retry_after_seconds": retry_after},
                )
                response.headers["Retry-After"] = str(retry_after)
                return response, status
            bucket.append(now)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def register_api_security(app):
    @app.before_request
    def api_request_context():
        if not request.path.startswith("/api/"):
            return None
        g.api_request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.api_started_at = time.monotonic()

    @app.after_request
    def api_response_headers(response):
        if not request.path.startswith("/api/"):
            return response
        response.headers["X-Request-ID"] = getattr(g, "api_request_id", uuid.uuid4().hex)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"

        origin = request.headers.get("Origin")
        allowed = current_app.config.get("API_CORS_ALLOWED_ORIGINS", [])
        if origin and origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token, X-Request-ID"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"

        started = getattr(g, "api_started_at", None)
        if started is not None:
            duration_ms = round((time.monotonic() - started) * 1000, 2)
            logger.info(
                "api_request request_id=%s method=%s path=%s status=%s duration_ms=%s remote=%s",
                response.headers.get("X-Request-ID"), request.method, request.path,
                response.status_code, duration_ms, request.remote_addr,
            )
        return response

    @app.route("/api/v1/<path:_path>", methods=["OPTIONS"])
    def api_preflight(_path):
        return "", 204

    @app.errorhandler(BadRequest)
    def api_bad_request(error):
        if request.path.startswith("/api/"):
            return error_response("INVALID_REQUEST", "The request body or syntax is invalid.", status=400)
        return error

    @app.errorhandler(404)
    def api_global_not_found(error):
        if request.path.startswith("/api/"):
            return error_response("API_ROUTE_NOT_FOUND", "The requested API route was not found.", status=404)
        return error

    @app.errorhandler(405)
    def api_global_method_not_allowed(error):
        if request.path.startswith("/api/"):
            return error_response("METHOD_NOT_ALLOWED", "This HTTP method is not allowed.", status=405)
        return error

    @app.errorhandler(Exception)
    def api_unhandled_exception(error):
        if not request.path.startswith("/api/"):
            if isinstance(error, HTTPException):
                return error
            raise error
        request_id = getattr(g, "api_request_id", None)
        logger.exception("api_unhandled_exception request_id=%s", request_id)
        return error_response(
            "INTERNAL_SERVER_ERROR",
            "An unexpected server error occurred.",
            status=500,
            details={"request_id": request_id},
        )
