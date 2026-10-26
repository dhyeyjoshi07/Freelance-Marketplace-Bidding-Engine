# DBMS Syllabus Coverage — BidForge

> All 9 units of a typical B.Tech DBMS syllabus demonstrated using BidForge's own entities (users, projects, bids, ratings) on **MySQL 26.7 (InnoDB)**.

---

## Unit 1: Introductory Concepts

BidForge uses MySQL as its DBMS instead of flat files because it needs concurrent access (row-level locking), data integrity (CHECK/FK constraints), crash recovery (InnoDB redo log), and structured queries (`SELECT ... ORDER BY match_score DESC`).

**Three-schema architecture (ANSI-SPARC):**
- **External level:** FastAPI routers return role-filtered JSON (clients see ranked bids, freelancers see their own bids)
- **Conceptual level:** SQLAlchemy models define 6 tables with relationships, constraints, triggers
- **Internal level:** InnoDB B+ tree indexes, 16KB pages, buffer pool, redo/undo logs

**Data independence:** SQLAlchemy ORM provides logical independence — renaming a column changes only the model, not the routers. Physical independence is inherent — MySQL manages storage internally.

---

## Unit 2: Entity-Relationship Model

**Entities:** User (strong), FreelancerProfile (weak, depends on User), Project (strong), Bid (strong), Rating (strong), AuditLog (strong)

**Key relationships:**
| Relationship | Cardinality | Implementation |
|---|---|---|
| User → FreelancerProfile | 1:1 | `UNIQUE(user_id)` on profiles |
| Client → Project | 1:N | FK `client_id` in projects |
| Project → Bid | 1:N | FK `project_id` in bids |
| Freelancer → Bid | 1:N | FK `freelancer_id` in bids |
| Project → Rating | 1:1 | `UNIQUE(project_id)` on ratings |

**Generalization:** User is specialized into Client/Freelancer via a discriminator column `role` (disjoint, total). Enforced by `CHECK(role IN ('client','freelancer'))`.

**Multivalued attributes:** `skills` and `required_skills` stored as JSON arrays (denormalized for Python `set` intersection performance).

**Derived attribute:** `avg_rating` computed incrementally via trigger, stored for O(1) reads.

---

## Unit 3: Relational Model

**ER-to-relational mapping:** Strong entities → tables with PK. Weak entity (FreelancerProfile) → table with FK + UNIQUE. 1:N relationships → FK in the "many" side. Multivalued attributes → JSON columns (denormalized).

**Relational algebra examples (BidForge queries):**
```
Selection:   σ_{status='open'}(projects)
Projection:  π_{username, email, role}(users)
Join:        bids ⋈_{freelancer_id = users.id} users
Aggregation: γ_{project_id; COUNT(*), AVG(amount)}(bids)
```

All translate directly to SQL queries used by the API.

---

## Unit 4: Normalization

**Functional dependencies in `bids`:**
- `id → project_id, freelancer_id, amount, match_score, created_at`
- `{project_id, freelancer_id} → id, amount, match_score, created_at`

**Normalization status:** All tables are in **BCNF** — every determinant is a candidate key.

**Intentional denormalizations:**
1. `skills` as JSON array instead of junction table → simpler Python `set` intersection, avoids JOIN + GROUP BY
2. `avg_rating` stored on profile instead of computed from ratings → O(1) reads, updated incrementally by trigger

---

## Unit 5: Query Processing

**Indexes created in `database.py`:**
```sql
CREATE INDEX idx_bids_project_score ON bids (project_id, match_score DESC);  -- covering index for bid ranking
CREATE INDEX idx_bids_freelancer ON bids (freelancer_id);
CREATE INDEX idx_projects_status ON projects (status);
```

**EXPLAIN comparison (with vs. without index):**
- With `idx_bids_project_score`: `type=ref`, `rows=3` — index lookup
- Without index: `type=ALL`, `rows=13`, `Using filesort` — full table scan

**Live demo:** `GET /api/admin/explain?query=SELECT * FROM bids WHERE project_id=1`

**Code:** `backend/services/query_analyzer.py`

---

## Unit 6: Transactions

**ACID in BidForge:**
- **Atomicity:** Bid acceptance (status update + accepted_bid_id) wrapped in single transaction. InnoDB undo log enables rollback.
- **Consistency:** CHECK constraints + FK constraints + triggers prevent invalid states.
- **Isolation:** Default REPEATABLE READ — concurrent reads see consistent snapshots.
- **Durability:** InnoDB redo log (WAL) — committed changes survive crashes.

