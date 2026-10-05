"""
User model with ABC hierarchy.

Design:
- UserBase is an abstract base class (ABC) that forces subclasses to implement
  get_role().  This satisfies the OOP abstraction/inheritance requirement.
- The SQLAlchemy User model stores all users in a single table with a `role`
  discriminator column.  The ABC subclasses (ClientUser, FreelancerUser) are
  used in the service layer for role-gated business logic.
- FreelancerProfile is a separate table (1:1 with User) holding freelancer-
  specific data: skills, hourly rate, and aggregated rating.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.enums import UserRole

if TYPE_CHECKING:
    from backend.models.project import Project
    from backend.models.bid import Bid


# ---------------------------------------------------------------------------
# Abstract Base Class hierarchy (OOP requirement: Abstraction + Inheritance)
# ---------------------------------------------------------------------------

class UserBase(ABC):
    """
    Abstract user.  Every concrete user type must declare its role.
    Used in the service layer to enforce role-based access control.
    """

    @abstractmethod
    def get_role(self) -> str:
        """Return the user's role identifier."""
        ...


class ClientUser(UserBase):
    """Concrete user type: can post projects and accept bids."""

    def get_role(self) -> str:
        return UserRole.CLIENT.value


class FreelancerUser(UserBase):
    """Concrete user type: can create a profile, browse projects, and bid."""

    def get_role(self) -> str:
        return UserRole.FREELANCER.value


# ---------------------------------------------------------------------------
# SQLAlchemy Models
# ---------------------------------------------------------------------------

class User(Base):
    """
    Persistent user record.  The `role` column maps to UserRole and determines
    which ABC subclass (ClientUser / FreelancerUser) governs the user's
    permissions in the service layer.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False)  # "client" or "freelancer"
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    freelancer_profile = relationship(
        "FreelancerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="freelancer", cascade="all, delete-orphan")

    def get_user_type(self) -> UserBase:
        """
        Factory method: returns the ABC subclass instance matching this user's
        stored role.  Used by the service layer for polymorphic role checks.
        """
        if self.role == UserRole.CLIENT.value:
            return ClientUser()
        return FreelancerUser()

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"


class FreelancerProfile(Base):
    """
    Extended profile for freelancers (1:1 with User).

    `skills` is stored as a JSON-encoded list of lowercase strings for
    set-based matching in the MatchEngine.
    `avg_rating` and `total_ratings` are denormalized aggregates updated each
    time a client submits a rating, avoiding expensive JOINs on read.
    """
    __tablename__ = "freelancer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    skills = Column(Text, nullable=False, default="[]")  # JSON list
    hourly_rate = Column(Float, nullable=False, default=0.0)
    avg_rating = Column(Float, nullable=False, default=0.0)
    total_ratings = Column(Integer, nullable=False, default=0)

    # Relationship
    user = relationship("User", back_populates="freelancer_profile")

    def get_skills_list(self) -> list[str]:
        """Deserialize the JSON skills column into a Python list."""
        return json.loads(self.skills) if self.skills else []

    def set_skills_list(self, skills: list[str]) -> None:
        """Serialize a Python list of skills into JSON for storage."""
        # Normalize to lowercase for consistent set matching
        self.skills = json.dumps([s.lower().strip() for s in skills])

    def update_rating(self, new_score: int) -> None:
        """
        Incrementally update the running average rating.

        Formula: new_avg = (old_avg * count + new_score) / (count + 1)
        This avoids re-querying all past ratings on every update.

        Guards against None defaults (SQLAlchemy Column defaults only apply
        at INSERT time, not at Python object construction).
        """
        current_avg = self.avg_rating or 0.0
        current_count = self.total_ratings or 0
        total = current_avg * current_count + new_score
        self.total_ratings = current_count + 1
        self.avg_rating = round(total / self.total_ratings, 2)

    def __repr__(self) -> str:
        return (
            f"<FreelancerProfile user_id={self.user_id} "
            f"rate={self.hourly_rate} rating={self.avg_rating}>"
        )
