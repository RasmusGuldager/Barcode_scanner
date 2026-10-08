"""Identifying with the AAU card, registering, and the user's own page."""

from flask import flash, g, redirect, render_template, request, session, url_for

from ..auth import log_in, log_out, login_required
from ..extensions import db
from ..models import Rental, User
from ..services.scanning import ScanError, normalize_card_number
from . import bp
from .forms import RegisterForm


def safe_next(target: str | None) -> str:
    """Only follow redirects within this site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("rental.me")


@bp.get("/")
def index():
    if g.user is not None:
        return redirect(url_for("rental.me"))
    return render_template("rental/index.html", next=request.args.get("next", ""))


@bp.post("/identify")
def identify():
    next_url = request.form.get("next")
    try:
        card_number = normalize_card_number(request.form.get("code", ""))
    except ScanError as error:
        flash(str(error), "error")
        return redirect(url_for("rental.index", next=next_url or None))

    user = db.session.execute(
        db.select(User).filter_by(card_number=card_number)
    ).scalar_one_or_none()
    if user is None:
        session["pending_card"] = card_number
        session["pending_next"] = next_url
        return redirect(url_for("rental.register"))

    log_in(user)
    return redirect(safe_next(next_url))


@bp.route("/register", methods=["GET", "POST"])
def register():
    card_number = session.get("pending_card")
    if card_number is None:
        return redirect(url_for("rental.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        taken = db.session.execute(
            db.select(User.id).filter_by(email=form.email.data)
        ).first()
        if taken:
            form.email.errors.append(
                "This email is already registered with another card. Ask an admin for help."
            )
        else:
            user = User(card_number=card_number)
            form.populate_obj(user)
            db.session.add(user)
            db.session.commit()
            next_url = session.get("pending_next")
            log_in(user)  # also clears the pending card
            flash("Your profile is created.", "success")
            return redirect(safe_next(next_url))
    return render_template("rental/register.html", form=form, card_number=card_number)


@bp.post("/logout")
def logout():
    log_out()
    flash("You are signed out.", "success")
    return redirect(url_for("rental.index"))


@bp.get("/me")
@login_required
def me():
    open_rentals = db.session.execute(
        db.select(Rental)
        .filter_by(user_id=g.user.id, returned_at=None)
        .order_by(Rental.rented_at)
    ).scalars().all()
    recent = db.session.execute(
        db.select(Rental)
        .filter(Rental.user_id == g.user.id, Rental.returned_at.is_not(None))
        .order_by(Rental.returned_at.desc())
        .limit(10)
    ).scalars().all()
    return render_template("rental/me.html", open_rentals=open_rentals, recent=recent)
