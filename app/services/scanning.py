"""Turn scanned or typed text into an item or container."""

import re

from ..extensions import db
from ..models import Container, Item
from .codes import ALPHABET, CONTAINER_PREFIX, ITEM_PREFIX, LENGTH

CARD_NUMBER = re.compile(r"\d{6}")
_CODE = re.compile(f"[{ALPHABET}]{{{LENGTH}}}")


class ScanError(Exception):
    """A scan that can't be used. The message is shown to the user."""


def normalize_card_number(text: str) -> str:
    card = text.strip()
    if not CARD_NUMBER.fullmatch(card):
        raise ScanError("That is not an AAU card number. It should be 6 digits.")
    return card


def find_label(text: str) -> Item | Container:
    """Look up the item or container a label (or a typed code) refers to.

    Scanned labels have a prefix (``VAP-K7F2Q8``). A code typed by hand may leave
    it out; then items are tried before containers.
    """
    text = text.strip().upper().replace(" ", "")
    if text.startswith(ITEM_PREFIX):
        models, code = [Item], text.removeprefix(ITEM_PREFIX)
    elif text.startswith(CONTAINER_PREFIX):
        models, code = [Container], text.removeprefix(CONTAINER_PREFIX)
    else:
        models, code = [Item, Container], text
    if not _CODE.fullmatch(code):
        raise ScanError("This code is not part of the VAP-LAB rental system.")

    for model in models:
        found = db.session.execute(
            db.select(model).filter_by(code=code)
        ).scalar_one_or_none()
        if found is not None and not (isinstance(found, Item) and found.in_trash):
            return found
    raise ScanError(f"No item or container has the code {code}.")


def find_item(text: str) -> Item:
    found = find_label(text)
    if not isinstance(found, Item):
        raise ScanError("That is a container label. Scan the label on the item itself.")
    return found
