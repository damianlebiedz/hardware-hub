"""Rentals router for Hardware Hub.

Exposes three endpoints:

* ``POST /api/rentals/rent``   — check out a hardware item to a user.
* ``POST /api/rentals/return`` — check an item back in.
* ``GET  /api/rentals/my``     — list active rentals for a given user.

The rent and return endpoints delegate all business-logic and state-machine
guards to :mod:`backend.services.rental_service` so the HTTP layer remains
thin and the core rules remain testable without the HTTP stack.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Rental
from backend.schemas import RentalRead, RentRequest, ReturnRequest
from backend.services.rental_service import rent_hardware, return_hardware


router: APIRouter = APIRouter(prefix="/api/rentals", tags=["Rentals"])


@router.post(
    "/rent",
    response_model=RentalRead,
    status_code=status.HTTP_201_CREATED,
    summary="Rent a hardware item",
    responses={
        201: {"description": "Rental created; hardware status set to 'In Use'."},
        404: {"description": "User or hardware not found."},
        409: {"description": "Hardware is 'In Use' or 'Repair' and cannot be rented."},
    },
)
def rent(payload: RentRequest, db: Session = Depends(get_db)) -> Rental:
    """Check out a hardware item to a user.

    Delegates to :func:`~backend.services.rental_service.rent_hardware` which
    enforces the strict rental guards: the item must be ``'Available'`` for the
    operation to succeed.

    Args:
        payload: JSON body with ``user_id`` and ``hardware_id``.
        db: Injected SQLAlchemy session.

    Returns:
        The newly created :class:`~backend.schemas.RentalRead` record.

    Raises:
        HTTPException (404): If ``user_id`` or ``hardware_id`` does not exist.
        HTTPException (409): If the hardware is ``'Repair'`` or ``'In Use'``.
    """
    return rent_hardware(db=db, user_id=payload.user_id, hardware_id=payload.hardware_id)


@router.post(
    "/return",
    response_model=RentalRead,
    summary="Return a rented hardware item",
    responses={
        200: {"description": "Rental closed; hardware status reset to 'Available'."},
        400: {"description": "Rental has already been returned."},
        404: {"description": "Rental not found."},
    },
)
def return_item(payload: ReturnRequest, db: Session = Depends(get_db)) -> Rental:
    """Check a hardware item back in and mark it ``'Available'``.

    Delegates to :func:`~backend.services.rental_service.return_hardware`.

    Args:
        payload: JSON body with ``rental_id``.
        db: Injected SQLAlchemy session.

    Returns:
        The updated :class:`~backend.schemas.RentalRead` record with
        ``returned_at`` populated.

    Raises:
        HTTPException (404): If no rental with the given ID exists.
        HTTPException (400): If the rental has already been closed.
    """
    return return_hardware(db=db, rental_id=payload.rental_id)


@router.get(
    "/my",
    response_model=List[RentalRead],
    summary="Get active rentals for a user",
)
def my_rentals(
    user_id: int = Query(..., description="Primary key of the user whose active rentals to fetch."),
    db: Session = Depends(get_db),
) -> List[Rental]:
    """Return all currently active (not yet returned) rentals for a given user.

    A rental is considered *active* when its ``returned_at`` column is
    ``NULL``.  Closed rentals are intentionally excluded so the frontend
    'My Rentals' view only shows items the user currently has checked out.

    Args:
        user_id: Query parameter identifying the requesting user.
        db: Injected SQLAlchemy session.

    Returns:
        List of :class:`~backend.schemas.RentalRead` objects with
        ``returned_at == None``.
    """
    return (
        db.query(Rental)
        .filter(Rental.user_id == user_id, Rental.returned_at.is_(None))
        .all()
    )
