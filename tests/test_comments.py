import pytest

from app.models import Comment, Item
from app.services.rentals import rent_items

HX = {"HX-Request": "true"}


@pytest.fixture
def item(db):
    item = Item(code="CAMAAA", name="Basler ace", number=5)
    db.session.add(item)
    db.session.commit()
    return item


def test_add_note_on_item_page(client, db, make_user, login, item):
    login(make_user(name="Alice"))
    response = client.post("/i/CAMAAA/comments", data={"text": "  Lens cap missing  "},
                           follow_redirects=True)
    assert b"Note added." in response.data
    assert b"Lens cap missing" in response.data
    assert item.comments[0].text == "Lens cap missing"


def test_note_author_is_hidden_from_users(client, db, make_user, login, item):
    db.session.add(Comment(item=item, user=make_user(name="Bob"), text="Scratched"))
    db.session.commit()
    login(make_user(name="Alice"))
    page = client.get("/i/CAMAAA").data
    assert b"Scratched" in page
    assert b"Bob" not in page


def test_note_needs_text_and_sign_in(client, db, make_user, login, item):
    assert client.post("/i/CAMAAA/comments", data={"text": "x"}).status_code == 302
    assert Comment.query.count() == 0

    login(make_user())
    response = client.post("/i/CAMAAA/comments", data={"text": "  "}, follow_redirects=True)
    assert b"Write a note first." in response.data
    response = client.post("/i/CAMAAA/comments", data={"text": "x" * 501},
                           follow_redirects=True)
    assert b"under 500 characters" in response.data
    assert Comment.query.count() == 0


def test_note_offered_after_return(client, db, make_user, login, item):
    user = make_user()
    login(user)
    rent_items(user, [item])
    page = client.post("/return/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    assert b"Anything wrong with Basler ace #5?" in page.data

    page = client.post("/i/CAMAAA/comments", data={"text": "Cable frayed"}, headers=HX)
    assert b"your note on Basler ace #5 is saved" in page.data
    assert b"<html" not in page.data
    assert item.comments[0].text == "Cable frayed"


def test_admin_sees_author_and_deletes_note(client, db, make_user, login, item):
    alice = make_user(name="Alice")
    db.session.add(Comment(item=item, user=alice, text="Lens cap missing"))
    db.session.commit()
    comment = item.comments[0]

    login(alice)
    assert client.post(f"/comments/{comment.id}/delete").status_code == 403

    login(make_user(is_admin=True))
    page = client.get("/i/CAMAAA").data
    assert b"Alice" in page
    response = client.post(f"/comments/{comment.id}/delete")
    assert response.headers["Location"] == "/i/CAMAAA"
    assert Comment.query.count() == 0
