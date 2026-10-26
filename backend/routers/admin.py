"""
Admin router — exposes DBMS-related endpoints for educational demonstration.

These endpoints are used to:
- Inspect query execution plans (DBMS Unit 5)
- View ACID property explanations (DBMS Unit 6)
- Test encryption/decryption (DBMS Unit 9)
- View database statistics and indexes
- Call stored procedures
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.services.query_analyzer import (
    explain_query, get_table_stats, get_index_info, demonstrate_query_optimization
)
from backend.services.transaction_manager import demonstrate_acid_properties
from backend.services.encryption import encrypt, decrypt


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/explain")
def explain_endpoint(query: str, db: Session = Depends(get_db)):
    """
    Run EXPLAIN on a query and return the execution plan.

    Query param: ?query=SELECT * FROM bids WHERE project_id = 1
    """
    plan = explain_query(db, query)
    return {"query": query, "plan": plan}


@router.get("/table-stats/{table_name}")
def table_stats(table_name: str, db: Session = Depends(get_db)):
    """Get optimizer statistics for a table (DBMS Unit 5)."""
    stats = get_table_stats(db, table_name)
    indexes = get_index_info(db, table_name)
    return {"stats": stats, "indexes": indexes}


@router.get("/query-optimization-demo")
def query_optimization_demo(db: Session = Depends(get_db)):
    """
    Demonstrate query optimization with/without indexes (DBMS Unit 5).
    Shows how indexes transform full table scans into indexed lookups.
    """
    return demonstrate_query_optimization(db)


@router.get("/acid")
def acid_properties(db: Session = Depends(get_db)):
    """Explain ACID properties as implemented in BidForge (DBMS Unit 6)."""
    return demonstrate_acid_properties(db)


@router.post("/encrypt")
def encrypt_demo(plaintext: str):
    """Encrypt a string using AES-256 (DBMS Unit 9: Data Security)."""
    ciphertext = encrypt(plaintext)
    decrypted = decrypt(ciphertext)
    return {
        "plaintext": plaintext,
        "ciphertext": ciphertext,
        "decrypted": decrypted,
        "match": plaintext == decrypted,
    }


@router.get("/stored-procedure/ranked-bids/{project_id}")
def call_sp_ranked_bids(project_id: int, db: Session = Depends(get_db)):
    """
    Call the sp_get_ranked_bids stored procedure (DBMS Unit 8: PL/SQL).

    This demonstrates calling a MySQL stored procedure from Python via
    SQLAlchemy's text() execution.
    """
    result = db.execute(text("CALL sp_get_ranked_bids(:pid)"), {"pid": project_id})
    columns = result.keys()
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return {"project_id": project_id, "ranked_bids": rows}


@router.get("/stored-procedure/freelancer-stats/{user_id}")
def call_sp_freelancer_stats(user_id: int, db: Session = Depends(get_db)):
    """Call the sp_freelancer_stats stored procedure (DBMS Unit 8)."""
    result = db.execute(text("CALL sp_freelancer_stats(:uid)"), {"uid": user_id})
    columns = result.keys()
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return {"user_id": user_id, "stats": rows[0] if rows else {}}


@router.get("/audit-log")
def get_audit_log(limit: int = 50, db: Session = Depends(get_db)):
    """View the audit log (DBMS Unit 9: Data Security)."""
    result = db.execute(text(
        "SELECT * FROM audit_log ORDER BY changed_at DESC LIMIT :limit"
    ), {"limit": limit})
    columns = result.keys()
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return {"audit_log": rows}


@router.get("/triggers")
def list_triggers(db: Session = Depends(get_db)):
    """List all triggers in the database (DBMS Unit 8)."""
    result = db.execute(text(
        "SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, "
        "ACTION_TIMING, ACTION_STATEMENT "
        "FROM INFORMATION_SCHEMA.TRIGGERS "
        "WHERE TRIGGER_SCHEMA = DATABASE()"
    ))
    columns = result.keys()
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return {"triggers": rows}


@router.get("/stored-procedures")
def list_stored_procedures(db: Session = Depends(get_db)):
    """List all stored procedures and functions (DBMS Unit 8)."""
    result = db.execute(text(
        "SELECT ROUTINE_NAME, ROUTINE_TYPE, DATA_TYPE, CREATED "
        "FROM INFORMATION_SCHEMA.ROUTINES "
        "WHERE ROUTINE_SCHEMA = DATABASE()"
    ))
    columns = result.keys()
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return {"routines": rows}


@router.get("/constraints")
def list_constraints(table_name: str = None, db: Session = Depends(get_db)):
    """List CHECK, UNIQUE, FOREIGN KEY constraints (DBMS Unit 7)."""
    query = (
        "SELECT CONSTRAINT_NAME, TABLE_NAME, CONSTRAINT_TYPE "
        "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
        "WHERE TABLE_SCHEMA = DATABASE()"
    )
    params = {}
    if table_name:
        query += " AND TABLE_NAME = :table"
        params["table"] = table_name

    result = db.execute(text(query), params)
    columns = result.keys()
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return {"constraints": rows}
