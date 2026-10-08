"""Searching the inventory, shared by the public and the admin item lists."""

from dataclasses import dataclass

from flask import Request
from sqlalchemy import or_

from ..extensions import db
from ..models import Container, Item

# Sort key -> column. Ties are broken by name and number.
SORTS = {
    "name": Item.name,
    "code": Item.code,
    "category": Item.category,
    "container": Container.name,
    "length": Item.length_mm,
    "width": Item.width_mm,
    "height": Item.height_mm,
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
        stmt = db.select(Item).outerjoin(Item.container).where(Item.deleted_at.is_(None))
        if self.q:
            pattern = f"%{self.q}%"
            stmt = stmt.where(
                or_(
                    Item.name.ilike(pattern),
                    Item.code.ilike(pattern),
                    Item.category.ilike(pattern),
                    Item.description.ilike(pattern),
                    Container.name.ilike(pattern),
                )
            )
        if self.category:
            stmt = stmt.where(Item.category == self.category)
        if self.container == "with":
            stmt = stmt.where(Item.container_id.is_not(None))
        elif self.container == "without":
            stmt = stmt.where(Item.container_id.is_(None))

        column = SORTS[self.sort]
        # Empty values (e.g. unknown size) always go last.
        order = (column.desc() if self.descending else column.asc()).nulls_last()
        return db.session.execute(stmt.order_by(order, Item.name, Item.number)).scalars().all()


def categories() -> list[str]:
    return list(
        db.session.execute(
            db.select(Item.category)
            .where(Item.category.is_not(None), Item.deleted_at.is_(None))
            .distinct()
            .order_by(Item.category)
        ).scalars()
    )
