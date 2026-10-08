from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Container, Item, Rental


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
    item = Item(code="K7F2Q8", name="Basler ace", number=5)
    db.session.add_all([item, Rental(item=item, user=user, returned_at=datetime.now(UTC))])
    db.session.add(Rental(item=item, user=user))
    db.session.commit()

    db.session.add(Rental(item=item, user=user))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_container_holds_only_one_item(db):
    box = Container(code="M4T9XC", name="Shelf B3, box 05")
    db.session.add_all([
        Item(code="AAAAAA", name="A", container=box),
        Item(code="BBBBBB", name="B", container=box),
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
