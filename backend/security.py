"""Password hashing utilities for authentication flows.

This module centralises password hashing/verification so routers do not need
to know hashing algorithm details.
"""

from passlib.context import CryptContext

_PASSWORD_CONTEXT: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a secure hash for the supplied plain-text password."""
    return _PASSWORD_CONTEXT.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return ``True`` when the password matches the stored hash."""
    return _PASSWORD_CONTEXT.verify(plain_password, password_hash)
