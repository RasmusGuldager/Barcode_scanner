from flask import Blueprint

bp = Blueprint("rental", __name__)

from . import comments, items, renting, routes  # noqa: E402, F401
