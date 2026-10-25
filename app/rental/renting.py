"""The scan pages for renting and returning.

Both pages keep the camera running and send each scan with htmx; the server
answers with the updated part of the page. Progress is kept in the session:
the list of items to rent, and the item waiting for its container scan.
"""

from flask import flash, g, redirect, render_template, request, session, url_for

from ..auth import login_required
from ..extensions import db
from ..models import Container, Item
from ..services.rentals import (
    RentalError,
    check_rentable,
    open_rental_for,
    rent_items,
    return_item,
)
from ..services.scanning import ScanError, find_item, find_label
from . import bp


def scanned_text() -> str:
    return request.form.get("code", "")


# Renting


def basket() -> list[Item]:
    ids = session.get("basket", [])
    items = [db.session.get(Item, item_id) for item_id in ids]
    return [item for item in items if item is not None and not item.in_trash]


def render_basket(message: str | None = None, category: str = "success"):
    template = "rental/_basket.html" if request.headers.get("HX-Request") else "rental/rent.html"
    return render_template(template, basket=basket(), message=message, category=category)


@bp.get("/rent")
@login_required
def rent():
    return render_basket()


@bp.post("/rent/scan")
@login_required
def rent_scan():
    in_basket = session.get("basket", [])
    try:
        item = find_item(scanned_text())
        if item.id in in_basket:
            return render_basket(f"{item.display_name} is already in the list.", "info")
        check_rentable(item)
    except (ScanError, RentalError) as error:
        return render_basket(str(error), "error")
    session["basket"] = in_basket + [item.id]
    return render_basket(f"Added {item.display_name}.")


@bp.post("/rent/remove/<int:item_id>")
@login_required
def rent_remove(item_id: int):
    session["basket"] = [i for i in session.get("basket", []) if i != item_id]
    return render_basket()


@bp.post("/rent/confirm")
@login_required
def rent_confirm():
    items = basket()
    try:
        rent_items(g.user, items)
    except RentalError as error:
        flash(str(error), "error")
        return redirect(url_for("rental.rent"))
    session.pop("basket", None)
    names = ", ".join(item.display_name for item in items)
    flash(f"You have rented {names}.", "success")
    return redirect(url_for("rental.me"))


# Returning


def pending_return() -> Item | None:
    """The item that was scanned and now waits for its container scan."""
    item_id = session.get("return_item")
    return db.session.get(Item, item_id) if item_id is not None else None


def render_return(message: str | None = None, category: str = "success",
                  returned: Item | None = None):
    """The return page; ``returned`` is the item just returned, to offer a note."""
    template = "rental/_return.html" if request.headers.get("HX-Request") else "rental/return.html"
    still_rented = [r for r in g.user.rentals if r.returned_at is None]
    return render_template(template, pending=pending_return(), still_rented=still_rented,
                           message=message, category=category, returned=returned)


@bp.get("/return")
@login_required
def return_():
    return render_return()


@bp.post("/return/scan")
@login_required
def return_scan():
    try:
        found = find_label(scanned_text())
        if isinstance(found, Item):
            return scan_item_to_return(found)
        return scan_container(found)
    except (ScanError, RentalError) as error:
        return render_return(str(error), "error")


def scan_item_to_return(item: Item):
    open_rental_for(g.user, item)  # raises if it isn't this user's to return
    if item.container is None:
        session.pop("return_item", None)
        return_item(g.user, item, None)
        return render_return(f"Returned {item.display_name}.", returned=item)
    session["return_item"] = item.id
    return render_return()


def scan_container(container: Container):
    item = pending_return()
    if item is None:
        raise RentalError("Scan the item first, then the container it goes in.")
    try:
        return_item(g.user, item, container)
    except RentalError:
        if item.open_rental is None or item.open_rental.user_id != g.user.id:
            session.pop("return_item", None)  # returned some other way meanwhile
        raise
    session.pop("return_item", None)
    return render_return(f"Returned {item.display_name} to {container.name}.", returned=item)


@bp.post("/return/cancel")
@login_required
def return_cancel():
    session.pop("return_item", None)
    return render_return()
