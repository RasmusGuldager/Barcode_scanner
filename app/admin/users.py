from flask import flash, g, redirect, render_template, url_for
from sqlalchemy import or_

from ..extensions import db
from ..models import Rental, User
from . import bp
from .forms import UserForm


@bp.get("/users")
def user_list():
    users = db.session.execute(
        db.select(User).order_by(User.is_admin.desc(), User.email)
    ).scalars().all()
    return render_template("admin/users.html", users=users)


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
def user_edit(user_id: int):
    user = db.get_or_404(User, user_id)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        clash = db.session.execute(
            db.select(User).where(
                User.id != user.id,
                or_(User.card_number == form.card_number.data, User.email == form.email.data),
            )
        ).scalars().first()
        if clash is not None and clash.card_number == form.card_number.data:
            form.card_number.errors.append(f"This card belongs to {clash.display_name}.")
        elif clash is not None:
            form.email.errors.append(f"This email belongs to {clash.display_name}.")
        else:
            form.populate_obj(user)
            db.session.commit()
            flash(f"Saved {user.display_name}.", "success")
            return redirect(url_for(".user_list"))
    open_rentals = db.session.execute(
        db.select(Rental).filter_by(user_id=user.id, returned_at=None)
    ).scalars().all()
    return render_template("admin/user_form.html", form=form, user=user,
                           open_rentals=open_rentals)


@bp.post("/users/<int:user_id>/promote")
def user_promote(user_id: int):
    user = db.get_or_404(User, user_id)
    user.is_admin = True
    db.session.commit()
    flash(f"{user.display_name} is now an admin.", "success")
    return redirect(url_for(".user_list"))


@bp.post("/users/<int:user_id>/demote")
def user_demote(user_id: int):
    user = db.get_or_404(User, user_id)
    if user.id == g.user.id:
        # Guarantees there is always at least one admin left.
        flash("You can't remove your own admin rights. Ask another admin.", "error")
    else:
        user.is_admin = False
        db.session.commit()
        flash(f"{user.display_name} is no longer an admin.", "success")
    return redirect(url_for(".user_list"))
