from flask import flash, g, redirect, render_template, url_for

from ..extensions import db
from ..models import Rental
from ..services.rentals import RentalError, force_return
from . import bp

HISTORY_LIMIT = 200


@bp.get("/rentals")
def rentals():
    out_now = db.session.execute(
        db.select(Rental).filter_by(returned_at=None).order_by(Rental.rented_at)
    ).scalars().all()
    history = db.session.execute(
        db.select(Rental)
        .where(Rental.returned_at.is_not(None))
        .order_by(Rental.returned_at.desc())
        .limit(HISTORY_LIMIT)
    ).scalars().all()
    return render_template("admin/rentals.html", out_now=out_now, history=history,
                           history_limit=HISTORY_LIMIT)


@bp.post("/rentals/<int:rental_id>/return")
def rental_force_return(rental_id: int):
    rental = db.get_or_404(Rental, rental_id)
    try:
        force_return(g.user, rental)
    except RentalError as error:
        flash(str(error), "error")
    else:
        flash(f"Marked {rental.item.display_name} as returned.", "success")
    return redirect(url_for(".rentals"))
