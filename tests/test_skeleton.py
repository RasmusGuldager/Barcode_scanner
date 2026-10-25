from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Container, Item, Product, Rental


def test_start_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Scan your AAU card" in response.data
    assert b"zxing-reader.iife.js" in response.data


def test_admin_redirects_anonymous_user_to_start(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/?next=/admin/"


def test_admin_forbidden_for_normal_user(client, make_user, login):
    login(make_user())
    assert client.get("/admin/").status_code == 403


def test_admin_allowed_for_admin(client, make_user, login):
    login(make_user(is_admin=True))
    assert client.get("/admin/").status_code == 200


def test_datetimes_come_back_in_utc(db, make_user):
    user = make_user()
    db.session.expire_all()
    assert user.created_at.tzinfo == UTC


def test_item_can_have_only_one_open_rental(db, make_user):
    user = make_user()
    item = Item(code="K7F2Q8", product=Product(name="Basler ace"), number=5)
    db.session.add_all([item, Rental(item=item, user=user, returned_at=datetime.now(UTC))])
    db.session.add(Rental(item=item, user=user))
    db.session.commit()

    db.session.add(Rental(item=item, user=user))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_container_holds_only_one_item(db):
    box = Container(code="M4T9XC", name="Shelf B3, box 05")
    db.session.add_all([
        Item(code="AAAAAA", product=Product(name="A"), container=box),
        Item(code="BBBBBB", product=Product(name="B"), container=box),
    ])
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_make_admin_cli(app, db, make_user):
    user = make_user(email="admin@aau.dk")
    result = app.test_cli_runner().invoke(args=["make-admin", "Admin@AAU.dk"])
    assert result.exit_code == 0, result.output
    assert user.is_admin


def test_make_admin_cli_unknown_email(app):
    result = app.test_cli_runner().invoke(args=["make-admin", "nobody@aau.dk"])
    assert result.exit_code != 0
    assert "No user with email" in result.output


def test_delete_user_cli(app, db, make_user):
    from app.models import Comment, User

    runner = app.test_cli_runner()
    admin = make_user(is_admin=True, email="admin@aau.dk")
    user = make_user(card_number="123456", email="test@aau.dk")
    busy = make_user(email="busy@aau.dk")
    item = Item(code="K7F2Q8", product=Product(name="Basler ace"))
    db.session.add_all([item, Comment(item=item, user=busy, text="Note")])
    db.session.commit()

    result = runner.invoke(args=["delete-user", "123456"], input="n\n")
    assert result.exit_code != 0  # declined
    result = runner.invoke(args=["delete-user", "123456"], input="y\n")
    assert result.exit_code == 0, result.output
    assert db.session.get(User, user.id) is None

    result = runner.invoke(args=["delete-user", "busy@aau.dk", "--yes"])
    assert "has rentals or notes" in result.output
    result = runner.invoke(args=["delete-user", "Admin@AAU.dk", "--yes"])
    assert "only admin" in result.output
    result = runner.invoke(args=["delete-user", "nobody@aau.dk", "--yes"])
    assert "No user" in result.output
    assert db.session.get(User, admin.id) is not None
