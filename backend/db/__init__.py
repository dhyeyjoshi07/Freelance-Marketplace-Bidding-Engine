"""
Database sub-package — triggers, indexes, stored procedures, and audit DDL.

Each module contains the raw SQL definitions and a create_*() function
that registers them against a live MySQL connection.
"""

from backend.db.triggers import create_triggers
from backend.db.indexes import create_indexes
from backend.db.procedures import create_stored_procedures
from backend.db.audit import AUDIT_LOG_TABLE

__all__ = [
    "create_triggers",
    "create_indexes",
    "create_stored_procedures",
    "AUDIT_LOG_TABLE",
]
