"""Export the whole database to JSON, and import it again (also on another machine).

Records refer to each other by natural keys (item and container codes, user card
numbers, product and category names), never by database ids, so a file can be
merged into a different database. Spec values are stored by field name, and
choices by their label.

Files from schema version 1 (before products existed) can still be imported:
items with the same name become copies of one product.

Import modes:
- replace: delete everything, then load the file.
- merge:   add or update records from the file; nothing is deleted.

An import either succeeds completely or changes nothing.
"""

from datetime import UTC, datetime
from typing import Any

from ..extensions import db
from ..models import (
    CHOICE,
    KINDS,
    NUMBER,
    Category,
    Comment,
    Container,
    Item,
    Product,
    Rental,
    SpecField,
    SpecOption,
    SpecValue,
    User,
)
from .specs import Value, set_spec

SCHEMA_VERSION = 2

USER_FIELDS = ["card_number", "name", "email", "study_number", "is_admin", "created_at"]
CONTAINER_FIELDS = ["code", "name", "description", "created_at", "updated_at"]
SPEC_FIELD_FIELDS = ["name", "kind", "unit", "options"]
PRODUCT_FIELDS = ["name", "description", "length_mm", "width_mm", "height_mm",
                  "created_at", "updated_at"]
ITEM_FIELDS = ["code", "number", "created_at", "updated_at", "deleted_at"]
V1_ITEM_FIELDS = ["code", "name", "number", "category", "description", "length_mm",
                  "width_mm", "height_mm", "created_at", "updated_at", "deleted_at"]
DATETIME_FIELDS = {"created_at", "updated_at", "deleted_at", "rented_at", "returned_at"}


class TransferError(Exception):
    """The file can't be imported. The message is shown to the user."""


# Export


def _value(obj, field: str):
    value = getattr(obj, field)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def _fields(obj, fields: list[str]) -> dict[str, Any]:
    return {field: _value(obj, field) for field in fields}


def _all(model, *order):
    return db.session.execute(db.select(model).order_by(*order)).scalars().all()


def export_data() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "users": [_fields(u, USER_FIELDS) for u in _all(User, User.card_number)],
        "containers": [_fields(c, CONTAINER_FIELDS) for c in _all(Container, Container.code)],
        "categories": [
            {
                "name": c.name,
                "fields": [
                    {"name": f.name, "kind": f.kind, "unit": f.unit,
                     "options": [o.label for o in f.options]}
                    for f in c.fields
                ],
            }
            for c in _all(Category, Category.name)
        ],
        "products": [
            {
                **_fields(p, PRODUCT_FIELDS),
                "category": p.category.name if p.category else None,
                "specs": {
                    s.field.name: s.value
                    for s in sorted(p.specs, key=lambda s: s.field.position)
                },
            }
            for p in _all(Product, Product.name)
        ],
        "items": [
            {
                **_fields(i, ITEM_FIELDS),
                "product": i.product.name,
                "container": i.container.code if i.container else None,
            }
            for i in _all(Item, Item.code)
        ],
        "rentals": [
            {
                "item": r.item.code,
                "user": r.user.card_number,
                "rented_at": _value(r, "rented_at"),
                "returned_at": _value(r, "returned_at"),
                "returned_by": r.returned_by.card_number if r.returned_by else None,
            }
            for r in _all(Rental, Rental.rented_at, Rental.id)
        ],
        "comments": [
            {
                "item": c.item.code,
                "user": c.user.card_number,
                "text": c.text,
                "created_at": _value(c, "created_at"),
            }
            for c in _all(Comment, Comment.created_at, Comment.id)
        ],
    }


# Import


def summary(counts: dict[str, int]) -> str:
    """E.g. "2 users, 1 category, 3 products, 1 container, 3 items, 0 rentals, 1 note"."""
    names = {"users": ("user", "users"), "categories": ("category", "categories"),
             "products": ("product", "products"), "containers": ("container", "containers"),
             "items": ("item", "items"), "rentals": ("rental", "rentals"),
             "comments": ("note", "notes")}
    return ", ".join(f"{n} {names[kind][n != 1]}" for kind, n in counts.items())


def _parse(record: dict[str, Any], fields: list[str], what: str) -> dict[str, Any]:
    """Pick ``fields`` from ``record``, turning ISO timestamps into datetimes."""
    try:
        values = {field: record[field] for field in fields}
    except KeyError as missing:
        raise TransferError(f"A {what} in the file is missing the field {missing}.")
    except TypeError:
        raise TransferError(f"The file has a {what} that is not a JSON object.")
    for field in DATETIME_FIELDS & values.keys():
        if values[field] is not None and not isinstance(values[field], datetime):
            try:
                values[field] = datetime.fromisoformat(values[field]).astimezone(UTC)
            except (TypeError, ValueError):
                raise TransferError(f"A {what} has an invalid date: {values[field]!r}.")
    return values


