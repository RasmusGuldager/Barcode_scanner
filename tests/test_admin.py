import re

import pytest

from app.models import (
    CHOICE,
    NUMBER,
    TEXT,
    Category,
    Comment,
    Container,
    Item,
    Product,
    Rental,
    SpecField,
    SpecOption,
    SpecValue,
)
from app.services.codes import ALPHABET, LENGTH


@pytest.fixture
def admin(client, make_user, login):
    user = make_user(is_admin=True)
    login(user)
    return user


def product(db, name: str = "Basler ace", **fields) -> Product:
    """The product called ``name``, created with ``fields`` if it doesn't exist."""
    found = db.session.execute(db.select(Product).filter_by(name=name)).scalar_one_or_none()
    if found is None:
        found = Product(name=name, **fields)
        db.session.add(found)
        db.session.commit()
    return found


def add_item(db, name: str = "Basler ace", **fields) -> Item:
    """A new copy of the product called ``name``."""
    item = Item(code=fields.pop("code", f"T{Item.query.count():05d}"),
                product=product(db, name), **fields)
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture
def camera(db):
    """A Camera category with one field of each kind."""
    category = Category(name="Camera", fields=[
        SpecField(name="Shutter", kind=CHOICE, position=1,
                  options=[SpecOption(label="Global"), SpecOption(label="Rolling")]),
        SpecField(name="Max frame rate", kind=NUMBER, unit="fps", position=2),
        SpecField(name="Sensor", kind=TEXT, position=3),
    ])
    db.session.add(category)
    db.session.commit()
    return category


def specs_of(p: Product) -> dict:
    return {s.field.name: s.value for s in p.specs}


# Products


def test_new_product_with_copies(client, db, admin):
    response = client.post("/admin/products/new", data={"name": "Basler ace", "copies": 2})
    p = db.session.execute(db.select(Product)).scalar_one()
    assert response.headers["Location"] == f"/admin/products/{p.id}/edit"
    assert [i.number for i in p.items] == [1, 2]
    for item in p.items:
        assert re.fullmatch(f"[{ALPHABET}]{{{LENGTH}}}", item.code)
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Added Basler ace #1, Basler ace #2." in page


def test_add_copies_continues_numbering_including_trash(client, db, admin):
    first = add_item(db)
    add_item(db)
    client.post(f"/admin/items/{first.id}/trash")
    client.post(f"/admin/products/{first.product_id}/copies", data={"copies": 2})
    assert [i.number for i in first.product.items] == [1, 2, 3, 4]
    client.post(f"/admin/products/{first.product_id}/copies", data={"copies": 0})
    assert len(first.product.items) == 4


def test_product_names_are_unique_ignoring_case(client, db, admin):
    product(db, "Basler ace")
    page = client.post("/admin/products/new", data={"name": "basler ACE", "copies": 1})
    assert b"There is already a product called Basler ace" in page.data
    assert Product.query.count() == 1


def test_rename_product_keeps_numbers(client, db, admin):
    item = add_item(db, number=7)
    client.post(f"/admin/products/{item.product_id}/edit", data={"name": "Basler ace 2"})
    assert item.display_name == "Basler ace 2 #7"


def test_category_existing_or_new(client, db, admin, camera):
    page = client.get("/admin/products/new").data
    assert f'<option value="{camera.id}">Camera</option>'.encode() in page
    assert b"New category..." in page

    def new(name, **data):
        return client.post("/admin/products/new", data={"name": name, "copies": 1, **data})

    new("A", category=camera.id)
    new("B", category="__new__", new_category="Mount")
    new("C", category="__new__", new_category="camera")  # exists already
    new("D", category="")
    by_name = {p.name: p.category.name if p.category else None for p in Product.query.all()}
    assert by_name == {"A": "Camera", "B": "Mount", "C": "Camera", "D": None}
    assert Category.query.count() == 2

    assert b"Type the name of the new category" in new("E", category="__new__").data
    assert b"Not a valid choice" in new("E", category="999").data
    assert Product.query.filter_by(name="E").first() is None


def test_similar_products_while_typing(client, db, admin):
    for _ in range(3):
        add_item(db, "Basler ace")
    add_item(db, "Tripod")

    page = client.get("/admin/products/similar?name=basl").get_data(as_text=True)
    assert "Basler ace" in page and "3 items" in page and "Add copies" in page
    assert "Tripod" not in page
    assert "<html" not in page
    assert "Basler ace" in client.get("/admin/products/similar?name=Balser").get_data(as_text=True)
    assert "Basler" not in client.get("/admin/products/similar?name=b").get_data(as_text=True)


