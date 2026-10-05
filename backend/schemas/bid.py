"""
Pydantic schemas for bid submission, ranking display, and ratings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BidCreate(BaseModel):
    """Request body for POST /api/projects/{id}/bids."""
    amount: float = Field(..., gt=0)
    proposal: str = ""


class BidOut(BaseModel):
    """Response body for bid endpoints — includes computed match_score."""
    id: int
    project_id: int
    freelancer_id: int
    freelancer_name: Optional[str] = None
    amount: float
    proposal: str
    match_score: float
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BidRankedOut(BaseModel):
    """
    Ranked bid for display — includes score breakdown
    and freelancer info for the client's ranked view.
    """
    bid_id: int
    freelancer_id: int
    freelancer_name: str = ""
    freelancer_skills: list[str] = []
    freelancer_rating: float = 0.0
    amount: float
    proposal: str = ""
    match_score: float
    rank: int = 0


class RatingCreate(BaseModel):
    """Request body for POST /api/projects/{id}/rate."""
    score: int = Field(..., ge=1, le=5)
    review: str = ""


class RatingOut(BaseModel):
    """Response body for rating endpoints."""
    id: int
    project_id: int
    freelancer_id: int
    client_id: int
    score: int
    review: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
