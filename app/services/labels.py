"""QR codes for item and container labels."""

import segno
from markupsafe import Markup

from ..models import Container, Item
from .codes import CONTAINER_PREFIX, ITEM_PREFIX


def label_text(thing: Item | Container) -> str:
    """What the QR code holds, e.g. ``VAP-K7F2Q8`` or ``BOX-M4T9XC``."""
    prefix = ITEM_PREFIX if isinstance(thing, Item) else CONTAINER_PREFIX
    return prefix + thing.code


def qr_svg(text: str) -> Markup:
    """An inline SVG QR code that scales to the size of its CSS box.

    micro=False: segno would otherwise pick Micro QR for short texts, which most
    phone and browser scanners can't read. Our texts fit in the smallest regular
    QR code (21x21 modules, alphanumeric mode).
    """
    qr = segno.make(text, error="m", micro=False)
    return Markup(qr.svg_inline(scale=1, border=2, omitsize=True, svgclass="qr"))
