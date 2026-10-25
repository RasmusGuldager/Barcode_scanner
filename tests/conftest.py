import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models import User


@pytest.fixture
def app(tmp_path):
    app = create_app(TestConfig)
    app.config["BACKUP_DIR"] = tmp_path / "backups"
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(db):
    counter = iter(range(100_000, 999_999))

    def make(**fields) -> User:
        n = next(counter)
        user = User(
            card_number=fields.pop("card_number", str(n)),  # 6 digits
            email=fields.pop("email", f"user{n}@example.com"),
            study_number=fields.pop("study_number", str(20_000_000 + n)),  # 8 digits
            **fields,
        )
        db.session.add(user)
        db.session.commit()
        return user

    return make


@pytest.fixture
def login(client):
    def login_as(user: User) -> None:
        with client.session_transaction() as session:
            session["user_id"] = user.id

    return login_as
