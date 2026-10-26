# Unit 6: Transaction Management — BidForge

## 6.1 ACID Properties in BidForge

### Atomicity
**"All or nothing"** — either every operation in a transaction is committed, or none are.

**BidForge example:** Accepting a bid requires two updates:
1. `UPDATE projects SET status = 'in_progress'`
2. `UPDATE projects SET accepted_bid_id = ?`

If step 2 fails, step 1 must be rolled back. SQLAlchemy's `session.commit()` wraps both in a single MySQL transaction.

```python
# backend/services/transaction_manager.py
with transactional_session() as db:
    project.status = "in_progress"       # Step 1
    project.accepted_bid_id = bid.id     # Step 2
    # If either fails → automatic rollback of BOTH
```

**MySQL mechanism:** InnoDB **undo log** stores the pre-modification version of each row. On `ROLLBACK`, the undo log is replayed to restore the original state.

### Consistency
**"Valid state to valid state"** — every transaction moves the database from one valid state to another.

**BidForge constraints that enforce consistency:**
- `CHECK(amount > 0)` — no zero/negative bids
- `CHECK(score >= 1 AND score <= 5)` — ratings are 1-5 stars
- `UNIQUE(project_id, freelancer_id)` — no duplicate bids
- `FOREIGN KEY` — can't bid on a non-existent project
- **Triggers:** `trg_before_insert_bid` validates values before insertion

### Isolation
**"Concurrent transactions don't interfere"** — each transaction sees a consistent snapshot.

**MySQL default: REPEATABLE READ**
```
Session A (reads bids):          Session B (inserts bid):
─────────────────────            ────────────────────────
START TRANSACTION;
SELECT COUNT(*) FROM bids;       
  → 13 bids                     START TRANSACTION;
                                 INSERT INTO bids VALUES(...);
                                 COMMIT;
SELECT COUNT(*) FROM bids;
  → 13 bids (snapshot!)         ← Session A doesn't see B's insert
COMMIT;
SELECT COUNT(*) FROM bids;
  → 14 bids (now visible)
```

### Durability
**"Committed = permanent"** — once committed, survives crashes.

**MySQL mechanism:** InnoDB **redo log** (write-ahead logging). Before modifying data pages, the change is first written to the redo log on disk. On crash, MySQL replays the redo log.

Config: `innodb_flush_log_at_trx_commit = 1` (default) = flush on every commit.

## 6.2 Savepoints

MySQL supports `SAVEPOINT` for partial rollback within a transaction:

```python
# backend/services/transaction_manager.py — execute_with_savepoint()
def execute_with_savepoint(db, operations):
    for i, op in enumerate(operations):
        savepoint = db.begin_nested()   # SAVEPOINT sp_i
        try:
            result = op(db)
            savepoint.commit()           # Release savepoint
        except Exception:
            savepoint.rollback()         # ROLLBACK TO SAVEPOINT sp_i
```

**Use case:** Process a batch of bids — if one bid fails validation, rollback only that bid, keep the rest.

## 6.3 Isolation Levels

| Level | Dirty Read | Non-Repeatable Read | Phantom Read |
|---|---|---|---|
| READ UNCOMMITTED | ✅ Possible | ✅ Possible | ✅ Possible |
| READ COMMITTED | ❌ Prevented | ✅ Possible | ✅ Possible |
| **REPEATABLE READ** (default) | ❌ Prevented | ❌ Prevented | ❌ Prevented* |
| SERIALIZABLE | ❌ Prevented | ❌ Prevented | ❌ Prevented |

*MySQL's REPEATABLE READ uses gap locking to prevent phantom reads, unlike the SQL standard.

```python
# Check current isolation level
isolation = get_isolation_level(db)  # "REPEATABLE-READ"

# Change for testing
set_isolation_level(db, "SERIALIZABLE")
```

## 6.4 Locking in InnoDB

| Lock Type | Scope | BidForge Use Case |
|---|---|---|
| **Shared (S)** | Row | `SELECT ... FOR SHARE` — read a project while preventing changes |
| **Exclusive (X)** | Row | `SELECT ... FOR UPDATE` — lock a project row before accepting a bid |
| **Intent Shared (IS)** | Table | Signals intent to acquire S locks on rows |
| **Intent Exclusive (IX)** | Table | Signals intent to acquire X locks on rows |
| **Gap Lock** | Index range | Prevents phantom inserts between existing index values |
| **Next-Key Lock** | Row + gap | Combination of row lock + gap lock (default for REPEATABLE READ) |

**Bid acceptance with explicit locking:**
```sql
START TRANSACTION;
-- Lock the project row (prevents concurrent accept)
SELECT * FROM projects WHERE id = 1 FOR UPDATE;
-- Now safe to update
UPDATE projects SET status = 'in_progress', accepted_bid_id = 1 WHERE id = 1;
COMMIT;
```

## 6.5 Deadlock Detection

InnoDB automatically detects deadlocks using a wait-for graph. When detected, it rolls back the transaction with the fewest changes:

```
Session A:                              Session B:
UPDATE projects SET ... WHERE id=1;     UPDATE bids SET ... WHERE id=2;
  (holds X-lock on project 1)             (holds X-lock on bid 2)
UPDATE bids SET ... WHERE id=2;         UPDATE projects SET ... WHERE id=1;
  ← BLOCKS (bid 2 locked by B)           ← BLOCKS (project 1 locked by A)

  → DEADLOCK DETECTED → MySQL rolls back one transaction
```

## 6.6 Log-Based Recovery

InnoDB uses **write-ahead logging (WAL)** with two log types:

```
Transaction T1: UPDATE bids SET amount=8000 WHERE id=1

1. Write to REDO LOG: <T1, bids, id=1, amount, old=5000, new=8000>
2. Flush redo log to disk (fsync)
3. Modify data page in buffer pool (in memory)
4. On COMMIT: mark T1 as committed in redo log
5. Data page written to disk later (async checkpoint)

On crash:
- Redo log replayed → committed changes restored
- Undo log replayed → uncommitted changes rolled back
```

## 6.7 Live Demo via API

```bash
# View ACID properties explanation
curl http://localhost:8000/api/admin/acid

# View audit log (populated by triggers on state changes)
curl http://localhost:8000/api/admin/audit-log
```

**Python code:** `backend/services/transaction_manager.py`
