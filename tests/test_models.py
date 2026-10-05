"""
Unit tests for OOP model classes.

Tests cover:
- ABC hierarchy (User abstraction + inheritance)
- BidRanked operator overloading (__lt__, __gt__, sorted, heapq)
- Project encapsulated status transitions
- FreelancerProfile incremental rating + skill serialization
- Custom exception raising and catching
- RankedBidQueue container operations
"""

import heapq
import pytest

from backend.models import (
    UserBase, ClientUser, FreelancerUser,
    ProjectStatus, UserRole,
    Project, BidRanked, FreelancerProfile,
)
from backend.exceptions import (
    BidOnExpiredProjectError,
    DuplicateBidError,
    InvalidBudgetError,
    InvalidStatusTransitionError,
    UnauthorizedActionError,
)
from backend.services.ranking import RankedBidQueue


# ====================================================================
# ABC Hierarchy
# ====================================================================

class TestUserABC:
    """Verify that the User ABC enforces get_role() implementation."""

    def test_client_role(self):
        assert ClientUser().get_role() == "client"

    def test_freelancer_role(self):
        assert FreelancerUser().get_role() == "freelancer"

    def test_isinstance_check(self):
        """Both concrete types must be instances of UserBase."""
        assert isinstance(ClientUser(), UserBase)
        assert isinstance(FreelancerUser(), UserBase)

    def test_abc_cannot_instantiate(self):
        """UserBase itself should not be instantiable."""
        with pytest.raises(TypeError):
            UserBase()


# ====================================================================
# BidRanked — Operator Overloading
# ====================================================================

class TestBidRankedComparison:
    """Verify inverted comparison for max-heap behavior."""

    def test_lt_higher_score_is_less(self):
        """Higher score should be 'less than' for min-heap → max ordering."""
        high = BidRanked(bid_id=1, match_score=0.95)
        low = BidRanked(bid_id=2, match_score=0.50)
        assert high < low  # inverted!

    def test_gt_lower_score_is_greater(self):
        low = BidRanked(bid_id=1, match_score=0.30)
        high = BidRanked(bid_id=2, match_score=0.80)
        assert low > high  # inverted!

    def test_eq_same_score(self):
        a = BidRanked(bid_id=1, match_score=0.75)
        b = BidRanked(bid_id=2, match_score=0.75)
        assert a == b

    def test_sorted_produces_descending_scores(self):
        bids = [
            BidRanked(bid_id=1, match_score=0.60),
            BidRanked(bid_id=2, match_score=0.90),
            BidRanked(bid_id=3, match_score=0.45),
            BidRanked(bid_id=4, match_score=0.78),
        ]
        ranked = sorted(bids)
        scores = [b.match_score for b in ranked]
        assert scores == [0.90, 0.78, 0.60, 0.45]

    def test_heapq_pops_highest_first(self):
        """heapq.heappop should return the highest-scoring bid."""
        heap = []
        heapq.heappush(heap, BidRanked(bid_id=1, match_score=0.50))
        heapq.heappush(heap, BidRanked(bid_id=2, match_score=0.85))
        heapq.heappush(heap, BidRanked(bid_id=3, match_score=0.70))

        first = heapq.heappop(heap)
        assert first.match_score == 0.85
        second = heapq.heappop(heap)
        assert second.match_score == 0.70

    def test_not_implemented_for_non_bidranked(self):
        bid = BidRanked(bid_id=1, match_score=0.5)
        assert bid.__lt__(42) is NotImplemented
        assert bid.__gt__("string") is NotImplemented
        assert bid.__eq__(3.14) is NotImplemented


# ====================================================================
# Project — Encapsulated Status Transitions
# ====================================================================

class TestProjectTransitions:
    """Verify that status changes only happen through methods."""

    def _make_project(self, status="open"):
        return Project(
            client_id=1, title="Test", budget_min=100, budget_max=500,
            status=status,
        )

    def test_accept_bid_open_to_in_progress(self):
        p = self._make_project()
        p.accept_bid(bid_id=42)
        assert p.status == ProjectStatus.IN_PROGRESS.value
        assert p.accepted_bid_id == 42

    def test_accept_bid_fails_if_not_open(self):
        p = self._make_project(status="in_progress")
        with pytest.raises(InvalidStatusTransitionError):
            p.accept_bid(bid_id=1)

    def test_accept_bid_fails_if_completed(self):
        p = self._make_project(status="completed")
        with pytest.raises(InvalidStatusTransitionError):
            p.accept_bid(bid_id=1)

    def test_dual_completion_client_first(self):
        p = self._make_project(status="in_progress")
        assert p.mark_completed_by("client") is False  # first party
        assert p.status == ProjectStatus.IN_PROGRESS.value
        assert p.mark_completed_by("freelancer") is True  # second → transitions
        assert p.status == ProjectStatus.COMPLETED.value

    def test_dual_completion_freelancer_first(self):
        p = self._make_project(status="in_progress")
        assert p.mark_completed_by("freelancer") is False
        assert p.mark_completed_by("client") is True
        assert p.status == ProjectStatus.COMPLETED.value

    def test_complete_fails_if_open(self):
        p = self._make_project(status="open")
        with pytest.raises(InvalidStatusTransitionError):
            p.mark_completed_by("client")

    def test_complete_fails_if_already_completed(self):
        p = self._make_project(status="completed")
        with pytest.raises(InvalidStatusTransitionError):
            p.mark_completed_by("client")


