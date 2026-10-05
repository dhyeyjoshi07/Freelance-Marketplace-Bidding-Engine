"""
Project model with encapsulated status transitions.

Design:
- Status is NEVER mutated directly.  All transitions go through accept_bid()
  or mark_completed(), which validate the current state before changing it.
- required_skills is JSON-encoded like FreelancerProfile.skills for consistent
  set intersection in the MatchEngine.
- Budget validation (min < max, both non-negative) is enforced at creation
  time via validate_budget().
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.enums import ProjectStatus
from backend.exceptions import (
    InvalidBudgetError,
    InvalidStatusTransitionError,
    BidOnExpiredProjectError,
)

if TYPE_CHECKING:
    from backend.models.bid import Bid


class Project(Base):
    """
    A client-posted project that freelancers can bid on.

    Lifecycle:  Open ──accept_bid()──▶ InProgress ──mark_completed()──▶ Completed
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    required_skills = Column(Text, nullable=False, default="[]")  # JSON list
    budget_min = Column(Float, nullable=False)
    budget_max = Column(Float, nullable=False)
    deadline = Column(DateTime, nullable=False)
    status = Column(
        String(20), nullable=False, default=ProjectStatus.OPEN.value
    )
    accepted_bid_id = Column(
        Integer, ForeignKey("bids.id", use_alter=True), nullable=True
    )
    # Dual-completion flags: both must be True to transition to Completed
    client_completed = Column(Integer, nullable=False, default=0)     # 0/1 boolean
    freelancer_completed = Column(Integer, nullable=False, default=0)  # 0/1 boolean
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    client = relationship("User", back_populates="projects")
    bids = relationship(
        "Bid", back_populates="project",
        foreign_keys="Bid.project_id", cascade="all, delete-orphan"
    )

    # --- Encapsulated status transitions (never mutate status directly) ---

    def accept_bid(self, bid_id: int) -> None:
        """
        Transition: Open → InProgress.
        Only the owning client should call this (enforced in the router layer).

        Raises:
            InvalidStatusTransitionError: if project is not currently Open.
        """
        if self.status != ProjectStatus.OPEN.value:
            raise InvalidStatusTransitionError(
                self.status, ProjectStatus.IN_PROGRESS.value
            )
        self.status = ProjectStatus.IN_PROGRESS.value
        self.accepted_bid_id = bid_id

    def mark_completed_by(self, role: str) -> bool:
        """
        Dual-confirmation completion: both client and freelancer must confirm.

        Returns True if this confirmation caused the project to transition
        to Completed (i.e., the other party had already confirmed).

        Raises:
            InvalidStatusTransitionError: if project is not InProgress.
        """
        if self.status != ProjectStatus.IN_PROGRESS.value:
            raise InvalidStatusTransitionError(
                self.status, ProjectStatus.COMPLETED.value
            )

        if role == "client":
            self.client_completed = 1
        elif role == "freelancer":
            self.freelancer_completed = 1

        # Transition only when BOTH parties have confirmed
        if self.client_completed and self.freelancer_completed:
            self.status = ProjectStatus.COMPLETED.value
            return True
        return False

    def _utc_deadline(self) -> datetime:
        """Return the deadline as a UTC-aware datetime, normalizing naive values."""
        if self.deadline.tzinfo is None:
            return self.deadline.replace(tzinfo=timezone.utc)
        return self.deadline

    def is_accepting_bids(self) -> bool:
        """Check whether the project is open and its deadline hasn't passed."""
        if self.status != ProjectStatus.OPEN.value:
            return False
        return datetime.now(timezone.utc) < self._utc_deadline()

    def ensure_biddable(self) -> None:
        """
        Guard method called before bid submission.

        Raises:
            BidOnExpiredProjectError: if the project is closed or past deadline.
        """
        if self.status != ProjectStatus.OPEN.value:
            raise BidOnExpiredProjectError(
                self.id, f"Project status is '{self.status}', not 'open'"
            )
        if datetime.now(timezone.utc) >= self._utc_deadline():
            raise BidOnExpiredProjectError(
                self.id, "Project deadline has passed"
            )

    # --- Helpers ---

    def get_required_skills_list(self) -> list[str]:
        """Deserialize the JSON required_skills column."""
        return json.loads(self.required_skills) if self.required_skills else []

    def set_required_skills_list(self, skills: list[str]) -> None:
        """Serialize a list of skill strings into JSON (lowercase-normalized)."""
        self.required_skills = json.dumps([s.lower().strip() for s in skills])

    @staticmethod
    def validate_budget(budget_min: float, budget_max: float) -> None:
        """
        Validate budget range before creating a project.

        Raises:
            InvalidBudgetError: if the range is invalid.
        """
        if budget_min < 0 or budget_max <= 0 or budget_min >= budget_max:
            raise InvalidBudgetError(budget_min, budget_max)

    def __repr__(self) -> str:
        return (
            f"<Project id={self.id} title={self.title!r} "
            f"status={self.status!r}>"
        )
