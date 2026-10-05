"""
Enums shared across models.

ProjectStatus governs the project lifecycle (Open → InProgress → Completed).
UserRole distinguishes clients from freelancers for role-based access control.
"""

import enum


class ProjectStatus(str, enum.Enum):
    """
    Project lifecycle states.  Transitions are enforced by Project methods:
        Open → InProgress  (via accept_bid)
        InProgress → Completed  (via mark_completed)
    """
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class UserRole(str, enum.Enum):
    """Determines which dashboard and API operations a user can access."""
    CLIENT = "client"
    FREELANCER = "freelancer"
