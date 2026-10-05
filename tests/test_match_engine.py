"""
Unit tests for the MatchEngine scoring algorithm.

Tests cover:
- Skill overlap scoring (full, partial, none, empty required)
- Price fit scoring (within budget, below budget, above budget, edge cases)
- Rating normalization (rated, unrated, max rating)
- Composite match_score integration
- WeightedSkillMatchEngine polymorphic override
- Score ordering (verify the engine's ranking matches expected order)
"""

import pytest

from backend.services.match_engine import MatchEngine, WeightedSkillMatchEngine


@pytest.fixture
def engine():
    """Default engine with standard weights (0.45/0.30/0.25)."""
    return MatchEngine()


# ====================================================================
# Skill Overlap
# ====================================================================

class TestSkillOverlap:
    def test_full_overlap(self, engine):
        score = engine._compute_skill_overlap(
            freelancer_skills=["python", "react", "sql"],
            required_skills=["python", "react", "sql"],
        )
        assert score == 1.0

    def test_partial_overlap(self, engine):
        score = engine._compute_skill_overlap(
            freelancer_skills=["python", "java"],
            required_skills=["python", "react", "sql"],
        )
        assert abs(score - 1 / 3) < 1e-9

    def test_no_overlap(self, engine):
        score = engine._compute_skill_overlap(
            freelancer_skills=["java", "c++"],
            required_skills=["python", "react"],
        )
        assert score == 0.0

    def test_empty_required_skills(self, engine):
        """No skills required → any freelancer is a full match."""
        score = engine._compute_skill_overlap(
            freelancer_skills=["python"],
            required_skills=[],
        )
        assert score == 1.0

    def test_case_insensitive(self, engine):
        score = engine._compute_skill_overlap(
            freelancer_skills=["PYTHON", "React"],
            required_skills=["python", "react"],
        )
        assert score == 1.0

    def test_superset_of_required(self, engine):
        """Freelancer has MORE skills than required → still 1.0."""
        score = engine._compute_skill_overlap(
            freelancer_skills=["python", "react", "sql", "docker", "aws"],
            required_skills=["python", "react"],
        )
        assert score == 1.0


# ====================================================================
# Price Fit
# ====================================================================

class TestPriceFit:
    def test_within_budget(self, engine):
        score = engine._compute_price_fit(300, 200, 500)
        assert score == 1.0

    def test_at_budget_min(self, engine):
        score = engine._compute_price_fit(200, 200, 500)
        assert score == 1.0

    def test_at_budget_max(self, engine):
        score = engine._compute_price_fit(500, 200, 500)
        assert score == 1.0

    def test_below_budget_half(self, engine):
        """At half the budget_min → score = 0.5."""
        score = engine._compute_price_fit(100, 200, 500)
        assert score == 0.5

    def test_above_budget_halfway(self, engine):
        """Halfway between budget_max and 2× budget_max → score = 0.5."""
        # budget_max = 500, overshoot midpoint = 750
        score = engine._compute_price_fit(750, 200, 500)
        assert score == 0.5

    def test_at_double_budget_max(self, engine):
        """At 2× budget_max → score = 0.0."""
        score = engine._compute_price_fit(1000, 200, 500)
        assert score == 0.0

    def test_way_above_budget(self, engine):
        """Beyond 2× budget_max → clamped to 0.0."""
        score = engine._compute_price_fit(2000, 200, 500)
        assert score == 0.0

    def test_zero_bid(self, engine):
        score = engine._compute_price_fit(0, 200, 500)
        assert score == 0.0

    def test_negative_bid(self, engine):
        score = engine._compute_price_fit(-50, 200, 500)
        assert score == 0.0


# ====================================================================
# Rating Normalization
# ====================================================================

class TestRatingNormalization:
    def test_perfect_rating(self, engine):
        assert engine._normalize_rating(5.0) == 1.0

    def test_mid_rating(self, engine):
        assert engine._normalize_rating(3.0) == 0.6

    def test_zero_rating_baseline(self, engine):
        """New freelancer (0 rating) gets a small baseline, not zero."""
        assert engine._normalize_rating(0.0) == 0.1

    def test_above_max_capped(self, engine):
        """Rating above 5 is capped at 1.0."""
        assert engine._normalize_rating(6.0) == 1.0


# ====================================================================
# Composite match_score
# ====================================================================

