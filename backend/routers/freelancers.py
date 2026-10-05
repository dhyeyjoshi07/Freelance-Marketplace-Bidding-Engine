"""
Freelancers router — profile management and ratings.

GET  /api/freelancers/me      — view own profile
PUT  /api/freelancers/me      — update skills / hourly rate
POST /api/projects/{id}/rate  — client rates the freelancer after completion
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user, require_role
from backend.models.user import User, FreelancerProfile
from backend.models.project import Project
from backend.models.bid import Bid, Rating
from backend.models.enums import ProjectStatus
from backend.schemas.user import FreelancerProfileOut, FreelancerProfileUpdate
from backend.schemas.bid import RatingCreate, RatingOut


router = APIRouter(tags=["freelancers"])


@router.get("/api/freelancers/me", response_model=FreelancerProfileOut)
def get_my_profile(
    current_user: User = Depends(require_role("freelancer")),
    db: Session = Depends(get_db),
):
    """Return the current freelancer's profile."""
    profile = (
        db.query(FreelancerProfile)
        .filter(FreelancerProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return FreelancerProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        skills=profile.get_skills_list(),
        hourly_rate=profile.hourly_rate,
        avg_rating=profile.avg_rating or 0.0,
        total_ratings=profile.total_ratings or 0,
    )


@router.put("/api/freelancers/me", response_model=FreelancerProfileOut)
def update_my_profile(
    body: FreelancerProfileUpdate,
    current_user: User = Depends(require_role("freelancer")),
    db: Session = Depends(get_db),
):
    """
    Update the freelancer's skills and/or hourly rate.

    Only provided fields are updated (partial update).
    """
    profile = (
        db.query(FreelancerProfile)
        .filter(FreelancerProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if body.skills is not None:
        profile.set_skills_list(body.skills)
    if body.hourly_rate is not None:
        profile.hourly_rate = body.hourly_rate

    db.commit()
    db.refresh(profile)

    return FreelancerProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        skills=profile.get_skills_list(),
        hourly_rate=profile.hourly_rate,
        avg_rating=profile.avg_rating or 0.0,
        total_ratings=profile.total_ratings or 0,
    )


@router.post("/api/projects/{project_id}/rate", response_model=RatingOut)
def rate_freelancer(
    project_id: int,
    body: RatingCreate,
    current_user: User = Depends(require_role("client")),
    db: Session = Depends(get_db),
):
    """
    Rate the freelancer after project completion.

    Rules:
    - Only the project owner (client) can rate
    - Project must be completed
    - Only one rating per project
    - Updates the freelancer's incremental avg_rating
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your project")

    if project.status != ProjectStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail="Can only rate after project is completed",
        )

    # Check for existing rating
    existing = db.query(Rating).filter(Rating.project_id == project_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Project already rated")

    # Find the accepted freelancer
    accepted_bid = db.query(Bid).filter(Bid.id == project.accepted_bid_id).first()
    if not accepted_bid:
        raise HTTPException(status_code=400, detail="No accepted bid found")

    # Create the rating
    rating = Rating(
        project_id=project_id,
        freelancer_id=accepted_bid.freelancer_id,
        client_id=current_user.id,
        score=body.score,
        review=body.review,
    )
    db.add(rating)

    # Update the freelancer's incremental average rating
    profile = (
        db.query(FreelancerProfile)
        .filter(FreelancerProfile.user_id == accepted_bid.freelancer_id)
        .first()
    )
    if profile:
        profile.update_rating(body.score)

    db.commit()
    db.refresh(rating)
    return rating
