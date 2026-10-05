"""
Auth router — registration and login endpoints.

POST /api/auth/register — create a new user (client or freelancer)
POST /api/auth/login    — authenticate and receive a JWT
GET  /api/auth/me       — return the current user's profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


from backend.dependencies import get_db, get_current_user
from backend.models.user import User, FreelancerProfile
from backend.models.enums import UserRole
from backend.schemas.user import (
    UserRegister, UserLogin, Token, UserOut, FreelancerProfileOut,
)
from backend.services.auth_service import hash_password, verify_password, create_access_token


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user.

    - Checks for duplicate username/email
    - Hashes the password with bcrypt
    - If role is 'freelancer', auto-creates an empty FreelancerProfile
    """
    # Check for existing username
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    # Check for existing email
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.flush()  # Get the user.id before creating the profile

    # Auto-create a freelancer profile with empty skills
    if body.role == UserRole.FREELANCER.value:
        profile = FreelancerProfile(user_id=user.id, hourly_rate=0.0)
        profile.set_skills_list([])
        db.add(profile)

    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(body: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT.

    The JWT payload includes the user's id (as 'sub') and role.
    """
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return Token(
        access_token=token,
        role=user.role,
        user_id=user.id,
        username=user.username,
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return current_user
