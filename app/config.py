import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))


def _secret_key() -> str:
    """Read SECRET_KEY from the environment, or from a file created on first run.

    The key must be the same for every gunicorn worker and survive restarts,
    otherwise users get logged out.
    """
    if key := os.environ.get("SECRET_KEY"):
        return key
    key_file = DATA_DIR / "secret_key"
    if not key_file.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'rental.db'}"
    )
    BACKUP_DIR = DATA_DIR / "backups"
    SESSION_COOKIE_SAMESITE = "Lax"
    # Users stay identified on their own phone for a long time.
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 180

    def __init__(self):
        self.SECRET_KEY = _secret_key()


class TestConfig:
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    BACKUP_DIR = None  # set per test
