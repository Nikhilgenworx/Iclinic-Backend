from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session
from src.config.database import SessionLocal


def get_db() -> Generator[Session]:
    db = SessionLocal()

    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session]:
    """Context manager for DB sessions — use in non-FastAPI contexts.

    Usage:
        with get_db_session() as db:
            # do work
        # auto-commits if no exception, rollbacks otherwise
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
