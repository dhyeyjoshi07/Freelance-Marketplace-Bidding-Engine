"""
Bid model with operator overloading for ranking.

Design:
- The SQLAlchemy Bid model stores the persistent bid record.
- BidRanked is a lightweight dataclass wrapper that holds a bid's id and its
  computed match_score.  It implements __lt__ and __gt__ with INVERTED
  comparison so that Python's min-heap (heapq) and sorted() produce a
  highest-score-first ordering.
- A unique constraint on (project_id, freelancer_id) prevents duplicate bids
  at the database level; the application also checks before insertion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, Float, DateTime, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship

from backend.database import Base


class Bid(Base):
    """
    A freelancer's bid on a specific project.

    match_score is computed by MatchEngine at bid-submission time and stored
    for fast retrieval when ranking bids.
    """
    __tablename__ = "bids"
    __table_args__ = (
        # Prevents the same freelancer from bidding twice on one project
        UniqueConstraint("project_id", "freelancer_id", name="uq_bid_project_freelancer"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    freelancer_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(Float, nullable=False)
    proposal = Column(Text, default="")
    match_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    project = relationship(
        "Project", back_populates="bids", foreign_keys=[project_id]
    )
    freelancer = relationship("User", back_populates="bids")

    def __repr__(self) -> str:
        return (
            f"<Bid id={self.id} project={self.project_id} "
            f"freelancer={self.freelancer_id} score={self.match_score:.2f}>"
        )


# ---------------------------------------------------------------------------
# Dataclass wrapper for heapq / sorted ranking
# (OOP requirement: operator overloading via __lt__ / __gt__)
# ---------------------------------------------------------------------------

@dataclass(order=False)
class BidRanked:
    """
    Lightweight ranking wrapper around a Bid.

    Comparison operators are INVERTED: __lt__ returns True when self has a
    HIGHER score than other.  This means:
      - sorted(list_of_BidRanked) yields highest-score-first order
      - heapq (a min-heap) will pop the highest-score bid first

    This inversion is the standard trick for using Python's min-heap as a
    max-heap without negating scores.
    """
    bid_id: int
    match_score: float
    freelancer_id: int = 0
    freelancer_name: str = ""
    amount: float = 0.0
    proposal: str = ""

    def __lt__(self, other: BidRanked) -> bool:
        """Higher match_score sorts first (inverted for min-heap max behavior)."""
        if not isinstance(other, BidRanked):
            return NotImplemented
        return self.match_score > other.match_score

    def __gt__(self, other: BidRanked) -> bool:
        if not isinstance(other, BidRanked):
            return NotImplemented
        return self.match_score < other.match_score

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BidRanked):
            return NotImplemented
        return self.match_score == other.match_score

    def __le__(self, other: BidRanked) -> bool:
        if not isinstance(other, BidRanked):
            return NotImplemented
        return self.match_score >= other.match_score

    def __ge__(self, other: BidRanked) -> bool:
        if not isinstance(other, BidRanked):
            return NotImplemented
        return self.match_score <= other.match_score

    def __hash__(self) -> int:
        return hash(self.bid_id)


class Rating(Base):
    """
    Client's rating of a freelancer after project completion.
    One rating per project (enforced by unique constraint on project_id).
    Score is 1–5; review text is optional.
    """
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_rating_project"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    freelancer_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    client_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    score = Column(Integer, nullable=False)  # 1–5
    review = Column(Text, default="")
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Rating project={self.project_id} freelancer={self.freelancer_id} "
            f"score={self.score}>"
        )
