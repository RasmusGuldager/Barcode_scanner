"""The public item list with filters, and the product page."""

import re
from datetime import UTC, datetime

import pytest

from app.models import (
    CHOICE,
    NUMBER,
    TEXT,
    Category,
    Item,
    Product,
    SpecField,
    SpecOption,
    SpecValue,
)
from app.services.rentals import rent_items


@pytest.fixture
def cameras(db, make_user):
    """Four cameras and a lens:

    Mako     Global   60 fps   2 copies, one rented
    Ace      Rolling 120 fps   1 copy, rented
    Old cam  (unknown) 30 fps  1 copy
    Thermal  Global   (unknown) 1 copy
    Kowa     a lens            1 copy
    """
    shutter = SpecField(name="Shutter", kind=CHOICE, position=1,
                        options=[SpecOption(label="Global"), SpecOption(label="Rolling")])
    fps = SpecField(name="Max frame rate", kind=NUMBER, unit="fps", position=2)
    sensor = SpecField(name="Sensor", kind=TEXT, position=3)
    camera = Category(name="Camera", fields=[shutter, fps, sensor])
    glob, rolling = shutter.options

    def make(name, copies, category=camera, **specs):
        product = Product(name=name, category=category)
        for field, value in specs.items():
            field = {"shutter": shutter, "fps": fps, "sensor": sensor}[field]
            product.specs.append(SpecValue(
                field=field,
                option=value if field.kind == CHOICE else None,
                number=value if field.kind == NUMBER else None,
                text=value if field.kind == TEXT else None,
            ))
        product.items = [Item(code=f"{name[:3].upper()}{n:03d}".replace(" ", "X"), number=n)
                         for n in range(1, copies + 1)]
        db.session.add(product)
        return product

    mako = make("Mako", 2, shutter=glob, fps=60, sensor="Sony IMX174")
    ace = make("Ace", 1, shutter=rolling, fps=120)
    make("Old cam", 1, fps=30)
    make("Thermal", 1, shutter=glob)
    make("Kowa", 1, category=Category(name="Lens"))
    db.session.commit()
    user = make_user()
    rent_items(user, [mako.items[0], ace.items[0]])
    return camera


def names(page: str) -> list[str]:
    """The product names in the results table, in order."""
    return [n for n in ["Ace", "Kowa", "Mako", "Old cam", "Thermal"]
            if f">{n}</a></td>" in page]


def get(client, query: str) -> str:
    return client.get(f"/items?{query}").get_data(as_text=True)


def test_only_available_by_default(client, cameras):
    page = get(client, "")
    assert names(page) == ["Kowa", "Mako", "Old cam", "Thermal"]
    assert "1 of 2" in page  # Mako
    page = get(client, "available=0")
    assert names(page) == ["Ace", "Kowa", "Mako", "Old cam", "Thermal"]
    # The form sends the hidden 0 and the ticked box's 1: the last one wins.
    assert "Ace" not in names(get(client, "available=0&available=1"))


def test_category_shows_its_specs_as_columns_and_filters(client, cameras):
    page = get(client, "category=Camera")
    assert names(page) == ["Mako", "Old cam", "Thermal"]
    assert "<th>Max frame rate (fps)</th>" in page
    assert "<td>60 fps</td>" in page and "<td>Sony IMX174</td>" in page
    assert 'name="shutter" value="Global"' in page
    assert 'name="max_frame_rate_min"' in page
    assert 'name="sensor"' not in page  # text fields are searched, not filtered
    assert 'aria-current="page">Camera</a>' in page


def test_choice_filter(client, cameras):
    page = get(client, "category=Camera&shutter=Global")
    assert names(page) == ["Mako", "Thermal"]
    assert "1 more product is not shown" in page  # Old cam: shutter unknown
    assert re.search(r'value="Global"\s+checked', page)

    page = get(client, "category=Camera&shutter=Global&shutter=Rolling&available=0")
    assert names(page) == ["Ace", "Mako", "Thermal"]


def test_number_filter(client, cameras):
    assert names(get(client, "category=Camera&max_frame_rate_min=50")) == ["Mako"]
    page = get(client, "category=Camera&max_frame_rate_min=50&available=0")
    assert names(page) == ["Ace", "Mako"]
    assert "1 more product" in page  # Thermal: frame rate unknown
    assert names(get(client, "category=Camera&max_frame_rate_max=59,9")) == ["Old cam"]
    # Junk is ignored rather than failing.
    assert names(get(client, "category=Camera&max_frame_rate_min=fast")) == [
        "Mako", "Old cam", "Thermal"]


def test_filters_combine(client, cameras):
    query = "category=Camera&shutter=Global&max_frame_rate_min=50&available=0"
    assert names(get(client, query)) == ["Mako"]


def test_spec_filters_ignored_without_category(client, cameras):
    assert names(get(client, "shutter=Rolling")) == ["Kowa", "Mako", "Old cam", "Thermal"]


def test_search_matches_specs(client, cameras):
    assert names(get(client, "q=imx174")) == ["Mako"]
    assert names(get(client, "q=rolling&available=0")) == ["Ace"]
    assert names(get(client, "q=lens")) == ["Kowa"]  # category name


def test_category_links_keep_search(client, cameras):
    page = get(client, "q=mako&available=0")
    assert 'href="/items?category=Camera&amp;q=mako&amp;available=0"' in page


def test_product_page(client, db, cameras, make_user, login):
    mako = Product.query.filter_by(name="Mako").one()
    page = client.get(f"/products/{mako.id}").get_data(as_text=True)
    assert "1 of 2 available" in page
    assert "<dt>Shutter</dt><dd>Global</dd>" in page
    assert "Mako #1" in page and "Rented out" in page
    assert "Rented by" not in page

    login(make_user(is_admin=True))
    assert "Rented by" in client.get(f"/products/{mako.id}").get_data(as_text=True)

    # A product with only trashed copies is gone for users.
    for item in mako.items:
        item.deleted_at = datetime.now(UTC)
    db.session.commit()
    assert client.get(f"/products/{mako.id}").status_code == 404


def test_item_page_shows_product_specs(client, cameras):
    page = client.get("/i/MAK002").get_data(as_text=True)
    assert "<dt>Max frame rate</dt><dd>60 fps</dd>" in page
    assert "<dt>Shutter</dt><dd>Global</dd>" in page
    assert "2 copies" in page
