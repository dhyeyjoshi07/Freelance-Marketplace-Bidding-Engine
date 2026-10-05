"""
Bids router — bid submission and ranked bid listing.

POST /api/projects/{id}/bids  — submit a bid (freelancer only)
GET  /api/projects/{id}/bids  — list all bids for a project (ranked by match_score)
GET  /api/freelancers/me/bids — list the current freelancer's bids
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user, require_role
from backend.models.user import User, FreelancerProfile
from backend.models.project import Project
from backend.models.bid import Bid, BidRanked
from backend.schemas.bid import BidCreate, BidOut, BidRankedOut
from backend.services.match_engine import MatchEngine
from backend.services.ranking import RankedBidQueue
from backend.exceptions import BidOnExpiredProjectError, DuplicateBidError


router = APIRouter(tags=["bids"])

# Singleton match engine (stateless, so safe to share)
_engine = MatchEngine()


@router.post(
    "/api/projects/{project_id}/bids",
    response_model=BidOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_bid(
    project_id: int,
    body: BidCreate,
    current_user: User = Depends(require_role("freelancer")),
    db: Session = Depends(get_db),
):
    """
    Submit a bid on a project.

    Business rules enforced:
    1. Project must exist and be open + not past deadline
       (via Project.ensure_biddable → BidOnExpiredProjectError)
    2. Freelancer cannot bid twice on the same project
       (via DB unique constraint + app check → DuplicateBidError)
    3. Match score is computed at submission time and stored with the bid
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Rule 1: project must be accepting bids
    try:
        project.ensure_biddable()
    except BidOnExpiredProjectError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Rule 2: no duplicate bids
    existing = db.query(Bid).filter(
        Bid.project_id == project_id,
        Bid.freelancer_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(DuplicateBidError(current_user.id, project_id)),
        )

    # Get freelancer profile for scoring
    profile = (
        db.query(FreelancerProfile)
        .filter(FreelancerProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=400, detail="Freelancer profile not found")

    # Rule 3: compute match score
    score = _engine.match_score(
        bid_amount=body.amount,
        freelancer_skills=profile.get_skills_list(),
        freelancer_avg_rating=profile.avg_rating or 0.0,
        required_skills=project.get_required_skills_list(),
        budget_min=project.budget_min,
        budget_max=project.budget_max,
    )

    bid = Bid(
        project_id=project_id,
        freelancer_id=current_user.id,
        amount=body.amount,
        proposal=body.proposal,
        match_score=score,
    )
    db.add(bid)
    db.commit()
    db.refresh(bid)

    return BidOut(
        id=bid.id,
        project_id=bid.project_id,
        freelancer_id=bid.freelancer_id,
        freelancer_name=current_user.username,
        amount=bid.amount,
        proposal=bid.proposal,
        match_score=bid.match_score,
        created_at=bid.created_at,
    )


@router.get("/api/projects/{project_id}/bids", response_model=list[BidRankedOut])
def list_ranked_bids(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    List all bids for a project, ranked by match_score (highest first).

    Uses the RankedBidQueue (heapq-based) to produce the ranked ordering,
    then enriches each entry with freelancer info for the client's view.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    bids = db.query(Bid).filter(Bid.project_id == project_id).all()

    if not bids:
        return []

    # Build ranked queue using BidRanked dataclass + heapq
    # Cache freelancer profiles to avoid redundant queries
    ranked_items = []
    profiles_cache: dict[int, FreelancerProfile | None] = {}
    for bid in bids:
        freelancer = db.query(User).filter(User.id == bid.freelancer_id).first()
        profile = (
            db.query(FreelancerProfile)
            .filter(FreelancerProfile.user_id == bid.freelancer_id)
            .first()
        )
        profiles_cache[bid.freelancer_id] = profile
        ranked_items.append(BidRanked(
            bid_id=bid.id,
            match_score=bid.match_score,
            freelancer_id=bid.freelancer_id,
            freelancer_name=freelancer.username if freelancer else "",
            amount=bid.amount,
            proposal=bid.proposal or "",
        ))

    # Use RankedBidQueue for heapq-based ranking
    queue = RankedBidQueue.from_bids(ranked_items)
    ranked = queue.ranked_list()

    # Build response with rank numbers and freelancer details
    result = []
    for rank, item in enumerate(ranked, start=1):
        profile = profiles_cache.get(item.freelancer_id)
        result.append(BidRankedOut(
            bid_id=item.bid_id,
            freelancer_id=item.freelancer_id,
            freelancer_name=item.freelancer_name,
            freelancer_skills=profile.get_skills_list() if profile else [],
            freelancer_rating=profile.avg_rating if profile else 0.0,
            amount=item.amount,
            proposal=item.proposal,
            match_score=item.match_score,
            rank=rank,
        ))

    return result


@router.get("/api/freelancers/me/bids", response_model=list[BidOut])
def my_bids(
    current_user: User = Depends(require_role("freelancer")),
    db: Session = Depends(get_db),
):
    """List all bids submitted by the current freelancer."""
    bids = (
        db.query(Bid)
        .filter(Bid.freelancer_id == current_user.id)
        .order_by(Bid.created_at.desc())
        .all()
    )

    return [
        BidOut(
            id=bid.id,
            project_id=bid.project_id,
            freelancer_id=bid.freelancer_id,
            freelancer_name=current_user.username,
            amount=bid.amount,
            proposal=bid.proposal,
            match_score=bid.match_score,
            created_at=bid.created_at,
        )
        for bid in bids
    ]
