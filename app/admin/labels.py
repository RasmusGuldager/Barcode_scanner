from flask import render_template, request

from ..extensions import db
from ..models import Container, Item, Product
from ..services.labels import label_text, qr_svg
from . import bp


@bp.get("/labels")
def labels():
    """Choose which labels to print."""
    items = db.session.execute(
        db.select(Item).join(Item.product).where(Item.deleted_at.is_(None))
        .order_by(Product.name, Item.number)
    ).scalars().all()
    containers = db.session.execute(
        db.select(Container).order_by(Container.name)
    ).scalars().all()
    return render_template("admin/labels.html", items=items, containers=containers)


@bp.get("/labels/print")
def labels_print():
    """A sheet of stickers for the items and containers chosen on /labels."""
    item_ids = request.args.getlist("item", type=int)
    container_ids = request.args.getlist("container", type=int)
    items = db.session.execute(
        db.select(Item)
        .join(Item.product)
        .where(Item.id.in_(item_ids), Item.deleted_at.is_(None))
        .order_by(Product.name, Item.number)
    ).scalars().all()
    containers = db.session.execute(
        db.select(Container).where(Container.id.in_(container_ids)).order_by(Container.name)
    ).scalars().all()

    stickers = [
        {"qr": qr_svg(label_text(item)), "code": label_text(item), "name": item.display_name}
        for item in items
    ] + [
        {"qr": qr_svg(label_text(box)), "code": label_text(box), "name": box.name}
        for box in containers
    ]
    return render_template("admin/labels_print.html", stickers=stickers)
