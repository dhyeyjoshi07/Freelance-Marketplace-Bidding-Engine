-- =============================================================================
-- Transactions (DBMS Unit 6: Transaction Management)
-- =============================================================================
-- Demonstrates BEGIN, COMMIT, ROLLBACK, SAVEPOINT in MySQL InnoDB.
-- =============================================================================

USE bidforge;

-- =============================================================================
-- 1. Basic Transaction: Atomic bid acceptance
-- =============================================================================
-- Both the project status update AND the accepted_bid_id update must
-- succeed together, or neither should be persisted.

START TRANSACTION;

    -- Step 1: Update project status to in_progress
    UPDATE projects SET status = 'in_progress' WHERE id = 1 AND status = 'open';

    -- Step 2: Set the accepted bid
    UPDATE projects SET accepted_bid_id = 1 WHERE id = 1;

    -- If both succeeded, commit
COMMIT;

-- If either failed, we would ROLLBACK instead:
-- ROLLBACK;


-- =============================================================================
-- 2. Savepoints: Partial rollback within a transaction
-- =============================================================================
-- Scenario: Process multiple bids, rolling back only the invalid ones

START TRANSACTION;

    -- Insert first bid (valid)
    INSERT INTO bids (project_id, freelancer_id, amount, proposal, match_score)
    VALUES (2, 4, 5000, 'Valid bid', 0.85);

    -- Create savepoint after first bid
    SAVEPOINT after_first_bid;

    -- Insert second bid (might fail due to CHECK constraint)
    -- INSERT INTO bids (project_id, freelancer_id, amount, proposal, match_score)
    -- VALUES (2, 5, -100, 'Invalid amount', 0.5);
    -- This would fail: CHECK constraint ck_bid_amount_positive

    -- If second bid failed, rollback to savepoint (keeps first bid)
    -- ROLLBACK TO after_first_bid;

    -- First bid is still intact
COMMIT;


-- =============================================================================
-- 3. Isolation Levels
-- =============================================================================

-- Check current isolation level
SELECT @@transaction_isolation;

-- Set isolation level for current session
-- SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
-- SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;  -- MySQL default
-- SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- Demonstrate REPEATABLE READ:
-- Session 1:
--   START TRANSACTION;
--   SELECT * FROM bids WHERE project_id = 1;  -- sees 3 bids
--
-- Session 2 (concurrent):
--   INSERT INTO bids (...) VALUES (...);       -- adds a new bid
--   COMMIT;
--
-- Session 1:
--   SELECT * FROM bids WHERE project_id = 1;  -- still sees 3 bids (snapshot)
--   COMMIT;
--   SELECT * FROM bids WHERE project_id = 1;  -- now sees 4 bids


-- =============================================================================
-- 4. Locking Demonstrations
-- =============================================================================

-- Shared lock (FOR SHARE): allows concurrent reads, blocks writes
-- SELECT * FROM projects WHERE id = 1 FOR SHARE;

-- Exclusive lock (FOR UPDATE): blocks both reads and writes
-- SELECT * FROM projects WHERE id = 1 FOR UPDATE;

-- Row-level locking example (bid acceptance):
-- START TRANSACTION;
-- SELECT * FROM projects WHERE id = 1 FOR UPDATE;  -- lock the project row
-- UPDATE projects SET status = 'in_progress', accepted_bid_id = 1 WHERE id = 1;
-- COMMIT;  -- releases the lock


-- =============================================================================
-- 5. Deadlock scenario (for documentation only — do NOT run)
-- =============================================================================
-- Session 1:                              Session 2:
-- START TRANSACTION;                      START TRANSACTION;
-- UPDATE projects SET ... WHERE id=1;     UPDATE bids SET ... WHERE id=2;
-- -- waits...                             -- waits...
-- UPDATE bids SET ... WHERE id=2;         UPDATE projects SET ... WHERE id=1;
-- -- DEADLOCK! MySQL auto-detects and     -- one session gets:
-- -- rolls back one transaction           -- ERROR 1213: Deadlock found


-- =============================================================================
-- 6. Log-based Recovery (conceptual — InnoDB internals)
-- =============================================================================
-- InnoDB uses two log types for crash recovery:
--
-- REDO LOG (write-ahead log):
--   - Before modifying a data page, the change is first written to the redo log
--   - On crash, MySQL replays the redo log to reconstruct committed changes
--   - Controlled by: innodb_flush_log_at_trx_commit
--     = 1 (default): flush to disk on every COMMIT (safest, slowest)
--     = 2: flush to OS buffer on COMMIT, fsync every second
--     = 0: write to buffer every second (fastest, least safe)
--
-- UNDO LOG:
--   - Stores the original data before modification
--   - Used for ROLLBACK and for MVCC (multi-version concurrency control)
--   - When a transaction reads a row, InnoDB uses the undo log to reconstruct
--     the row version that was current at the transaction's snapshot time
--
-- SHOW ENGINE INNODB STATUS\G  -- view InnoDB internals including log info
