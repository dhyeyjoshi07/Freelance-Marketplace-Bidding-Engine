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

    5. After table creation, create_triggers() registers MySQL BEFORE/AFTER
       triggers (DBMS Unit 8: PL/SQL equivalents).

    6. create_indexes() adds performance indexes (DBMS Unit 5: Query Optimization).
"""

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

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
# MySQL Triggers (DBMS Unit 8: PL/SQL — stored procedures/triggers)
# ---------------------------------------------------------------------------

# Rating auto-update trigger: when a new rating is inserted, automatically
# update the freelancer's avg_rating and total_ratings.
TRIGGER_AFTER_INSERT_RATING = """
CREATE TRIGGER IF NOT EXISTS trg_after_insert_rating
AFTER INSERT ON ratings
FOR EACH ROW
BEGIN
    UPDATE freelancer_profiles
    SET total_ratings = total_ratings + 1,
        avg_rating = ROUND(
            (avg_rating * total_ratings + NEW.score) / (total_ratings + 1),
            2
        )
    WHERE user_id = NEW.freelancer_id;
END
"""

# Bid validation trigger: prevent bids with non-positive amounts
TRIGGER_BEFORE_INSERT_BID = """
CREATE TRIGGER IF NOT EXISTS trg_before_insert_bid
BEFORE INSERT ON bids
FOR EACH ROW
BEGIN
    IF NEW.amount <= 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Bid amount must be positive';
    END IF;
    IF NEW.match_score < 0 OR NEW.match_score > 1 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Match score must be between 0 and 1';
    END IF;
END
"""

# Project budget validation trigger: ensure budget_min < budget_max
TRIGGER_BEFORE_INSERT_PROJECT = """
CREATE TRIGGER IF NOT EXISTS trg_before_insert_project
BEFORE INSERT ON projects
FOR EACH ROW
BEGIN
    IF NEW.budget_min < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Budget minimum cannot be negative';
    END IF;
    IF NEW.budget_min >= NEW.budget_max THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Budget minimum must be less than budget maximum';
    END IF;
END
"""

# Audit log trigger: log project status changes
TRIGGER_AFTER_UPDATE_PROJECT_STATUS = """
CREATE TRIGGER IF NOT EXISTS trg_after_update_project_status
AFTER UPDATE ON projects
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status THEN
        INSERT INTO audit_log (table_name, record_id, action, old_value, new_value, changed_at)
        VALUES ('projects', NEW.id, 'STATUS_CHANGE', OLD.status, NEW.status, NOW());
    END IF;
