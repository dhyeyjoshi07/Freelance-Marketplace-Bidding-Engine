"""
SQLAlchemy database setup for MySQL.

Connection flow:
    1. config.py builds the DATABASE_URL string:
       mysql+pymysql://bidforge_user:bidforge_pass@localhost:3306/bidforge

    2. create_engine() uses PyMySQL to open a TCP connection to MySQL on port 3306.

    3. SessionLocal() creates a session factory — each FastAPI request gets its own
       session via the get_db() dependency (in dependencies.py).

    4. init_db() calls Base.metadata.create_all() which:
       - Introspects all models that inherit from Base
       - Generates CREATE TABLE IF NOT EXISTS statements
       - Sends them to MySQL via the PyMySQL connection

    5. After table creation, triggers, indexes, and stored procedures are
       registered via the backend.db sub-package.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import DATABASE_URL


# --- Engine Configuration ---
# pool_size: number of persistent connections kept open to MySQL
# max_overflow: extra connections allowed when pool is full
# pool_recycle: seconds before a connection is recycled (MySQL default wait_timeout=28800)
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables, triggers, indexes, and stored procedures.

    This is called once at application startup (via the FastAPI lifespan handler).
    The sequence is:
        1. Import all models so they register with Base.metadata
        2. create_all() generates CREATE TABLE IF NOT EXISTS for each model
        3. Create the audit_log table (used by triggers)
        4. Create triggers, indexes, and stored procedures
    """
    from backend.db import (
        create_triggers,
        create_indexes,
        create_stored_procedures,
        AUDIT_LOG_TABLE,
    )

    # Import all models so they register with Base.metadata before create_all
    import backend.models.user       # noqa: F401
    import backend.models.project    # noqa: F401
    import backend.models.bid        # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Create auxiliary objects (triggers, indexes, procedures)
    with engine.connect() as conn:
        conn.execute(text(AUDIT_LOG_TABLE))
        conn.commit()

        create_triggers(conn)
        conn.commit()

        create_indexes(conn)
        conn.commit()

        create_stored_procedures(conn)
        conn.commit()
