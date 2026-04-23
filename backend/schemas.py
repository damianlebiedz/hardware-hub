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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer

# ── User ──────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Payload required to register a new user.

    Attributes:
        email: Valid email address; must be unique in the database.
        password: Plain-text password accepted on creation and hashed before
            persistence.

    Note:
        Accounts created via this schema are always assigned the ``'user'``
        role.  Admin accounts can only be provisioned via the bootstrap
        mechanism (environment variables at startup).
    """

    email: EmailStr
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


class SeedFieldChange(BaseModel):
    """Describes a single field corrected by the AI during seed sanitization.

    Attributes:
        field: Name of the field that was changed.
        before: Raw value before AI correction (as a string, or None).
        after: Cleaned value after AI correction (as a string, or None).
        reason: Optional short note (e.g. why an ``id`` was reassigned in preview).
    """

    field: str
    before: str | None
    after: str | None
    reason: str | None = None


class SeedRecordChange(BaseModel):
    """Per-record correction summary produced by the AI seed pipeline.

    Attributes:
        index: Zero-based position of the record in the original raw payload.
        name: Final (cleaned) device name, used as a human-readable label.
        changes: List of individual field corrections applied to this record.
    """

    index: int
    name: str
    changes: list[SeedFieldChange]


class SeedPreviewRecord(BaseModel):
    """A single proposed record from the AI preview pipeline.

    Attributes:
        index: Zero-based position of this record in the original raw payload.
        proposed: The AI-cleaned record ready for insertion.
        proposed_id: The integer ID to use on insert.  Set to the original
            raw ID when it is free; reassigned to the next available ID when
            the original is already taken; ``None`` when the raw record had no
            ``id`` field (database auto-assigns).
        changes: Field-level corrections applied by the AI or by the ID
            conflict resolver (empty if none).
    """

    index: int
    proposed: HardwareCreate
    proposed_id: int | None = None
    changes: list[SeedFieldChange] = Field(default_factory=list)


class SeedPreviewResponse(BaseModel):
    """Response returned by ``POST /api/ai/seed/preview``.

    Returns the AI-sanitized records without inserting them, allowing the
    caller to review and selectively confirm which records to import.

    Attributes:
        total: Total number of records that passed AI sanitization.
        records: Per-record preview with proposed values and change diffs.
    """

    total: int
    records: list[SeedPreviewRecord]


class SeedResponse(BaseModel):
    """Response returned by the ``POST /api/ai/seed`` endpoint.

    Summarises the outcome of an AI-assisted bulk import operation.

    Attributes:
        inserted: Number of hardware rows successfully written to the database.
        items: Full representation of every inserted hardware record.
        changes: Per-record corrections made by the AI; only records that had
            at least one field modified are included.
    """

    inserted: int
    items: list[HardwareRead]
    changes: list[SeedRecordChange] = Field(default_factory=list)


# ── Plain Seed ─────────────────────────────────────────────────────────────────


class PlainSeedRejection(BaseModel):
    """Describes a single record rejected during plain seed import.

    Attributes:
        index: Zero-based position of the record in the original raw payload.
        record: The raw record that failed validation.
        reason: Human-readable explanation of why the record was rejected.
    """

    index: int
    record: Any
    reason: str


class PlainSeedResponse(BaseModel):
    """Response returned by the ``POST /api/admin/seed`` endpoint.

    Attributes:
        inserted: Number of records successfully written to the database.
        items: Full representation of every inserted hardware record.
        rejected: Records that failed validation and were not inserted.
    """

    inserted: int
    items: list[HardwareRead]
    rejected: list[PlainSeedRejection] = Field(default_factory=list)


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


def _utc_iso_z(value: datetime.datetime | None) -> str | None:
    """Serialise DB datetimes (naive UTC) to RFC 3339 with ``Z`` for unambiguous JSON."""
    if value is None:
        return None
    aware = (
        value.replace(tzinfo=datetime.timezone.utc)
        if value.tzinfo is None
        else value.astimezone(datetime.timezone.utc)
    )
    return aware.isoformat().replace("+00:00", "Z")


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

    @field_serializer("rented_at", "returned_at", when_used="json")
    def _serialize_rental_timestamps(
        self, value: datetime.datetime | None
    ) -> str | None:
        return _utc_iso_z(value)
