"""Searching the inventory for the admin pages."""

import difflib
from dataclasses import dataclass

from flask import Request
from sqlalchemy import or_

from ..extensions import db
from ..models import Category, Container, Item, Product

# Sort key -> column. Ties are broken by name and number.
SORTS = {
    "name": Product.name,
    "code": Item.code,
    "category": Category.name,
    "container": Container.name,
    "length": Product.length_mm,
    "width": Product.width_mm,
    "height": Product.height_mm,
}


@dataclass
class ItemSearch:
    q: str = ""
    category: str = ""
    container: str = ""  # "", "with" or "without"
    sort: str = "name"
    descending: bool = False

    @classmethod
    def from_request(cls, request: Request) -> "ItemSearch":
        sort = request.args.get("sort", "name")
        return cls(
            q=request.args.get("q", "").strip(),
            category=request.args.get("category", ""),
            container=request.args.get("container", ""),
            sort=sort if sort in SORTS else "name",
            descending=request.args.get("dir") == "desc",
        )

    def run(self) -> list[Item]:
        stmt = (
            db.select(Item)
            .join(Item.product)
            .outerjoin(Product.category)
            .outerjoin(Item.container)
            .where(Item.deleted_at.is_(None))
        )
        if self.q:
            pattern = f"%{self.q}%"
            stmt = stmt.where(
                or_(
                    Product.name.ilike(pattern),
                    Item.code.ilike(pattern),
                    Category.name.ilike(pattern),
                    Product.description.ilike(pattern),
                    Container.name.ilike(pattern),
                )
            )
        if self.category:
            stmt = stmt.where(Category.name == self.category)
        if self.container == "with":
            stmt = stmt.where(Item.container_id.is_not(None))
        elif self.container == "without":
            stmt = stmt.where(Item.container_id.is_(None))

        column = SORTS[self.sort]
        # Empty values (e.g. unknown size) always go last.
        order = (column.desc() if self.descending else column.asc()).nulls_last()
        return db.session.execute(stmt.order_by(order, Product.name, Item.number)).scalars().all()


def categories() -> list[Category]:
    return db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()


def similar_products(query: str, limit: int = 6) -> list[Product]:
    """Existing products with a name like ``query``, best matches first.

    Names containing the query come first, then names that are merely close
    (typos such as "Balser"). Used while typing the name of a new product.
    """
    query = query.strip().casefold()
    if len(query) < 2:
        return []
    products = db.session.execute(db.select(Product)).scalars().all()

    def score(product: Product) -> float:
        name = product.name.casefold()
        if name == query:
            return 3
        if query in name:
            return 2
        return difflib.SequenceMatcher(None, query, name).ratio()

    ranked = sorted((p for p in products if score(p) >= 0.6), key=score, reverse=True)
    return ranked[:limit]
