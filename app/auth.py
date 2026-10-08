"""Who is using the app right now.

Everyone, admins included, is identified by scanning their card. The user id is
kept in the session cookie, and loaded into ``g.user`` on every request.
"""

from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from .extensions import db
from .models import User


def load_current_user() -> None:
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id is not None else None


def log_in(user: User) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user.id


def log_out() -> None:
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("rental.index", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("rental.index", next=request.path))
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
