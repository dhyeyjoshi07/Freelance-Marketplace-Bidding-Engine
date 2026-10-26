-- =============================================================================
-- DDL (Data Definition Language) — DBMS Unit 7: SQL
-- =============================================================================
-- DDL statements define the database schema: CREATE, ALTER, DROP, TRUNCATE.
-- These are the equivalent of what SQLAlchemy's Base.metadata.create_all()
-- generates automatically, but shown here as raw SQL for reference.
-- =============================================================================

-- Create the database
CREATE DATABASE IF NOT EXISTS bidforge
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE bidforge;

-- ----- Table: users ---------------------------------------------------------
-- Primary Key: id (auto-increment, unique identifier for each user)
-- UNIQUE constraints: username and email must be globally unique
-- CHECK constraint: role must be 'client' or 'freelancer'
-- NOT NULL: username, email, password_hash, role, created_at

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- CHECK constraint (enforced in MySQL 8.0.16+)
    CONSTRAINT ck_users_role_valid CHECK (role IN ('client', 'freelancer')),

    -- Performance indexes
    INDEX idx_users_username (username),
    INDEX idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ----- Table: freelancer_profiles -------------------------------------------
-- 1:1 relationship with users (FOREIGN KEY user_id → users.id)
-- Skills stored as JSON array for flexible set-based matching
-- avg_rating is denormalized (updated incrementally, not computed on read)

CREATE TABLE IF NOT EXISTS freelancer_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    skills TEXT NOT NULL DEFAULT '[]',
    hourly_rate FLOAT NOT NULL DEFAULT 0.0,
    avg_rating FLOAT NOT NULL DEFAULT 0.0,
    total_ratings INT NOT NULL DEFAULT 0,

    -- Foreign Key constraint with CASCADE delete
    CONSTRAINT fk_profile_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,

    -- CHECK constraints
    CONSTRAINT ck_profile_rate_positive CHECK (hourly_rate >= 0),
    CONSTRAINT ck_profile_rating_range CHECK (avg_rating >= 0 AND avg_rating <= 5),
    CONSTRAINT ck_profile_total_ratings_positive CHECK (total_ratings >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ----- Table: projects ------------------------------------------------------
-- Many-to-one with users (client_id → users.id)
-- Status field uses CHECK constraint to enforce valid lifecycle states
-- accepted_bid_id is nullable (NULL until a bid is accepted)

CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    required_skills TEXT NOT NULL DEFAULT '[]',
    budget_min FLOAT NOT NULL,
    budget_max FLOAT NOT NULL,
    deadline DATETIME NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    accepted_bid_id INT,
    client_completed INT NOT NULL DEFAULT 0,
    freelancer_completed INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_project_client FOREIGN KEY (client_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_project_accepted_bid FOREIGN KEY (accepted_bid_id)
        REFERENCES bids(id),

    CONSTRAINT ck_project_budget_min_positive CHECK (budget_min >= 0),
    CONSTRAINT ck_project_budget_max_positive CHECK (budget_max > 0),
    CONSTRAINT ck_project_status_valid CHECK (status IN ('open', 'in_progress', 'completed')),

    INDEX idx_projects_status (status),
    INDEX idx_projects_client (client_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ----- Table: bids ----------------------------------------------------------
-- Many-to-one with projects AND users (freelancers)
-- UNIQUE constraint prevents duplicate bids (same freelancer on same project)
-- match_score is computed by MatchEngine and stored for fast ranking

CREATE TABLE IF NOT EXISTS bids (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    freelancer_id INT NOT NULL,
    amount FLOAT NOT NULL,
    proposal TEXT DEFAULT '',
    match_score FLOAT NOT NULL DEFAULT 0.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_bid_project FOREIGN KEY (project_id)
        REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_bid_freelancer FOREIGN KEY (freelancer_id)
        REFERENCES users(id) ON DELETE CASCADE,

    CONSTRAINT uq_bid_project_freelancer UNIQUE (project_id, freelancer_id),
    CONSTRAINT ck_bid_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_bid_score_range CHECK (match_score >= 0 AND match_score <= 1),

    INDEX idx_bids_project_score (project_id, match_score DESC),
    INDEX idx_bids_freelancer (freelancer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ----- Table: ratings -------------------------------------------------------
-- One rating per project (UNIQUE on project_id)
-- Score is 1-5 stars, enforced by CHECK constraint

CREATE TABLE IF NOT EXISTS ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    freelancer_id INT NOT NULL,
    client_id INT NOT NULL,
    score INT NOT NULL,
    review TEXT DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_rating_project FOREIGN KEY (project_id)
        REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_rating_freelancer FOREIGN KEY (freelancer_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_rating_client FOREIGN KEY (client_id)
        REFERENCES users(id) ON DELETE CASCADE,

    CONSTRAINT uq_rating_project UNIQUE (project_id),
    CONSTRAINT ck_rating_score_range CHECK (score >= 1 AND score <= 5),

    INDEX idx_ratings_freelancer (freelancer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ----- Table: audit_log (DBMS Unit 9: Data Security) -----------------------
-- Records all project status transitions for audit trail

CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,
    record_id INT NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_audit_table (table_name),
    INDEX idx_audit_record (record_id),
    INDEX idx_audit_time (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- ALTER TABLE examples (DDL modification)
-- =============================================================================

-- Add a column
-- ALTER TABLE users ADD COLUMN phone VARCHAR(20);

-- Modify a column type
-- ALTER TABLE users MODIFY COLUMN username VARCHAR(100) NOT NULL;

-- Drop a column
-- ALTER TABLE users DROP COLUMN phone;

-- Add an index
-- ALTER TABLE bids ADD INDEX idx_bids_amount (amount);

-- Drop an index
-- ALTER TABLE bids DROP INDEX idx_bids_amount;
