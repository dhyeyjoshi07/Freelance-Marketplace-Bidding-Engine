-- =============================================================================
-- Stored Procedures & Functions (DBMS Unit 8: PL/SQL equivalents)
-- =============================================================================
-- MySQL stored procedures are the equivalent of Oracle PL/SQL procedures.
-- They encapsulate reusable SQL logic on the database server.
--
-- Key syntax differences from PL/SQL:
--   - DELIMITER // is required to define multi-statement bodies
--   - Variables are declared with DECLARE (same as PL/SQL)
--   - SIGNAL replaces RAISE_APPLICATION_ERROR
--   - No packages — procedures and functions are standalone
-- =============================================================================

USE bidforge;

DELIMITER //

-- =============================================================================
-- Stored Procedure: Get ranked bids for a project
-- =============================================================================
-- Demonstrates: IN parameter, JOIN, ORDER BY
-- Equivalent to: GET /api/projects/{id}/bids

CREATE PROCEDURE IF NOT EXISTS sp_get_ranked_bids(IN p_project_id INT)
BEGIN
    SELECT b.id, b.freelancer_id, u.username, b.amount, b.proposal,
           b.match_score, b.created_at
    FROM bids b
    JOIN users u ON b.freelancer_id = u.id
    WHERE b.project_id = p_project_id
    ORDER BY b.match_score DESC;
END //


-- =============================================================================
-- Stored Procedure: Get freelancer statistics
-- =============================================================================
-- Demonstrates: DECLARE variables, SELECT INTO, multiple queries

CREATE PROCEDURE IF NOT EXISTS sp_freelancer_stats(IN p_user_id INT)
BEGIN
    DECLARE v_total_bids INT;
    DECLARE v_accepted_bids INT;
    DECLARE v_avg_score FLOAT;

    -- Count total bids
    SELECT COUNT(*) INTO v_total_bids
    FROM bids WHERE freelancer_id = p_user_id;

    -- Count accepted bids (bids that became the project's accepted_bid_id)
    SELECT COUNT(*) INTO v_accepted_bids
    FROM bids b JOIN projects p ON b.id = p.accepted_bid_id
    WHERE b.freelancer_id = p_user_id;

    -- Average match score across all bids
    SELECT COALESCE(AVG(match_score), 0) INTO v_avg_score
    FROM bids WHERE freelancer_id = p_user_id;

    -- Return results as a single row
    SELECT v_total_bids AS total_bids,
           v_accepted_bids AS accepted_bids,
           ROUND(v_avg_score, 3) AS avg_match_score;
END //


-- =============================================================================
-- Stored Function: Compute price fit score
-- =============================================================================
-- Demonstrates: RETURNS, DETERMINISTIC, IF-ELSEIF-ELSE
-- This mirrors the Python MatchEngine._compute_price_fit() method

CREATE FUNCTION IF NOT EXISTS fn_price_fit(
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
END //


-- =============================================================================
-- Stored Procedure: Cursor demonstration
-- =============================================================================
-- Demonstrates: CURSOR, OPEN, FETCH, CLOSE, LOOP, HANDLER
-- Iterates through all bids for a project and builds a summary

CREATE PROCEDURE IF NOT EXISTS sp_bid_summary_cursor(IN p_project_id INT)
BEGIN
    DECLARE v_bid_id INT;
    DECLARE v_amount FLOAT;
    DECLARE v_score FLOAT;
    DECLARE v_count INT DEFAULT 0;
    DECLARE v_total_amount FLOAT DEFAULT 0;
    DECLARE v_max_score FLOAT DEFAULT 0;
    DECLARE v_done INT DEFAULT FALSE;

    -- Declare cursor
    DECLARE bid_cursor CURSOR FOR
        SELECT id, amount, match_score
        FROM bids
        WHERE project_id = p_project_id;

    -- Handler for when cursor reaches end of result set
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;

    -- Open cursor
    OPEN bid_cursor;

    -- Fetch loop
    read_loop: LOOP
        FETCH bid_cursor INTO v_bid_id, v_amount, v_score;
        IF v_done THEN
            LEAVE read_loop;
        END IF;

        SET v_count = v_count + 1;
        SET v_total_amount = v_total_amount + v_amount;
        IF v_score > v_max_score THEN
            SET v_max_score = v_score;
        END IF;
    END LOOP;

    -- Close cursor
    CLOSE bid_cursor;

    -- Return summary
    SELECT v_count AS total_bids,
           ROUND(v_total_amount, 2) AS total_amount,
           ROUND(CASE WHEN v_count > 0 THEN v_total_amount / v_count ELSE 0 END, 2) AS avg_amount,
           ROUND(v_max_score, 3) AS highest_score;
END //

DELIMITER ;


-- =============================================================================
-- Usage examples
-- =============================================================================

-- Call stored procedure
-- CALL sp_get_ranked_bids(1);
-- CALL sp_freelancer_stats(4);
-- CALL sp_bid_summary_cursor(1);

-- Call stored function (use in SELECT)
-- SELECT fn_price_fit(8000, 3000, 12000) AS score;  -- Returns 1.0 (within range)
-- SELECT fn_price_fit(1500, 3000, 12000) AS score;  -- Returns 0.5 (below range)
-- SELECT fn_price_fit(20000, 3000, 12000) AS score;  -- Returns ~0.33 (above range)


-- =============================================================================
-- List stored routines
-- =============================================================================
SELECT ROUTINE_NAME, ROUTINE_TYPE, DATA_TYPE, CREATED
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = 'bidforge';