def _upsert(model, key: str, values: dict[str, Any]):
    obj = db.session.execute(
        db.select(model).filter_by(**{key: values[key]})
    ).scalar_one_or_none()
    if obj is None:
        obj = model()
        db.session.add(obj)
    for field, value in values.items():
        setattr(obj, field, value)
    return obj


def import_data(data: dict[str, Any], mode: str) -> dict[str, int]:
    """Load an export into the database. Returns the number of records per kind."""
    if mode not in ("replace", "merge"):
        raise ValueError(f"Unknown import mode {mode!r}")
    if not isinstance(data, dict) or data.get("schema_version") not in (1, SCHEMA_VERSION):
        raise TransferError(
            f"This is not a rental system export (schema version {SCHEMA_VERSION})."
        )
    try:
        if data["schema_version"] == 1:
            data = _from_version_1(data)
        counts = _load(data, mode)
        db.session.flush()
        if not db.session.execute(db.select(User.id).filter_by(is_admin=True)).first():
            raise TransferError("After this import there would be no admins left.")
        db.session.commit()
    except TransferError:
        db.session.rollback()
        raise
    except Exception as error:  # e.g. a duplicate email or a second open rental
        db.session.rollback()
        reason = getattr(error, "orig", error)  # the database's short message, if any
        raise TransferError(f"The file could not be imported: {reason}") from error
    return counts


def _list(value, what: str) -> list:
    if not isinstance(value, list):
        raise TransferError(f"The {what} in the file should be a list.")
    return value


def _spec_value(field: SpecField, value, product: str) -> Value:
    """A spec value from the file, checked against the field's kind."""
    if value is None:
        return None
    problem = f"{product} has an invalid value for {field.name}: {value!r}."
    if field.kind == CHOICE:
        option = next((o for o in field.options if o.label == value), None)
        if option is None:
            raise TransferError(problem)
        return option
    if field.kind == NUMBER:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TransferError(problem)
        return float(value)
    if not isinstance(value, str):
        raise TransferError(problem)
    return value


