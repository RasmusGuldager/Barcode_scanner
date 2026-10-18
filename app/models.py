import re
from datetime import UTC, datetime

from sqlalchemy import Connection, ForeignKey, Index, String, Text, UniqueConstraint, event, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    card_number: Mapped[str] = mapped_column(String(6), unique=True)
    name: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    study_number: Mapped[str] = mapped_column(String(8))
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    rentals: Mapped[list["Rental"]] = relationship(
        back_populates="user", foreign_keys="Rental.user_id"
    )

    @property
    def display_name(self) -> str:
        return self.name or self.email


class Container(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    item: Mapped["Item | None"] = relationship(back_populates="container")


class Category(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)

    fields: Mapped[list["SpecField"]] = relationship(
        back_populates="category", cascade="all, delete-orphan",
        order_by="SpecField.position",
    )
    products: Mapped[list["Product"]] = relationship(back_populates="category")


# Spec field kinds.
CHOICE = "choice"  # one of a fixed list of options, e.g. Global / Rolling
NUMBER = "number"  # a number with an optional unit, e.g. 60 fps
TEXT = "text"      # anything, e.g. the sensor name
KINDS = {CHOICE: "Choice", NUMBER: "Number", TEXT: "Text"}


def slugify(name: str) -> str:
    """The name as used in filter URLs: "Max FPS" -> "max_fps"."""
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")


class SpecField(db.Model):
    """A spec that products in one category have, e.g. "Shutter" for cameras."""

    __tablename__ = "spec_field"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(10))
    unit: Mapped[str | None] = mapped_column(String(20))  # numbers only
    position: Mapped[int] = mapped_column(default=0)  # order on forms and in lists

    category: Mapped[Category] = relationship(back_populates="fields")
    options: Mapped[list["SpecOption"]] = relationship(
        back_populates="field", cascade="all, delete-orphan", order_by="SpecOption.id"
    )

    __table_args__ = (UniqueConstraint("category_id", "name"),)

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def label(self) -> str:
        """The name with its unit, e.g. "Max frame rate (fps)"."""
        return f"{self.name} ({self.unit})" if self.unit else self.name


class SpecOption(db.Model):
    """One of the choices of a choice field, e.g. "Global"."""

    __tablename__ = "spec_option"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("spec_field.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(50))

    field: Mapped[SpecField] = relationship(back_populates="options")

    __table_args__ = (UniqueConstraint("field_id", "label"),)


class Product(db.Model):
    """A kind of equipment, e.g. "Basler ace". Each physical copy is an Item.

    Everything that is the same for all copies lives here: category, specs,
    description and size.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(Text)
    length_mm: Mapped[int | None]
    width_mm: Mapped[int | None]
    height_mm: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    category: Mapped[Category | None] = relationship(back_populates="products")
    items: Mapped[list["Item"]] = relationship(back_populates="product", order_by="Item.number")
    specs: Mapped[list["SpecValue"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    @property
    def active_items(self) -> list["Item"]:
        """The copies that are not in the trash."""
        return [item for item in self.items if not item.in_trash]

    def spec(self, field: SpecField) -> "SpecValue | None":
        # Compared by object, so values not yet saved (without ids) are found too.
        return next((s for s in self.specs if s.field is field), None)


class SpecValue(db.Model):
    """A product's value for one spec field. Missing means unknown."""

    __tablename__ = "spec_value"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), primary_key=True
    )
    field_id: Mapped[int] = mapped_column(
        ForeignKey("spec_field.id", ondelete="CASCADE"), primary_key=True
    )
    # Exactly one of these is set, depending on the field's kind.
    option_id: Mapped[int | None] = mapped_column(
        ForeignKey("spec_option.id", ondelete="CASCADE")
    )
    number: Mapped[float | None]
    text: Mapped[str | None] = mapped_column(String(200))

    product: Mapped[Product] = relationship(back_populates="specs")
    field: Mapped[SpecField] = relationship()
    option: Mapped[SpecOption | None] = relationship()

    @property
    def value(self) -> str | float | None:
        """The raw value: the option's label, the number or the text."""
        if self.field.kind == CHOICE:
            return self.option.label if self.option else None
        return self.number if self.field.kind == NUMBER else self.text

    def __str__(self) -> str:
        if self.field.kind == NUMBER and self.number is not None:
            number = f"{self.number:g}"
            return f"{number} {self.field.unit}" if self.field.unit else number
        return str(self.value or "")


class Item(db.Model):
    """One physical copy of a product, with its own QR label."""

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    # Tells the copies of a product apart: Basler ace #1, #2, ... Assigned automatically.
    number: Mapped[int]
    # Unique: a container holds exactly one item.
    container_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    # Set while the item is in the trash.
    deleted_at: Mapped[datetime | None]

    product: Mapped[Product] = relationship(back_populates="items")
    container: Mapped[Container | None] = relationship(back_populates="item")
    rentals: Mapped[list["Rental"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    open_rental: Mapped["Rental | None"] = relationship(
        primaryjoin="and_(Rental.item_id == Item.id, Rental.returned_at.is_(None))",
        viewonly=True,
    )

    __table_args__ = (UniqueConstraint("product_id", "number"),)

    @property
    def display_name(self) -> str:
        return f"{self.product.name} #{self.number}"

    @property
    def in_trash(self) -> bool:
        return self.deleted_at is not None


def next_item_number(connection: Connection, product_id: int) -> int:
    """The next free number for a copy of the product. Trashed items count too,
    so restoring one never causes a clash."""
    highest = connection.execute(
        select(func.max(Item.number)).where(Item.product_id == product_id)
    ).scalar()
    return (highest or 0) + 1


@event.listens_for(Item, "before_insert")
def _assign_number(mapper, connection: Connection, item: Item) -> None:
    # Flush after adding each copy when adding several, so each one sees the
    # numbers given to the ones before it.
    if item.number is None:
        item.number = next_item_number(connection, item.product_id)


class Rental(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    rented_at: Mapped[datetime] = mapped_column(default=utcnow)
    returned_at: Mapped[datetime | None]
    # The admin who force-returned the item, if it wasn't returned by the renter.
    returned_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))

    item: Mapped[Item] = relationship(back_populates="rentals")
    user: Mapped[User] = relationship(back_populates="rentals", foreign_keys=[user_id])
    returned_by: Mapped[User | None] = relationship(foreign_keys=[returned_by_id])

    __table_args__ = (
        # At most one open rental per item, enforced by the database.
        Index(
            "uq_rental_open_item",
            "item_id",
            unique=True,
            sqlite_where=db.text("returned_at IS NULL"),
        ),
    )


class Comment(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    item: Mapped[Item] = relationship(back_populates="comments")
    user: Mapped[User] = relationship()
