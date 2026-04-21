"""SQLAlchemy ORM models for Hardware Hub.

Defines the three core entities — ``User``, ``Hardware``, and ``Rental`` —
that map directly to the SQLite tables described in ARCHITECTURE.md §2.
Relationships are declared bidirectionally so that SQLAlchemy can navigate
the object graph in both directions without extra queries.
"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class User(Base):
    """Represents an internal company user who can rent hardware.

    Attributes:
        id: Auto-incremented primary key.
        email: Unique email address used as the login identifier.
        role: Either ``'admin'`` (full access) or ``'user'`` (self-service only).
        password_hash: Bcrypt hash used for password verification.
        rentals: Back-populated list of ``Rental`` records for this user.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    rentals: Mapped[list[Rental]] = relationship(
        "Rental", back_populates="user", cascade="all, delete-orphan"
    )


class Hardware(Base):
    """Represents a physical piece of company equipment.

    The ``status`` column acts as the core state-machine flag.  Valid values
    are ``'Available'``, ``'In Use'``, and ``'Repair'``.  Rental service
    functions enforce allowed transitions at the transaction level.

    Attributes:
        id: Auto-incremented primary key.
        name: Human-readable device name (e.g. ``'MacBook Pro 14"'``).
        brand: Manufacturer / brand (e.g. ``'Apple'``).
        purchase_date: ISO-8601 date the item was acquired.
        status: Current availability state of the item.
        notes: Free-text field for additional context (damage notes, etc.).
        rentals: Back-populated list of ``Rental`` records for this item.
    """

    __tablename__ = "hardware"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    purchase_date: Mapped[datetime.date | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="Available", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    rentals: Mapped[list[Rental]] = relationship(
        "Rental", back_populates="hardware", cascade="all, delete-orphan"
    )


class Rental(Base):
    """Represents a single check-out event linking a ``User`` to a ``Hardware`` item.

    A rental is considered *active* while ``returned_at`` is ``NULL``.  The
    return service sets ``returned_at`` and resets the hardware status to
    ``'Available'`` inside the same transaction.

    Attributes:
        id: Auto-incremented primary key.
        user_id: Foreign key referencing ``users.id``.
        hardware_id: Foreign key referencing ``hardware.id``.
        rented_at: UTC timestamp recorded automatically when the row is created.
        returned_at: UTC timestamp set when the item is returned; ``NULL`` if
            still active.
        user: Relationship to the owning ``User``.
        hardware: Relationship to the associated ``Hardware`` item.
    """

    __tablename__ = "rentals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    hardware_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hardware.id"), nullable=False, index=True
    )
    rented_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    returned_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="rentals")
    hardware: Mapped[Hardware] = relationship("Hardware", back_populates="rentals")
