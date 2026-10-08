from flask import Blueprint

from ..auth import admin_required

bp = Blueprint("admin", __name__)


@bp.before_request
@admin_required
def require_admin():
    """Every page in this blueprint is admin-only."""


from . import containers, data, items, labels, rentals, routes, users  # noqa: E402, F401