def test_spec_inputs_follow_the_category(client, db, admin, camera):
    page = client.get(f"/admin/products/spec-inputs?category={camera.id}").get_data(as_text=True)
    assert "Max frame rate (fps)" in page and ">Global</option>" in page
    assert "<html" not in page
    assert "<legend>" not in client.get("/admin/products/spec-inputs?category=").get_data(as_text=True)


def test_save_specs(client, db, admin, camera):
    shutter, fps, sensor = camera.fields
    p = product(db, category=camera)
    url = f"/admin/products/{p.id}/edit"
    data = {"name": "Basler ace", "category": camera.id,
            f"spec-{shutter.id}": shutter.options[0].id, f"spec-{fps.id}": "41,5",
            f"spec-{sensor.id}": "Sony IMX174"}
    client.post(url, data=data)
    assert specs_of(p) == {"Shutter": "Global", "Max frame rate": 41.5, "Sensor": "Sony IMX174"}
    page = client.get(url).get_data(as_text=True)
    assert 'value="41.5"' in page
    assert f'<option value="{shutter.options[0].id}" selected>Global</option>' in page

    # Empty means unknown.
    client.post(url, data={**data, f"spec-{sensor.id}": ""})
    assert "Sensor" not in specs_of(p)

    page = client.post(url, data={**data, f"spec-{fps.id}": "fast"}).get_data(as_text=True)
    assert "Enter a number" in page and 'value="fast"' in page
    assert specs_of(p)["Max frame rate"] == 41.5

    # Another category's option id is not accepted.
    lens = Category(name="Lens", fields=[SpecField(name="Mount", kind=CHOICE,
                                                   options=[SpecOption(label="C")])])
    db.session.add(lens)
    db.session.commit()
    page = client.post(url, data={**data, f"spec-{shutter.id}": lens.fields[0].options[0].id})
    assert b"Not one of the options" in page.data

    # Moving to another category drops the old values.
    client.post(url, data={"name": "Basler ace", "category": lens.id})
    assert specs_of(p) == {}


def test_new_product_with_specs(client, db, admin, camera):
    fps = camera.fields[1]
    client.post("/admin/products/new", data={"name": "Mako", "copies": 1,
                                             "category": camera.id, f"spec-{fps.id}": "60"})
    assert specs_of(Product.query.one()) == {"Max frame rate": 60}

    page = client.post("/admin/products/new", data={"name": "Ace", "copies": 1,
                                                    "category": camera.id,
                                                    f"spec-{fps.id}": "x"})
    assert b"Enter a number" in page.data
    assert Product.query.count() == 1 and Item.query.count() == 1


def test_copies_cannot_share_a_container(client, db, admin):
    box = Container(code="BOX001", name="B3-05")
    db.session.add(box)
    db.session.commit()
    response = client.post("/admin/products/new",
                           data={"name": "Cable", "copies": 2, "container_id": box.id})
    assert b"Leave the container empty" in response.data
    assert Item.query.count() == 0

    client.post("/admin/products/new", data={"name": "Cable", "copies": 1,
                                             "container_id": box.id})
    assert Item.query.one().container == box


def test_delete_product_only_without_items(client, db, admin):
    item = add_item(db)
    client.post(f"/admin/products/{item.product_id}/delete")
    assert Product.query.count() == 1
    client.post(f"/admin/items/{item.id}/trash")
    client.post(f"/admin/trash/{item.id}/delete")
    client.post(f"/admin/products/{item.product_id}/delete")
    assert Product.query.count() == 0


def test_admin_product_list(client, db, admin, camera):
    product(db, "Basler ace", category=camera)
    product(db, "Tripod")
    page = client.get("/admin/products?category=Camera").get_data(as_text=True)
    assert "Basler ace" in page and "Tripod" not in page and "0 of 3" in page


# Items


def test_edit_item_container(client, db, admin):
    item = add_item(db)
    box = Container(code="BOX001", name="B3-05")
    db.session.add(box)
    db.session.commit()
    client.post(f"/admin/items/{item.id}/edit",
                data={"product_id": item.product_id, "container_id": box.id})
    assert item.container == box
    client.post(f"/admin/items/{item.id}/edit",
                data={"product_id": item.product_id, "container_id": 0})
    assert item.container is None


def test_move_item_to_another_product(client, db, admin):
    add_item(db, "Tripod")
    item = add_item(db, "Basler ace")
    tripod = product(db, "Tripod")
    response = client.post(f"/admin/items/{item.id}/edit",
                           data={"product_id": tripod.id, "container_id": 0})
    assert response.status_code == 302
    assert item.display_name == "Tripod #2"


def test_full_container_is_not_offered(client, db, admin):
    box = Container(code="BOX001", name="B3-05")
    first = add_item(db, "First", container=box)
    second = add_item(db, "Second")
    response = client.post(f"/admin/items/{second.id}/edit",
                           data={"product_id": second.product_id, "container_id": box.id})
    assert response.status_code == 200  # form shown again with an error
    assert second.container is None
    assert first.container == box


