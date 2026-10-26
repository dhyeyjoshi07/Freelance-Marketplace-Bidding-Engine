-- =============================================================================
-- Triggers (DBMS Unit 8: PL/SQL — MySQL native triggers)
-- =============================================================================
-- MySQL triggers are procedural blocks that execute automatically
-- BEFORE or AFTER INSERT/UPDATE/DELETE on a table.
--
-- These are the MySQL equivalent of PL/SQL triggers in Oracle.
-- The SIGNAL statement replaces Oracle's RAISE_APPLICATION_ERROR.
-- =============================================================================

USE bidforge;

DELIMITER //

-- =============================================================================
-- BEFORE INSERT triggers (validation)
-- =============================================================================

-- Validate bid amount and match_score before insertion.
-- If invalid, SIGNAL raises an error and aborts the INSERT.
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
END //

-- Validate project budget range before insertion.
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
END //


-- =============================================================================
-- AFTER INSERT triggers (side effects)
-- =============================================================================

-- Automatically update the freelancer's average rating when a new rating
-- is inserted.  This is the database-level equivalent of the Python
-- FreelancerProfile.update_rating() method.
--
-- Formula: new_avg = (old_avg * count + new_score) / (count + 1)
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
END //


-- =============================================================================
-- AFTER UPDATE triggers (audit trail)
-- =============================================================================

-- Log every project status change to the audit_log table.
-- This creates an immutable audit trail for compliance and debugging.
CREATE TRIGGER IF NOT EXISTS trg_after_update_project_status
AFTER UPDATE ON projects
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status THEN
        INSERT INTO audit_log (table_name, record_id, action, old_value, new_value, changed_at)
        VALUES ('projects', NEW.id, 'STATUS_CHANGE', OLD.status, NEW.status, NOW());
    END IF;
END //

DELIMITER ;


-- =============================================================================
-- Verify triggers
-- =============================================================================
SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, ACTION_TIMING
FROM INFORMATION_SCHEMA.TRIGGERS
WHERE TRIGGER_SCHEMA = 'bidforge';
