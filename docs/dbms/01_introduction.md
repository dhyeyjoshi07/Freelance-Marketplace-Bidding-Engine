# Unit 1: Introductory DBMS Concepts — Mapped to BidForge

## 1.1 Applications and Purpose of DBMS

A DBMS (Database Management System) provides structured storage, concurrent access, data integrity, and crash recovery. BidForge uses **MySQL 26.7** (InnoDB engine) as its DBMS.

**Why BidForge needs a DBMS instead of flat files:**

| Requirement | Flat Files | MySQL (BidForge) |
|---|---|---|
| Concurrent bid submissions | Race conditions, data corruption | InnoDB row-level locking, ACID transactions |
| Prevent duplicate bids | Manual file scanning | `UNIQUE(project_id, freelancer_id)` constraint |
| Enforce budget rules | Application code only | `CHECK(budget_min >= 0)` at DB level |
| Crash recovery | Data loss | InnoDB redo log + write-ahead logging |
| Query ranked bids | Parse all bid files, sort in memory | `SELECT ... ORDER BY match_score DESC` with index |

## 1.2 Data Independence

**Physical data independence:** BidForge's application code never references file paths, page sizes, or storage layout. MySQL manages all physical storage in InnoDB tablespace files (`ibdata1`, `.ibd` files). We can move the data directory, change page size, or switch storage engines without modifying a single line of Python code.

**Logical data independence:** SQLAlchemy ORM provides logical independence. The Python models (`User`, `Project`, `Bid`) map to tables, but the application logic works with Python objects, not SQL. If we rename a column (e.g., `match_score` → `fit_score`), only the model definition changes — all routers and services continue to reference `bid.match_score` through the ORM.

```python
# Application code is independent of physical storage:
db.query(User).filter(User.username == "alice")
# SQLAlchemy translates this to SQL, PyMySQL sends it over TCP to MySQL
# MySQL reads from InnoDB pages — none of this is visible to the app
```

## 1.3 System Architecture (Three-Schema / ANSI-SPARC)

BidForge implements the ANSI-SPARC three-level architecture:

```
┌─────────────────────────────────────────────────────────┐
│ EXTERNAL LEVEL (View Level)                              │
│                                                          │
│ Client view:   sees projects, ranked bids, ratings       │
│ Freelancer view: sees open projects, own bids, profile   │
│ Admin view:    sees audit logs, query plans, constraints │
│                                                          │
│ Implementation: FastAPI routers return role-filtered JSON │
├─────────────────────────────────────────────────────────┤
│ CONCEPTUAL LEVEL (Logical Level)                         │
│                                                          │
│ Tables: users, freelancer_profiles, projects, bids,      │
│         ratings, audit_log                               │
│ Relationships: FK constraints (user→profile, project→bid)│
│ Constraints: CHECK, UNIQUE, NOT NULL                     │
│                                                          │
│ Implementation: SQLAlchemy models define the schema       │
├─────────────────────────────────────────────────────────┤
│ INTERNAL LEVEL (Physical Level)                          │
│                                                          │
│ InnoDB tablespace files (.ibd), B+ tree indexes,         │
│ buffer pool, redo/undo logs, page format (16KB default)  │
│                                                          │
│ Implementation: MySQL InnoDB storage engine               │
└─────────────────────────────────────────────────────────┘
```

## 1.4 Data Abstraction

The three levels of data abstraction in BidForge:

1. **Physical level:** How data is physically stored. InnoDB stores rows in 16KB pages within B+ tree structures. Indexes are separate B+ trees. The `idx_bids_project_score` index stores `(project_id, match_score)` pairs for efficient bid ranking.

2. **Logical level:** What data is stored and the relationships between them. The `bids` table has columns `(id, project_id, freelancer_id, amount, match_score, ...)` with foreign keys to `projects` and `users`.

3. **View level:** What each user type sees. A client calling `GET /api/projects/1/bids` sees ranked bids with freelancer names. A freelancer calling `GET /api/freelancers/me/bids` sees only their own bids. The same underlying `bids` table serves both views.

## 1.5 Database Users and DBA

| User Type | BidForge Mapping | Database Access |
|---|---|---|
| **End users** | Clients and Freelancers | Access via REST API → ORM → MySQL. Never see SQL. |
| **Application programmers** | The developers | Write SQLAlchemy models, FastAPI routes. Use `db.query()`. |
| **Database Administrator** | Admin endpoints (`/api/admin/*`) | Can run `EXPLAIN`, view triggers, check constraints, audit logs. |
| **System DBA** | MySQL root user | Full access: `GRANT`, `REVOKE`, backup, replication, tuning. |

**DBA responsibilities in BidForge:**
- Create the `bidforge` database and `bidforge_user` account (`scripts/sql/dcl.sql`)
- Monitor query performance via `EXPLAIN` (`/api/admin/explain`)
- Review audit logs for unauthorized state transitions (`/api/admin/audit-log`)
- Manage backups via `mysqldump bidforge > backup.sql`
