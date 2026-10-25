from flask import flash, redirect, render_template, url_for

from ..extensions import db
from ..models import Container
from ..services.codes import new_code
from . import bp
from .forms import ContainerForm


@bp.get("/containers")
def container_list():
    containers = db.session.execute(
        db.select(Container).order_by(Container.name)
    ).scalars().all()
    return render_template("admin/containers.html", containers=containers)


@bp.route("/containers/new", methods=["GET", "POST"])
def container_new():
    form = ContainerForm()
    if form.validate_on_submit():
        container = Container(code=new_code(Container))
        form.populate_obj(container)
        db.session.add(container)
        db.session.commit()
        flash(f"Added container {container.name}.", "success")
        return redirect(url_for(".container_list"))
    return render_template("admin/container_form.html", form=form, container=None)


@bp.route("/containers/<int:container_id>/edit", methods=["GET", "POST"])
def container_edit(container_id: int):
    container = db.get_or_404(Container, container_id)
    form = ContainerForm(obj=container)
    if form.validate_on_submit():
        form.populate_obj(container)
        db.session.commit()
        flash(f"Saved container {container.name}.", "success")
        return redirect(url_for(".container_list"))
    return render_template("admin/container_form.html", form=form, container=container)


@bp.post("/containers/<int:container_id>/delete")
def container_delete(container_id: int):
    container = db.get_or_404(Container, container_id)
    name = container.name
    # The item inside (if any) is kept and simply has no container afterwards.
    db.session.delete(container)
    db.session.commit()
    flash(f"Deleted container {name}.", "success")
    return redirect(url_for(".container_list"))
