"""Admin router for Hardware Hub.

Provides privileged operations that are restricted to users with the
``'admin'`` role.  Currently exposes a single endpoint:

* ``POST /api/admin/users`` — create a new user account.

As with other admin-gated endpoints in this MVP, the role check is performed
via the ``X-User-Role`` request header rather than a verified JWT claim.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.schemas import UserCreate, UserRead


router: APIRouter = APIRouter(prefix="/api/admin", tags=["Admin"])


def _require_admin(x_user_role: Optional[str]) -> None:
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
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
) -> User:
    """Register a new user account in the system.

    Args:
        payload: JSON body containing ``email`` and optional ``role``
            (defaults to ``'user'``).
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

    user: User = User(email=str(payload.email), role=payload.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{payload.email}' already exists.",
        )
    db.refresh(user)
    return user