class TestMatchScore:
    def test_perfect_match(self, engine):
        """Full skill match + within budget + 5-star rating → ~1.0."""
        score = engine.match_score(
            bid_amount=300,
            freelancer_skills=["python", "react"],
            freelancer_avg_rating=5.0,
            required_skills=["python", "react"],
            budget_min=200,
            budget_max=500,
        )
        # 0.45 × 1.0 + 0.30 × 1.0 + 0.25 × 1.0 = 1.0
        assert score == 1.0

    def test_no_match(self, engine):
        """No skill overlap + over budget + no rating → near minimum."""
        score = engine.match_score(
            bid_amount=2000,
            freelancer_skills=["java"],
            freelancer_avg_rating=0.0,
            required_skills=["python", "react"],
            budget_min=200,
            budget_max=500,
        )
        # 0.45 × 0.0 + 0.30 × 0.0 + 0.25 × 0.1 = 0.025
        assert score == 0.025

    def test_partial_match(self, engine):
        """Partial skills + budget fit + decent rating."""
        score = engine.match_score(
            bid_amount=400,
            freelancer_skills=["python", "docker"],
            freelancer_avg_rating=4.0,
            required_skills=["python", "react", "sql"],
            budget_min=200,
            budget_max=500,
        )
        # skill = 1/3, price = 1.0, rating = 0.8
        # 0.45 × 0.333 + 0.30 × 1.0 + 0.25 × 0.8 = 0.15 + 0.30 + 0.20 = 0.65
        assert 0.64 <= score <= 0.66

    def test_score_clamped_to_0_1(self, engine):
        """Ensure score is always within [0.0, 1.0]."""
        score = engine.match_score(
            bid_amount=300,
            freelancer_skills=["python"],
            freelancer_avg_rating=5.0,
            required_skills=["python"],
            budget_min=200,
            budget_max=500,
        )
        assert 0.0 <= score <= 1.0

    def test_ranking_order(self, engine):
        """
        Verify that the engine correctly ranks a set of candidates.
        Expected order: Alice (full match) > Charlie (partial) > Bob (no match).
        """
        # Alice: full skills, in budget, 4.5 rating
        alice_score = engine.match_score(
            bid_amount=350,
            freelancer_skills=["python", "react", "sql"],
            freelancer_avg_rating=4.5,
            required_skills=["python", "react", "sql"],
            budget_min=200,
            budget_max=500,
        )
        # Bob: no skills, over budget, low rating
        bob_score = engine.match_score(
            bid_amount=800,
            freelancer_skills=["java", "c++"],
            freelancer_avg_rating=2.0,
            required_skills=["python", "react", "sql"],
            budget_min=200,
            budget_max=500,
        )
        # Charlie: 2/3 skills, in budget, 3.5 rating
        charlie_score = engine.match_score(
            bid_amount=400,
            freelancer_skills=["python", "react"],
            freelancer_avg_rating=3.5,
            required_skills=["python", "react", "sql"],
            budget_min=200,
            budget_max=500,
        )
        assert alice_score > charlie_score > bob_score


# ====================================================================
# WeightedSkillMatchEngine — Polymorphism
# ====================================================================

class TestWeightedSkillMatchEngine:
    def test_bonus_skills_boost_score(self):
        """Skills marked as 'bonus' should produce a higher overlap score."""
        base_engine = MatchEngine()
        weighted_engine = WeightedSkillMatchEngine(
            bonus_skills={"python", "react"}
        )

        freelancer_skills = ["python", "react"]
        required_skills = ["python", "react", "sql"]

        base_score = base_engine._compute_skill_overlap(
            freelancer_skills, required_skills
        )
        weighted_score = weighted_engine._compute_skill_overlap(
            freelancer_skills, required_skills
        )
        # python + react are bonus (1.5× each), so weighted > base
        assert weighted_score > base_score

    def test_no_bonus_skills_same_as_base(self):
        """Without bonus skills, behavior should match the base engine."""
        base_engine = MatchEngine()
        weighted_engine = WeightedSkillMatchEngine(bonus_skills=set())

        skills = ["python", "react"]
        required = ["python", "react", "sql"]

        base = base_engine._compute_skill_overlap(skills, required)
        weighted = weighted_engine._compute_skill_overlap(skills, required)
        assert abs(base - weighted) < 1e-9

    def test_full_overlap_with_bonus(self):
        engine = WeightedSkillMatchEngine(bonus_skills={"python"})
        score = engine._compute_skill_overlap(
            ["python", "react"], ["python", "react"]
        )
        assert score == 1.0  # full overlap is always 1.0 regardless of weights

    def test_empty_required(self):
        engine = WeightedSkillMatchEngine(bonus_skills={"python"})
        score = engine._compute_skill_overlap(["python"], [])
        assert score == 1.0
