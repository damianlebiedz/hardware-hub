"""Business logic for hardware rentals.

This module is the single source of truth for the rental state machine.
All status-transition rules are enforced here — at the service / transaction
level — so they apply regardless of how the service is called (HTTP endpoint,
CLI script, test fixture, etc.).

State transitions
-----------------
* ``Available``  → ``In Use``   (via :func:`rent_hardware`)
* ``In Use``     → ``Available`` (via :func:`return_hardware`)
* ``Repair``     → blocked from rental; Admin must reset via the hardware
                   CRUD endpoint.

Raises:
    fastapi.HTTPException: 404 when the referenced entity does not exist.
    fastapi.HTTPException: 409 when a rental guard condition is violated
        (hardware is ``'Repair'`` or ``'In Use'``).
    fastapi.HTTPException: 400 when a return is attempted on a rental that
        has already been closed.
"""

import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models import Hardware, Rental, User

# ---------------------------------------------------------------------------
# Rent
# ---------------------------------------------------------------------------


def rent_hardware(db: Session, user_id: int, hardware_id: int) -> Rental:
    """Create a rental record and mark the hardware item as ``'In Use'``.

    This function performs all validation and the state transition inside a
    single database transaction.  If any guard fails the transaction is left
    untouched.

    Args:
        db: Active SQLAlchemy session (injected via ``Depends(get_db)``).
        user_id: Primary key of the user initiating the rental.
        hardware_id: Primary key of the hardware item being rented.

    Returns:
        The newly created :class:`~backend.models.Rental` ORM instance,
        populated with its auto-assigned ``id`` and ``rented_at`` timestamp.

    Raises:
        HTTPException (404): If ``user_id`` or ``hardware_id`` does not exist.
        HTTPException (409): If the hardware status is ``'Repair'`` — the item
            cannot be rented until an admin clears the repair flag.
        HTTPException (409): If the hardware status is ``'In Use'`` — the item
            is already checked out by another user.

    Example:
        >>> rental = rent_hardware(db, user_id=1, hardware_id=3)
        >>> rental.hardware.status
        'In Use'
    """
    user: User | None = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id={user_id} not found.",
        )

    hardware: Hardware | None = db.get(Hardware, hardware_id)
    if hardware is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hardware with id={hardware_id} not found.",
        )

    # ── STRICT GUARDS ──────────────────────────────────────────────────────
    if hardware.status == "Repair":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Hardware '{hardware.name}' (id={hardware_id}) is currently under "
                "repair and cannot be rented."
            ),
        )

    if hardware.status == "In Use":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Hardware '{hardware.name}' (id={hardware_id}) is already in use "
                "and cannot be rented."
            ),
        )
    # ───────────────────────────────────────────────────────────────────────

    hardware.status = "In Use"
    rental: Rental = Rental(user_id=user_id, hardware_id=hardware_id)
    db.add(rental)
    db.commit()
    db.refresh(rental)
    return rental


# ---------------------------------------------------------------------------
# Return
# ---------------------------------------------------------------------------


def return_hardware(db: Session, rental_id: int) -> Rental:
    """Close an active rental and reset the hardware status to ``'Available'``.

    Args:
        db: Active SQLAlchemy session.
        rental_id: Primary key of the :class:`~backend.models.Rental` to close.

    Returns:
        The updated :class:`~backend.models.Rental` instance with
        ``returned_at`` set to the current UTC time.

    Raises:
        HTTPException (404): If no rental with ``rental_id`` exists.
        HTTPException (400): If the rental has already been returned
            (``returned_at`` is not ``None``).

    Example:
        >>> closed = return_hardware(db, rental_id=7)
        >>> closed.returned_at is not None
        True
        >>> closed.hardware.status
        'Available'
    """
    rental: Rental | None = db.get(Rental, rental_id)
    if rental is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rental with id={rental_id} not found.",
        )

    if rental.returned_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rental id={rental_id} has already been returned.",
        )

    rental.returned_at = datetime.datetime.utcnow()
    rental.hardware.status = "Available"
    db.commit()
    db.refresh(rental)
    return rental
