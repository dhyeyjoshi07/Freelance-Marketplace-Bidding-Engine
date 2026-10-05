"""
Pydantic schemas for project CRUD operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request body for POST /api/projects."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = ""
    required_skills: list[str] = []
    budget_min: float = Field(..., gt=0)
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


class ProjectAcceptBid(BaseModel):
    """Request body for POST /api/projects/{id}/accept-bid."""
    bid_id: int
