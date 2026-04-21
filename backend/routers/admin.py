"""Admin router for Hardware Hub.

Provides privileged operations that are restricted to users with the
``'admin'`` role.  Currently exposes a single endpoint:

* ``POST /api/admin/users`` — create a new user account.

As with other admin-gated endpoints in this MVP, the role check is performed
via the ``X-User-Role`` request header rather than a verified JWT claim.
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Hardware, User
from backend.schemas import (
    HardwareCreate,
    HardwareRead,
    PlainSeedRejection,
    PlainSeedResponse,
    UserCreate,
    UserRead,
)
from backend.security import hash_password

router: APIRouter = APIRouter(prefix="/api/admin", tags=["Admin"])


def _require_admin(x_user_role: str | None) -> None:
    """Raise HTTP 403 if the caller is not an admin.

    Args:
        x_user_role: Value of the ``X-User-Role`` request header.

    Raises:
        HTTPException (403): If the header is absent or not ``'admin'``.
    """
    if x_user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this operation.",
        )


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account (admin only)",
    responses={
        201: {"description": "User created successfully."},
        403: {"description": "Caller does not have admin privileges."},
        409: {"description": "A user with this email address already exists."},
    },
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> User:
    """Register a new user account in the system.

    The created account always receives the ``'user'`` role.  Admin accounts
    can only be provisioned via the bootstrap mechanism (env vars at startup).

    Args:
        payload: JSON body containing ``email`` and ``password``.
        db: Injected SQLAlchemy session.
        x_user_role: Value of the ``X-User-Role`` request header; must be
            ``'admin'``.

    Returns:
        The newly created :class:`~backend.schemas.UserRead` object.

    Raises:
        HTTPException (403): If the caller is not an admin.
        HTTPException (409): If the email address is already registered.
    """
    _require_admin(x_user_role)

    user: User = User(
        email=str(payload.email),
        role="user",
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{payload.email}' already exists.",
        ) from exc
    db.refresh(user)
    return user


@router.post(
    "/seed",
    response_model=PlainSeedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Plain bulk hardware import without AI (admin only)",
    responses={
        201: {"description": "Valid records inserted; rejected records reported."},
        403: {"description": "Caller does not have admin privileges."},
        500: {"description": "Database transaction failed."},
    },
)
def plain_seed(
    raw_payload: list[Any],
    db: Session = Depends(get_db),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> PlainSeedResponse:
    """Bulk-insert hardware records without AI sanitization.

    Each record is validated directly against :class:`~backend.schemas.HardwareCreate`.
    Records that fail validation are collected in the ``rejected`` list and
    returned to the caller — they are never written to the database.  Only
    records that pass validation are persisted.

    Args:
        raw_payload: A JSON array of raw hardware objects.
        db: Injected SQLAlchemy session.
        x_user_role: Value of the ``X-User-Role`` request header; must be
            ``'admin'``.

    Returns:
        :class:`~backend.schemas.PlainSeedResponse` with ``inserted`` count,
        ``items`` list, and ``rejected`` list of failed records with reasons.

    Raises:
        HTTPException (403): If the caller is not an admin.
        HTTPException (500): If the database transaction fails.
    """
    _require_admin(x_user_role)

    inserted_items: list[Hardware] = []
    rejected: list[PlainSeedRejection] = []

    for i, raw in enumerate(raw_payload):
        try:
            if not isinstance(raw, dict):
                raise ValueError("Record must be a JSON object.")
            record = HardwareCreate(**raw)
            hw = Hardware(**record.model_dump())
            db.add(hw)
            inserted_items.append(hw)
        except (ValidationError, ValueError, TypeError) as exc:
            rejected.append(
                PlainSeedRejection(
                    index=i,
                    record=raw,
                    reason=str(exc),
                )
            )

    if inserted_items:
        try:
            db.commit()
            for hw in inserted_items:
                db.refresh(hw)
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database transaction failed: {exc}",
            ) from exc

    return PlainSeedResponse(
        inserted=len(inserted_items),
        items=[HardwareRead.model_validate(hw) for hw in inserted_items],
        rejected=rejected,
    )
