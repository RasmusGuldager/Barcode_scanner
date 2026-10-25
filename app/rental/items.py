"""Browsing the inventory, and the page for a single item."""

from flask import abort, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..extensions import db
from ..models import Item, Product
from ..services.catalog import ProductSearch
from ..services.inventory import categories
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
    """Products, filtered by category, availability and specs."""
    search = ProductSearch.from_args(request.args)
    rows, unknown = search.run()
    return render_template("rental/items.html", rows=rows, unknown=unknown,
                           search=search, categories=categories())


@bp.get("/products/<int:product_id>")
def product_page(product_id: int):
    product = db.get_or_404(Product, product_id)
    if not product.active_items:
        abort(404)
    return render_template("rental/product.html", product=product)


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
