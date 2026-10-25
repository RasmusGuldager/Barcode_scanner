"""Random codes for items and containers.

A code is made once, when the record is created, and never changes. The QR label
holds the code with a prefix (``VAP-K7F2Q8``); the database stores the code only.
"""

import secrets

from ..extensions import db
from ..models import Container, Item

# No 0/O or 1/I/L, so a code can be read and typed by hand.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 6

ITEM_PREFIX = "VAP-"
CONTAINER_PREFIX = "BOX-"


def new_code(model: type[Item] | type[Container]) -> str:
    """Return a random code that isn't used by any row of ``model`` yet."""
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        if not db.session.execute(db.select(model.id).filter_by(code=code)).first():
            return code
