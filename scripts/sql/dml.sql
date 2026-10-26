-- =============================================================================
-- DML (Data Manipulation Language) — DBMS Unit 7: SQL
-- =============================================================================
-- DML statements manipulate data: SELECT, INSERT, UPDATE, DELETE.
-- All examples use BidForge's own entities.
-- =============================================================================

USE bidforge;

-- =============================================================================
-- INSERT — Adding new records
-- =============================================================================

-- Insert a new client
INSERT INTO users (username, email, password_hash, role)
VALUES ('john_doe', 'john@example.com', '$2b$12$hashed...', 'client');

-- Insert a new freelancer
INSERT INTO users (username, email, password_hash, role)
VALUES ('jane_dev', 'jane@dev.io', '$2b$12$hashed...', 'freelancer');

-- Insert a freelancer profile
INSERT INTO freelancer_profiles (user_id, skills, hourly_rate, avg_rating, total_ratings)
VALUES (2, '["python", "fastapi", "sql"]', 85.00, 0.0, 0);

-- Insert a project
INSERT INTO projects (client_id, title, description, required_skills, budget_min, budget_max, deadline)
VALUES (1, 'API Development', 'Build a REST API', '["python", "fastapi"]', 3000, 12000, '2026-12-01');

-- Insert a bid
INSERT INTO bids (project_id, freelancer_id, amount, proposal, match_score)
VALUES (1, 2, 8000, 'I have 5 years of FastAPI experience', 0.925);


-- =============================================================================
-- SELECT — Querying data
-- =============================================================================

-- Basic: all open projects
SELECT * FROM projects WHERE status = 'open';

-- With columns: specific fields from users
SELECT id, username, email, role FROM users;

-- JOIN: get bids with freelancer names for a project
SELECT b.id, u.username, b.amount, b.match_score, b.proposal
FROM bids b
JOIN users u ON b.freelancer_id = u.id
WHERE b.project_id = 1
ORDER BY b.match_score DESC;

-- Aggregate: average bid amount per project
SELECT project_id, COUNT(*) AS num_bids, AVG(amount) AS avg_bid, MAX(match_score) AS best_score
FROM bids
GROUP BY project_id;

-- Subquery: projects with more than 2 bids
SELECT p.title, p.budget_min, p.budget_max
FROM projects p
WHERE p.id IN (
    SELECT project_id FROM bids GROUP BY project_id HAVING COUNT(*) > 2
);

-- IN operator: freelancers with specific skills (JSON search)
SELECT u.username, fp.skills, fp.hourly_rate
FROM users u
JOIN freelancer_profiles fp ON u.id = fp.user_id
WHERE fp.skills LIKE '%python%' OR fp.skills LIKE '%fastapi%';

-- BETWEEN: bids within a specific amount range
SELECT * FROM bids WHERE amount BETWEEN 5000 AND 10000;

-- EXISTS: clients who have at least one project
SELECT u.username
FROM users u
WHERE u.role = 'client'
  AND EXISTS (SELECT 1 FROM projects p WHERE p.client_id = u.id);

-- LEFT JOIN: all freelancers and their bid count (including those with 0 bids)
SELECT u.username, COUNT(b.id) AS bid_count
FROM users u
LEFT JOIN bids b ON u.id = b.freelancer_id
WHERE u.role = 'freelancer'
GROUP BY u.username;

-- Self-join concept: find projects where budget overlaps
SELECT p1.title AS project_a, p2.title AS project_b
FROM projects p1
JOIN projects p2 ON p1.id < p2.id
WHERE p1.budget_min <= p2.budget_max AND p2.budget_min <= p1.budget_max;

-- CASE expression: categorize bids by match quality
SELECT b.id, u.username, b.match_score,
    CASE
        WHEN b.match_score >= 0.8 THEN 'Excellent'
        WHEN b.match_score >= 0.5 THEN 'Good'
        WHEN b.match_score >= 0.3 THEN 'Fair'
        ELSE 'Poor'
    END AS quality
FROM bids b
JOIN users u ON b.freelancer_id = u.id
ORDER BY b.match_score DESC;


-- =============================================================================
-- UPDATE — Modifying existing records
-- =============================================================================

-- Update a freelancer's hourly rate
UPDATE freelancer_profiles SET hourly_rate = 95.00 WHERE user_id = 2;

-- Accept a bid (project status transition)
UPDATE projects SET status = 'in_progress', accepted_bid_id = 1 WHERE id = 1;


-- =============================================================================
-- DELETE — Removing records
-- =============================================================================

-- Delete a specific bid
DELETE FROM bids WHERE id = 1;

-- Delete all bids for a cancelled project (CASCADE would handle this,
-- but shown here for DML completeness)
DELETE FROM bids WHERE project_id = 5;
