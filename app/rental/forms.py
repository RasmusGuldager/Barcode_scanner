from flask_wtf import FlaskForm
from wtforms import EmailField, StringField
from wtforms.validators import DataRequired, Length, Optional, Regexp


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _normalize_email(value):
    return value.strip().lower() if isinstance(value, str) else value


def _blank_to_none(value):
    value = _strip(value)
    return value or None


class RegisterForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[
            DataRequired(),
            Length(max=254),
            Regexp(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", message="Enter a valid email address."),
        ],
        filters=[_normalize_email],
    )
    study_number = StringField(
        "Study number",
        validators=[
            DataRequired(),
            Regexp(r"^\d{8}$", message="A study number is 8 digits."),
        ],
        filters=[_strip],
        description="8 digits. Not the number on your card.",
    )
    name = StringField(
        "Name (optional)", validators=[Optional(), Length(max=100)], filters=[_blank_to_none]
    )
