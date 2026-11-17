"""
Pydantic schemas for user registration, login, and profile responses.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Registration ---

class UserRegister(BaseModel):
    """Request body for POST /api/auth/register."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr  # M-1 fix: use EmailStr for proper email validation
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(..., pattern="^(client|freelancer)$")


# --- Login ---

class UserLogin(BaseModel):
    """Request body for POST /api/auth/login."""
    username: str
    password: str


class Token(BaseModel):
    """Response body for POST /api/auth/login."""
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    username: str


# --- Profile responses ---

class UserOut(BaseModel):
    """Public user info returned by endpoints."""
    id: int
    username: str
    email: str
    role: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FreelancerProfileOut(BaseModel):
    """Freelancer profile info."""
    id: int
    user_id: int
    skills: list[str] = []
    hourly_rate: float
    avg_rating: float
    total_ratings: int

    model_config = {"from_attributes": True}

    @field_validator("skills", mode="before")
    @classmethod
    def parse_skills_json(cls, v):
        """H-4 fix: deserialize JSON string if ORM passes raw Text column."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v


class FreelancerProfileUpdate(BaseModel):
    """Request body for PUT /api/freelancers/me."""
    skills: Optional[list[str]] = None
    hourly_rate: Optional[float] = Field(None, gt=0)
