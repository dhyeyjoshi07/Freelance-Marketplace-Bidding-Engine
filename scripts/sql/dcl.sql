-- =============================================================================
-- DCL (Data Control Language) — DBMS Unit 7: SQL
-- =============================================================================
-- DCL statements control access: GRANT, REVOKE.
-- MySQL supports full DCL natively (unlike SQLite).
-- =============================================================================

-- =============================================================================
-- User Creation & Privileges
-- =============================================================================

-- Create the application user with a password
CREATE USER IF NOT EXISTS 'bidforge_user'@'localhost'
    IDENTIFIED BY 'bidforge_pass';

-- GRANT: give full access to the bidforge database
-- This is what was run during setup to allow the Python app to connect.
GRANT ALL PRIVILEGES ON bidforge.* TO 'bidforge_user'@'localhost';

-- GRANT: selective privileges (principle of least privilege)
-- In production, you'd create a read-only user for reporting:
CREATE USER IF NOT EXISTS 'bidforge_readonly'@'localhost'
    IDENTIFIED BY 'readonly_pass';

GRANT SELECT ON bidforge.* TO 'bidforge_readonly'@'localhost';

-- GRANT specific operations on specific tables:
-- A "bid_service" user that can only INSERT/SELECT on bids
CREATE USER IF NOT EXISTS 'bid_service'@'localhost'
    IDENTIFIED BY 'bid_pass';

GRANT SELECT, INSERT ON bidforge.bids TO 'bid_service'@'localhost';
GRANT SELECT ON bidforge.projects TO 'bid_service'@'localhost';
GRANT SELECT ON bidforge.users TO 'bid_service'@'localhost';
GRANT SELECT ON bidforge.freelancer_profiles TO 'bid_service'@'localhost';


-- =============================================================================
-- REVOKE: Remove privileges
-- =============================================================================

-- Remove INSERT privilege from the read-only user (if accidentally granted)
REVOKE INSERT ON bidforge.* FROM 'bidforge_readonly'@'localhost';

-- Remove all privileges from a user
-- REVOKE ALL PRIVILEGES ON bidforge.* FROM 'bid_service'@'localhost';


-- =============================================================================
-- View current grants
-- =============================================================================

-- Show what privileges a user has
SHOW GRANTS FOR 'bidforge_user'@'localhost';
SHOW GRANTS FOR 'bidforge_readonly'@'localhost';


-- =============================================================================
-- Role-Based Access Control (MySQL 8.0+)
-- =============================================================================
-- MySQL supports named roles, which map directly to BidForge's
-- client/freelancer role concept.

-- Create roles
CREATE ROLE IF NOT EXISTS 'bidforge_client_role', 'bidforge_freelancer_role';

-- Grant table-level access to each role
GRANT SELECT, INSERT ON bidforge.projects TO 'bidforge_client_role';
GRANT SELECT ON bidforge.bids TO 'bidforge_client_role';
GRANT UPDATE ON bidforge.projects TO 'bidforge_client_role';  -- accept bid, complete
GRANT INSERT ON bidforge.ratings TO 'bidforge_client_role';    -- rate freelancer

GRANT SELECT ON bidforge.projects TO 'bidforge_freelancer_role';
GRANT SELECT, INSERT ON bidforge.bids TO 'bidforge_freelancer_role';
GRANT SELECT, UPDATE ON bidforge.freelancer_profiles TO 'bidforge_freelancer_role';

-- Assign roles to users
-- GRANT 'bidforge_client_role' TO 'some_client_user'@'localhost';
-- GRANT 'bidforge_freelancer_role' TO 'some_freelancer_user'@'localhost';

-- Activate a role for the current session
-- SET ROLE 'bidforge_client_role';


-- =============================================================================
-- Flush and apply
-- =============================================================================
FLUSH PRIVILEGES;


-- =============================================================================
-- Note on BidForge's Application-Level RBAC
-- =============================================================================
-- In addition to MySQL's DCL, BidForge implements role-based access control
-- at the application level using:
--   1. JWT tokens containing the user's role ('client' or 'freelancer')
--   2. FastAPI's require_role() dependency that checks the JWT role claim
--   3. Router-level guards (e.g., only clients can POST /api/projects)
--
-- This dual-layer approach (DB-level DCL + app-level RBAC) is the recommended
-- pattern for production systems — defense in depth.