def test_item_list_search_and_sort(client, db, admin):
    product(db, "Basler ace", length_mm=50)
    product(db, "Tripod", length_mm=900)
    for name in ["Basler ace", "Tripod", "Cable"]:  # unknown length goes last
        add_item(db, name)

    response = client.get("/admin/items?q=basler")
    assert b"Basler ace" in response.data
    assert b"Tripod" not in response.data

    page = client.get("/admin/items?sort=length&dir=desc").get_data(as_text=True)
    assert page.index("Tripod") < page.index("Basler ace") < page.index("Cable")


# Categories and spec fields


def test_add_category_and_fields(client, db, admin):
    response = client.post("/admin/categories", data={"name": "Camera"})
    camera = Category.query.one()
    assert response.headers["Location"] == f"/admin/categories/{camera.id}/edit"
    assert b"There is already a category" in client.post("/admin/categories",
                                                         data={"name": "camera"}).data

    url = f"/admin/categories/{camera.id}/fields/new"
    client.post(url, data={"name": "Shutter", "kind": "choice",
                           "options": "Global\n rolling \n\nGLOBAL\nRolling", "unit": "x"})
    client.post(url, data={"name": "Max frame rate", "kind": "number", "unit": "fps"})
    shutter, fps = camera.fields
    assert [o.label for o in shutter.options] == ["Global", "rolling"]
    assert shutter.unit is None  # units are for numbers only
    assert (fps.unit, fps.position) == ("fps", 2)

    for data, error in [
        ({"name": "shutter", "kind": "text"}, b"There is already a field"),
        ({"name": "Max frame-rate", "kind": "text"}, b"Too similar"),
        ({"name": "Max frame rate min", "kind": "text"}, b"Too similar"),  # max_frame_rate_min
        ({"name": "Category", "kind": "text"}, b"Too similar"),
        ({"name": "!!", "kind": "text"}, b"at least one letter"),
        ({"name": "Mount", "kind": "choice", "options": ""}, b"Type at least one option"),
    ]:
        assert error in client.post(url, data=data).data, data
    assert len(camera.fields) == 2


def test_edit_field_and_options(client, db, admin, camera):
    shutter, fps, _ = camera.fields
    p = product(db, category=camera)
    p.specs.append(SpecValue(field=shutter, option=shutter.options[1]))
    p.specs.append(SpecValue(field=fps, number=60))
    db.session.commit()
    page = client.get(f"/admin/fields/{shutter.id}/edit").get_data(as_text=True)
    assert "used by 1 product" in page

    client.post(f"/admin/fields/{fps.id}/edit", data={"name": "Frame rate", "unit": "Hz"})
    assert (fps.name, fps.unit) == ("Frame rate", "Hz")

    rolling = shutter.options[1]
    client.post(f"/admin/options/{rolling.id}/rename", data={"label": "Rolling shutter"})
    assert specs_of(p)["Shutter"] == "Rolling shutter"  # renaming keeps the value
    client.post(f"/admin/options/{rolling.id}/rename", data={"label": "global"})
    assert rolling.label == "Rolling shutter"  # clashes with Global

    client.post(f"/admin/fields/{shutter.id}/options", data={"label": "Global reset"})
    assert [o.label for o in shutter.options] == ["Global", "Rolling shutter", "Global reset"]

    client.post(f"/admin/options/{rolling.id}/delete")
    db.session.expire_all()
    assert "Shutter" not in specs_of(p)  # the product's value is now unknown


def test_move_and_delete_fields(client, db, admin, camera):
    shutter, fps, sensor = camera.fields
    p = product(db, category=camera)
    p.specs.append(SpecValue(field=fps, number=60))
    db.session.commit()

    client.post(f"/admin/fields/{sensor.id}/move", data={"direction": "up"})
    client.post(f"/admin/fields/{shutter.id}/move", data={"direction": "up"})  # already first
    db.session.expire_all()
    assert [f.name for f in camera.fields] == ["Shutter", "Sensor", "Max frame rate"]

    client.post(f"/admin/fields/{fps.id}/delete")
    db.session.expire_all()
    assert [f.name for f in camera.fields] == ["Shutter", "Sensor"]
    assert specs_of(p) == {}


def test_delete_category_keeps_products(client, db, admin, camera):
    item = add_item(db)
    item.product.category = camera
    item.product.specs.append(SpecValue(field=camera.fields[1], number=60))
    db.session.commit()
    client.post(f"/admin/categories/{camera.id}/delete")
    db.session.expire_all()
    assert Category.query.count() == 0
    assert item.product.category is None and item.product.specs == []
    assert Item.query.count() == 1


# Trash


