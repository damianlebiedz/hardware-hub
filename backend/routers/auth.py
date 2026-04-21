"""Authentication router for Hardware Hub.

SECURITY NOTE — MVP HACK (STILL IN PLACE)
-----------------------------------------
This module now verifies ``email + password`` using secure password hashes,
but it still intentionally skips production-grade session/auth infrastructure.

Current MVP behavior:
* Login returns the user profile object on success.
* The frontend stores that object in ``localStorage``.
* Subsequent requests rely on role/user context passed from the client side.

What is still missing:
* No JWT/OAuth2/OIDC token flow.
* No HTTP-only secure session cookies.
* No server-side token/session invalidation lifecycle.

This shortcut is acceptable for the MVP scope but **must be replaced** before
production deployment.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.schemas import UserRead
from backend.security import verify_password

router: APIRouter = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    """Payload for the login endpoint.

    Attributes:
        email: User login email.
        password: Plain-text password to verify against ``password_hash``.
    """

    email: EmailStr
    password: str


@router.post(
    "/login",
    response_model=UserRead,
    summary="Login with email and password",
    responses={
        200: {"description": "Credentials valid; user object returned."},
        401: {"description": "Invalid credentials."},
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> User:
    """Authenticate by email+password and return user profile on success.

    Args:
        payload: JSON body containing the ``email`` field.
        db: Injected SQLAlchemy session.

    Returns:
        The :class:`~backend.models.User` ORM instance serialised via
        :class:`~backend.schemas.UserRead`.

    Raises:
        HTTPException (401): If credentials are invalid.
    """
    user: User | None = db.query(User).filter(User.email == payload.email).first()
    if user is None or user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    return user
