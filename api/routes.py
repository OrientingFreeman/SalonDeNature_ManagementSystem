from datetime import datetime, timezone

from flask import Response, jsonify, request

from api import api_docs_bp, api_v1_bp
from api.openapi import build_openapi_spec
from api.responses import error_response, success_response
from api.security import get_or_create_csrf_token, rate_limit
from bookings.models import Service, StaffService
from bookings.services import get_available_slots, get_available_slots_any_staff
from staff.models import Staff


def _positive_int_arg(name):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return None, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, error_response(
            "INVALID_QUERY_PARAMETER",
            f"{name} must be a positive integer.",
            status=400,
            details={"parameter": name},
        )
    if value <= 0:
        return None, error_response(
            "INVALID_QUERY_PARAMETER",
            f"{name} must be a positive integer.",
            status=400,
            details={"parameter": name},
        )
    return value, None


def _service_payload(service):
    return {
        "id": service.id,
        "category": service.category,
        "name_ko": service.name_ko,
        "name_en": service.name_en,
        "duration_minutes": service.duration_minutes,
        "price": service.price,
        "deposit_required": bool(service.deposit_required),
        "deposit_amount": service.deposit_amount or 0,
    }


def _staff_payload(staff):
    return {
        "id": staff.id,
        "name": staff.name,
        "position": staff.position,
        "introduction": staff.introduction,
        "specialties": staff.specialties,
        "career_years": staff.career_years,
        "profile_image": staff.profile_image,
        "display_order": staff.display_order or 0,
    }


@api_v1_bp.get("/health")
@rate_limit(limit=60, window_seconds=60)
def health():
    return success_response({
        "status": "ok",
        "api_version": "v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@api_v1_bp.get("/csrf-token")
@rate_limit(limit=30, window_seconds=60)
def csrf_token():
    return success_response({"csrf_token": get_or_create_csrf_token()})


@api_v1_bp.get("/services")
@rate_limit()
def list_services():
    category = (request.args.get("category") or "").strip()
    query = Service.query.filter_by(is_active=True)
    if category:
        query = query.filter(Service.category == category)
    services = query.order_by(Service.category.asc(), Service.id.asc()).all()
    return success_response([_service_payload(service) for service in services])


@api_v1_bp.get("/staff")
@rate_limit()
def list_staff():
    service_id, invalid = _positive_int_arg("service_id")
    if invalid:
        return invalid

    query = Staff.query.filter_by(is_active=True)
    if service_id is not None:
        service = Service.query.filter_by(id=service_id, is_active=True).first()
        if not service:
            return error_response(
                "SERVICE_NOT_FOUND",
                "The requested active service was not found.",
                status=404,
            )
        query = query.join(StaffService, StaffService.staff_id == Staff.id).filter(
            StaffService.service_id == service_id
        )

    staff_members = query.order_by(Staff.display_order.asc(), Staff.id.asc()).all()
    return success_response([_staff_payload(staff) for staff in staff_members])


@api_v1_bp.get("/availability")
@rate_limit(limit=60, window_seconds=60)
def availability():
    date_raw = (request.args.get("date") or "").strip()
    service_id, invalid = _positive_int_arg("service_id")
    if invalid:
        return invalid
    staff_id, invalid = _positive_int_arg("staff_id")
    if invalid:
        return invalid

    missing = []
    if not date_raw:
        missing.append("date")
    if service_id is None:
        missing.append("service_id")
    if missing:
        return error_response(
            "MISSING_REQUIRED_QUERY_PARAMETERS",
            "Required query parameters are missing.",
            status=400,
            details={"parameters": missing},
        )

    try:
        target_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError:
        return error_response(
            "INVALID_DATE_FORMAT",
            "date must use YYYY-MM-DD format.",
            status=400,
            details={"parameter": "date"},
        )

    service = Service.query.filter_by(id=service_id, is_active=True).first()
    if not service:
        return error_response(
            "SERVICE_NOT_FOUND",
            "The requested active service was not found.",
            status=404,
        )

    if staff_id is not None:
        staff = Staff.query.filter_by(id=staff_id, is_active=True).first()
        if not staff:
            return error_response(
                "STAFF_NOT_FOUND",
                "The requested active staff member was not found.",
                status=404,
            )
        result = get_available_slots(
            staff_id=staff_id,
            service_id=service_id,
            target_date=target_date,
        )
    else:
        result = get_available_slots_any_staff(
            service_id=service_id,
            target_date=target_date,
        )

    if not result.get("ok"):
        code = result.get("error", "AVAILABILITY_LOOKUP_FAILED")
        status = 422 if code == "STAFF_CANNOT_DO_SERVICE" else 400
        return error_response(
            code,
            result.get("message", "Availability could not be calculated."),
            status=status,
        )

    slots = result.get("available_slots", [])
    return success_response({
        "date": target_date.isoformat(),
        "service_id": service_id,
        "staff_id": staff_id,
        "available_slots": slots,
        "slot_count": len(slots),
    })


@api_docs_bp.get("/openapi.json")
def openapi_json():
    return jsonify(build_openapi_spec())


@api_docs_bp.get("/docs")
def swagger_docs():
    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Salon De Nature API Docs</title>
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css\">
</head>
<body>
  <div id=\"swagger-ui\"></div>
  <script src=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
  <script>
    window.onload = function () {
      SwaggerUIBundle({
        url: '/api/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        displayRequestDuration: true,
        tryItOutEnabled: true
      });
    };
  </script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@api_v1_bp.errorhandler(404)
def api_not_found(_error):
    return error_response("API_ROUTE_NOT_FOUND", "The requested API route was not found.", status=404)


@api_v1_bp.errorhandler(405)
def api_method_not_allowed(_error):
    return error_response("METHOD_NOT_ALLOWED", "This HTTP method is not allowed.", status=405)