def _load(data: dict[str, Any], mode: str) -> dict[str, int]:
    if mode == "replace":
        for model in (Comment, Rental, Item, SpecValue, Product, SpecOption, SpecField,
                      Category, Container, User):
            db.session.execute(db.delete(model))
        # Forget the deleted objects, so new rows reusing their ids don't clash.
        db.session.expunge_all()

    users = {}
    for record in data.get("users", []):
        user = _upsert(User, "card_number", _parse(record, USER_FIELDS, "user"))
        users[user.card_number] = user

    containers = {}
    for record in data.get("containers", []):
        container = _upsert(Container, "code", _parse(record, CONTAINER_FIELDS, "container"))
        containers[container.code] = container

    def lookup(table: dict, key, what: str, model, field: str):
        if key is None:
            return None
        found = table.get(key) or db.session.execute(
            db.select(model).filter_by(**{field: key})
        ).scalar_one_or_none()
        if found is None:
            raise TransferError(f"The file refers to an unknown {what}: {key}.")
        return found

    categories = {}
    for record in data.get("categories", []):
        values = _parse(record, ["name", "fields"], "category")
        category = _upsert(Category, "name", {"name": values["name"]})
        for position, spec_record in enumerate(_list(values["fields"], "fields"), start=1):
            spec = _parse(spec_record, SPEC_FIELD_FIELDS, "spec field")
            if spec["kind"] not in KINDS:
                raise TransferError(f"The field {spec['name']} has an unknown type: "
                                    f"{spec['kind']!r}.")
            field = next((f for f in category.fields if f.name == spec["name"]), None)
            if field is None:
                field = SpecField(name=spec["name"], kind=spec["kind"])
                category.fields.append(field)
            elif field.kind != spec["kind"]:
                raise TransferError(
                    f"The field {category.name} / {field.name} is a {field.kind} field "
                    f"here, but a {spec['kind']} field in the file."
                )
            field.unit = spec["unit"]
            field.position = position
            labels = {o.label for o in field.options}
            for label in _list(spec["options"], "options"):
                if label not in labels:
                    field.options.append(SpecOption(label=label))
                    labels.add(label)
        categories[category.name] = category
    db.session.flush()  # gives new fields and options their ids

    products = {}
    for record in data.get("products", []):
        values = _parse(record, PRODUCT_FIELDS + ["category", "specs"], "product")
        category = lookup(categories, values.pop("category"), "category", Category, "name")
        specs = values.pop("specs")
        if not isinstance(specs, dict):
            raise TransferError(f"The specs of {values['name']} should be an object.")
        product = _upsert(Product, "name", values)
        product.category = category
        fields = {f.name: f for f in category.fields} if category else {}
        for spec in list(product.specs):  # values from another category
            if spec.field not in fields.values():
                product.specs.remove(spec)
        for name, value in specs.items():
            if name not in fields:
                raise TransferError(
                    f"{product.name} has a value for a field its category doesn't have: "
                    f"{name}."
                )
            set_spec(product, fields[name], _spec_value(fields[name], value, product.name))
        products[product.name] = product

    items = {}
    for record in data.get("items", []):
        values = _parse(record, ITEM_FIELDS + ["product", "container"], "item")
        values["product"] = lookup(products, values["product"], "product", Product, "name")
        if values["product"] is None:
            raise TransferError(f"The item {values['code']} has no product.")
        values["container"] = lookup(containers, values["container"], "container",
                                     Container, "code")
        item = _upsert(Item, "code", values)
        items[item.code] = item
    db.session.flush()
    rentals = 0
    for record in data.get("rentals", []):
        values = _parse(record, ["item", "user", "rented_at", "returned_at", "returned_by"],
                        "rental")
        # Resolve every reference before touching the session.
        item = lookup(items, values["item"], "item", Item, "code")
        user = lookup(users, values["user"], "user", User, "card_number")
        returned_by = lookup(users, values["returned_by"], "user", User, "card_number")
        rental = db.session.execute(
            db.select(Rental).filter_by(item_id=item.id, rented_at=values["rented_at"])
        ).scalar_one_or_none()
        if rental is None:
            rental = Rental(item=item, rented_at=values["rented_at"])
            db.session.add(rental)
        rental.user = user
        rental.returned_at = values["returned_at"]
        rental.returned_by = returned_by
        db.session.flush()  # catches a second open rental for the same item early
        rentals += 1

    comments = 0
    for record in data.get("comments", []):
        values = _parse(record, ["item", "user", "text", "created_at"], "comment")
        item = lookup(items, values["item"], "item", Item, "code")
        user = lookup(users, values["user"], "user", User, "card_number")
        exists = db.session.execute(
            db.select(Comment.id).filter_by(item_id=item.id, user_id=user.id,
                                            created_at=values["created_at"],
                                            text=values["text"])
        ).first()
        if not exists:
            db.session.add(Comment(item=item, user=user, text=values["text"],
                                   created_at=values["created_at"]))
        comments += 1

    return {"users": len(users), "categories": len(categories), "products": len(products),
            "containers": len(containers), "items": len(items), "rentals": rentals,
            "comments": comments}


def _from_version_1(data: dict[str, Any]) -> dict[str, Any]:
    """Turn a version 1 file into version 2: items with the same name (ignoring
    upper/lower case) become copies of one product, which takes over their
    category, description and size."""
    records = [_parse(r, V1_ITEM_FIELDS + ["container"], "item")
               for r in _list(data.get("items", []), "items")]
    # Lowest number first; its spelling of the name is kept. Missing numbers last.
    records.sort(key=lambda r: (r["number"] is None, r["number"] or 0))

    groups: dict[str, list[dict]] = {}
    for record in records:
        groups.setdefault(str(record["name"]).casefold(), []).append(record)

    categories: dict[str, str] = {}  # casefolded -> first spelling
    products, items = [], []
    for group in groups.values():
        def known(field):
            return next((r[field] for r in group if r[field] is not None), None)

        category = known("category")
        if category:
            category = categories.setdefault(category.casefold(), category)
        products.append({
            "name": group[0]["name"], "category": category,
            "description": known("description"), "length_mm": known("length_mm"),
            "width_mm": known("width_mm"), "height_mm": known("height_mm"),
            "created_at": min(r["created_at"] for r in group),
            "updated_at": max(r["updated_at"] for r in group),
            "specs": {},
        })
        used: set[int] = set()
        for record in group:
            number = record["number"]
            if number is None or number in used:
                number = max(used, default=0) + 1
            used.add(number)
            items.append({
                "code": record["code"], "product": group[0]["name"], "number": number,
                "container": record["container"], "created_at": record["created_at"],
                "updated_at": record["updated_at"], "deleted_at": record["deleted_at"],
            })

    return {
        **data,
        "schema_version": SCHEMA_VERSION,
        "categories": [{"name": name, "fields": []} for name in categories.values()],
        "products": products,
        "items": items,
    }