def test_trash_restore_and_delete(client, db, admin, make_user):
    item = add_item(db, name="Basler ace")
    db.session.add_all([
        Rental(item=item, user=admin, returned_at=item.created_at),
        Comment(item=item, user=admin, text="Lens is scratched"),
    ])
    db.session.commit()

    client.post(f"/admin/items/{item.id}/trash")
    assert item.in_trash
    assert b"0 items." in client.get("/admin/items").data
    assert b"Basler ace" in client.get("/admin/trash").data

    client.post(f"/admin/trash/{item.id}/restore")
    assert not item.in_trash

    client.post(f"/admin/items/{item.id}/trash")
    client.post(f"/admin/trash/{item.id}/delete")
    assert Item.query.count() == 0
    assert Rental.query.count() == 0
    assert Comment.query.count() == 0


def test_rented_item_cannot_be_trashed(client, db, admin):
    item = add_item(db, name="Basler ace")
    db.session.add(Rental(item=item, user=admin))
    db.session.commit()
    client.post(f"/admin/items/{item.id}/trash")
    assert not item.in_trash


def test_only_trashed_items_can_be_deleted_permanently(client, db, admin):
    item = add_item(db, name="Basler ace")
    assert client.post(f"/admin/trash/{item.id}/delete").status_code == 404
    assert Item.query.count() == 1


# Containers


def test_create_container_and_delete_keeps_item(client, db, admin):
    client.post("/admin/containers/new", data={"name": "Shelf B3, box 05"})
    box = db.session.execute(db.select(Container)).scalar_one()
    assert re.fullmatch(f"[{ALPHABET}]{{{LENGTH}}}", box.code)

    item = add_item(db, name="Basler ace", container=box)
    client.post(f"/admin/containers/{box.id}/delete")
    db.session.expire_all()
    assert Container.query.count() == 0
    assert item.container_id is None


# Users


def test_promote_and_demote(client, db, admin, make_user):
    other = make_user()
    client.post(f"/admin/users/{other.id}/promote")
    assert other.is_admin
    client.post(f"/admin/users/{other.id}/demote")
    assert not other.is_admin


def test_admin_cannot_demote_self(client, db, admin):
    client.post(f"/admin/users/{admin.id}/demote")
    assert admin.is_admin


def test_admin_pages_render(client, db, admin):
    box = Container(code="BOX001", name="B3-05")
    item = add_item(db, name="Basler ace", number=5, container=box)
    category = Category(name="Camera", fields=[
        SpecField(name="Shutter", kind=CHOICE, options=[SpecOption(label="Global")])])
    item.product.category = category
    db.session.commit()
    field = category.fields[0]
    for url in ["/admin/", "/admin/items", f"/admin/items/{item.id}/edit",
                "/admin/products", "/admin/products/new",
                f"/admin/products/{item.product_id}/edit", "/admin/categories",
                f"/admin/categories/{category.id}/edit",
                f"/admin/categories/{category.id}/fields/new", f"/admin/fields/{field.id}/edit",
                "/admin/containers", "/admin/containers/new",
                f"/admin/containers/{box.id}/edit", "/admin/users", "/admin/trash"]:
        assert client.get(url).status_code == 200, url


def test_admin_changes_card_number(client, db, admin, make_user):
    user = make_user(card_number="111111", email="bob@aau.dk")
    data = {"card_number": "222222", "email": "Bob@AAU.dk", "study_number": "20201234",
            "name": "Bob"}
    response = client.post(f"/admin/users/{user.id}/edit", data=data)
    assert response.status_code == 302
    assert user.card_number == "222222"
    assert user.email == "bob@aau.dk"

    # The user can now sign in with the new card.
    client.post("/logout")
    response = client.post("/identify", data={"code": "222222"})
    assert response.headers["Location"] == "/me"


def test_edit_user_rejects_taken_card_and_email(client, db, admin, make_user):
    user = make_user()
    other = make_user(card_number="333333", email="other@aau.dk", name="Other")
    data = {"card_number": "333333", "email": user.email, "study_number": "20201234"}
    page = client.post(f"/admin/users/{user.id}/edit", data=data)
    assert b"This card belongs to Other" in page.data

    data = {"card_number": user.card_number, "email": "other@aau.dk",
            "study_number": "20201234"}
    page = client.post(f"/admin/users/{user.id}/edit", data=data)
    assert b"This email belongs to Other" in page.data

    data = {"card_number": "12345678", "email": user.email, "study_number": "123456"}
    page = client.post(f"/admin/users/{user.id}/edit", data=data)
    assert b"A card number is 6 digits" in page.data
    assert b"A study number is 8 digits" in page.data
    assert user.card_number != "12345678"
    assert client.get(f"/admin/users/{other.id}/edit").status_code == 200
