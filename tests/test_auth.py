"""Authentication and user-creation tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base
from backend.models import User
from backend.routers.admin import create_user
from backend.routers.auth import LoginRequest, login
from backend.schemas import UserCreate
from backend.security import verify_password


@pytest.fixture(scope="function")
def db() -> Session:  # type: ignore[return]
    """Provide a fresh in-memory SQLite session for each test."""
    engine: Engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    testing_session_local: sessionmaker[Session] = sessionmaker(
        bind=engine, autocommit=False, autoflush=False
    )
    Base.metadata.create_all(bind=engine)
    try:
        session: Session = testing_session_local()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_login_success_with_correct_email_and_password(db: Session) -> None:
    """A user with a valid hash can authenticate successfully."""
    created = create_user(
        payload=UserCreate(email="alice@example.com", role="user", password="strongpass123"),
        db=db,
        x_user_role="admin",
    )
    assert created.email == "alice@example.com"

    logged_in = login(
        payload=LoginRequest(email="alice@example.com", password="strongpass123"),
        db=db,
    )
    assert logged_in.email == "alice@example.com"


def test_login_fails_with_wrong_password(db: Session) -> None:
    """Invalid password returns a generic 401 response."""
    create_user(
        payload=UserCreate(email="bob@example.com", role="user", password="strongpass123"),
        db=db,
        x_user_role="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        login(payload=LoginRequest(email="bob@example.com", password="incorrect-password"), db=db)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid credentials."


def test_login_fails_when_password_hash_is_missing(db: Session) -> None:
    """Legacy users without a password hash are denied login."""
    db.add(User(email="legacy@example.com", role="user", password_hash=None))
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        login(payload=LoginRequest(email="legacy@example.com", password="any-password"), db=db)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid credentials."


def test_admin_create_user_stores_hashed_password(db: Session) -> None:
    """Admin creation persists a hash, not the plain-text password."""
    plain_password = "Secur3Pass!"
    created = create_user(
        payload=UserCreate(email="charlie@example.com", role="admin", password=plain_password),
        db=db,
        x_user_role="admin",
    )
    assert created.email == "charlie@example.com"

    user = db.query(User).filter(User.email == "charlie@example.com").first()
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash != plain_password
    assert verify_password(plain_password, user.password_hash)
    assert user.password_hash.startswith("$2")
