from datetime import UTC, datetime

from app.models import Container, Item, Product
from app.services.labels import label_text, qr_svg


def test_label_text_has_prefix():
    assert label_text(Item(code="K7F2Q8")) == "VAP-K7F2Q8"
    assert label_text(Container(code="M4T9XC")) == "BOX-M4T9XC"


def test_qr_is_regular_version_1():
    svg = qr_svg("VAP-K7F2Q8")
    # Version 1 is 21 modules, plus a 2-module border on each side.
    assert 'viewBox="0 0 25 25"' in svg


def test_label_sheet(client, db, make_user, login):
    login(make_user(is_admin=True))
    box = Container(code="M4T9XC", name="Shelf B3, box 05")
    item = Item(code="K7F2Q8", product=Product(name="Basler ace"), number=5)
    trashed = Item(code="TRASH1", product=Product(name="Old"), deleted_at=datetime.now(UTC))
    db.session.add_all([box, item, trashed])
    db.session.commit()

    assert client.get("/admin/labels").status_code == 200
    page = client.get(
        f"/admin/labels/print?item={item.id}&item={trashed.id}&container={box.id}"
    ).get_data(as_text=True)
    assert "VAP-K7F2Q8" in page
    assert "Basler ace #5" in page
    assert "BOX-M4T9XC" in page
    assert "VAP-TRASH1" not in page
    assert page.count("<svg") == 2
