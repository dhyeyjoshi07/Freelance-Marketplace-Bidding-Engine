"""
FastAPI dependencies — reusable Depends() callables.

get_db: yields a SQLAlchemy session per request (auto-closed).
get_current_user: extracts and validates the JWT from the Authorization header.
require_role: factory that returns a dependency enforcing a specific user role.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.user import User
from backend.services.auth_service import decode_access_token


# OAuth2 scheme — tells FastAPI where to look for the bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db():
    """
    Yield a database session for the duration of a request.
    Automatically closed when the request completes (even on error).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT and return the corresponding User from the database.

    Raises 401 if the token is invalid/expired or the user doesn't exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user


def require_role(role: str):
    """
    Factory that produces a dependency enforcing a specific role.

    Usage in a router:
        @router.post("/projects", dependencies=[Depends(require_role("client"))])

    Or inject the user directly:
        current_user: User = Depends(require_role("client"))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the '{role}' role",
            )
        return current_user
    return role_checker
