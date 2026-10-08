import io
import json
from datetime import UTC, datetime, timedelta

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models import Comment, Container, Item, Rental, User
from app.services.backup import backup_files, write_backup
from app.services.transfer import TransferError, export_data, import_data

T0 = datetime(2026, 9, 1, 8, 30, tzinfo=UTC)


@pytest.fixture
def seeded(db):
    admin = User(card_number="111111", email="admin@aau.dk", study_number="20001111",
                 name="Admin", is_admin=True, created_at=T0)
    alice = User(card_number="222222", email="alice@student.aau.dk", study_number="20202222",
                 created_at=T0)
    box = Container(code="BXAAAA", name="Shelf B3, box 05", description="Top shelf",
                    created_at=T0, updated_at=T0)
    camera = Item(code="CAMAAA", name="Basler ace", number=5, category="Camera",
                  container=box, length_mm=60, width_mm=29, height_mm=29,
                  created_at=T0, updated_at=T0)
    cable = Item(code="CABAAA", name="USB-C cable", created_at=T0, updated_at=T0)
    old = Item(code="ZZZAAA", name="Old tripod", created_at=T0, updated_at=T0,
               deleted_at=T0 + timedelta(days=3))
    db.session.add_all([
        admin, alice, box, camera, cable, old,
        Rental(item=camera, user=alice, rented_at=T0 + timedelta(hours=1),
               returned_at=T0 + timedelta(hours=5)),
        Rental(item=old, user=alice, rented_at=T0, returned_at=T0 + timedelta(days=1),
               returned_by=admin),
        Rental(item=camera, user=alice, rented_at=T0 + timedelta(days=2)),
        Comment(item=camera, user=alice, text="Lens cap missing", created_at=T0),
    ])
    db.session.commit()
    return admin


def without_timestamp(data):
    return {k: v for k, v in data.items() if k != "exported_at"}


@pytest.fixture
def other_app(tmp_path):
    """A second, separate database: "another computer"."""
    class OtherConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'other.db'}"

    other = create_app(OtherConfig)
    with other.app_context():
        _db.create_all()
    return other


def test_round_trip_to_another_database(app, seeded, other_app):
    exported = export_data()
    assert exported["schema_version"] == 1
    assert [u["card_number"] for u in exported["users"]] == ["111111", "222222"]
    json.dumps(exported)  # must be plain JSON

    with other_app.app_context():
        counts = import_data(json.loads(json.dumps(exported)), "replace")
        assert counts == {"users": 2, "containers": 1, "items": 3, "rentals": 3,
                          "comments": 1}
        assert without_timestamp(export_data()) == without_timestamp(exported)
        camera = _db.session.execute(_db.select(Item).filter_by(code="CAMAAA")).scalar_one()
        assert camera.container.name == "Shelf B3, box 05"
        assert camera.open_rental.user.card_number == "222222"
        assert camera.created_at == T0


def test_replace_removes_everything_else(db, seeded):
    exported = export_data()
    db.session.add(Item(code="EXTRAA", name="Extra"))
    db.session.commit()
    import_data(exported, "replace")
    assert Item.query.filter_by(code="EXTRAA").first() is None
    assert without_timestamp(export_data()) == without_timestamp(exported)


def test_merge_adds_and_updates_but_never_deletes(db, seeded):
    exported = export_data()
    db.session.add(Item(code="EXTRAA", name="Extra"))
    db.session.commit()
    exported["items"][0]["name"] = "Basler ace 2"  # CABAAA is first by code
    exported["items"].append({**exported["items"][1], "code": "NEWAAA", "container": None})

    import_data(exported, "merge")
    import_data(exported, "merge")  # merging twice changes nothing more

    assert Item.query.filter_by(code="EXTRAA").one()
    assert Item.query.filter_by(code="NEWAAA").one()
    assert Item.query.filter_by(code="CABAAA").one().name == "Basler ace 2"
    assert Rental.query.count() == 3
    assert Comment.query.count() == 1


