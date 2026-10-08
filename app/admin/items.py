from datetime import UTC, datetime

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from ..extensions import db
from ..models import Container, Item
from ..services.codes import new_code
from ..services.inventory import ItemSearch, categories
from . import bp
from .forms import NO_CONTAINER, ItemForm, NewItemForm

def get_item_or_404(item_id: int, in_trash: bool = False) -> Item:
    item = db.get_or_404(Item, item_id)
    if item.in_trash != in_trash:
        abort(404)
    return item


def container_choices(item: Item | None = None) -> list[tuple[int, str]]:
    """Empty containers, plus the one ``item`` is already in."""
    stmt = db.select(Container).outerjoin(Container.item).order_by(Container.name)
    if item is not None and item.container_id is not None:
        stmt = stmt.where(or_(Item.id.is_(None), Item.id == item.id))
    else:
        stmt = stmt.where(Item.id.is_(None))
    containers = db.session.execute(stmt).scalars()
    return [(NO_CONTAINER, "No container")] + [(c.id, c.name) for c in containers]


def apply_form(form: ItemForm, item: Item) -> None:
    item.name = form.name.data
    item.number = form.number.data
    item.category = form.category.data
    item.description = form.description.data
    item.container_id = form.container_id.data or None
    item.length_mm = form.length_mm.data
    item.width_mm = form.width_mm.data
    item.height_mm = form.height_mm.data


@bp.get("/items")
def item_list():
    search = ItemSearch.from_request(request)
    return render_template(
        "admin/items.html", items=search.run(), categories=categories(), search=search
    )


@bp.route("/items/new", methods=["GET", "POST"])
def item_new():
    form = NewItemForm()
    form.container_id.choices = container_choices()
    if form.validate_on_submit():
        copies = form.copies.data
        start = form.number.data
        if copies > 1 and start is None:
            start = 1
        for i in range(copies):
            item = Item(code=new_code(Item))
            apply_form(form, item)
            if start is not None:
                item.number = start + i
            db.session.add(item)
        db.session.commit()
        flash(f"Added {copies} item{'s' if copies > 1 else ''}.", "success")
        return redirect(url_for(".item_list"))
    return render_template("admin/item_form.html", form=form, item=None,
                           categories=categories())


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
def item_edit(item_id: int):
    item = get_item_or_404(item_id)
    form = ItemForm(obj=item)
    form.container_id.choices = container_choices(item)
    if request.method == "GET":
        form.container_id.data = item.container_id or NO_CONTAINER
    if form.validate_on_submit():
        apply_form(form, item)
        db.session.commit()
        flash(f"Saved {item.display_name}.", "success")
        return redirect(url_for(".item_list"))
    return render_template("admin/item_form.html", form=form, item=item,
                           categories=categories())


@bp.post("/items/<int:item_id>/trash")
def item_trash(item_id: int):
    item = get_item_or_404(item_id)
    if item.open_rental is not None:
        flash(f"{item.display_name} is rented out. It must be returned before it can "
              "be moved to the trash.", "error")
        return redirect(url_for(".item_edit", item_id=item.id))
    item.deleted_at = datetime.now(UTC)
    db.session.commit()
    flash(f"Moved {item.display_name} to the trash.", "success")
    return redirect(url_for(".item_list"))


@bp.get("/trash")
def trash():
    items = db.session.execute(
        db.select(Item).where(Item.deleted_at.is_not(None)).order_by(Item.deleted_at.desc())
    ).scalars().all()
    return render_template("admin/trash.html", items=items)


@bp.post("/trash/<int:item_id>/restore")
def item_restore(item_id: int):
    item = get_item_or_404(item_id, in_trash=True)
    item.deleted_at = None
    db.session.commit()
    flash(f"Restored {item.display_name}.", "success")
    return redirect(url_for(".trash"))


@bp.post("/trash/<int:item_id>/delete")
def item_delete(item_id: int):
    item = get_item_or_404(item_id, in_trash=True)
    name = item.display_name
    db.session.delete(item)
    db.session.commit()
    flash(f"Deleted {name} permanently, including its rental history and comments.",
          "success")
    return redirect(url_for(".trash"))
