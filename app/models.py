from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, String, Text
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


class Item(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    number: Mapped[int | None]
    category: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    # Unique: a container holds exactly one item.
    container_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), unique=True
    )
    length_mm: Mapped[int | None]
    width_mm: Mapped[int | None]
    height_mm: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    # Set while the item is in the trash.
    deleted_at: Mapped[datetime | None]

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

    @property
    def display_name(self) -> str:
        return f"{self.name} #{self.number}" if self.number is not None else self.name

    @property
    def in_trash(self) -> bool:
        return self.deleted_at is not None


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
