"""
Pydantic schemas for user registration, login, and profile responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# --- Registration ---

class UserRegister(BaseModel):
    """Request body for POST /api/auth/register."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=120)
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


class FreelancerProfileUpdate(BaseModel):
    """Request body for PUT /api/freelancers/me."""
    skills: Optional[list[str]] = None
    hourly_rate: Optional[float] = Field(None, gt=0)
