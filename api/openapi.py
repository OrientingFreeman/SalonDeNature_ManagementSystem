def build_openapi_spec():
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Salon De Nature Public API",
            "version": "1.0.0",
            "description": (
                "Phase14-1 public read API for health, services, staff, and booking availability. "
                "Existing web and internal AJAX endpoints remain unchanged."
            ),
        },
        "servers": [{"url": "/", "description": "Current server"}],
        "tags": [
            {"name": "System"},
            {"name": "Catalog"},
            {"name": "Availability"},
        ],
        "paths": {
            "/api/v1/health": {
                "get": {
                    "tags": ["System"],
                    "summary": "API health check",
                    "responses": {
                        "200": {
                            "description": "API is available",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SuccessEnvelope"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/v1/services": {
                "get": {
                    "tags": ["Catalog"],
                    "summary": "List active services",
                    "parameters": [
                        {
                            "name": "category",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Optional exact service category filter",
                        }
                    ],
                    "responses": {
                        "200": {"description": "Active service list"},
                    },
                }
            },
            "/api/v1/staff": {
                "get": {
                    "tags": ["Catalog"],
                    "summary": "List active staff",
                    "parameters": [
                        {
                            "name": "service_id",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1},
                            "description": "Only staff assigned to the service",
                        }
                    ],
                    "responses": {
                        "200": {"description": "Active staff list"},
                        "404": {"description": "Service not found"},
                    },
                }
            },
            "/api/v1/availability": {
                "get": {
                    "tags": ["Availability"],
                    "summary": "List available booking start times",
                    "parameters": [
                        {
                            "name": "date",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string", "format": "date"},
                            "example": "2026-08-01",
                        },
                        {
                            "name": "service_id",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer", "minimum": 1},
                        },
                        {
                            "name": "staff_id",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1},
                            "description": "When omitted, combines slots from all eligible active staff",
                        },
                    ],
                    "responses": {
                        "200": {"description": "Available start times"},
                        "400": {"description": "Invalid or missing query parameters"},
                        "404": {"description": "Service or staff not found"},
                        "422": {"description": "Staff cannot perform the selected service"},
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "SuccessEnvelope": {
                    "type": "object",
                    "required": ["success", "data"],
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {},
                    },
                },
                "ErrorEnvelope": {
                    "type": "object",
                    "required": ["success", "error"],
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {
                            "type": "object",
                            "required": ["code", "message"],
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                                "details": {},
                            },
                        },
                    },
                },
            }
        },
    }