END
"""


def create_triggers(connection):
    """
    Register MySQL triggers.

    Triggers are the MySQL equivalent of PL/SQL procedural code that
    executes automatically on INSERT/UPDATE/DELETE events.  They enforce
    business rules at the database level, independent of application code.
    """
    triggers = [
        TRIGGER_BEFORE_INSERT_BID,
        TRIGGER_BEFORE_INSERT_PROJECT,
        TRIGGER_AFTER_INSERT_RATING,
        TRIGGER_AFTER_UPDATE_PROJECT_STATUS,
    ]
    for trigger_sql in triggers:
        try:
            # MySQL requires DELIMITER changes for multi-statement triggers,
            # but SQLAlchemy's execute handles this transparently
            connection.execute(text(trigger_sql))
        except Exception:
            # Trigger may already exist — MySQL's IF NOT EXISTS for triggers
            # is available in 8.0.29+; silently skip if unsupported
            pass


# ---------------------------------------------------------------------------
# Performance Indexes (DBMS Unit 5: Query Optimization)
# ---------------------------------------------------------------------------

INDEX_DEFINITIONS = [
    # Covering index for bid ranking queries: given a project, sort bids by score
    "CREATE INDEX IF NOT EXISTS idx_bids_project_score ON bids (project_id, match_score DESC)",
    # Fast lookup of freelancer's bids
    "CREATE INDEX IF NOT EXISTS idx_bids_freelancer ON bids (freelancer_id)",
    # Filter projects by status (most queries filter for 'open')
    "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status)",
    # Client's own projects
    "CREATE INDEX IF NOT EXISTS idx_projects_client ON projects (client_id)",
    # Rating lookups by freelancer
    "CREATE INDEX IF NOT EXISTS idx_ratings_freelancer ON ratings (freelancer_id)",
    # Composite index for duplicate-bid check (supplements the UNIQUE constraint)
    "CREATE INDEX IF NOT EXISTS idx_bids_project_freelancer ON bids (project_id, freelancer_id)",
]


def create_indexes(connection):
    """Create performance indexes for query optimization."""
    for idx_sql in INDEX_DEFINITIONS:
        try:
            connection.execute(text(idx_sql))
        except Exception:
            pass  # Index already exists


# ---------------------------------------------------------------------------
# Stored Procedures (DBMS Unit 8: PL/SQL — MySQL native procedures)
# ---------------------------------------------------------------------------

STORED_PROCEDURES = [
    # Stored procedure: get ranked bids for a project
    """
    CREATE PROCEDURE IF NOT EXISTS sp_get_ranked_bids(IN p_project_id INT)
    BEGIN
        SELECT b.id, b.freelancer_id, u.username, b.amount, b.proposal,
               b.match_score, b.created_at
        FROM bids b
        JOIN users u ON b.freelancer_id = u.id
        WHERE b.project_id = p_project_id
        ORDER BY b.match_score DESC;
    END
    """,

    # Stored procedure: get freelancer statistics
    """
    CREATE PROCEDURE IF NOT EXISTS sp_freelancer_stats(IN p_user_id INT)
    BEGIN
        DECLARE v_total_bids INT;
        DECLARE v_accepted_bids INT;
        DECLARE v_avg_score FLOAT;

        SELECT COUNT(*) INTO v_total_bids FROM bids WHERE freelancer_id = p_user_id;

        SELECT COUNT(*) INTO v_accepted_bids
        FROM bids b JOIN projects p ON b.id = p.accepted_bid_id
        WHERE b.freelancer_id = p_user_id;

        SELECT COALESCE(AVG(match_score), 0) INTO v_avg_score
        FROM bids WHERE freelancer_id = p_user_id;

        SELECT v_total_bids AS total_bids,
               v_accepted_bids AS accepted_bids,
               ROUND(v_avg_score, 3) AS avg_match_score;
    END
    """,

    # Stored function: compute price fit score (mirrors Python MatchEngine logic)
    """
    CREATE FUNCTION IF NOT EXISTS fn_price_fit(
        bid_amount FLOAT, budget_min FLOAT, budget_max FLOAT
    ) RETURNS FLOAT DETERMINISTIC
    BEGIN
        IF bid_amount BETWEEN budget_min AND budget_max THEN
            RETURN 1.0;
        ELSEIF bid_amount < budget_min THEN
            IF budget_min = 0 THEN RETURN 0.0; END IF;
            RETURN bid_amount / budget_min;
        ELSE
            RETURN GREATEST(0, 1.0 - (bid_amount - budget_max) / budget_max);
        END IF;
    END
    """,
]


def create_stored_procedures(connection):
    """Create MySQL stored procedures and functions."""
    for sp_sql in STORED_PROCEDURES:
        try:
            connection.execute(text(sp_sql))
        except Exception:
            pass  # Already exists or syntax variation


# ---------------------------------------------------------------------------
# Audit Log Table (DBMS Unit 9: Data Security)
# ---------------------------------------------------------------------------

AUDIT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,
    record_id INT NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_table (table_name),
    INDEX idx_audit_record (record_id),
    INDEX idx_audit_time (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db():
    """
    Create all tables, triggers, indexes, and stored procedures.

    This is called once at application startup (via the FastAPI lifespan handler).
    The sequence is:
        1. Import all models so they register with Base.metadata
        2. create_all() generates CREATE TABLE IF NOT EXISTS for each model
        3. Create the audit_log table (used by triggers)
        4. Create triggers, indexes, and stored procedures
    """
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