@pytest.mark.parametrize("change, message", [
    (lambda d: d.update(schema_version=99), "not a rental system export"),
    (lambda d: d["items"][0].pop("name"), "missing the field 'name'"),
    (lambda d: d["rentals"][0].update(rented_at="yesterday"), "invalid date"),
    (lambda d: d["items"][0].update(container="NOPEAA"), "unknown container: NOPEAA"),
    (lambda d: d["rentals"][0].update(user="999999"), "unknown user: 999999"),
    (lambda d: [u.update(is_admin=False) for u in d["users"]], "no admins left"),
    (lambda d: d["users"][1].update(email="admin@aau.dk"), "could not be imported"),
])
def test_bad_files_change_nothing(db, seeded, change, message):
    before = export_data()
    data = json.loads(json.dumps(before))
    change(data)
    db.session.add(Item(code="EXTRAA", name="Extra"))
    db.session.commit()
    with pytest.raises(TransferError, match=message):
        import_data(data, "replace")
    assert Item.query.filter_by(code="EXTRAA").one()
    assert len(export_data()["items"]) == len(before["items"]) + 1


def test_merge_rejects_second_open_rental(db, seeded):
    data = export_data()
    # A different open rental for the camera, which already has one.
    data["rentals"].append({"item": "CAMAAA", "user": "111111",
                            "rented_at": T0.isoformat(), "returned_at": None,
                            "returned_by": None})
    with pytest.raises(TransferError, match="could not be imported"):
        import_data(data, "merge")
    assert Rental.query.count() == 3


# Backups


def test_backup_keeps_newest(tmp_path, db, seeded):
    for day in range(1, 6):
        (tmp_path / f"rental-2026-01-0{day}-000000.json").write_text("{}")
    newest = write_backup(tmp_path, keep=3)
    names = [p.name for p in backup_files(tmp_path)]
    assert names == [newest.name, "rental-2026-01-05-000000.json",
                     "rental-2026-01-04-000000.json"]
    assert json.loads(newest.read_text())["schema_version"] == 1


# CLI


def test_cli_export_import_backup(app, db, seeded, tmp_path):
    runner = app.test_cli_runner()
    path = tmp_path / "export.json"
    assert runner.invoke(args=["export", str(path)]).exit_code == 0
    exported = json.loads(path.read_text())

    db.session.add(Item(code="EXTRAA", name="Extra"))
    db.session.commit()
    result = runner.invoke(args=["import", str(path), "--mode", "replace"], input="n\n")
    assert result.exit_code != 0  # declined at the prompt
    assert Item.query.filter_by(code="EXTRAA").first()

    result = runner.invoke(args=["import", str(path), "--mode", "replace", "--yes"])
    assert result.exit_code == 0, result.output
    assert "3 items" in result.output
    assert without_timestamp(export_data()) == without_timestamp(exported)

    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    result = runner.invoke(args=["import", str(bad), "--mode", "merge"])
    assert result.exit_code != 0 and "not valid JSON" in result.output

    result = runner.invoke(args=["backup"])
    assert result.exit_code == 0
    assert len(backup_files(app.config["BACKUP_DIR"])) == 1


# Web


def test_web_export_and_import(client, db, seeded, login):
    login(seeded)
    response = client.get("/admin/data/export.json")
    assert response.headers["Content-Disposition"].startswith("attachment")
    exported = response.get_json()
    assert len(exported["items"]) == 3

    db.session.add(Item(code="EXTRAA", name="Extra"))
    db.session.commit()

    def upload(mode, confirm=None):
        form = {"mode": mode, "file": (io.BytesIO(json.dumps(exported).encode()), "e.json")}
        if confirm:
            form["confirm"] = confirm
        return client.post("/admin/data/import", data=form, follow_redirects=True)

    page = upload("replace")
    assert b"Tick the box" in page.data
    assert Item.query.filter_by(code="EXTRAA").first()

    page = upload("replace", confirm="yes")
    assert b"Imported 2 users, 1 container, 3 items, 3 rentals, 1 note." in page.data
    assert Item.query.filter_by(code="EXTRAA").first() is None
    # Still signed in as the same admin, even though database ids were rebuilt.
    assert client.get("/admin/").status_code == 200


def test_web_import_rejects_garbage(client, db, seeded, login):
    login(seeded)
    form = {"mode": "merge", "file": (io.BytesIO(b"\x00\xff not json"), "x.json")}
    page = client.post("/admin/data/import", data=form, follow_redirects=True)
    assert b"not a JSON export" in page.data


def test_web_backups(client, db, seeded, login, app):
    login(seeded)
    page = client.post("/admin/data/backups", follow_redirects=True)
    [path] = backup_files(app.config["BACKUP_DIR"])
    assert path.name.encode() in page.data
    response = client.get(f"/admin/data/backups/{path.name}")
    assert response.status_code == 200
    assert json.loads(response.data)["schema_version"] == 1
    assert client.get("/admin/data/backups/..%2Fsecret_key").status_code == 404
    assert client.get("/admin/data/backups/nope.json").status_code == 404
