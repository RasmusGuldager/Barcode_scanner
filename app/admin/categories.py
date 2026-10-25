"""Categories and their spec fields, e.g. Camera: Shutter (Global / Rolling)."""

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import CHOICE, KINDS, NUMBER, Category, SpecField, SpecOption, SpecValue
from ..services.inventory import categories
from . import bp
from .forms import CategoryForm, OptionForm, SpecFieldForm


def values_using(column, value) -> int:
    """How many products have a value for this field or option."""
    return db.session.execute(
        db.select(func.count()).select_from(SpecValue).where(column == value)
    ).scalar_one()


@bp.route("/categories", methods=["GET", "POST"])
def category_list():
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category(name=form.name.data)
        db.session.add(category)
        db.session.commit()
        flash(f"Added category {category.name}. Now add its spec fields.", "success")
        return redirect(url_for(".category_edit", category_id=category.id))
    return render_template("admin/categories.html", categories=categories(), form=form)


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
def category_edit(category_id: int):
    category = db.get_or_404(Category, category_id)
    form = CategoryForm(category=category)
    if form.validate_on_submit():
        category.name = form.name.data
        db.session.commit()
        flash(f"Saved category {category.name}.", "success")
        return redirect(url_for(".category_edit", category_id=category.id))
    return render_template("admin/category_form.html", category=category, form=form,
                           kinds=KINDS)


@bp.post("/categories/<int:category_id>/delete")
def category_delete(category_id: int):
    category = db.get_or_404(Category, category_id)
    name = category.name
    # Its products are kept without a category; their spec values go with the fields.
    db.session.delete(category)
    db.session.commit()
    flash(f"Deleted category {name}.", "success")
    return redirect(url_for(".category_list"))


@bp.route("/categories/<int:category_id>/fields/new", methods=["GET", "POST"])
def field_new(category_id: int):
    category = db.get_or_404(Category, category_id)
    form = SpecFieldForm(category=category)
    if form.validate_on_submit():
        field = SpecField(
            name=form.name.data,
            kind=form.kind.data,
            unit=form.unit.data if form.kind.data == NUMBER else None,
            position=max((f.position for f in category.fields), default=0) + 1,
        )
        if field.kind == CHOICE:
            field.options = [SpecOption(label=label) for label in form.option_labels()]
        category.fields.append(field)
        db.session.commit()
        flash(f"Added the field {field.name} to {category.name}.", "success")
        return redirect(url_for(".category_edit", category_id=category.id))
    return render_template("admin/field_form.html", category=category, field=None, form=form,
                           kinds=KINDS)


@bp.route("/fields/<int:field_id>/edit", methods=["GET", "POST"])
def field_edit(field_id: int):
    field = db.get_or_404(SpecField, field_id)
    form = SpecFieldForm(category=field.category, field=field)
    if form.validate_on_submit():
        field.name = form.name.data
        if field.kind == NUMBER:
            field.unit = form.unit.data
        db.session.commit()
        flash(f"Saved the field {field.name}.", "success")
        return redirect(url_for(".category_edit", category_id=field.category_id))
    return render_template(
        "admin/field_form.html", category=field.category, field=field, form=form, kinds=KINDS,
        option_form=OptionForm(formdata=None, field=field),
        in_use=values_using(SpecValue.field_id, field.id),
        option_use={o.id: values_using(SpecValue.option_id, o.id) for o in field.options},
    )


@bp.post("/fields/<int:field_id>/move")
def field_move(field_id: int):
    """Move a field one place up or down in its category."""
    field = db.get_or_404(SpecField, field_id)
    fields = list(field.category.fields)
    index = fields.index(field)
    other = index - 1 if request.form.get("direction") == "up" else index + 1
    if 0 <= other < len(fields):
        fields[index], fields[other] = fields[other], fields[index]
        for position, f in enumerate(fields, start=1):
            f.position = position
        db.session.commit()
    return redirect(url_for(".category_edit", category_id=field.category_id))


@bp.post("/fields/<int:field_id>/delete")
def field_delete(field_id: int):
    field = db.get_or_404(SpecField, field_id)
    category_id, name = field.category_id, field.name
    db.session.delete(field)
    db.session.commit()
    flash(f"Deleted the field {name}.", "success")
    return redirect(url_for(".category_edit", category_id=category_id))


@bp.post("/fields/<int:field_id>/options")
def option_add(field_id: int):
    field = db.get_or_404(SpecField, field_id)
    form = OptionForm(field=field)
    if field.kind == CHOICE and form.validate_on_submit():
        field.options.append(SpecOption(label=form.label.data))
        db.session.commit()
        flash(f"Added the option {form.label.data}.", "success")
    else:
        flash(" ".join(form.label.errors) or "Could not add the option.", "error")
    return redirect(url_for(".field_edit", field_id=field.id))


@bp.post("/options/<int:option_id>/rename")
def option_rename(option_id: int):
    option = db.get_or_404(SpecOption, option_id)
    form = OptionForm(field=option.field, option=option)
    if form.validate_on_submit():
        option.label = form.label.data
        db.session.commit()
        flash(f"Renamed the option to {option.label}.", "success")
    else:
        flash(" ".join(form.label.errors) or "Could not rename the option.", "error")
    return redirect(url_for(".field_edit", field_id=option.field_id))


@bp.post("/options/<int:option_id>/delete")
def option_delete(option_id: int):
    option = db.get_or_404(SpecOption, option_id)
    field_id, label = option.field_id, option.label
    db.session.delete(option)
    db.session.commit()
    flash(f"Deleted the option {label}.", "success")
    return redirect(url_for(".field_edit", field_id=field_id))
