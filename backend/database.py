"""Database engine, session factory, and declarative base for Hardware Hub.

If ``DATABASE_URL`` is unset, SQLite uses ``<project_root>/data/hardware.db``,
where the project root is the parent of the ``backend`` package.  That is
``data/hardware.db`` next to your checkout locally and ``/app/data/hardware.db``
in the Docker image (volume in ``docker-compose.yml``).  Set ``DATABASE_URL`` in
``.env`` to override (e.g. ``sqlite:///:memory:`` for tests).
"""

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _default_sqlite_database_url() -> str:
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "data" / "hardware.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL: str = os.getenv("DATABASE_URL") or _default_sqlite_database_url()

# ``check_same_thread=False`` is required for SQLite when the same connection
# may be accessed from multiple threads (e.g. FastAPI's async request handling).
engine: Engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def init_db() -> None:
    """Create all database tables defined on ``Base`` metadata.

    This is called once at application startup.  In production the tables are
    created on the persisted SQLite file; in tests an in-memory engine is used.

    Note:
        Alembic migrations are the recommended long-term approach, but for this
        MVP ``create_all`` is sufficient.
    """
    Base.metadata.create_all(bind=engine)
    _ensure_users_password_hash_column()


def _ensure_users_password_hash_column() -> None:
    """Add ``users.password_hash`` for pre-auth-migration SQLite databases."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        columns: list[str] = [
            row[1] for row in connection.execute(text("PRAGMA table_info(users)")).fetchall()
        ]
        if "password_hash" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy ``Session`` and guarantee it is closed afterwards.

    Designed for use as a FastAPI dependency::

        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    Yields:
        Session: An active database session bound to ``SessionLocal``.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
