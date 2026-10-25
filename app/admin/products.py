"""Products: what a kind of equipment is (category, specs, size), and its copies."""

from flask import flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Category, Item, Product
from ..services.codes import new_code
from ..services.inventory import categories, similar_products
from ..services.specs import form_values, parse_specs, save_specs
from . import bp
from .forms import NEW_CATEGORY, NO_CATEGORY, AddCopiesForm, NewProductForm, ProductForm
from .items import container_choices


def category_choices() -> list[tuple[str, str]]:
    return (
        [(NO_CATEGORY, "No category")]
        + [(str(c.id), c.name) for c in categories()]
        + [(NEW_CATEGORY, "New category...")]
    )


def selected_category(value: str | None) -> Category | None:
    """The category picked in the form's select, if it's an existing one."""
    if value and value.isdigit():
        return db.session.get(Category, int(value))
    return None


def render_form(form: ProductForm, product: Product | None, spec_errors=None):
    category = selected_category(form.category.data)
    fields = category.fields if category else []
    values = request.form if request.method == "POST" else form_values(product, fields)
    return render_template(
        "admin/product_form.html", form=form, product=product,
        category=category, fields=fields, values=values, errors=spec_errors or {},
        similar=similar_products(form.name.data or "") if product is None else [],
        copies_form=AddCopiesForm(formdata=None),
    )


def add_copies(product: Product, count: int, container_id: int | None = None) -> list[Item]:
    added = []
    for _ in range(count):
        item = Item(code=new_code(Item), product=product, container_id=container_id)
        db.session.add(item)
        db.session.flush()  # gets the next number, so the next copy sees it
        added.append(item)
    return added


def save(form: ProductForm, product: Product):
    """Validate the form and the spec inputs, and copy them into ``product``.
    Returns the spec errors (empty when saved)."""
    category = selected_category(form.category.data)
    fields = category.fields if category else []
    values, errors = parse_specs(fields, request.form)
    if errors:
        return errors
    product.category = form.chosen_category()
    product.name = form.name.data
    product.description = form.description.data
    product.length_mm = form.length_mm.data
    product.width_mm = form.width_mm.data
    product.height_mm = form.height_mm.data
    save_specs(product, fields, values)
    return {}


@bp.get("/products")
def product_list():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    stmt = db.select(Product).outerjoin(Product.category).order_by(Product.name)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Category.name == category)
    products = db.session.execute(stmt).scalars().all()
    return render_template("admin/products.html", products=products,
                           categories=categories(), q=q, category=category)


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    form = NewProductForm()
    form.category.choices = category_choices()
    form.container_id.choices = container_choices()
    spec_errors = {}
    if form.validate_on_submit():
        product = Product()
        spec_errors = save(form, product)
        if not spec_errors:
            db.session.add(product)
            added = add_copies(product, form.copies.data, form.container_id.data or None)
            db.session.commit()
            names = ", ".join(item.display_name for item in added)
            flash(f"Added {names}.", "success")
            return redirect(url_for(".product_edit", product_id=product.id))
    return render_form(form, None, spec_errors)


@bp.get("/products/similar")
def product_similar():
    """Products named like the one being typed on the new-product form (htmx)."""
    return render_template("admin/_similar.html",
                           similar=similar_products(request.args.get("name", "")))


@bp.get("/products/spec-inputs")
def product_spec_inputs():
    """The spec inputs for the category just chosen on the product form (htmx)."""
    category = selected_category(request.args.get("category"))
    product = db.session.get(Product, request.args.get("product", type=int) or 0)
    fields = category.fields if category else []
    return render_template("admin/_spec_inputs.html", category=category, fields=fields,
                           values=form_values(product, fields), errors={})


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id: int):
    product = db.get_or_404(Product, product_id)
    form = ProductForm(product=product)
    form.category.choices = category_choices()
    if request.method == "GET":
        form.category.data = str(product.category_id) if product.category_id else NO_CATEGORY
    spec_errors = {}
    if form.validate_on_submit():
        spec_errors = save(form, product)
        if not spec_errors:
            db.session.commit()
            flash(f"Saved {product.name}.", "success")
            return redirect(url_for(".product_edit", product_id=product.id))
    return render_form(form, product, spec_errors)


@bp.post("/products/<int:product_id>/copies")
def product_add_copies(product_id: int):
    product = db.get_or_404(Product, product_id)
    form = AddCopiesForm()
    if form.validate_on_submit():
        added = add_copies(product, form.copies.data)
        db.session.commit()
        flash(f"Added {', '.join(item.display_name for item in added)}.", "success")
    else:
        flash("Enter a number of copies from 1 to 100.", "error")
    return redirect(url_for(".product_edit", product_id=product.id))


@bp.post("/products/<int:product_id>/delete")
def product_delete(product_id: int):
    product = db.get_or_404(Product, product_id)
    if product.items:
        flash(f"{product.name} still has items (also counting the trash). Delete those "
              "first.", "error")
        return redirect(url_for(".product_edit", product_id=product.id))
    db.session.delete(product)
    db.session.commit()
    flash(f"Deleted {product.name}.", "success")
    return redirect(url_for(".product_list"))
