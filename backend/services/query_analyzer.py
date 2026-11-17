"""
Query analyzer service (DBMS Unit 5: Query Processing & Optimization).

Wraps MySQL's EXPLAIN statement to inspect query execution plans.
This demonstrates how the query optimizer chooses access paths (full table scan
vs. index lookup), join strategies, and row estimates.

Usage:
    from backend.services.query_analyzer import explain_query
    plan = explain_query(db, "SELECT * FROM bids WHERE project_id = 1")
    # Returns the EXPLAIN output as a list of dicts

EXPLAIN output columns (MySQL):
    id            — query sequence number
    select_type   — SIMPLE, PRIMARY, SUBQUERY, DERIVED, etc.
    table         — the table being accessed
    type          — access type: ALL (full scan), ref (index), eq_ref (unique index), range, etc.
    possible_keys — indexes MySQL considered
    key           — index MySQL actually chose
    rows          — estimated rows to examine
    Extra         — additional info (Using index, Using where, Using filesort, etc.)
"""

import re

from sqlalchemy import text
from sqlalchemy.orm import Session


# Tables that the EXPLAIN and SHOW INDEX endpoints are allowed to reference.
# Any table name not in this set is rejected to prevent SQL injection.
ALLOWED_TABLES = frozenset({
    "users", "freelancer_profiles", "projects",
    "bids", "ratings", "audit_log",
})

# Regex that matches a bare SELECT statement (no semicolons, no stacked
# queries).  This is intentionally restrictive: it allows SELECT … but
# rejects DDL, DML writes, and multi-statement payloads.
_SAFE_SELECT_RE = re.compile(
    r"^\s*SELECT\s.+$",
    re.IGNORECASE | re.DOTALL,
)


def _validate_select_query(sql: str) -> str:
    """
    Validate that *sql* is a single SELECT statement.

    Raises ValueError for anything that looks like injection:
    semicolons (stacked queries), DDL/DML keywords at statement
    boundaries, or non-SELECT statements.
    """
    stripped = sql.strip().rstrip(";").strip()

    # Reject if it contains a semicolon (attempt to stack queries)
    if ";" in stripped:
        raise ValueError("Query must not contain semicolons")

    # Must start with SELECT
    if not _SAFE_SELECT_RE.match(stripped):
        raise ValueError("Only SELECT queries are allowed for EXPLAIN")

    return stripped


def _validate_table_name(table_name: str) -> str:
    """
    Validate that *table_name* is one of the known BidForge tables.

    Raises ValueError for unknown or malicious table names.
    """
    cleaned = table_name.strip().lower()
    if cleaned not in ALLOWED_TABLES:
        raise ValueError(
            f"Unknown table: '{table_name}'. "
            f"Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}"
        )
    return cleaned


def explain_query(db: Session, sql: str) -> list[dict]:
    """
    Run EXPLAIN on a SQL query and return the execution plan.

    Args:
        db: SQLAlchemy session.
        sql: The SELECT query to analyze (must be a single SELECT statement).

    Returns:
        List of dicts, each representing one row of the EXPLAIN output.

    Raises:
        ValueError: If *sql* is not a valid SELECT statement.
    """
    safe_sql = _validate_select_query(sql)
    result = db.execute(text(f"EXPLAIN {safe_sql}"))
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


def explain_analyze(db: Session, sql: str) -> list[dict]:
    """
    Run EXPLAIN ANALYZE (MySQL 8.0.18+) to get actual execution metrics.

    Unlike plain EXPLAIN, this actually executes the query and reports
    real row counts, loop counts, and timing — useful for identifying
    where the optimizer's estimates diverge from reality.
    """
    safe_sql = _validate_select_query(sql)
    result = db.execute(text(f"EXPLAIN ANALYZE {safe_sql}"))
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


def get_table_stats(db: Session, table_name: str) -> dict:
    """
    Retrieve optimizer statistics for a table from INFORMATION_SCHEMA.

    MySQL's query optimizer uses these statistics to estimate selectivity
    and choose between index scan vs. full table scan.
    """
    validated_table = _validate_table_name(table_name)
    result = db.execute(text(
        "SELECT TABLE_ROWS, AVG_ROW_LENGTH, DATA_LENGTH, INDEX_LENGTH "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
    ), {"table": validated_table})
    row = result.fetchone()
    if not row:
        return {}
    return {
        "table": validated_table,
        "estimated_rows": row[0],
        "avg_row_length": row[1],
        "data_size_bytes": row[2],
        "index_size_bytes": row[3],
    }


def get_index_info(db: Session, table_name: str) -> list[dict]:
    """
    List all indexes on a table via SHOW INDEX.

    Useful for verifying that the expected indexes exist and checking
    their cardinality (number of distinct values — higher cardinality
    means the index is more selective and more useful to the optimizer).
    """
    validated_table = _validate_table_name(table_name)
    result = db.execute(text(f"SHOW INDEX FROM {validated_table}"))
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


def demonstrate_query_optimization(db: Session) -> dict:
    """
    Demonstrate query optimization concepts using BidForge's own tables.

    Compares query plans WITH and WITHOUT indexes to show how indexes
    transform a full table scan (type=ALL) into an index lookup (type=ref).

    Returns a dict with 'with_index' and 'without_index' plans.
    """
    # Query: "Find all bids for project 1, ranked by score"
    query = "SELECT * FROM bids WHERE project_id = 1 ORDER BY match_score DESC"

    plan_with_index = explain_query(db, query)

    # Get table statistics
    bids_stats = get_table_stats(db, "bids")
    projects_stats = get_table_stats(db, "projects")

    return {
        "query": query,
        "execution_plan": plan_with_index,
        "table_stats": {
            "bids": bids_stats,
            "projects": projects_stats,
        },
        "optimization_notes": [
            "idx_bids_project_score covers (project_id, match_score DESC) — "
            "the optimizer uses this index to avoid a filesort",
            "Without this index, MySQL would do a full table scan (type=ALL) "
            "and then sort all matching rows in memory",
        ],
    }
