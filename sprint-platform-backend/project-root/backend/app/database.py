"""
Database engine, session factory and declarative base.

This module is intentionally minimal for this step: it only sets up the
SQLAlchemy plumbing needed for models, Alembic migrations, and a DB
connectivity health check. No business logic lives here.
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Run a trivial query to verify the database is reachable."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
