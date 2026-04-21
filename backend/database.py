"""Database engine, session factory, and declarative base for Hardware Hub.

The production SQLite database file is stored at ``/app/data/hardware.db``,
which is mapped to the named Docker volume defined in ``docker-compose.yml``.
The ``DATABASE_URL`` environment variable can override this path, which is
exploited by the test suite to substitute an in-memory SQLite database.
"""

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:////app/data/hardware.db",
)

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


def get_db():
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
