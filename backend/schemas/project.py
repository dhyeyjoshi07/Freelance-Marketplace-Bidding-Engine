"""
Pydantic schemas for project CRUD operations.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    """Request body for POST /api/projects."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = ""
    required_skills: list[str] = []
    budget_min: float = Field(..., ge=0)  # M-5 fix: ge=0 matches DB CHECK constraint
    budget_max: float = Field(..., gt=0)
    deadline: datetime


class ProjectOut(BaseModel):
    """Response body for project endpoints."""
    id: int
    client_id: int
    client_name: Optional[str] = None
    title: str
    description: str
    required_skills: list[str] = []
    budget_min: float
    budget_max: float
    deadline: datetime
    status: str
    accepted_bid_id: Optional[int] = None
    client_completed: bool = False
    freelancer_completed: bool = False
    created_at: Optional[datetime] = None
    bid_count: int = 0

    model_config = {"from_attributes": True}

    @field_validator("required_skills", mode="before")
    @classmethod
    def parse_skills_json(cls, v):
        """H-5 fix: deserialize JSON string if ORM passes raw Text column."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v

    @field_validator("client_completed", "freelancer_completed", mode="before")
    @classmethod
    def coerce_int_to_bool(cls, v):
        """H-5 fix: coerce Integer 0/1 columns to bool for from_attributes mode."""
        return bool(v)


class ProjectAcceptBid(BaseModel):
    """Request body for POST /api/projects/{id}/accept-bid."""
    bid_id: int
