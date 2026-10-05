"""
Match Engine — computes a composite fitness score for each bid.

Scoring formula:
    match_score = SKILL_WEIGHT  × skill_overlap_ratio
                + PRICE_WEIGHT  × price_fit_score
                + RATING_WEIGHT × normalized_rating

Three scoring dimensions:
  1. Skill overlap  (0.45 weight) — set intersection of freelancer skills
     vs. project required skills.  Uses polymorphic strategy: full overlap,
     partial overlap, and no overlap each produce different scores.
  2. Price fit      (0.30 weight) — how well the bid amount fits the client's
     budget range.  Perfect fit inside range = 1.0; linear decay outside.
  3. Past rating    (0.25 weight) — freelancer's avg_rating / 5.0.

The engine is designed to be subclassed: override _compute_skill_overlap()
or _compute_price_fit() to change the scoring strategy (polymorphism).
"""

from __future__ import annotations

from backend.config import SKILL_WEIGHT, PRICE_WEIGHT, RATING_WEIGHT


class MatchEngine:
    """
    Stateless scoring engine.  Instantiate once and call match_score()
    for each bid.  All configuration comes from backend.config.

    Polymorphism: subclass and override _compute_skill_overlap() to
    implement a different matching strategy (e.g., weighted skills,
    NLP-based semantic matching).
    """

    def __init__(
        self,
        skill_weight: float = SKILL_WEIGHT,
        price_weight: float = PRICE_WEIGHT,
        rating_weight: float = RATING_WEIGHT,
    ):
        self.skill_weight = skill_weight
        self.price_weight = price_weight
        self.rating_weight = rating_weight

    def match_score(
        self,
        bid_amount: float,
        freelancer_skills: list[str],
        freelancer_avg_rating: float,
        required_skills: list[str],
        budget_min: float,
        budget_max: float,
    ) -> float:
        """
        Compute the composite match score for a bid.

        Returns a float in [0.0, 1.0] where 1.0 is a perfect fit.
        """
        skill_score = self._compute_skill_overlap(
            freelancer_skills, required_skills
        )
        price_score = self._compute_price_fit(
            bid_amount, budget_min, budget_max
        )
        rating_score = self._normalize_rating(freelancer_avg_rating)

        raw = (
            self.skill_weight * skill_score
            + self.price_weight * price_score
            + self.rating_weight * rating_score
        )
        # Clamp to [0.0, 1.0] for safety
        return round(max(0.0, min(1.0, raw)), 4)

    # ------------------------------------------------------------------
    # Polymorphic scoring components — override in subclasses for custom
    # strategies (OOP requirement: polymorphism)
    # ------------------------------------------------------------------

    def _compute_skill_overlap(
        self,
        freelancer_skills: list[str],
        required_skills: list[str],
    ) -> float:
        """
        Compute skill overlap ratio via set intersection.

        Strategy (polymorphic behavior based on overlap level):
          - Full overlap   (all required skills matched) → 1.0
          - Partial overlap (some matched)               → ratio in (0, 1)
          - No overlap     (zero skills matched)         → 0.0

        Complexity: O(min(|freelancer_skills|, |required_skills|)) via
        Python set intersection.
        """
        if not required_skills:
            # No skills required → any freelancer is a full match
            return 1.0

        # Normalize to lowercase sets for case-insensitive matching
        required = set(s.lower().strip() for s in required_skills)
        offered = set(s.lower().strip() for s in freelancer_skills)

        overlap = required & offered
        return len(overlap) / len(required)

    def _compute_price_fit(
        self,
        bid_amount: float,
        budget_min: float,
        budget_max: float,
    ) -> float:
        """
        Score how well the bid amount fits the client's budget range.

        - Bid within [budget_min, budget_max] → 1.0 (perfect fit)
        - Bid below budget_min → linear decay toward 0.0 at $0
        - Bid above budget_max → linear decay toward 0.0 at 2× budget_max

        The idea: bids slightly outside the range are still acceptable,
        but extremely high or low bids get penalized heavily.
        """
        if bid_amount <= 0:
            return 0.0

        if budget_min <= bid_amount <= budget_max:
            return 1.0

        if bid_amount < budget_min:
            # Linear decay from budget_min down to 0
            # At $0 the score is 0.0, at budget_min it's 1.0
            if budget_min == 0:
                return 1.0
            return max(0.0, bid_amount / budget_min)

        # bid_amount > budget_max
        # Linear decay from budget_max up to 2× budget_max
        overshoot = bid_amount - budget_max
        max_overshoot = budget_max  # decays to 0 at 2× budget_max
        if max_overshoot == 0:
            return 0.0
        return max(0.0, 1.0 - (overshoot / max_overshoot))

    def _normalize_rating(self, avg_rating: float) -> float:
        """
        Normalize a 1–5 star rating to [0.0, 1.0].

        New freelancers (rating = 0.0) get a small baseline score (0.1)
        so they aren't completely disadvantaged vs. rated freelancers.
        """
        if avg_rating <= 0:
            # New freelancer bonus: don't penalize to zero
            return 0.1
        return min(avg_rating / 5.0, 1.0)


class WeightedSkillMatchEngine(MatchEngine):
    """
    Example subclass demonstrating polymorphic override.

    Instead of treating all skills equally, this variant gives bonus
    weight to rare/critical skills.  The bonus_skills set can be
    configured per project.
    """

    def __init__(self, bonus_skills: set[str] | None = None, **kwargs):
        super().__init__(**kwargs)
        # Skills that get 1.5× weight in the overlap calculation
        self.bonus_skills = {s.lower() for s in (bonus_skills or set())}

    def _compute_skill_overlap(
        self,
        freelancer_skills: list[str],
        required_skills: list[str],
    ) -> float:
        """
        Weighted skill overlap: bonus skills count 1.5× in the numerator.
        """
        if not required_skills:
            return 1.0

        required = set(s.lower().strip() for s in required_skills)
        offered = set(s.lower().strip() for s in freelancer_skills)
        overlap = required & offered

        if not overlap:
            return 0.0

        # Weight each overlapping skill: 1.5 if bonus, 1.0 otherwise
        weighted_score = sum(
            1.5 if skill in self.bonus_skills else 1.0
            for skill in overlap
        )
        # Max possible weighted score (all required skills matched)
        max_score = sum(
            1.5 if skill in self.bonus_skills else 1.0
            for skill in required
        )
        return weighted_score / max_score
