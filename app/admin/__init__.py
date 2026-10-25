from flask import Blueprint

from ..auth import admin_required

bp = Blueprint("admin", __name__)


@bp.before_request
@admin_required
def require_admin():
    """Every page in this blueprint is admin-only."""


from . import (  # noqa: E402, F401
    categories, containers, data, items, labels, products, rentals, routes, users,
)
