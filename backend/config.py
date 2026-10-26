"""
Application configuration.

Centralizes all settings (database URL, JWT secret, token expiry, encryption key)
so they can be imported from a single place and overridden via environment variables.

Connection architecture (MySQL):
    Python code  →  SQLAlchemy ORM  →  PyMySQL driver  →  MySQL server (port 3306)
    ───────────     ──────────────     ──────────────     ─────────────────────────
    db.query(User)  translates to SQL  sends over TCP     executes & returns rows

    The DATABASE_URL encodes all connection details:
    mysql+pymysql://user:password@host:port/database
    ^^^^^^^^^^^^^^  ^^^^  ^^^^^^^^  ^^^^  ^^^^  ^^^^^^^^
    dialect+driver  user  password  host  port  db name
"""

import os


# --- Database ---
# MySQL connection — PyMySQL is a pure-Python MySQL client that speaks the
# MySQL wire protocol over TCP to the MySQL server on localhost:3306.
# SQLAlchemy uses this driver to translate ORM calls into raw SQL.
MYSQL_USER = os.getenv("MYSQL_USER", "bidforge_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "bidforge_pass")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "bidforge")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
)

# --- JWT Authentication ---
# In production, set SECRET_KEY as an env var; this default is for local dev only
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# --- Match Engine Weights ---
# Configurable scoring weights (must sum to 1.0)
SKILL_WEIGHT = 0.45
PRICE_WEIGHT = 0.30
RATING_WEIGHT = 0.25

# --- Data Encryption (DBMS Unit 9: Data Security) ---
# AES-256 key for encrypting sensitive columns (e.g., email).
# In production, use a proper key management system.
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "bidforge-dev-encryption-key-32b!")