**Savepoints:** `backend/services/transaction_manager.py` uses `db.begin_nested()` for partial rollback within batch operations.

**Isolation levels:** READ UNCOMMITTED → READ COMMITTED → REPEATABLE READ (default) → SERIALIZABLE. MySQL's REPEATABLE READ also prevents phantom reads via gap locking.

**Locking:** `SELECT ... FOR UPDATE` used for safe bid acceptance (prevents concurrent accept of same project).

**Live demo:** `GET /api/admin/acid`

---

## Unit 7: SQL

All SQL scripts are in `scripts/sql/`:

| Script | Contents |
|---|---|
| `ddl.sql` | CREATE TABLE with constraints, ALTER TABLE examples |
| `dml.sql` | SELECT (JOINs, subqueries, aggregates, CASE, EXISTS, BETWEEN), INSERT, UPDATE, DELETE |
| `dcl.sql` | CREATE USER, GRANT, REVOKE, roles (bidforge_user, bidforge_readonly, bidforge_client_role) |
| `transactions.sql` | START TRANSACTION, COMMIT, ROLLBACK, SAVEPOINT, isolation levels, locking |

**Constraints on all models:**
- `CHECK(amount > 0)` on bids, `CHECK(score >= 1 AND score <= 5)` on ratings
- `UNIQUE(project_id, freelancer_id)` on bids, `UNIQUE(project_id)` on ratings
- `FOREIGN KEY ... ON DELETE CASCADE` on all child tables

**Live demo:** `GET /api/admin/constraints?table_name=bids`

---

## Unit 8: PL/SQL (MySQL Equivalents)

MySQL stored procedures and triggers are the direct equivalent of Oracle PL/SQL.

**Triggers (defined in `database.py`):**
| Trigger | Type | Purpose |
|---|---|---|
| `trg_before_insert_bid` | BEFORE INSERT | Validate amount > 0, 0 ≤ match_score ≤ 1 |
| `trg_before_insert_project` | BEFORE INSERT | Validate budget_min < budget_max |
| `trg_after_insert_rating` | AFTER INSERT | Auto-update freelancer avg_rating |
| `trg_after_update_project_status` | AFTER UPDATE | Log status changes to audit_log |

**Stored procedures:**
- `sp_get_ranked_bids(project_id)` — ranked bids with freelancer names (IN param, JOIN, ORDER BY)
- `sp_freelancer_stats(user_id)` — bid statistics using DECLARE, SELECT INTO
- `sp_bid_summary_cursor(project_id)` — CURSOR + FETCH + LOOP + HANDLER demo

**Stored function:**
- `fn_price_fit(amount, min, max)` — mirrors Python `MatchEngine._compute_price_fit()` as DETERMINISTIC function

**Key MySQL vs. PL/SQL differences:** `SIGNAL` replaces `RAISE_APPLICATION_ERROR`, `NEW.column` instead of `:NEW.column`, `DELIMITER //` needed, no packages.

**Live demo:** `GET /api/admin/triggers`, `GET /api/admin/stored-procedures`, `GET /api/admin/stored-procedure/ranked-bids/1`

---

## Unit 9: Advanced Topics

**AES-256 column encryption** (`backend/services/encryption.py`):
```python
from backend.services.encryption import encrypt, decrypt
encrypted = encrypt("alice@dev.io")   # Fernet ciphertext with IV + HMAC
original  = decrypt(encrypted)        # "alice@dev.io"
```
Key stored only in app config, never in DB. Defense-in-depth: even with full DB access, encrypted columns are unreadable.

**Audit trail** (`audit_log` table): Populated automatically by `trg_after_update_project_status` trigger. Immutable record of all project status transitions.

**Access control (GRANT/REVOKE):** `scripts/sql/dcl.sql` defines `bidforge_user` (full access), `bidforge_readonly` (SELECT only), role-based grants (`bidforge_client_role`, `bidforge_freelancer_role`).

**Application-level RBAC:** JWT tokens contain role claim → `require_role("client")` dependency guards routes. Dual-layer: app-level RBAC + DB-level GRANT.

**Password hashing:** bcrypt with random salt and work factor 12 (~250ms per hash).

**JSON/NoSQL hybrid:** Skills stored as JSON arrays in relational tables — demonstrates how relational and document paradigms coexist.

**Live demo:** `POST /api/admin/encrypt?plaintext=test`, `GET /api/admin/audit-log`
