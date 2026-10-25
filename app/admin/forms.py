from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from ..extensions import db
from ..models import CHOICE, KINDS, Category, Product, SpecField, SpecOption, slugify
from ..rental.forms import RegisterForm
from ..services.catalog import RESERVED

NO_CONTAINER = 0
NO_CATEGORY = ""
NEW_CATEGORY = "__new__"


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _blank_to_none(value):
    value = _strip(value)
    return value or None


def _unique(name: str, existing, what: str) -> None:
    """Refuse ``name`` if one of ``existing`` has it already, ignoring case."""
    for other in existing:
        if other.casefold() == name.casefold():
            raise ValidationError(f"There is already {what} called {other}.")


class ProductForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=100)],
        filters=[_strip],
        description="E.g. the model name. Copies are numbered automatically: #1, #2, ...",
    )
    # A category id, NO_CATEGORY, or NEW_CATEGORY to type one in new_category.
    category = SelectField(
        "Category", default=NO_CATEGORY, filters=[lambda value: value or NO_CATEGORY]
    )
    new_category = StringField(
        "New category", validators=[Length(max=50)], filters=[_blank_to_none]
    )
    description = TextAreaField("Description", filters=[_blank_to_none])
    length_mm = IntegerField("Length (mm)", validators=[Optional(), NumberRange(min=0)])
    width_mm = IntegerField("Width (mm)", validators=[Optional(), NumberRange(min=0)])
    height_mm = IntegerField("Height (mm)", validators=[Optional(), NumberRange(min=0)])

    def __init__(self, *args, product: Product | None = None, **kwargs):
        super().__init__(*args, obj=product, **kwargs)
        self.product = product

    def validate_name(self, field):
        others = db.select(Product.name)
        if self.product is not None:
            others = others.where(Product.id != self.product.id)
        _unique(field.data, db.session.execute(others).scalars(), "a product")

    def validate_new_category(self, field):
        if self.category.data == NEW_CATEGORY and not field.data:
            raise ValidationError("Type the name of the new category.")

    def chosen_category(self) -> Category | None:
        """The category to save. A "new" one that already exists (in any letter
        case) is reused, so categories don't get duplicated."""
        if self.category.data == NO_CATEGORY:
            return None
        if self.category.data != NEW_CATEGORY:
            return db.session.get(Category, int(self.category.data))
        for category in db.session.execute(db.select(Category)).scalars():
            if category.name.casefold() == self.new_category.data.casefold():
                return category
        category = Category(name=self.new_category.data)
        db.session.add(category)
        return category


class NewProductForm(ProductForm):
    copies = IntegerField(
        "Copies",
        default=1,
        validators=[InputRequired(), NumberRange(min=1, max=100)],
        description="How many you have. Each gets its own number, code and label.",
    )
    container_id = SelectField(
        "Container", coerce=int, default=NO_CONTAINER,
        filters=[lambda value: value or NO_CONTAINER],
    )

    def validate_copies(self, field):
        if field.data and field.data > 1 and self.container_id.data != NO_CONTAINER:
            raise ValidationError(
                "Containers are assigned one item at a time. Leave the container empty "
                "when adding several copies."
            )


class AddCopiesForm(FlaskForm):
    copies = IntegerField(
        "Copies to add", default=1, validators=[InputRequired(), NumberRange(min=1, max=100)]
    )


class ItemForm(FlaskForm):
    product_id = SelectField(
        "Product", coerce=int,
        description="Change this only to fix a mistake. The item then gets the next "
                    "number of that product, so its label must be reprinted.",
    )
    container_id = SelectField(
        "Container", coerce=int, default=NO_CONTAINER,
        filters=[lambda value: value or NO_CONTAINER],
    )


class CategoryForm(FlaskForm):
    name = StringField(
        "Name", validators=[DataRequired(), Length(max=50)], filters=[_strip]
    )

    def __init__(self, *args, category: Category | None = None, **kwargs):
        super().__init__(*args, obj=category, **kwargs)
        self.category = category

    def validate_name(self, field):
        others = db.select(Category.name)
        if self.category is not None:
            others = others.where(Category.id != self.category.id)
        _unique(field.data, db.session.execute(others).scalars(), "a category")


class SpecFieldForm(FlaskForm):
    name = StringField(
        "Name", validators=[DataRequired(), Length(max=50)], filters=[_strip],
        description="E.g. Shutter, Max frame rate, Lens mount.",
    )
    kind = SelectField("Type", choices=list(KINDS.items()), default=CHOICE)
    unit = StringField(
        "Unit", validators=[Length(max=20)], filters=[_blank_to_none],
        description="Numbers only, e.g. fps, mm, MP. Use the same unit for every product.",
    )
    options = TextAreaField(
        "Options", filters=[_strip],
        description="Choice only: one option per line, e.g. Global and Rolling.",
    )

    def __init__(self, *args, category: Category, field: SpecField | None = None, **kwargs):
        super().__init__(*args, obj=field, **kwargs)
        self.category = category
        self.field = field
        if field is not None:  # the type and options are set when creating a field
            del self.kind
            del self.options

    def validate_name(self, field):
        others = [f for f in self.category.fields if f is not self.field]
        _unique(field.data, [f.name for f in others], "a field")
        slug = slugify(field.data)
        if not slug:
            raise ValidationError("Use at least one letter or digit.")
        # The filter URL uses the slug, and slug_min / slug_max for numbers.
        # None of these may collide with another field's, or with q, category, ...
        def params(s):
            return {s, f"{s}_min", f"{s}_max"}

        taken = set().union(*(params(s) for s in RESERVED | {f.slug for f in others}))
        if params(slug) & taken:
            raise ValidationError("Too similar to another field's name. Choose another.")

    def option_labels(self) -> list[str]:
        """The options typed in, without blanks and duplicates."""
        labels: list[str] = []
        for line in self.options.data.splitlines():
            line = line.strip()
            if line and line.casefold() not in {label.casefold() for label in labels}:
                labels.append(line)
        return labels

    def validate_options(self, field):
        if self.kind.data != CHOICE:
            return
        labels = self.option_labels()
        if not labels:
            raise ValidationError("Type at least one option.")
        if too_long := [label for label in labels if len(label) > 50]:
            raise ValidationError(f"Options can be at most 50 characters: {too_long[0]}")


class OptionForm(FlaskForm):
    label = StringField(
        "Option", validators=[DataRequired(), Length(max=50)], filters=[_strip]
    )

    def __init__(self, *args, field: SpecField, option: SpecOption | None = None, **kwargs):
        super().__init__(*args, obj=option, **kwargs)
        self.field = field
        self.option = option

    def validate_label(self, label):
        others = [o.label for o in self.field.options if o is not self.option]
        _unique(label.data, others, "an option")


class ContainerForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=100)],
        filters=[_strip],
        description="Where to find it, e.g. Shelf B3, box 05.",
    )
    description = TextAreaField("Description", filters=[_blank_to_none])


class UserForm(RegisterForm):
    card_number = StringField(
        "Card number",
        validators=[DataRequired(), Regexp(r"^\d{6}$", message="A card number is 6 digits.")],
        filters=[_strip],
        description="Change this when someone gets a new AAU card.",
    )
