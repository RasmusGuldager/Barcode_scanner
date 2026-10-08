import pytest

from app.models import Container, Item, Rental, User
from app.services.rentals import (
    RentalError,
    force_return,
    rent_items,
    return_item,
)
from app.services.scanning import ScanError, find_label, normalize_card_number

HX = {"HX-Request": "true"}


@pytest.fixture
def box(db):
    box = Container(code="BXAAAA", name="Shelf B3, box 05")
    db.session.add(box)
    db.session.commit()
    return box


@pytest.fixture
def camera(db, box):
    item = Item(code="CAMAAA", name="Basler ace", number=5, container=box)
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture
def cable(db):
    item = Item(code="CABAAA", name="USB-C cable")
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture
def user(make_user):
    return make_user(name="Alice")


@pytest.fixture
def signed_in(client, user, login):
    login(user)
    return user


def open_rentals(db):
    return db.session.execute(db.select(Rental).filter_by(returned_at=None)).scalars().all()


# Scanning


def test_find_label(camera, box):
    assert find_label("VAP-CAMAAA") == camera
    assert find_label(" vap-camaaa ") == camera
    assert find_label("BOX-BXAAAA") == box
    assert find_label("CAMAAA") == camera  # typed without prefix
    assert find_label("BXAAAA") == box


@pytest.mark.parametrize("text", ["https://example.com", "12345678", "VAP-", "ABC"])
def test_find_label_rejects_foreign_codes(db, text):
    with pytest.raises(ScanError, match="not part of"):
        find_label(text)


def test_find_label_unknown_and_trashed(db, camera):
    with pytest.raises(ScanError, match="No item"):
        find_label("VAP-ZZZZZZ")
    with pytest.raises(ScanError, match="No item"):
        find_label("BOX-CAMAAA")  # an item code with a container prefix
    camera.deleted_at = camera.created_at
    with pytest.raises(ScanError, match="No item"):
        find_label("VAP-CAMAAA")


def test_card_number():
    assert normalize_card_number(" 123456 ") == "123456"
    for bad in ["12345", "1234567", "20201234", "12345a", ""]:
        with pytest.raises(ScanError):
            normalize_card_number(bad)


# Rules


def test_rent_and_no_double_rental(db, user, make_user, camera):
    rent_items(user, [camera])
    with pytest.raises(RentalError, match="already rented out"):
        rent_items(make_user(), [camera])


def test_rent_is_all_or_nothing(db, user, make_user, camera, cable):
    rent_items(make_user(), [cable])
    with pytest.raises(RentalError):
        rent_items(user, [camera, cable])
    assert camera.open_rental is None


def test_rent_nothing(db, user):
    with pytest.raises(RentalError, match="at least one"):
        rent_items(user, [])


def test_return_without_container(db, user, cable):
    rent_items(user, [cable])
    return_item(user, cable, None)
    assert cable.open_rental is None


def test_return_needs_right_container(db, user, camera, box):
    other_box = Container(code="BXBBBB", name="Shelf A1, box 01")
    db.session.add(other_box)
    rent_items(user, [camera])
    with pytest.raises(RentalError, match="belongs in Shelf B3, box 05"):
        return_item(user, camera, None)
    with pytest.raises(RentalError, match="Wrong container"):
        return_item(user, camera, other_box)
    return_item(user, camera, box)
    assert camera.open_rental is None


def test_only_renter_can_return(db, user, make_user, cable):
    rent_items(user, [cable])
    with pytest.raises(RentalError, match="Only the person who rented it"):
        return_item(make_user(), cable, None)
    with pytest.raises(RentalError, match="not rented out"):
        return_item(user, Item(code="X", name="Other"), None)


def test_force_return(db, user, make_user, camera):
    admin = make_user(is_admin=True)
    [rental] = rent_items(user, [camera])
    force_return(admin, rental)
    assert rental.returned_at is not None
    assert rental.returned_by == admin
    with pytest.raises(RentalError, match="already been returned"):
        force_return(admin, rental)


# Identify and register


