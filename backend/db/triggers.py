"""
MySQL BEFORE/AFTER triggers (DBMS Unit 8: PL/SQL equivalents).

Triggers enforce business rules at the database level, independent of
application code.  They fire automatically on INSERT/UPDATE/DELETE events.
"""

from sqlalchemy import text


# Rating auto-update trigger: when a new rating is inserted, automatically
# update the freelancer's avg_rating and total_ratings.
TRIGGER_AFTER_INSERT_RATING = """
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
END
"""

# Bid validation trigger: prevent bids with non-positive amounts
TRIGGER_BEFORE_INSERT_BID = """
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
END
"""

# Project budget validation trigger: ensure budget_min < budget_max
TRIGGER_BEFORE_INSERT_PROJECT = """
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
END
"""

# Audit log trigger: log project status changes
TRIGGER_AFTER_UPDATE_PROJECT_STATUS = """
CREATE TRIGGER IF NOT EXISTS trg_after_update_project_status
AFTER UPDATE ON projects
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status THEN
        INSERT INTO audit_log (table_name, record_id, action, old_value, new_value, changed_at)
        VALUES ('projects', NEW.id, 'STATUS_CHANGE', OLD.status, NEW.status, NOW());
    END IF;
END
"""


_TRIGGERS = [
    TRIGGER_BEFORE_INSERT_BID,
    TRIGGER_BEFORE_INSERT_PROJECT,
    TRIGGER_AFTER_INSERT_RATING,
    TRIGGER_AFTER_UPDATE_PROJECT_STATUS,
]


def create_triggers(connection) -> None:
    """
    Register MySQL triggers.

    Triggers are the MySQL equivalent of PL/SQL procedural code that
    executes automatically on INSERT/UPDATE/DELETE events.  They enforce
    business rules at the database level, independent of application code.
    """
    for trigger_sql in _TRIGGERS:
        try:
            connection.execute(text(trigger_sql))
        except Exception:
            # Trigger may already exist — MySQL's IF NOT EXISTS for triggers
            # is available in 8.0.29+; silently skip if unsupported
            pass
