"""
Projects router — CRUD, bid acceptance, and project completion.

POST /api/projects                  — create a project (client only)
GET  /api/projects                  — list open projects (with optional filters)
GET  /api/projects/{id}             — project detail (with bid count)
POST /api/projects/{id}/accept-bid  — accept a bid (client only, Open → InProgress)
POST /api/projects/{id}/complete    — mark project complete (dual-confirmation)
GET  /api/projects/my               — list current user's projects
"""

from __future__ import annotations


from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user, require_role
from backend.models.user import User
from backend.models.project import Project
from backend.models.bid import Bid
from backend.models.enums import ProjectStatus, UserRole
from backend.schemas.project import ProjectCreate, ProjectOut, ProjectAcceptBid
from backend.exceptions import (
    InvalidBudgetError,
    InvalidStatusTransitionError,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_to_out(project: Project, db: Session) -> ProjectOut:
    """
    Convert a Project ORM instance to the response schema.

    Deserializes JSON skills and counts bids — done here rather than
    in the model to keep the ORM layer clean of presentation logic.
    """
    client = db.query(User).filter(User.id == project.client_id).first()
    bid_count = db.query(Bid).filter(Bid.project_id == project.id).count()

    return ProjectOut(
        id=project.id,
        client_id=project.client_id,
        client_name=client.username if client else None,
        title=project.title,
        description=project.description or "",
        required_skills=project.get_required_skills_list(),
        budget_min=project.budget_min,
        budget_max=project.budget_max,
        deadline=project.deadline,
        status=project.status,
        accepted_bid_id=project.accepted_bid_id,
        client_completed=bool(project.client_completed),
        freelancer_completed=bool(project.freelancer_completed),
        created_at=project.created_at,
        bid_count=bid_count,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    current_user: User = Depends(require_role("client")),
    db: Session = Depends(get_db),
):
    """
    Create a new project.

    Validates the budget range and deadline before persisting.
    Only clients can create projects (enforced by require_role).
    """
    # Validate budget via the encapsulated static method
    try:
        Project.validate_budget(body.budget_min, body.budget_max)
    except InvalidBudgetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Validate deadline is in the future
    if body.deadline.tzinfo is None:
        deadline = body.deadline.replace(tzinfo=timezone.utc)
    else:
        deadline = body.deadline

    if deadline <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deadline must be in the future",
        )

    project = Project(
        client_id=current_user.id,
        title=body.title,
        description=body.description,
        budget_min=body.budget_min,
        budget_max=body.budget_max,
        deadline=deadline,
        status=ProjectStatus.OPEN.value,
    )
    project.set_required_skills_list(body.required_skills)

    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_to_out(project, db)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    status_filter: str | None = Query(None, alias="status"),
    skill: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    List projects, optionally filtered by status or required skill.

    Default (no filter): returns all open projects.
    """
    query = db.query(Project)

    if status_filter:
        query = query.filter(Project.status == status_filter)
    else:
        # Default to open projects
        query = query.filter(Project.status == ProjectStatus.OPEN.value)

    projects = query.order_by(Project.created_at.desc()).all()

    # Optional skill filter (application-level since skills are JSON)
    if skill:
        skill_lower = skill.lower().strip()
        projects = [
            p for p in projects
            if skill_lower in p.get_required_skills_list()
        ]

    return [_project_to_out(p, db) for p in projects]


@router.get("/my", response_model=list[ProjectOut])
def my_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List the current user's projects.

    For clients: projects they posted.
    For freelancers: projects they have bids on.
    """
    if current_user.role == UserRole.CLIENT.value:
        projects = (
            db.query(Project)
            .filter(Project.client_id == current_user.id)
            .order_by(Project.created_at.desc())
            .all()
        )
    else:
        # Freelancer: projects they've bid on
        bid_project_ids = (
            db.query(Bid.project_id)
            .filter(Bid.freelancer_id == current_user.id)
            .subquery()
        )
        projects = (
            db.query(Project)
            .filter(Project.id.in_(bid_project_ids))
            .order_by(Project.created_at.desc())
            .all()
        )

    return [_project_to_out(p, db) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a single project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_out(project, db)


@router.post("/{project_id}/accept-bid", response_model=ProjectOut)
def accept_bid(
    project_id: int,
    body: ProjectAcceptBid,
    current_user: User = Depends(require_role("client")),
    db: Session = Depends(get_db),
):
    """
    Accept a bid on a project (Open → InProgress).

    Only the project owner (client) can accept bids.
    Uses the encapsulated Project.accept_bid() method.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your project")

    # Verify the bid exists and belongs to this project
    bid = db.query(Bid).filter(
        Bid.id == body.bid_id, Bid.project_id == project_id
    ).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found on this project")

    try:
        project.accept_bid(body.bid_id)
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(project)
    return _project_to_out(project, db)


@router.post("/{project_id}/complete", response_model=ProjectOut)
def complete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a project as complete (dual-confirmation).

    Both the client and the freelancer (whose bid was accepted) must
    call this endpoint.  The project transitions to 'completed' only
    when both parties have confirmed.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Authorization: must be the client OR the accepted freelancer
    accepted_bid = None
    if project.accepted_bid_id:
        accepted_bid = db.query(Bid).filter(Bid.id == project.accepted_bid_id).first()

    is_client = (current_user.id == project.client_id)
    is_freelancer = (accepted_bid and current_user.id == accepted_bid.freelancer_id)

    if not is_client and not is_freelancer:
        raise HTTPException(status_code=403, detail="Not authorized for this project")

    role = "client" if is_client else "freelancer"

    try:
        project.mark_completed_by(role)
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(project)
    return _project_to_out(project, db)
