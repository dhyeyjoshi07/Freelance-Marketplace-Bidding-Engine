"""
Transaction manager (DBMS Unit 6: Transaction Management).

Demonstrates ACID properties, savepoints, and isolation levels using
MySQL's InnoDB engine through SQLAlchemy.

ACID in BidForge:
    Atomicity    — bid acceptance (accept bid + update project status) either
                   fully commits or fully rolls back on error.
    Consistency  — CHECK constraints and triggers enforce business rules;
                   the DB is always in a valid state after each transaction.
    Isolation    — MySQL's default REPEATABLE READ prevents dirty reads and
                   non-repeatable reads within a transaction.
    Durability   — InnoDB's redo log ensures committed transactions survive
                   crashes (write-ahead logging / WAL).

Savepoints:
    MySQL supports SAVEPOINT within a transaction, allowing partial rollback:
        BEGIN;
        INSERT INTO bids ...;
        SAVEPOINT before_score;
        UPDATE bids SET match_score = ...;  -- if this fails...
        ROLLBACK TO before_score;           -- ...only undo the score update
        COMMIT;                             -- the INSERT is preserved

Isolation Levels (MySQL InnoDB):
    READ UNCOMMITTED  — allows dirty reads (seeing uncommitted changes)
    READ COMMITTED    — no dirty reads, but non-repeatable reads possible
    REPEATABLE READ   — (default) consistent snapshot within a transaction
    SERIALIZABLE      — full isolation, effectively sequential execution
"""

from contextlib import contextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import SessionLocal


@contextmanager
def transactional_session():
    """
    Context manager that provides a transactional database session.

    Automatically commits on success and rolls back on any exception,
    demonstrating atomicity — either ALL changes within the `with` block
    are persisted, or NONE of them are.

    Usage:
        with transactional_session() as db:
            db.add(new_bid)
            project.accept_bid(new_bid.id)
            # If accept_bid raises, the new_bid INSERT is also rolled back
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


def execute_with_savepoint(db: Session, operations: list[callable]) -> list:
    """
    Execute a sequence of operations within a single transaction, using
    savepoints for partial rollback.

    Each operation is wrapped in its own savepoint.  If an operation fails,
    only that operation is rolled back; earlier operations are preserved.

    Args:
        db: SQLAlchemy session.
        operations: List of callables, each taking (db,) as argument.

    Returns:
        List of (index, result_or_error) tuples.
    """
    results = []
    for i, op in enumerate(operations):
        savepoint = db.begin_nested()  # SAVEPOINT
        try:
            result = op(db)
            savepoint.commit()  # Release savepoint (changes preserved)
            results.append((i, {"status": "committed", "result": result}))
        except Exception as e:
            savepoint.rollback()  # ROLLBACK TO SAVEPOINT (undo this op only)
            results.append((i, {"status": "rolled_back", "error": str(e)}))
    return results


def get_isolation_level(db: Session) -> str:
    """Query the current transaction isolation level from MySQL."""
    result = db.execute(text("SELECT @@transaction_isolation"))
    return result.scalar()


def set_isolation_level(db: Session, level: str) -> None:
    """
    Set the transaction isolation level for the current session.

    Valid levels: 'READ UNCOMMITTED', 'READ COMMITTED',
                  'REPEATABLE READ', 'SERIALIZABLE'
    """
    valid_levels = {
        "READ UNCOMMITTED", "READ COMMITTED",
        "REPEATABLE READ", "SERIALIZABLE"
    }
    if level.upper() not in valid_levels:
        raise ValueError(f"Invalid isolation level: {level}")
    db.execute(text(f"SET SESSION TRANSACTION ISOLATION LEVEL {level}"))


def demonstrate_acid_properties(db: Session) -> dict:
    """
    Return a description of how each ACID property is implemented in BidForge.

    This is used by the /api/admin/acid endpoint to provide an educational
    overview for the DBMS report.
    """
    current_isolation = get_isolation_level(db)

    return {
        "atomicity": {
            "mechanism": "SQLAlchemy session.commit() / session.rollback()",
            "example": "Bid acceptance: update project.status + set project.accepted_bid_id "
                       "in one transaction. If either fails, both are rolled back.",
            "mysql_feature": "InnoDB undo log — stores pre-modification data for rollback",
        },
        "consistency": {
            "mechanism": "CHECK constraints + MySQL triggers + application validation",
            "constraints": [
                "ck_bid_amount_positive: bid.amount > 0",
                "ck_bid_score_range: 0 <= match_score <= 1",
                "ck_project_status_valid: status IN ('open','in_progress','completed')",
                "ck_rating_score_range: 1 <= score <= 5",
                "trg_before_insert_bid: validates amount and score",
                "trg_before_insert_project: validates budget_min < budget_max",
            ],
        },
        "isolation": {
            "current_level": current_isolation,
            "available_levels": [
                "READ UNCOMMITTED", "READ COMMITTED",
                "REPEATABLE READ", "SERIALIZABLE",
            ],
            "explanation": "REPEATABLE READ (MySQL default) ensures that within a "
                           "transaction, SELECT queries see a consistent snapshot — "
                           "other transactions' commits are invisible until you commit.",
        },
        "durability": {
            "mechanism": "InnoDB redo log (write-ahead logging)",
            "explanation": "Before modifying data pages, InnoDB writes the change to "
                           "the redo log on disk. If MySQL crashes, the redo log is "
                           "replayed on restart to recover committed transactions.",
            "config": "innodb_flush_log_at_trx_commit = 1 (default) — log flushed "
                      "to disk on every commit for maximum durability",
        },
    }
