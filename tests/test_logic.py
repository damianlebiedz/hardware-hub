"""Core business-logic tests for the rental service.

These tests exercise the three critical paths of the rental state machine
without any HTTP layer — the service functions are called directly against
an isolated, in-memory SQLite database so the tests are fast and hermetic.

Test matrix
-----------
1. ``test_successful_rent``        — renting ``Available`` hardware succeeds.
2. ``test_rent_repair_gear_fails`` — renting ``Repair`` hardware raises HTTP 409.
3. ``test_rent_in_use_gear_fails`` — renting ``In Use`` hardware raises HTTP 409.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base
from backend.models import Hardware, User
from backend.services.rental_service import rent_hardware

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db() -> Session:  # type: ignore[return]
    """Provide a fresh, in-memory SQLite session for each test function.

    Yields:
        Session: A database session wired to a temporary in-memory SQLite
            database.  The database is discarded after each test.
    """
    engine: Engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession: sessionmaker[Session] = sessionmaker(
        bind=engine, autocommit=False, autoflush=False
    )
    session: Session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def seeded_db(db: Session) -> dict[str, int]:
    """Seed the in-memory database with one user and three hardware items.

    Hardware items cover all three status values so that every test can pick
    the one matching its scenario without duplication.

    Args:
        db: The in-memory session provided by the ``db`` fixture.

    Returns:
        A dict mapping ``'user_id'``, ``'available_id'``, ``'repair_id'``,
        and ``'in_use_id'`` to the auto-assigned primary keys.
    """
    user = User(email="alice@example.com", role="user")
    hw_available = Hardware(name="ThinkPad X1", brand="Lenovo", status="Available")
    hw_repair = Hardware(name="MacBook Pro", brand="Apple", status="Repair")
    hw_in_use = Hardware(name="Dell XPS", brand="Dell", status="In Use")

    db.add_all([user, hw_available, hw_repair, hw_in_use])
    db.commit()

    return {
        "user_id": user.id,
        "available_id": hw_available.id,
        "repair_id": hw_repair.id,
        "in_use_id": hw_in_use.id,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_successful_rent(db: Session, seeded_db: dict[str, int]) -> None:
    """Renting an ``Available`` item creates a rental and marks it ``In Use``.

    Verifies:
        - A :class:`~backend.models.Rental` row is created with the correct
          ``user_id`` and ``hardware_id``.
        - The hardware ``status`` is mutated to ``'In Use'`` within the same
          transaction.
        - ``returned_at`` is ``None`` on the new rental (still active).
    """
    rental = rent_hardware(
        db=db,
        user_id=seeded_db["user_id"],
        hardware_id=seeded_db["available_id"],
    )

    assert rental.id is not None, "Rental should have been persisted with a PK."
    assert rental.user_id == seeded_db["user_id"]
    assert rental.hardware_id == seeded_db["available_id"]
    assert rental.returned_at is None, "A fresh rental should have no return timestamp."

    db.refresh(rental.hardware)
    assert (
        rental.hardware.status == "In Use"
    ), "Hardware status must be updated to 'In Use' upon successful rental."


def test_rent_repair_gear_fails(db: Session, seeded_db: dict[str, int]) -> None:
    """Renting hardware whose status is ``'Repair'`` must raise HTTP 409.

    This is a hard business-logic guard: items under repair are unavailable
    regardless of who is requesting them.

    Verifies:
        - An :class:`fastapi.HTTPException` is raised.
        - The status code is ``409 Conflict``.
        - The hardware status remains ``'Repair'`` (no mutation on failure).
    """
    with pytest.raises(HTTPException) as exc_info:
        rent_hardware(
            db=db,
            user_id=seeded_db["user_id"],
            hardware_id=seeded_db["repair_id"],
        )

    assert exc_info.value.status_code == 409, "Renting 'Repair' gear must return HTTP 409 Conflict."

    hw = db.get(Hardware, seeded_db["repair_id"])
    assert hw is not None
    assert hw.status == "Repair", "Hardware status must not change on a failed rent."


def test_rent_in_use_gear_fails(db: Session, seeded_db: dict[str, int]) -> None:
    """Renting hardware whose status is ``'In Use'`` must raise HTTP 409.

    Verifies that double-booking is prevented at the service level.

    Verifies:
        - An :class:`fastapi.HTTPException` is raised.
        - The status code is ``409 Conflict``.
        - The hardware status remains ``'In Use'`` (no mutation on failure).
    """
    with pytest.raises(HTTPException) as exc_info:
        rent_hardware(
            db=db,
            user_id=seeded_db["user_id"],
            hardware_id=seeded_db["in_use_id"],
        )

    assert exc_info.value.status_code == 409, "Renting 'In Use' gear must return HTTP 409 Conflict."

    hw = db.get(Hardware, seeded_db["in_use_id"])
    assert hw is not None
    assert hw.status == "In Use", "Hardware status must not change on a failed rent."
