import re

import pytest

from app.models import Comment, Container, Item, Rental
from app.services.codes import ALPHABET, LENGTH


@pytest.fixture
def admin(client, make_user, login):
    user = make_user(is_admin=True)
    login(user)
    return user


def add_item(db, **fields) -> Item:
    item = Item(code=fields.pop("code", f"T{Item.query.count():05d}"), **fields)
    db.session.add(item)
    db.session.commit()
    return item


# Items


def test_create_item_gets_a_valid_code(client, db, admin):
    response = client.post("/admin/items/new", data={"name": "Basler ace", "copies": 1})
    assert response.status_code == 302
    item = db.session.execute(db.select(Item)).scalar_one()
    assert re.fullmatch(f"[{ALPHABET}]{{{LENGTH}}}", item.code)
    assert item.number is None


def test_create_copies_are_numbered(client, db, admin):
    client.post("/admin/items/new",
                data={"name": "Basler ace", "number": 3, "copies": 4, "container_id": 0})
    items = db.session.execute(db.select(Item).order_by(Item.number)).scalars().all()
    assert [i.number for i in items] == [3, 4, 5, 6]
    assert len({i.code for i in items}) == 4


def test_copies_without_number_start_at_one(client, db, admin):
    client.post("/admin/items/new", data={"name": "Cable", "copies": 2})
    numbers = db.session.execute(db.select(Item.number).order_by(Item.number)).scalars()
    assert list(numbers) == [1, 2]


def test_copies_cannot_share_a_container(client, db, admin):
    box = Container(code="BOX001", name="B3-05")
    db.session.add(box)
    db.session.commit()
    response = client.post("/admin/items/new",
                           data={"name": "Cable", "copies": 2, "container_id": box.id})
    assert response.status_code == 200
    assert b"Leave the container empty" in response.data
    assert Item.query.count() == 0


def test_edit_item_and_assign_container(client, db, admin):
    item = add_item(db, name="Old name")
    box = Container(code="BOX001", name="B3-05")
    db.session.add(box)
    db.session.commit()
    client.post(f"/admin/items/{item.id}/edit",
                data={"name": "New name", "container_id": box.id, "length_mm": 120})
    assert item.name == "New name"
    assert item.container == box
    assert item.length_mm == 120


def test_full_container_is_not_offered(client, db, admin):
    box = Container(code="BOX001", name="B3-05")
    first = add_item(db, name="First", container=box)
    second = add_item(db, name="Second")
    response = client.post(f"/admin/items/{second.id}/edit",
                           data={"name": "Second", "container_id": box.id})
    assert response.status_code == 200  # form shown again with an error
    assert second.container is None
    assert first.container == box


def test_unassign_container(client, db, admin):
    box = Container(code="BOX001", name="B3-05")
    item = add_item(db, name="Item", container=box)
    client.post(f"/admin/items/{item.id}/edit", data={"name": "Item", "container_id": 0})
    assert item.container is None


def test_item_list_search_and_sort(client, db, admin):
    add_item(db, name="Basler ace", length_mm=50)
    add_item(db, name="Tripod", length_mm=900)
    add_item(db, name="Cable")  # unknown length goes last

    response = client.get("/admin/items?q=basler")
    assert b"Basler ace" in response.data
    assert b"Tripod" not in response.data

    page = client.get("/admin/items?sort=length&dir=desc").get_data(as_text=True)
    assert page.index("Tripod") < page.index("Basler ace") < page.index("Cable")


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
    for url in ["/admin/", "/admin/items", "/admin/items/new", f"/admin/items/{item.id}/edit",
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
