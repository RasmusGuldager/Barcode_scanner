"""The public item list: products filtered by category, availability and specs.

Filters live in the URL, so a filtered list can be bookmarked and shared, e.g.
``/items?category=Camera&shutter=Global&max_frame_rate_min=60``:

- choice fields: ``<slug>=<option>``, repeated for several options (any of them)
- number fields: ``<slug>_min`` and ``<slug>_max``
- ``available=0`` also shows products with no copy available right now

The inventory is small (tens of products), so filtering is done in Python.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import CHOICE, NUMBER, Category, Item, Product, SpecField, SpecValue
from .specs import parse_number

# Query parameters that a spec field's slug must not use.
RESERVED = {"q", "category", "available"}


@dataclass
class SpecFilter:
    field: SpecField
    options: list[str] = field(default_factory=list)  # choice: any of these labels
    low: float | None = None  # number: at least
    high: float | None = None  # number: at most

    @property
    def active(self) -> bool:
        return bool(self.options) or self.low is not None or self.high is not None

    def test(self, product: Product) -> bool | None:
        """Whether the product matches, or None if its value is unknown."""
        spec = product.spec(self.field)
        if self.field.kind == CHOICE:
            if spec is None or spec.option is None:
                return None
            return spec.option.label in self.options
        if spec is None or spec.number is None:
            return None
        return (self.low is None or spec.number >= self.low) and (
            self.high is None or spec.number <= self.high
        )


@dataclass
class ProductRow:
    product: Product
    available: int  # copies not rented out
    total: int  # copies not in the trash


@dataclass
class ProductSearch:
    q: str = ""
    category: Category | None = None
    available_only: bool = True
    filters: list[SpecFilter] = field(default_factory=list)

    @classmethod
    def from_args(cls, args) -> "ProductSearch":
        category = db.session.execute(
            db.select(Category).filter_by(name=args.get("category", ""))
        ).scalar_one_or_none()
        filters = []
        for spec_field in category.fields if category else []:
            if spec_field.kind == CHOICE:
                filters.append(SpecFilter(spec_field, options=args.getlist(spec_field.slug)))
            elif spec_field.kind == NUMBER:
                filters.append(SpecFilter(
                    spec_field,
                    low=_number(args.get(f"{spec_field.slug}_min")),
                    high=_number(args.get(f"{spec_field.slug}_max")),
                ))
        return cls(
            q=args.get("q", "").strip(),
            category=category,
            # The checkbox comes after a hidden "0", so the last value wins.
            # Without either (a plain link), only available products are shown.
            available_only=(args.getlist("available") or ["1"])[-1] != "0",
            filters=filters,
        )

    @property
    def active_filters(self) -> list[SpecFilter]:
        return [f for f in self.filters if f.active]

    def filter_for(self, spec_field: SpecField) -> SpecFilter | None:
        return next((f for f in self.filters if f.field.id == spec_field.id), None)

    def run(self) -> tuple[list[ProductRow], int]:
        """The matching products, and how many more were left out only because a
        filtered spec is unknown for them."""
        stmt = db.select(Product).options(
            selectinload(Product.items).selectinload(Item.open_rental),
            selectinload(Product.specs).selectinload(SpecValue.option),
            selectinload(Product.category),
        )
        if self.category:
            stmt = stmt.where(Product.category_id == self.category.id)
        products = db.session.execute(stmt).scalars().all()

        rows, unknown = [], 0
        for product in sorted(products, key=lambda p: p.name.casefold()):
            items = product.active_items
            available = sum(1 for item in items if item.open_rental is None)
            if not items or (self.available_only and not available):
                continue
            if self.q and not self._matches_text(product):
                continue
            results = [f.test(product) for f in self.active_filters]
            if False in results:
                continue
            if None in results:
                unknown += 1
                continue
            rows.append(ProductRow(product, available, len(items)))
        return rows, unknown

    def _matches_text(self, product: Product) -> bool:
        words = [product.name, product.description or ""]
        if product.category:
            words.append(product.category.name)
        words += [str(spec) for spec in product.specs]
        text = " ".join(words).casefold()
        return all(word in text for word in self.q.casefold().split())


def _number(raw: str | None) -> float | None:
    try:
        return parse_number(raw) if raw else None
    except ValueError:
        return None  # ignore what isn't a number, like an empty filter
