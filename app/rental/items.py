"""Browsing the inventory, and the page for a single item."""

from flask import abort, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..extensions import db
from ..models import Item
from ..services.inventory import ItemSearch, categories
from ..services.rentals import RentalError, rent_items
from . import bp


def get_item_by_code_or_404(code: str) -> Item:
    item = db.session.execute(
        db.select(Item).filter_by(code=code.upper())
    ).scalar_one_or_none()
    if item is None or item.in_trash:
        abort(404)
    return item


@bp.get("/items")
def item_list():
    search = ItemSearch(
        q=request.args.get("q", "").strip(), category=request.args.get("category", "")
    )
    return render_template(
        "rental/items.html", items=search.run(), categories=categories(), search=search
    )


@bp.get("/i/<code>")
def item_page(code: str):
    return render_template("rental/item.html", item=get_item_by_code_or_404(code))


@bp.post("/i/<code>/rent")
@login_required
def item_rent(code: str):
    item = get_item_by_code_or_404(code)
    try:
        rent_items(g.user, [item])
    except RentalError as error:
        flash(str(error), "error")
        return redirect(url_for("rental.item_page", code=item.code))
    flash(f"You have rented {item.display_name}.", "success")
    return redirect(url_for("rental.me"))
