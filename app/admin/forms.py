from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from ..rental.forms import RegisterForm

NO_CONTAINER = 0


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _blank_to_none(value):
    value = _strip(value)
    return value or None


class ItemForm(FlaskForm):
    name = StringField(
        "Name", validators=[DataRequired(), Length(max=100)], filters=[_strip]
    )
    number = IntegerField(
        "Number",
        validators=[Optional(), NumberRange(min=0)],
        description="Tells identical items apart, e.g. 5 for Basler ace #5.",
    )
    category = StringField(
        "Category", validators=[Optional(), Length(max=50)], filters=[_blank_to_none]
    )
    description = TextAreaField("Description", filters=[_blank_to_none])
    container_id = SelectField("Container", coerce=int, default=NO_CONTAINER)
    length_mm = IntegerField("Length (mm)", validators=[Optional(), NumberRange(min=0)])
    width_mm = IntegerField("Width (mm)", validators=[Optional(), NumberRange(min=0)])
    height_mm = IntegerField("Height (mm)", validators=[Optional(), NumberRange(min=0)])


class NewItemForm(ItemForm):
    copies = IntegerField(
        "Copies",
        default=1,
        validators=[DataRequired(), NumberRange(min=1, max=100)],
        description=(
            "Add several identical items at once. They are numbered from the number "
            "above (or from 1), and each gets its own code and label."
        ),
    )

    def validate_copies(self, field):
        if field.data and field.data > 1 and self.container_id.data != NO_CONTAINER:
            raise ValidationError(
                "Containers are assigned one item at a time. Leave the container empty "
                "when adding several copies."
            )


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
