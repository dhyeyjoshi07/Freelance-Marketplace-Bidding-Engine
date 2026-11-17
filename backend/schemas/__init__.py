"""
Pydantic schemas package — request/response validation at the API boundary.

Re-exports all schema classes for convenient importing:
    from backend.schemas import UserRegister, ProjectCreate, BidCreate, ...
"""

from backend.schemas.user import (
    UserRegister, UserLogin, Token, UserOut,
    FreelancerProfileOut, FreelancerProfileUpdate,
)
from backend.schemas.project import ProjectCreate, ProjectOut, ProjectAcceptBid
from backend.schemas.bid import BidCreate, BidOut, BidRankedOut, RatingCreate, RatingOut

__all__ = [
    # User
    "UserRegister", "UserLogin", "Token", "UserOut",
    "FreelancerProfileOut", "FreelancerProfileUpdate",
    # Project
    "ProjectCreate", "ProjectOut", "ProjectAcceptBid",
    # Bid
    "BidCreate", "BidOut", "BidRankedOut", "RatingCreate", "RatingOut",
]