class TestProjectBudgetValidation:
    def test_valid_budget(self):
        Project.validate_budget(100, 500)  # should not raise

    def test_negative_min(self):
        with pytest.raises(InvalidBudgetError):
            Project.validate_budget(-10, 500)

    def test_min_greater_than_max(self):
        with pytest.raises(InvalidBudgetError):
            Project.validate_budget(600, 500)

    def test_zero_max(self):
        with pytest.raises(InvalidBudgetError):
            Project.validate_budget(0, 0)

    def test_equal_min_max(self):
        with pytest.raises(InvalidBudgetError):
            Project.validate_budget(100, 100)


# ====================================================================
# FreelancerProfile
# ====================================================================

class TestFreelancerProfile:
    def _make_profile(self):
        return FreelancerProfile(user_id=1, hourly_rate=50.0)

    def test_incremental_rating_single(self):
        fp = self._make_profile()
        fp.update_rating(5)
        assert fp.avg_rating == 5.0
        assert fp.total_ratings == 1

    def test_incremental_rating_multiple(self):
        fp = self._make_profile()
        fp.update_rating(5)
        fp.update_rating(3)
        assert fp.avg_rating == 4.0
        assert fp.total_ratings == 2
        fp.update_rating(4)
        assert fp.avg_rating == 4.0
        assert fp.total_ratings == 3

    def test_skills_serialization_lowercase(self):
        fp = self._make_profile()
        fp.set_skills_list(["Python", "REACT", " fastAPI "])
        assert fp.get_skills_list() == ["python", "react", "fastapi"]

    def test_skills_empty(self):
        fp = self._make_profile()
        fp.set_skills_list([])
        assert fp.get_skills_list() == []


# ====================================================================
# Custom Exceptions
# ====================================================================

class TestCustomExceptions:
    def test_bid_on_expired_project(self):
        exc = BidOnExpiredProjectError(42, "deadline passed")
        assert "42" in str(exc)
        assert "deadline passed" in str(exc)
        assert exc.project_id == 42

    def test_duplicate_bid(self):
        exc = DuplicateBidError(1, 2)
        assert exc.freelancer_id == 1
        assert exc.project_id == 2

    def test_invalid_budget(self):
        exc = InvalidBudgetError(-10, 50)
        assert exc.budget_min == -10
        assert exc.budget_max == 50

    def test_invalid_status_transition(self):
        exc = InvalidStatusTransitionError("open", "completed")
        assert exc.current_status == "open"
        assert exc.attempted_status == "completed"

    def test_unauthorized_action(self):
        exc = UnauthorizedActionError("freelancer", "post project")
        assert "freelancer" in str(exc)


# ====================================================================
# RankedBidQueue — Container
# ====================================================================

class TestRankedBidQueue:
    def _make_bids(self):
        return [
            BidRanked(bid_id=1, match_score=0.60, freelancer_name="Alice"),
            BidRanked(bid_id=2, match_score=0.90, freelancer_name="Bob"),
            BidRanked(bid_id=3, match_score=0.45, freelancer_name="Charlie"),
            BidRanked(bid_id=4, match_score=0.78, freelancer_name="Diana"),
        ]

    def test_push_and_peek(self):
        q = RankedBidQueue()
        q.push(BidRanked(bid_id=1, match_score=0.50))
        q.push(BidRanked(bid_id=2, match_score=0.80))
        top = q.peek()
        assert top is not None
        assert top.match_score == 0.80

    def test_pop_returns_highest_first(self):
        q = RankedBidQueue()
        for b in self._make_bids():
            q.push(b)
        first = q.pop()
        assert first is not None
        assert first.match_score == 0.90
        second = q.pop()
        assert second is not None
        assert second.match_score == 0.78

    def test_ranked_list_descending(self):
        q = RankedBidQueue()
        for b in self._make_bids():
            q.push(b)
        ranked = q.ranked_list()
        scores = [b.match_score for b in ranked]
        assert scores == [0.90, 0.78, 0.60, 0.45]

    def test_len(self):
        q = RankedBidQueue()
        assert len(q) == 0
        q.push(BidRanked(bid_id=1, match_score=0.5))
        assert len(q) == 1
        q.push(BidRanked(bid_id=2, match_score=0.7))
        assert len(q) == 2

    def test_remove(self):
        q = RankedBidQueue()
        for b in self._make_bids():
            q.push(b)
        assert q.remove(2) is True  # remove Bob (0.90)
        assert len(q) == 3
        ranked = q.ranked_list()
        assert ranked[0].match_score == 0.78  # Diana is now top

    def test_remove_nonexistent(self):
        q = RankedBidQueue()
        assert q.remove(999) is False

    def test_from_bids_factory(self):
        bids = self._make_bids()
        q = RankedBidQueue.from_bids(bids)
        assert len(q) == 4
        ranked = q.ranked_list()
        assert ranked[0].match_score == 0.90

    def test_replace_bid_via_push(self):
        """Pushing the same bid_id should replace the old entry."""
        q = RankedBidQueue()
        q.push(BidRanked(bid_id=1, match_score=0.50))
        q.push(BidRanked(bid_id=1, match_score=0.95))  # replace
        assert len(q) == 1
        assert q.peek().match_score == 0.95

    def test_empty_queue(self):
        q = RankedBidQueue()
        assert q.peek() is None
        assert q.pop() is None
        assert q.ranked_list() == []
        assert not q
