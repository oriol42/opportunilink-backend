
# app/database.py
# Database connection setup — SQLAlchemy engine, session factory, and base model

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=False,    # Tests connection before using it (avoids stale connections)
    pool_size=10,          # Max simultaneous connections kept open
    max_overflow=20,       # Extra connections allowed when pool is full
    echo=not settings.is_production,  # Logs SQL queries in dev, silent in prod
)

# SESSION FACTORY

# A session = one "conversation" with the database.
# You open a session, do your queries, then close it.
# SessionLocal is the factory that creates sessions on demand.

SessionLocal = sessionmaker(
    autocommit=False,  # We control when to commit (save) changes manually
    autoflush=False,   # Don't auto-send queries before commit
    bind=engine,       # Which database this session talks to
)


# BASE MODEL

# All SQLAlchemy models (User, Opportunity, etc.) will inherit from Base.
# This is what lets SQLAlchemy know which classes represent DB tables.

Base = declarative_base()



# DEPENDENCY — get_db()

# This is a FastAPI "dependency" — a function injected into route handlers.
# It guarantees every request gets a fresh session, and it's always closed
# after the request finishes — even if an error occurs.

def get_db():
    """
    Yields a database session for a single request lifecycle.

    Usage in a route:
        @router.get("/something")
        def my_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db        # Give the session to the route handler
        db.commit()     # If no errors, save all changes
    except Exception:
        db.rollback()   # If something went wrong, undo all changes
        raise           # Re-raise the exception so FastAPI handles it
    finally:
        db.close()      # Always close the session, no matter what