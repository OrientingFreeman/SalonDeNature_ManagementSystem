from flask import Blueprint

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
api_docs_bp = Blueprint("api_docs", __name__, url_prefix="/api")

from api import routes  # noqa: E402,F401
from api import customer_routes  # noqa: E402,F401

from api import admin_routes  # noqa: E402,F401
