"""Pydantic schemas for request validation and response serialisation.

Each ORM model has a corresponding family of schemas:

* ``<Model>Create``  — fields required when creating a new record (no ``id``).
* ``<Model>Read``    — full representation returned by the API (includes ``id``
                        and computed / relational fields).

``model_config = ConfigDict(from_attributes=True)`` is set on every *Read*
schema so that SQLAlchemy ORM instances can be passed directly to
``model.model_validate(orm_obj)`` without manual conversion.
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ── User ──────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Payload required to register a new user.

    Attributes:
        email: Valid email address; must be unique in the database.
        role: Access level — either ``'admin'`` or ``'user'``.
        password: Plain-text password accepted on creation and hashed before
            persistence.
    """

    email: EmailStr
    role: Literal["admin", "user"] = Field(default="user")
    password: str = Field(..., min_length=8)


class UserRead(BaseModel):
    """Full user representation returned by the API.

    Attributes:
        id: Auto-assigned primary key.
        email: Registered email address.
        role: Access level of the user.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str


# ── Hardware ───────────────────────────────────────────────────────────────────


class HardwareCreate(BaseModel):
    """Payload required to register a new hardware item.

    Attributes:
        name: Human-readable device name.
        brand: Manufacturer / brand name.
        purchase_date: Date of acquisition in ``YYYY-MM-DD`` format.
        status: Initial availability status; defaults to ``'Available'``.
        notes: Optional free-text notes (damage descriptions, serial numbers, etc.).
    """

    name: str = Field(..., min_length=1)
    brand: str | None = None
    purchase_date: datetime.date | None = None
    status: Literal["Available", "In Use", "Repair"] = Field(default="Available")
    notes: str | None = None


class HardwareUpdate(BaseModel):
    """Payload for partial hardware updates (e.g. toggling repair status).

    All fields are optional so callers only need to supply what has changed.

    Attributes:
        name: New device name.
        brand: New brand.
        purchase_date: Updated acquisition date.
        status: New status value.
        notes: Updated notes.
    """

    name: str | None = None
    brand: str | None = None
    purchase_date: datetime.date | None = None
    status: Literal["Available", "In Use", "Repair"] | None = None
    notes: str | None = None


class HardwareRead(BaseModel):
    """Full hardware representation returned by the API.

    Attributes:
        id: Auto-assigned primary key.
        name: Device name.
        brand: Manufacturer / brand.
        purchase_date: Date of acquisition.
        status: Current availability state.
        notes: Free-text notes.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    brand: str | None
    purchase_date: datetime.date | None
    status: str
    notes: str | None


# ── AI Search ──────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    """Payload for the natural-language semantic search endpoint.

    Attributes:
        query: Free-text question or description, e.g.
            ``'Show me broken Apple laptops'``.
    """

    query: str = Field(..., min_length=1)


# ── AI Seed ────────────────────────────────────────────────────────────────────


class SeedResponse(BaseModel):
    """Response returned by the ``POST /api/ai/seed`` endpoint.

    Summarises the outcome of an AI-assisted bulk import operation.

    Attributes:
        inserted: Number of hardware rows successfully written to the database.
        items: Full representation of every inserted hardware record.
    """

    inserted: int
    items: list[HardwareRead]


# ── Rental ─────────────────────────────────────────────────────────────────────


class RentRequest(BaseModel):
    """Payload for initiating a hardware rental.

    Attributes:
        user_id: ID of the user who is renting the item.
        hardware_id: ID of the hardware item to be rented.
    """

    user_id: int
    hardware_id: int


class ReturnRequest(BaseModel):
    """Payload for returning a rented hardware item.

    Attributes:
        rental_id: ID of the active rental record to close.
    """

    rental_id: int


class RentalRead(BaseModel):
    """Full rental record representation returned by the API.

    Attributes:
        id: Auto-assigned primary key.
        user_id: ID of the renting user.
        hardware_id: ID of the rented hardware.
        rented_at: UTC timestamp when the rental was created.
        returned_at: UTC timestamp when the item was returned; ``None`` if active.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    hardware_id: int
    rented_at: datetime.datetime
    returned_at: datetime.datetime | None
