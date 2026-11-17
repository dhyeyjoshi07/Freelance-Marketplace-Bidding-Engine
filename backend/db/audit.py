"""
Audit log table DDL (DBMS Unit 9: Data Security).

The audit_log table is populated by the trg_after_update_project_status
trigger defined in triggers.py.
"""

AUDIT_LOG_TABLE = """
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