def test_new_card_registers_and_signs_in(client, db):
    response = client.post("/identify", data={"code": "123456"})
    assert response.headers["Location"] == "/register"

    response = client.post("/register", data={
        "email": " Alice@Student.AAU.dk ", "study_number": "20201234", "name": "",
    })
    assert response.headers["Location"] == "/me"
    user = db.session.execute(db.select(User)).scalar_one()
    assert user.card_number == "123456"
    assert user.study_number == "20201234"
    assert user.email == "alice@student.aau.dk"
    assert user.name is None
    assert client.get("/me").status_code == 200


def test_register_requires_email_and_study_number(client, db):
    client.post("/identify", data={"code": "123456"})
    response = client.post("/register", data={"email": "not-an-email", "study_number": ""})
    assert response.status_code == 200
    assert b"Enter a valid email address" in response.data
    response = client.post("/register",
                           data={"email": "a@aau.dk", "study_number": "123456"})
    assert b"A study number is 8 digits" in response.data
    assert User.query.count() == 0


def test_register_rejects_taken_email(client, db, user):
    client.post("/identify", data={"code": "999999"})
    response = client.post("/register", data={"email": user.email, "study_number": "20201234"})
    assert b"already registered" in response.data


def test_register_without_card_goes_to_start(client):
    assert client.get("/register").headers["Location"] == "/"


def test_known_card_signs_in_and_follows_next(client, user):
    response = client.post("/identify", data={"code": user.card_number, "next": "/rent"})
    assert response.headers["Location"] == "/rent"


def test_next_must_stay_on_site(client, user):
    response = client.post("/identify",
                           data={"code": user.card_number, "next": "//evil.example"})
    assert response.headers["Location"] == "/me"


def test_invalid_card_number(client):
    response = client.post("/identify", data={"code": "123"}, follow_redirects=True)
    assert b"should be 6 digits" in response.data


def test_pages_need_sign_in(client):
    for url in ["/me", "/rent", "/return"]:
        assert client.get(url).headers["Location"] == f"/?next={url}"


def test_logout(client, signed_in):
    client.post("/logout")
    assert client.get("/me").status_code == 302


# Rent page


