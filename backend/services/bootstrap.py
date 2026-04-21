"""Admin bootstrap service for Hardware Hub.

On every application startup this module checks whether a first admin user
must be created or promoted.  The routine is idempotent — running it on a DB
that already has the target admin account in the correct state is a no-op.

Environment variables
---------------------
BOOTSTRAP_ADMIN_ENABLED
    Set to ``"false"`` (case-insensitive) to skip the routine entirely.
    Defaults to ``"true"``.
BOOTSTRAP_ADMIN_EMAIL
    Email address of the bootstrap admin account.  Required when the routine
    is enabled.
BOOTSTRAP_ADMIN_PASSWORD
    Plain-text password for the bootstrap account.  Required only when a new
    account must be created (not used when the user already exists).  Must be
    at least 8 characters.

Startup outcomes
----------------
* disabled      — ``BOOTSTRAP_ADMIN_ENABLED`` is ``false``.
* created       — No user with the given email existed; a new admin was created.
* promoted      — User existed but had a non-admin role; role was promoted to
                  ``admin`` (password left unchanged).
* already_admin — User already exists with ``admin`` role; no changes made.
* error         — Configuration is invalid; startup is aborted.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from backend.models import User
from backend.security import hash_password

logger: logging.Logger = logging.getLogger(__name__)


def bootstrap_admin(db: Session) -> None:
    """Ensure an admin user exists according to bootstrap environment config.

    This function is safe to call on every restart.  All outcomes are logged
    at ``INFO`` level so operators can audit the startup behaviour in
    container logs.

    Args:
        db: An active SQLAlchemy session used to query and mutate the
            ``users`` table.

    Raises:
        RuntimeError: When ``BOOTSTRAP_ADMIN_ENABLED`` is ``true`` but either
            ``BOOTSTRAP_ADMIN_EMAIL`` or ``BOOTSTRAP_ADMIN_PASSWORD`` is not
            set, or when the password is shorter than 8 characters.  The
            error message is intentionally human-readable so that it surfaces
            clearly in startup logs.
    """
    enabled_raw: str = os.getenv("BOOTSTRAP_ADMIN_ENABLED", "true")
    if enabled_raw.strip().lower() != "true":
        logger.info("[bootstrap] Admin bootstrap is disabled (BOOTSTRAP_ADMIN_ENABLED=%s).", enabled_raw)
        return

    email: str | None = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    password: str | None = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")

    if not email:
        raise RuntimeError(
            "[bootstrap] BOOTSTRAP_ADMIN_ENABLED is true but BOOTSTRAP_ADMIN_EMAIL is not set. "
            "Set the variable or disable bootstrap with BOOTSTRAP_ADMIN_ENABLED=false."
        )
    if not password:
        raise RuntimeError(
            "[bootstrap] BOOTSTRAP_ADMIN_ENABLED is true but BOOTSTRAP_ADMIN_PASSWORD is not set. "
            "Set the variable or disable bootstrap with BOOTSTRAP_ADMIN_ENABLED=false."
        )
    if len(password) < 8:
        raise RuntimeError(
            "[bootstrap] BOOTSTRAP_ADMIN_PASSWORD must be at least 8 characters."
        )

    existing: User | None = db.query(User).filter(User.email == email).first()

    if existing is None:
        new_admin = User(
            email=email,
            role="admin",
            password_hash=hash_password(password),
        )
        db.add(new_admin)
        db.commit()
        logger.info("[bootstrap] Admin user '%s' created successfully.", email)
        return

    if existing.role != "admin":
        existing.role = "admin"
        db.commit()
        logger.info(
            "[bootstrap] Existing user '%s' promoted to admin role (password unchanged).",
            email,
        )
        return

    logger.info("[bootstrap] Admin user '%s' already exists — no changes made.", email)
