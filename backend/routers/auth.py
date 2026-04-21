"""Authentication router for Hardware Hub.

SECURITY NOTE — MVP HACK
------------------------
This module intentionally bypasses production-grade authentication for the
sake of rapid prototyping.  The login endpoint accepts a plain-text email
address, looks it up in the ``users`` table, and returns the full user
object.  There is **no password hashing**, **no JWT issuance**, and **no
session management**.  The frontend stores the returned object in
``localStorage`` and passes the ``user_id`` in subsequent requests.

**This approach MUST be replaced with proper authentication (e.g. OAuth2 /
JWT with hashed passwords) before any production or public deployment.**
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.schemas import UserRead

router: APIRouter = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    """Payload for the MVP login endpoint.

    Attributes:
        email: The email address to look up in the ``users`` table.

    Note:
        No password field is present.  This is a deliberate MVP shortcut —
        see the module-level security warning above.
    """

    email: EmailStr


@router.post(
    "/login",
    response_model=UserRead,
    summary="MVP login (email-only, no password)",
    responses={
        200: {"description": "User found — object returned for localStorage storage."},
        404: {"description": "No user with this email address exists."},
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> User:
    """Authenticate a user by email address and return their user record.

    .. warning::
        **MVP SECURITY HACK** — This endpoint performs no password verification
        and issues no token.  It simply checks whether the supplied email exists
        in the database and returns the matching row.  The Vue.js frontend is
        expected to store this object in ``localStorage`` and include the
        ``user_id`` in subsequent API calls.  This shortcut was chosen to
        eliminate auth infrastructure overhead during the initial MVP sprint and
        **must not be used in a production environment**.

    Args:
        payload: JSON body containing the ``email`` field.
        db: Injected SQLAlchemy session.

    Returns:
        The :class:`~backend.models.User` ORM instance serialised via
        :class:`~backend.schemas.UserRead`.

    Raises:
        HTTPException (404): If no user with the supplied email exists.
    """
    user: User | None = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user found with email '{payload.email}'.",
        )
    return user