def test_rent_flow(client, db, signed_in, camera, cable):
    page = client.post("/rent/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    assert b"Added Basler ace #5" in page.data
    assert b"<html" not in page.data  # htmx gets only the list

    page = client.post("/rent/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    assert b"already in the list" in page.data

    page = client.post("/rent/scan", data={"code": "BOX-BXAAAA"}, headers=HX)
    assert b"That is a container label" in page.data

    page = client.post("/rent/scan", data={"code": "cabaaa"}, headers=HX)
    assert b"Rent 2 items" in page.data

    client.post(f"/rent/remove/{cable.id}", headers=HX)
    response = client.post("/rent/confirm")
    assert response.headers["Location"] == "/me"
    assert [r.item for r in open_rentals(db)] == [camera]
    assert b"No items scanned yet" in client.get("/rent").data


def test_rent_scan_rejects_rented_item(client, db, signed_in, make_user, camera):
    rent_items(make_user(name="Bob"), [camera])
    page = client.post("/rent/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    assert b"already rented out" in page.data
    assert b"Bob" not in page.data


def test_rent_confirm_fails_if_item_was_taken_meanwhile(client, db, signed_in, make_user,
                                                        camera, cable):
    client.post("/rent/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    client.post("/rent/scan", data={"code": "VAP-CABAAA"}, headers=HX)
    rent_items(make_user(), [cable])
    response = client.post("/rent/confirm", follow_redirects=True)
    assert b"already rented" in response.data
    assert camera.open_rental is None


# Return page


def test_return_flow_with_container(client, db, signed_in, camera, box):
    rent_items(signed_in, [camera])

    page = client.post("/return/scan", data={"code": "BOX-BXAAAA"}, headers=HX)
    assert b"Scan the item first" in page.data

    page = client.post("/return/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    assert b"Put Basler ace #5 in Shelf B3, box 05" in page.data
    assert camera.open_rental is not None

    other = Container(code="BXBBBB", name="Shelf A1, box 01")
    db.session.add(other)
    db.session.commit()
    page = client.post("/return/scan", data={"code": "BOX-BXBBBB"}, headers=HX)
    assert b"Wrong container" in page.data
    assert b"Put Basler ace #5 in" in page.data  # still waiting for the right one

    page = client.post("/return/scan", data={"code": "BOX-BXAAAA"}, headers=HX)
    assert b"Returned Basler ace #5 to Shelf B3, box 05" in page.data
    assert camera.open_rental is None
    assert b"All your items are returned" in page.data


def test_return_without_container_is_immediate(client, db, signed_in, cable):
    rent_items(signed_in, [cable])
    page = client.post("/return/scan", data={"code": "VAP-CABAAA"}, headers=HX)
    assert b"Returned USB-C cable" in page.data
    assert cable.open_rental is None


def test_return_cancel(client, db, signed_in, camera):
    rent_items(signed_in, [camera])
    client.post("/return/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    page = client.post("/return/cancel", headers=HX)
    assert b"Put Basler" not in page.data
    assert camera.open_rental is not None


def test_cannot_return_someone_elses_item(client, db, signed_in, make_user, cable):
    rent_items(make_user(name="Bob"), [cable])
    page = client.post("/return/scan", data={"code": "VAP-CABAAA"}, headers=HX)
    assert b"Only the person who rented it" in page.data
    assert b"Bob" not in page.data
    assert cable.open_rental is not None


def test_pending_return_forgotten_after_force_return(client, db, signed_in, make_user,
                                                     camera):
    [rental] = rent_items(signed_in, [camera])
    client.post("/return/scan", data={"code": "VAP-CAMAAA"}, headers=HX)
    force_return(make_user(is_admin=True), rental)
    page = client.post("/return/scan", data={"code": "BOX-BXAAAA"}, headers=HX)
    assert b"not rented out" in page.data
    page = client.get("/return")
    assert b"Put Basler" not in page.data


# Item pages


def test_item_page_and_rent_button(client, db, user, login, camera):
    page = client.get("/i/CAMAAA")
    assert b"Available" in page.data
    assert b"Scan your card" in page.data

    login(user)
    assert b"Rent this item" in client.get("/i/camaaa").data
    response = client.post("/i/CAMAAA/rent")
    assert response.headers["Location"] == "/me"
    assert camera.open_rental.user == user
    assert b"Rented by you" in client.get("/i/CAMAAA").data


def test_trashed_item_page_is_404(client, db, camera):
    camera.deleted_at = camera.created_at
    db.session.commit()
    assert client.get("/i/CAMAAA").status_code == 404


def test_public_item_list(client, db, camera, cable):
    page = client.get("/items?q=basler").data
    assert b"Basler ace #5" in page
    assert b"USB-C cable" not in page


def test_me_lists_rentals(client, db, signed_in, camera):
    rent_items(signed_in, [camera])
    page = client.get("/me").data
    assert b"Basler ace #5" in page
    assert b"Shelf B3, box 05" in page


# Admin rentals


def test_admin_force_return_view(client, db, user, make_user, login, camera):
    [rental] = rent_items(user, [camera])
    admin = make_user(is_admin=True, name="Admin")
    login(admin)
    assert b"Basler ace #5" in client.get("/admin/rentals").data
    client.post(f"/admin/rentals/{rental.id}/return")
    assert rental.returned_by == admin
    assert b"by admin Admin" in client.get("/admin/rentals").data


def test_only_admins_see_who_rented_an_item(client, db, make_user, login, camera):
    rent_items(make_user(name="Bob"), [camera])
    page = client.get("/i/CAMAAA").data
    assert b"Rented out" in page and b"Bob" not in page

    login(make_user())
    page = client.get("/i/CAMAAA").data
    assert b"Rented out" in page and b"Bob" not in page

    login(make_user(is_admin=True))
    assert b"Rented by Bob" in client.get("/i/CAMAAA").data
