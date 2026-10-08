from flask import render_template
from sqlalchemy import func

from ..extensions import db
from ..models import Container, Item, Rental, User
from . import bp


def count(stmt) -> int:
    return db.session.execute(stmt).scalar_one()


@bp.get("/")
def index():
    stats = {
        "items": count(db.select(func.count(Item.id)).where(Item.deleted_at.is_(None))),
        "rented": count(db.select(func.count(Rental.id)).where(Rental.returned_at.is_(None))),
        "containers": count(db.select(func.count(Container.id))),
        "users": count(db.select(func.count(User.id))),
        "trash": count(db.select(func.count(Item.id)).where(Item.deleted_at.is_not(None))),
    }
    return render_template("admin/index.html", stats=stats)
