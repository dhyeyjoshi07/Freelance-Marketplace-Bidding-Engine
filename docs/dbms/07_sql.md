# Unit 7: SQL — BidForge

All SQL examples use BidForge's actual tables and data.

## 7.1 DDL (Data Definition Language)

**Full DDL script:** `scripts/sql/ddl.sql`

```sql
-- CREATE TABLE with constraints
CREATE TABLE bids (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    freelancer_id INT NOT NULL,
    amount FLOAT NOT NULL,
    match_score FLOAT NOT NULL DEFAULT 0.0,
    CONSTRAINT fk_bid_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT uq_bid_project_freelancer UNIQUE (project_id, freelancer_id),
    CONSTRAINT ck_bid_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_bid_score_range CHECK (match_score >= 0 AND match_score <= 1)
) ENGINE=InnoDB;

-- ALTER TABLE
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
ALTER TABLE users MODIFY COLUMN username VARCHAR(100) NOT NULL;
ALTER TABLE users DROP COLUMN phone;

-- DROP TABLE
DROP TABLE IF EXISTS temp_table;

-- TRUNCATE (DDL — cannot be rolled back)
TRUNCATE TABLE audit_log;
```

## 7.2 DML (Data Manipulation Language)

**Full DML script:** `scripts/sql/dml.sql`

### INSERT
```sql
INSERT INTO users (username, email, password_hash, role)
VALUES ('alice', 'alice@dev.io', '$2b$12$...', 'freelancer');
```

### SELECT with JOINs
```sql
-- Ranked bids with freelancer names
SELECT b.id, u.username, b.amount, b.match_score
FROM bids b
JOIN users u ON b.freelancer_id = u.id
WHERE b.project_id = 1
ORDER BY b.match_score DESC;
```

### Aggregate Functions
```sql
SELECT project_id,
       COUNT(*) AS num_bids,
       AVG(amount) AS avg_bid,
       MAX(match_score) AS best_score
FROM bids
GROUP BY project_id
HAVING COUNT(*) > 2;
```

### Subqueries
```sql
-- Projects with at least one excellent bid
SELECT title FROM projects
WHERE id IN (SELECT project_id FROM bids WHERE match_score > 0.9);

-- Correlated subquery: freelancers above average bid amount
SELECT u.username, b.amount FROM bids b
JOIN users u ON b.freelancer_id = u.id
WHERE b.amount > (SELECT AVG(amount) FROM bids b2 WHERE b2.project_id = b.project_id);
```

### Set Operations
```sql
-- UNION: all users who have either posted projects OR submitted bids
SELECT username FROM users WHERE id IN (SELECT client_id FROM projects)
UNION
SELECT username FROM users WHERE id IN (SELECT freelancer_id FROM bids);

-- EXCEPT (MySQL uses NOT IN): freelancers who bid but never got accepted
SELECT DISTINCT freelancer_id FROM bids
WHERE freelancer_id NOT IN (
    SELECT b.freelancer_id FROM bids b
    JOIN projects p ON b.id = p.accepted_bid_id
);
```

### UPDATE and DELETE
```sql
UPDATE projects SET status = 'in_progress', accepted_bid_id = 1 WHERE id = 1;
DELETE FROM bids WHERE project_id = 5;
```

## 7.3 DCL (Data Control Language)

**Full DCL script:** `scripts/sql/dcl.sql`

```sql
-- Create user with privileges
CREATE USER 'bidforge_user'@'localhost' IDENTIFIED BY 'bidforge_pass';
GRANT ALL PRIVILEGES ON bidforge.* TO 'bidforge_user'@'localhost';

-- Read-only user for reporting
CREATE USER 'bidforge_readonly'@'localhost' IDENTIFIED BY 'readonly_pass';
GRANT SELECT ON bidforge.* TO 'bidforge_readonly'@'localhost';

-- Role-based access control (MySQL 8.0+)
CREATE ROLE 'bidforge_client_role';
GRANT SELECT, INSERT ON bidforge.projects TO 'bidforge_client_role';
GRANT SELECT ON bidforge.bids TO 'bidforge_client_role';

-- Revoke privileges
REVOKE INSERT ON bidforge.* FROM 'bidforge_readonly'@'localhost';
```

## 7.4 TCL (Transaction Control Language)

**Full script:** `scripts/sql/transactions.sql`

```sql
START TRANSACTION;
    UPDATE projects SET status = 'in_progress' WHERE id = 1;
    SAVEPOINT after_status;
    UPDATE projects SET accepted_bid_id = 1 WHERE id = 1;
    -- If second update fails:
    -- ROLLBACK TO after_status;
COMMIT;
```

## 7.5 Constraints Summary

| Constraint | Type | Table | MySQL Implementation |
|---|---|---|---|
| Primary key | Entity integrity | All tables | `PRIMARY KEY (id)` |
| Not null | Domain | Most columns | `NOT NULL` |
| Unique | Key | users.username, users.email | `UNIQUE` |
| Foreign key | Referential integrity | bids.project_id → projects.id | `FOREIGN KEY ... ON DELETE CASCADE` |
| Check | Domain | bid.amount > 0 | `CHECK (amount > 0)` |
| Default | Domain | bid.match_score | `DEFAULT 0.0` |
| Composite unique | Key | bids(project_id, freelancer_id) | `UNIQUE (project_id, freelancer_id)` |

## 7.6 Views

```sql
-- View: open projects with bid counts
CREATE VIEW v_open_projects AS
SELECT p.id, p.title, p.budget_min, p.budget_max,
       COUNT(b.id) AS bid_count,
       MAX(b.match_score) AS best_score
FROM projects p
LEFT JOIN bids b ON p.id = b.project_id
WHERE p.status = 'open'
GROUP BY p.id;

-- View: freelancer leaderboard
CREATE VIEW v_freelancer_leaderboard AS
SELECT u.username, fp.avg_rating, fp.total_ratings, fp.hourly_rate,
       COUNT(b.id) AS total_bids
FROM users u
JOIN freelancer_profiles fp ON u.id = fp.user_id
LEFT JOIN bids b ON u.id = b.freelancer_id
GROUP BY u.id
ORDER BY fp.avg_rating DESC;

-- Usage
SELECT * FROM v_open_projects WHERE bid_count > 2;
SELECT * FROM v_freelancer_leaderboard LIMIT 10;
```

## 7.7 Live Demo via API

```bash
# List all constraints on a table
curl "http://localhost:8000/api/admin/constraints?table_name=bids"
```
