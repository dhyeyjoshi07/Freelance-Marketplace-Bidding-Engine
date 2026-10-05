"""
SQLAlchemy database setup.

Creates the engine (SQLite), a session factory, and the declarative Base class.
All models inherit from Base to register their tables.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import DATABASE_URL


# SQLite requires check_same_thread=False for FastAPI's async request handling
# (each request may run on a different thread from the pool)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """
    Create all tables defined by Base subclasses.
    Called once at application startup.
    """
    # Import all models so they register with Base.metadata before create_all
    import backend.models.user       # noqa: F401
    import backend.models.project    # noqa: F401
    import backend.models.bid        # noqa: F401

    Base.metadata.create_all(bind=engine)
