"""
MySQL stored procedures and functions (DBMS Unit 8: PL/SQL — MySQL native procedures).
"""

from sqlalchemy import text


STORED_PROCEDURES = [
    # Stored procedure: get ranked bids for a project
    """
    CREATE PROCEDURE IF NOT EXISTS sp_get_ranked_bids(IN p_project_id INT)
    BEGIN
        SELECT b.id, b.freelancer_id, u.username, b.amount, b.proposal,
               b.match_score, b.created_at
        FROM bids b
        JOIN users u ON b.freelancer_id = u.id
        WHERE b.project_id = p_project_id
        ORDER BY b.match_score DESC;
    END
    """,

    # Stored procedure: get freelancer statistics
    """
    CREATE PROCEDURE IF NOT EXISTS sp_freelancer_stats(IN p_user_id INT)
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
    END
    """,

    # Stored function: compute price fit score (mirrors Python MatchEngine logic)
    """
    CREATE FUNCTION IF NOT EXISTS fn_price_fit(
        bid_amount FLOAT, budget_min FLOAT, budget_max FLOAT
    ) RETURNS FLOAT DETERMINISTIC
    BEGIN
        IF bid_amount <= 0 THEN
            RETURN 0.0;
        END IF;
        IF bid_amount BETWEEN budget_min AND budget_max THEN
            RETURN 1.0;
        ELSEIF bid_amount < budget_min THEN
            IF budget_min = 0 THEN RETURN 1.0; END IF;
            RETURN GREATEST(0.0, bid_amount / budget_min);
        ELSE
            IF budget_max = 0 THEN RETURN 0.0; END IF;
            RETURN GREATEST(0.0, 1.0 - (bid_amount - budget_max) / budget_max);
        END IF;
    END
    """,

    # Stored procedure with CURSOR demonstration
    """
    CREATE PROCEDURE IF NOT EXISTS sp_bid_summary_cursor(IN p_project_id INT)
    BEGIN
        DECLARE v_bid_id INT;
        DECLARE v_amount FLOAT;
        DECLARE v_score FLOAT;
        DECLARE v_count INT DEFAULT 0;
        DECLARE v_total_amount FLOAT DEFAULT 0;
        DECLARE v_max_score FLOAT DEFAULT 0;
        DECLARE v_done INT DEFAULT FALSE;

        DECLARE bid_cursor CURSOR FOR
            SELECT id, amount, match_score
            FROM bids
            WHERE project_id = p_project_id;

        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;

        OPEN bid_cursor;

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

        CLOSE bid_cursor;

        SELECT v_count AS total_bids,
               ROUND(v_total_amount, 2) AS total_amount,
               ROUND(CASE WHEN v_count > 0 THEN v_total_amount / v_count ELSE 0 END, 2) AS avg_amount,
               ROUND(v_max_score, 3) AS highest_score;
    END
    """,
]


def create_stored_procedures(connection) -> None:
    """Create MySQL stored procedures and functions."""
    for sp_sql in STORED_PROCEDURES:
        try:
            connection.execute(text(sp_sql))
        except Exception:
            pass  # Already exists or syntax variation
