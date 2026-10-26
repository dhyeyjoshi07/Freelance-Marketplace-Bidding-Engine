"""
DBMS feature tests — verifies triggers, constraints, encryption,
query analysis, transactions, and stored procedures.

These tests demonstrate DBMS syllabus topics using BidForge's own
entities and MySQL-specific features.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.services.encryption import encrypt, decrypt
from backend.services.query_analyzer import explain_query, get_table_stats
from backend.services.transaction_manager import (
    get_isolation_level, demonstrate_acid_properties
)


# ---- MySQL test database ----
TEST_DATABASE_URL = "mysql+pymysql://bidforge_user:bidforge_pass@localhost:3306/bidforge_test"
test_engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Helper SQL: user insert with all NOT NULL columns
_INSERT_USER = (
    "INSERT INTO users (id, username, email, password_hash, role, created_at) "
    "VALUES (:id, :username, :email, 'hash', :role, NOW())"
)
_INSERT_PROJECT = (
    "INSERT INTO projects (id, client_id, title, required_skills, "
    "budget_min, budget_max, deadline, status, client_completed, freelancer_completed, created_at) "
    "VALUES (:id, :cid, :title, '[]', :bmin, :bmax, '2027-01-01', :status, 0, 0, NOW())"
)
_INSERT_BID = (
    "INSERT INTO bids (project_id, freelancer_id, amount, match_score, created_at) "
    "VALUES (:pid, :fid, :amount, :score, NOW())"
)


@pytest.fixture(autouse=True)
def setup_db():
    """Set up clean test database."""
    import backend.models.user       # noqa: F401
    import backend.models.project    # noqa: F401
    import backend.models.bid        # noqa: F401

    Base.metadata.create_all(bind=test_engine)

    # Clean slate
    with test_engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"TRUNCATE TABLE {table.name}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    yield

    with test_engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"TRUNCATE TABLE {table.name}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


# =========================================================================
# Unit 5: Query Processing
# =========================================================================

class TestQueryProcessing:
    """DBMS Unit 5: Query analysis and EXPLAIN."""

    def test_explain_returns_plan(self, db):
        """EXPLAIN produces an execution plan for a SELECT query."""
        plan = explain_query(db, "SELECT 1 FROM users WHERE role = 'client'")
        assert len(plan) > 0
        # EXPLAIN output varies on empty tables but should always have these keys
        first = plan[0]
        assert "select_type" in first or "EXPLAIN" in str(first)

    def test_table_stats(self, db):
        """INFORMATION_SCHEMA.TABLES provides optimizer statistics."""
        stats = get_table_stats(db, "users")
        assert "table" in stats
        assert stats["table"] == "users"
        assert "estimated_rows" in stats


# =========================================================================
# Unit 6: Transactions
# =========================================================================

class TestTransactions:
    """DBMS Unit 6: ACID properties and isolation levels."""

    def test_isolation_level(self, db):
        """MySQL default isolation level is REPEATABLE-READ."""
        level = get_isolation_level(db)
        assert "REPEATABLE" in level.upper()

    def test_acid_explanation(self, db):
        """ACID properties are fully documented for BidForge."""
        acid = demonstrate_acid_properties(db)
        assert "atomicity" in acid
        assert "consistency" in acid
        assert "isolation" in acid
        assert "durability" in acid
        assert "mechanism" in acid["atomicity"]

    def test_transaction_rollback(self, db):
        """Rollback undoes all changes in the transaction."""
        db.execute(text(_INSERT_USER), {"id": 1, "username": "rollback_test", "email": "rb@t.com", "role": "client"})
        db.rollback()
        result = db.execute(text("SELECT COUNT(*) FROM users WHERE username='rollback_test'"))
        assert result.scalar() == 0

    def test_savepoint(self, db):
        """Savepoints allow partial rollback within a transaction."""
        # Insert first user
        db.execute(text(_INSERT_USER), {"id": 1, "username": "sp_user1", "email": "sp1@t.com", "role": "client"})

        # Create savepoint
        savepoint = db.begin_nested()

        # Insert second user
        db.execute(text(_INSERT_USER), {"id": 2, "username": "sp_user2", "email": "sp2@t.com", "role": "client"})

        # Rollback to savepoint (undoes sp_user2 only)
        savepoint.rollback()

        # sp_user1 should still exist, sp_user2 should not
        r1 = db.execute(text("SELECT COUNT(*) FROM users WHERE username='sp_user1'"))
        r2 = db.execute(text("SELECT COUNT(*) FROM users WHERE username='sp_user2'"))
        assert r1.scalar() == 1
        assert r2.scalar() == 0

        db.rollback()  # Clean up


# =========================================================================
# Unit 7: SQL Constraints
# =========================================================================

class TestConstraints:
    """DBMS Unit 7: CHECK, UNIQUE, FK constraints."""

    def test_check_constraint_role(self, db):
        """CHECK constraint rejects invalid role values."""
        with pytest.raises(Exception):
            db.execute(text(_INSERT_USER), {"id": 1, "username": "bad", "email": "bad@t.com", "role": "admin"})
            db.commit()
        db.rollback()

    def test_check_constraint_rating_score(self, db):
        """CHECK constraint rejects rating scores outside 1-5."""
        # Set up: client, freelancer, completed project
        db.execute(text(_INSERT_USER), {"id": 100, "username": "ck_client", "email": "ckc@t.com", "role": "client"})
        db.execute(text(_INSERT_USER), {"id": 101, "username": "ck_free", "email": "ckf@t.com", "role": "freelancer"})
        db.execute(text(_INSERT_PROJECT), {"id": 100, "cid": 100, "title": "Test", "bmin": 100, "bmax": 200, "status": "completed"})
        db.commit()

        # Score of 6 should be rejected by CHECK constraint
        with pytest.raises(Exception):
            db.execute(text(
                "INSERT INTO ratings (project_id, freelancer_id, client_id, score, created_at) "
                "VALUES (100, 101, 100, 6, NOW())"
            ))
            db.commit()
        db.rollback()

    def test_unique_constraint_duplicate_bid(self, db):
        """UNIQUE constraint prevents duplicate bids."""
        db.execute(text(_INSERT_USER), {"id": 200, "username": "uq_client", "email": "uqc@t.com", "role": "client"})
        db.execute(text(_INSERT_USER), {"id": 201, "username": "uq_free", "email": "uqf@t.com", "role": "freelancer"})
        db.execute(text(_INSERT_PROJECT), {"id": 200, "cid": 200, "title": "UQ Test", "bmin": 100, "bmax": 200, "status": "open"})
        db.execute(text(_INSERT_BID), {"pid": 200, "fid": 201, "amount": 5000, "score": 0.8})
        db.commit()

        # Duplicate bid should fail
        with pytest.raises(Exception):
            db.execute(text(_INSERT_BID), {"pid": 200, "fid": 201, "amount": 6000, "score": 0.9})
            db.commit()
        db.rollback()

    def test_foreign_key_constraint(self, db):
        """FK constraint prevents bids on non-existent projects."""
        db.execute(text(_INSERT_USER), {"id": 300, "username": "fk_free", "email": "fkf@t.com", "role": "freelancer"})
        db.commit()

        with pytest.raises(Exception):
            db.execute(text(_INSERT_BID), {"pid": 99999, "fid": 300, "amount": 5000, "score": 0.5})
            db.commit()
        db.rollback()

    def test_check_bid_amount_positive(self, db):
        """CHECK constraint rejects non-positive bid amounts."""
        db.execute(text(_INSERT_USER), {"id": 400, "username": "ck_client2", "email": "ck2c@t.com", "role": "client"})
        db.execute(text(_INSERT_USER), {"id": 401, "username": "ck_free2", "email": "ck2f@t.com", "role": "freelancer"})
        db.execute(text(_INSERT_PROJECT), {"id": 400, "cid": 400, "title": "CK Test", "bmin": 100, "bmax": 200, "status": "open"})
        db.commit()

        with pytest.raises(Exception):
            db.execute(text(_INSERT_BID), {"pid": 400, "fid": 401, "amount": -100, "score": 0.5})
            db.commit()
        db.rollback()


# =========================================================================
# Unit 9: Data Security — Encryption
# =========================================================================

class TestEncryption:
    """DBMS Unit 9: AES-256 column-level encryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encryption followed by decryption returns the original text."""
        original = "alice@dev.io"
        encrypted = encrypt(original)
        assert encrypted != original
        assert decrypt(encrypted) == original

    def test_encrypted_values_are_different(self):
        """Each encryption produces a different ciphertext (due to IV)."""
        plaintext = "test@example.com"
        e1 = encrypt(plaintext)
        e2 = encrypt(plaintext)
        assert e1 != e2  # Different IVs

    def test_empty_string_passthrough(self):
        """Empty strings are passed through without encryption."""
        assert encrypt("") == ""
        assert decrypt("") == ""

    def test_encrypt_none_passthrough(self):
        """None values are passed through without encryption."""
        assert encrypt(None) is None
        assert decrypt(None) is None
