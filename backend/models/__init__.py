"""
Models package.

Re-exports all model classes for convenient importing:
    from backend.models import User, Project, Bid, Rating, ...
"""

from backend.models.enums import ProjectStatus, UserRole
from backend.models.user import User, FreelancerProfile, UserBase, ClientUser, FreelancerUser
from backend.models.project import Project
from backend.models.bid import Bid, BidRanked, Rating

__all__ = [
    "ProjectStatus",
    "UserRole",
    "User",
    "FreelancerProfile",
    "UserBase",
    "ClientUser",
    "FreelancerUser",
    "Project",
    "Bid",
    "BidRanked",
    "Rating",
]
