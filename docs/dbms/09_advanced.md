# Unit 9: Advanced Topics — Data Security, Encryption & NoSQL Concepts

## 9.1 Data Security Architecture

BidForge implements security at three layers:

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Application-Level RBAC                  │
│ JWT tokens + require_role() dependency           │
│ Clients can't bid, Freelancers can't post        │
├─────────────────────────────────────────────────┤
│ Layer 2: Database-Level DCL                      │
│ GRANT/REVOKE on bidforge_user                    │
│ Read-only users for reporting                    │
├─────────────────────────────────────────────────┤
│ Layer 3: Column-Level Encryption                 │
│ AES-256 encryption of sensitive fields           │
│ Key never stored in database                     │
└─────────────────────────────────────────────────┘
```

## 9.2 Column-Level Encryption (AES-256)

**Python code:** `backend/services/encryption.py`

```python
from backend.services.encryption import encrypt, decrypt

# Encrypt sensitive data before storing
encrypted_email = encrypt("alice@dev.io")
# → "gAAAAABm_x5kZ..." (base64-encoded AES ciphertext)

# Decrypt when reading
original = decrypt(encrypted_email)
# → "alice@dev.io"
```

**How it works:**
1. The `ENCRYPTION_KEY` (32 bytes) is stored only in the application config (environment variable)
2. We derive a Fernet-compatible key using SHA-256
3. Fernet uses AES-128-CBC under the hood with HMAC-SHA256 for authentication
4. The ciphertext includes a timestamp, IV, and authentication tag
5. Even with full database access, encrypted columns are unreadable without the key

**Production recommendations:**
- Use PBKDF2 or Argon2 instead of raw SHA-256 for key derivation
- Store the encryption key in AWS KMS, HashiCorp Vault, or similar
- Rotate keys periodically with re-encryption migration

## 9.3 Audit Trail

The `audit_log` table records all project status transitions:

```sql
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,    -- 'projects'
    record_id INT NOT NULL,             -- project id
    action VARCHAR(50) NOT NULL,        -- 'STATUS_CHANGE'
    old_value TEXT,                      -- 'open'
    new_value TEXT,                      -- 'in_progress'
    changed_at DATETIME DEFAULT NOW()
);
```

**Populated automatically by trigger:**
```sql
CREATE TRIGGER trg_after_update_project_status
AFTER UPDATE ON projects
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status THEN
        INSERT INTO audit_log (...)
        VALUES ('projects', NEW.id, 'STATUS_CHANGE', OLD.status, NEW.status, NOW());
    END IF;
END;
```

**Purpose:** Immutable audit trail for:
- Detecting unauthorized state transitions
- Compliance reporting
- Debugging workflow issues

## 9.4 Access Control: GRANT / REVOKE

MySQL's native DCL implements discretionary access control:

```sql
-- Full access for the application
GRANT ALL PRIVILEGES ON bidforge.* TO 'bidforge_user'@'localhost';

-- Read-only access for reporting/analytics
GRANT SELECT ON bidforge.* TO 'bidforge_readonly'@'localhost';

-- Minimal access for a microservice
GRANT SELECT, INSERT ON bidforge.bids TO 'bid_service'@'localhost';

-- Role-based (MySQL 8.0+)
CREATE ROLE 'bidforge_client_role', 'bidforge_freelancer_role';
GRANT SELECT, INSERT ON bidforge.projects TO 'bidforge_client_role';
GRANT SELECT, INSERT ON bidforge.bids TO 'bidforge_freelancer_role';
```

**Full DCL script:** `scripts/sql/dcl.sql`

## 9.5 Application-Level RBAC

BidForge's Python code enforces role-based access using JWT tokens:

```python
# backend/dependencies.py
def require_role(role: str):
    def checker(user = Depends(get_current_user)):
        if user.role != role:
            raise HTTPException(403, "Forbidden: wrong role")
        return user
    return checker

# backend/routers/projects.py
@router.post("/api/projects")
def create_project(
    data: ProjectCreate,
    user = Depends(require_role("client")),  # Only clients can post
    db = Depends(get_db)
):
    ...
```

**Dual-layer defense:** Even if an attacker bypasses the JWT check, MySQL's `GRANT` restricts what the DB user can do. And even if they access the DB directly, encrypted columns are unreadable.

## 9.6 Password Hashing

BidForge uses **bcrypt** for password storage:

```python
import bcrypt

# Registration: hash password with random salt
password_hash = bcrypt.hashpw("password123".encode(), bcrypt.gensalt())
# → b'$2b$12$Q7x...' (60 chars, includes algorithm + salt + hash)

# Login: verify password against stored hash
bcrypt.checkpw("password123".encode(), stored_hash)  # True
```

**Why bcrypt, not SHA-256:**
- bcrypt is intentionally slow (configurable work factor)
- Each hash has a unique random salt (prevents rainbow tables)
- Work factor `12` = ~250ms per hash (attackers can't brute-force)

## 9.7 NoSQL / JSON Concepts in MySQL

BidForge uses JSON-in-SQL for the `skills` field — a hybrid approach:

```sql
-- Skills stored as JSON array
INSERT INTO freelancer_profiles (user_id, skills)
VALUES (2, '["python", "fastapi", "sql"]');

-- JSON search (MySQL 5.7+ supports JSON functions)
SELECT * FROM freelancer_profiles
WHERE JSON_CONTAINS(skills, '"python"');

-- JSON extract
SELECT JSON_LENGTH(skills) AS skill_count FROM freelancer_profiles;
```

**Trade-off:**
| Approach | Pros | Cons |
|---|---|---|
| Normalized (junction table) | Full relational integrity, standard joins | More tables, more complex queries |
| JSON array (BidForge's choice) | Simple, fast Python deserialization, flexible | No FK enforcement on skill values |

This hybrid approach is common in modern applications and demonstrates how relational and document (NoSQL) paradigms can coexist.

## 9.8 Live Demo via API

```bash
# Test encryption/decryption
curl -X POST "http://localhost:8000/api/admin/encrypt?plaintext=alice@dev.io"

# View audit log
curl http://localhost:8000/api/admin/audit-log

# List all constraints
curl http://localhost:8000/api/admin/constraints
```
