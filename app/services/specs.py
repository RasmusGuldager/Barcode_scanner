"""Spec values of products: reading them from the product form and saving them.

The form has one input per spec field of the product's category, named
``spec-<field id>``. An empty input means the value is unknown.
"""

from ..models import CHOICE, NUMBER, TEXT, Product, SpecField, SpecOption, SpecValue

TEXT_MAX = 200

# What a field holds once parsed: an option, a number, a text, or None (unknown).
Value = SpecOption | float | str | None


def input_name(field: SpecField) -> str:
    return f"spec-{field.id}"


def parse_number(raw: str) -> float:
    """A number as typed, also with a decimal comma ("12,5"). Raises ValueError."""
    number = float(raw.replace(",", "."))
    if number != number or number in (float("inf"), float("-inf")):  # NaN, inf
        raise ValueError(raw)
    return number


def parse_specs(fields: list[SpecField], form) -> tuple[dict[int, Value], dict[int, str]]:
    """Read the spec inputs. Returns the values and the errors, both by field id."""
    values: dict[int, Value] = {}
    errors: dict[int, str] = {}
    for field in fields:
        raw = (form.get(input_name(field)) or "").strip()
        if not raw:
            values[field.id] = None
        elif field.kind == CHOICE:
            option = next((o for o in field.options if str(o.id) == raw), None)
            if option is None:
                errors[field.id] = "Not one of the options."
            values[field.id] = option
        elif field.kind == NUMBER:
            try:
                values[field.id] = parse_number(raw)
            except ValueError:
                errors[field.id] = "Enter a number, e.g. 60 or 12.5."
        else:
            if len(raw) > TEXT_MAX:
                errors[field.id] = f"At most {TEXT_MAX} characters."
            values[field.id] = raw
    return values, errors


def form_values(product: Product | None, fields: list[SpecField]) -> dict[str, str]:
    """The product's current values as the inputs show them, by input name (like
    the submitted form)."""
    values = {}
    for field in fields:
        spec = product.spec(field) if product else None
        if spec is None:
            value = ""
        elif field.kind == CHOICE:
            value = str(spec.option_id or "")
        elif field.kind == NUMBER:
            value = f"{spec.number:g}" if spec.number is not None else ""
        else:
            value = spec.text or ""
        values[input_name(field)] = value
    return values


def set_spec(product: Product, field: SpecField, value: Value) -> None:
    """Set one value. None removes it (unknown)."""
    spec = product.spec(field)
    if value is None:
        if spec is not None:
            product.specs.remove(spec)
        return
    if spec is None:
        spec = SpecValue(field=field)
        product.specs.append(spec)
    spec.option = value if field.kind == CHOICE else None
    spec.number = value if field.kind == NUMBER else None
    spec.text = value if field.kind == TEXT else None


def save_specs(product: Product, fields: list[SpecField], values: dict[int, Value]) -> None:
    """Replace the product's values with ``values``. Values for fields that are not
    in ``fields`` (from a previous category) are removed."""
    field_ids = {field.id for field in fields}
    for spec in list(product.specs):
        if spec.field_id not in field_ids:
            product.specs.remove(spec)
    for field in fields:
        set_spec(product, field, values.get(field.id))
