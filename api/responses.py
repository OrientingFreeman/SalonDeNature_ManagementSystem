from flask import jsonify


def success_response(data=None, *, status=200, meta=None):
    payload = {"success": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status


def error_response(code, message, *, status=400, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return jsonify({"success": False, "error": error}), status
