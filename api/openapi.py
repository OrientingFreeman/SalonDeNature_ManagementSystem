def _error_response(description):
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
            }
        },
    }


def build_openapi_spec():
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Salon De Nature API",
            "version": "1.3.0",
            "description": (
                "Phase14-4 API with session authentication, CSRF protection, restricted CORS, rate limits, and request tracing."
            ),
        },
        "servers": [{"url": "/", "description": "Current server"}],
        "tags": [
            {"name": "System"},
            {"name": "Catalog"},
            {"name": "Availability"},
            {"name": "Customer bookings"},
            {"name": "Administrator bookings"},
            {"name": "Administrator analytics"},
        ],
        "paths": {
            "/api/v1/csrf-token": {
                "get": {
                    "tags": ["System"],
                    "summary": "Issue or return the session CSRF token",
                    "description": "Call this in the authenticated browser session, then send the value in X-CSRF-Token for POST and PATCH requests.",
                    "responses": {"200": {"description": "CSRF token"}, "429": _error_response("Rate limit exceeded")},
                }
            },
            "/api/v1/health": {
                "get": {
                    "tags": ["System"],
                    "summary": "API health check",
                    "responses": {"200": {"description": "API is available"}},
                }
            },
            "/api/v1/services": {
                "get": {
                    "tags": ["Catalog"],
                    "summary": "List active services",
                    "parameters": [{
                        "name": "category", "in": "query", "required": False,
                        "schema": {"type": "string"},
                    }],
                    "responses": {"200": {"description": "Active service list"}},
                }
            },
            "/api/v1/staff": {
                "get": {
                    "tags": ["Catalog"],
                    "summary": "List active staff",
                    "parameters": [{
                        "name": "service_id", "in": "query", "required": False,
                        "schema": {"type": "integer", "minimum": 1},
                    }],
                    "responses": {
                        "200": {"description": "Active staff list"},
                        "404": _error_response("Service not found"),
                    },
                }
            },
            "/api/v1/availability": {
                "get": {
                    "tags": ["Availability"],
                    "summary": "List available booking start times",
                    "parameters": [
                        {"name": "date", "in": "query", "required": True, "schema": {"type": "string", "format": "date"}},
                        {"name": "service_id", "in": "query", "required": True, "schema": {"type": "integer", "minimum": 1}},
                        {"name": "staff_id", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1}},
                    ],
                    "responses": {
                        "200": {"description": "Available start times"},
                        "400": _error_response("Invalid query parameters"),
                        "404": _error_response("Service or staff not found"),
                        "422": _error_response("Staff cannot perform the service"),
                    },
                }
            },
            "/api/v1/admin/bookings": {
                "get": {
                    "tags": ["Administrator bookings"],
                    "summary": "List bookings with filters and pagination",
                    "description": "Uses the existing Flask administrator login session cookie.",
                    "parameters": [
                        {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["pending", "confirmed", "completed", "cancelled", "no_show"]}},
                        {"name": "staff_id", "in": "query", "schema": {"type": "integer", "minimum": 1}},
                        {"name": "service_id", "in": "query", "schema": {"type": "integer", "minimum": 1}},
                        {"name": "customer_id", "in": "query", "schema": {"type": "integer", "minimum": 1}},
                        {"name": "date_from", "in": "query", "schema": {"type": "string", "format": "date"}},
                        {"name": "date_to", "in": "query", "schema": {"type": "string", "format": "date"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "minimum": 1, "default": 1}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}
                    ],
                    "responses": {"200": {"description": "Paginated booking list"}, "401": _error_response("Administrator login required")}
                }
            },
            "/api/v1/admin/bookings/{booking_id}": {
                "get": {
                    "tags": ["Administrator bookings"], "summary": "Get booking detail and event history",
                    "parameters": [{"$ref": "#/components/parameters/BookingId"}],
                    "responses": {"200": {"description": "Booking detail"}, "401": _error_response("Administrator login required"), "404": _error_response("Booking not found")}
                }
            },
            "/api/v1/admin/bookings/{booking_id}/events": {
                "get": {
                    "tags": ["Administrator bookings"], "summary": "List booking events",
                    "parameters": [{"$ref": "#/components/parameters/BookingId"}],
                    "responses": {"200": {"description": "Chronological BookingEvent list"}, "401": _error_response("Administrator login required"), "404": _error_response("Booking not found")}
                }
            },
            "/api/v1/admin/bookings/{booking_id}/status": {
                "patch": {
                    "tags": ["Administrator bookings"], "summary": "Apply a controlled booking status transition",
                    "parameters": [{"$ref": "#/components/parameters/BookingId"}, {"$ref": "#/components/parameters/CsrfToken"}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AdminStatusRequest"}}}},
                    "responses": {"200": {"description": "Status changed using existing event, notification, and cancellation SMS workflow"}, "401": _error_response("Administrator login required"), "404": _error_response("Booking not found"), "409": _error_response("Invalid status transition"), "422": _error_response("Cancellation or no-show reason required")}
                }
            },
            "/api/v1/admin/analytics/revenue": {
                "get": {
                    "tags": ["Administrator analytics"], "summary": "Get revenue and operations analytics",
                    "parameters": [{"name": "start_date", "in": "query", "schema": {"type": "string", "format": "date"}}, {"name": "end_date", "in": "query", "schema": {"type": "string", "format": "date"}}],
                    "responses": {"200": {"description": "Revenue, conversion, cancellation, no-show, customer, staff, service, weekday, and hourly metrics"}, "400": _error_response("Invalid date format"), "401": _error_response("Administrator login required")}
                }
            },
            "/api/v1/me/bookings": {
                "get": {
                    "tags": ["Customer bookings"],
                    "summary": "List the authenticated customer's bookings",
                    "description": "Uses the existing Flask customer login session cookie.",
                    "parameters": [
                        {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["all", "upcoming", "completed", "closed"], "default": "all"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "minimum": 1, "default": 1}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}},
                    ],
                    "responses": {
                        "200": {"description": "Paginated booking list"},
                        "401": _error_response("Customer login required"),
                    },
                },
                "post": {
                    "tags": ["Customer bookings"],
                    "summary": "Create a booking for the authenticated customer",
                    "parameters": [{"$ref": "#/components/parameters/CsrfToken"}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CreateBookingRequest"}}},
                    },
                    "responses": {
                        "201": {"description": "Booking created"},
                        "401": _error_response("Customer login required"),
                        "409": _error_response("Selected time is unavailable"),
                        "422": _error_response("Validation or booking policy failure"),
                    },
                },
            },
            "/api/v1/me/bookings/{booking_id}": {
                "get": {
                    "tags": ["Customer bookings"],
                    "summary": "Get an owned booking and its event history",
                    "parameters": [{"$ref": "#/components/parameters/BookingId"}],
                    "responses": {
                        "200": {"description": "Owned booking detail"},
                        "401": _error_response("Customer login required"),
                        "404": _error_response("Booking not found or not owned by the customer"),
                    },
                }
            },
            "/api/v1/me/bookings/{booking_id}/cancel": {
                "post": {
                    "tags": ["Customer bookings"],
                    "summary": "Cancel an owned booking",
                    "parameters": [{"$ref": "#/components/parameters/BookingId"}, {"$ref": "#/components/parameters/CsrfToken"}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CancelBookingRequest"}}},
                    },
                    "responses": {
                        "200": {"description": "Booking cancelled; existing SMS and event workflow is used"},
                        "401": _error_response("Customer login required"),
                        "404": _error_response("Booking not found or not owned by the customer"),
                        "409": _error_response("Booking status cannot be cancelled"),
                        "422": _error_response("Reason missing or same-day cancellation blocked"),
                    },
                }
            },
            "/api/v1/me/bookings/{booking_id}/reschedule": {
                "post": {
                    "tags": ["Customer bookings"],
                    "summary": "Reschedule an owned booking",
                    "parameters": [{"$ref": "#/components/parameters/BookingId"}, {"$ref": "#/components/parameters/CsrfToken"}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RescheduleBookingRequest"}}},
                    },
                    "responses": {
                        "200": {"description": "Booking rescheduled; existing SMS and event workflow is used"},
                        "401": _error_response("Customer login required"),
                        "404": _error_response("Booking not found or not owned by the customer"),
                        "409": _error_response("New time unavailable or booking cannot be changed"),
                        "422": _error_response("Validation or same-day rescheduling failure"),
                    },
                }
            },
        },
        "components": {
            "parameters": {
                "BookingId": {
                    "name": "booking_id", "in": "path", "required": True,
                    "schema": {"type": "integer", "minimum": 1},
                },
                "CsrfToken": {
                    "name": "X-CSRF-Token", "in": "header", "required": True,
                    "schema": {"type": "string"},
                    "description": "Token returned by GET /api/v1/csrf-token in the same Flask session."
                }
            },
            "schemas": {
                "SuccessEnvelope": {
                    "type": "object", "required": ["success", "data"],
                    "properties": {"success": {"type": "boolean", "example": True}, "data": {}},
                },
                "ErrorEnvelope": {
                    "type": "object", "required": ["success", "error"],
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {
                            "type": "object", "required": ["code", "message"],
                            "properties": {"code": {"type": "string"}, "message": {"type": "string"}, "details": {}},
                        },
                    },
                },
                "CreateBookingRequest": {
                    "type": "object", "required": ["service_id", "start_time"],
                    "properties": {
                        "service_id": {"type": "integer", "minimum": 1},
                        "staff_id": {"oneOf": [{"type": "integer", "minimum": 1}, {"type": "string", "enum": ["any"]}], "default": "any"},
                        "start_time": {"type": "string", "example": "2026-08-01T14:00"},
                    },
                },
                "CancelBookingRequest": {
                    "type": "object", "required": ["reason"],
                    "properties": {"reason": {"type": "string", "minLength": 1}},
                },
                "AdminStatusRequest": {
                    "type": "object", "required": ["status"],
                    "properties": {"status": {"type": "string", "enum": ["confirmed", "completed", "cancelled", "no_show"]}, "reason": {"type": "string"}},
                },
                "RescheduleBookingRequest": {
                    "type": "object", "required": ["new_start_time"],
                    "properties": {"new_start_time": {"type": "string", "example": "2026-08-02T15:30"}},
                },
            },
        },
    }
