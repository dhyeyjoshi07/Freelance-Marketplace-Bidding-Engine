"""
Application configuration.

Centralizes all settings (database URL, JWT secret, token expiry) so they can
be imported from a single place and overridden via environment variables.
"""

import os


# --- Database ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./freelance_marketplace.db"
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
