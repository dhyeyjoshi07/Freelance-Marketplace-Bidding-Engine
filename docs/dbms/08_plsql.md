# Unit 8: PL/SQL Equivalents — MySQL Stored Procedures & Triggers

MySQL stored procedures and triggers are the direct equivalent of Oracle PL/SQL.

## 8.1 Triggers

**Script:** `scripts/sql/triggers.sql`  
**Python:** `backend/database.py` → `create_triggers()`

### BEFORE INSERT — Validation

```sql
-- Validate bid data before insertion
CREATE TRIGGER trg_before_insert_bid
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
END;
```

**PL/SQL equivalent:**
```plsql
-- Oracle PL/SQL version
CREATE TRIGGER trg_before_insert_bid
BEFORE INSERT ON bids
FOR EACH ROW
BEGIN
    IF :NEW.amount <= 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 'Bid amount must be positive');
    END IF;
END;
```

### AFTER INSERT — Side Effects

```sql
-- Auto-update freelancer avg_rating when a rating is inserted
CREATE TRIGGER trg_after_insert_rating
AFTER INSERT ON ratings
FOR EACH ROW
BEGIN
    UPDATE freelancer_profiles
    SET total_ratings = total_ratings + 1,
        avg_rating = ROUND(
            (avg_rating * total_ratings + NEW.score) / (total_ratings + 1), 2
        )
    WHERE user_id = NEW.freelancer_id;
END;
```

### AFTER UPDATE — Audit Trail

```sql
-- Log project status changes to audit_log
CREATE TRIGGER trg_after_update_project_status
AFTER UPDATE ON projects
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status THEN
        INSERT INTO audit_log (table_name, record_id, action, old_value, new_value)
        VALUES ('projects', NEW.id, 'STATUS_CHANGE', OLD.status, NEW.status);
    END IF;
END;
```

## 8.2 Stored Procedures

**Script:** `scripts/sql/procedures.sql`  
**Python:** `backend/database.py` → `create_stored_procedures()`

### Procedure with IN parameter

```sql
-- Get ranked bids for a project (mirrors GET /api/projects/{id}/bids)
CREATE PROCEDURE sp_get_ranked_bids(IN p_project_id INT)
BEGIN
    SELECT b.id, u.username, b.amount, b.match_score
    FROM bids b JOIN users u ON b.freelancer_id = u.id
    WHERE b.project_id = p_project_id
    ORDER BY b.match_score DESC;
END;

-- Call it:
CALL sp_get_ranked_bids(1);
```

### Procedure with DECLARE + SELECT INTO

```sql
-- Freelancer statistics with local variables
CREATE PROCEDURE sp_freelancer_stats(IN p_user_id INT)
BEGIN
    DECLARE v_total_bids INT;
    DECLARE v_accepted_bids INT;
    DECLARE v_avg_score FLOAT;

    SELECT COUNT(*) INTO v_total_bids FROM bids WHERE freelancer_id = p_user_id;

    SELECT COUNT(*) INTO v_accepted_bids
    FROM bids b JOIN projects p ON b.id = p.accepted_bid_id
    WHERE b.freelancer_id = p_user_id;

    SELECT COALESCE(AVG(match_score), 0) INTO v_avg_score
    FROM bids WHERE freelancer_id = p_user_id;

    SELECT v_total_bids AS total_bids,
           v_accepted_bids AS accepted_bids,
           ROUND(v_avg_score, 3) AS avg_match_score;
END;
```

## 8.3 Stored Functions

```sql
-- Price fit calculation (mirrors Python MatchEngine._compute_price_fit)
CREATE FUNCTION fn_price_fit(
    bid_amount FLOAT, budget_min FLOAT, budget_max FLOAT
) RETURNS FLOAT DETERMINISTIC
BEGIN
    IF bid_amount BETWEEN budget_min AND budget_max THEN
        RETURN 1.0;
    ELSEIF bid_amount < budget_min THEN
        IF budget_min = 0 THEN RETURN 0.0; END IF;
        RETURN bid_amount / budget_min;
    ELSE
        RETURN GREATEST(0, 1.0 - (bid_amount - budget_max) / budget_max);
    END IF;
END;

-- Use in SELECT:
SELECT fn_price_fit(8000, 3000, 12000) AS score;  -- 1.0 (within range)
SELECT fn_price_fit(1500, 3000, 12000) AS score;  -- 0.5 (below range)
```

## 8.4 Cursors

```sql
-- Iterate through bids with a cursor (explicit row-by-row processing)
CREATE PROCEDURE sp_bid_summary_cursor(IN p_project_id INT)
BEGIN
    DECLARE v_bid_id INT;
    DECLARE v_amount FLOAT;
    DECLARE v_score FLOAT;
    DECLARE v_count INT DEFAULT 0;
    DECLARE v_total FLOAT DEFAULT 0;
    DECLARE v_done INT DEFAULT FALSE;

    DECLARE bid_cursor CURSOR FOR
        SELECT id, amount, match_score FROM bids WHERE project_id = p_project_id;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;

    OPEN bid_cursor;
    read_loop: LOOP
        FETCH bid_cursor INTO v_bid_id, v_amount, v_score;
        IF v_done THEN LEAVE read_loop; END IF;
        SET v_count = v_count + 1;
        SET v_total = v_total + v_amount;
    END LOOP;
    CLOSE bid_cursor;

    SELECT v_count AS total_bids, ROUND(v_total, 2) AS total_amount;
END;
```

## 8.5 MySQL vs. PL/SQL Syntax Comparison

| Feature | Oracle PL/SQL | MySQL |
|---|---|---|
| Block structure | `BEGIN ... END;` | `BEGIN ... END` |
| Variable declaration | `v_name NUMBER;` | `DECLARE v_name INT;` |
| Assignment | `v_name := 10;` | `SET v_name = 10;` |
| Error raising | `RAISE_APPLICATION_ERROR(-20001, 'msg')` | `SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'msg'` |
| NEW/OLD in triggers | `:NEW.column`, `:OLD.column` | `NEW.column`, `OLD.column` |
| Packages | `CREATE PACKAGE` | Not supported (use separate procedures) |
| Autonomous transactions | `PRAGMA AUTONOMOUS_TRANSACTION` | Not supported natively |
| Delimiter | `;` | `DELIMITER //` needed for multi-statement |

## 8.6 Live Demo via API

```bash
# Call stored procedure: ranked bids
curl http://localhost:8000/api/admin/stored-procedure/ranked-bids/1

# Call stored procedure: freelancer stats
curl http://localhost:8000/api/admin/stored-procedure/freelancer-stats/4

# List all triggers
curl http://localhost:8000/api/admin/triggers

# List all stored procedures and functions
curl http://localhost:8000/api/admin/stored-procedures
```

**Python code:** `backend/database.py` (trigger/procedure definitions), `backend/routers/admin.py` (API endpoints)
