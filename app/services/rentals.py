"""The rules for renting and returning items."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Container, Item, Rental, User


class RentalError(Exception):
    """A rent or return that isn't allowed. The message is shown to the user."""


def check_rentable(item: Item) -> None:
    if item.in_trash:
        raise RentalError(f"{item.display_name} is not available.")
    if item.open_rental is not None:
        # Don't name the renter: only admins may see who has an item.
        raise RentalError(f"{item.display_name} is already rented out.")


def rent_items(user: User, items: list[Item]) -> list[Rental]:
    """Rent all ``items`` to ``user``, or none of them if any can't be rented."""
    if not items:
        raise RentalError("Scan at least one item first.")
    for item in items:
        db.session.refresh(item)  # pick up rentals made since the item was scanned
        check_rentable(item)
    rentals = [Rental(item=item, user=user) for item in items]
    db.session.add_all(rentals)
    try:
        db.session.commit()
    except IntegrityError:
        # Someone else rented one of them at the same moment.
        db.session.rollback()
        raise RentalError("One of the items was just rented by someone else. Try again.")
    return rentals


def open_rental_for(user: User, item: Item) -> Rental:
    """The rental ``user`` has to close to return ``item``."""
    rental = item.open_rental
    if rental is None:
        raise RentalError(f"{item.display_name} is not rented out.")
    if rental.user_id != user.id:
        raise RentalError(
            f"{item.display_name} is rented by someone else. "
            "Only the person who rented it can return it."
        )
    return rental


def return_item(user: User, item: Item, container: Container | None) -> Rental:
    """Return ``item``. If it has a container, ``container`` must be that one."""
    rental = open_rental_for(user, item)
    if item.container is not None and container != item.container:
        raise RentalError(
            f"Wrong container. {item.display_name} belongs in {item.container.name}."
        )
    rental.returned_at = datetime.now(UTC)
    db.session.commit()
    return rental


def force_return(admin: User, rental: Rental) -> None:
    """An admin closes a rental, e.g. when the renter lost their card."""
    if rental.returned_at is not None:
        raise RentalError(f"{rental.item.display_name} has already been returned.")
    rental.returned_at = datetime.now(UTC)
    rental.returned_by = admin
    db.session.commit()
