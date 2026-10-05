"""
Custom exceptions for domain-specific error handling.

Each exception maps to a specific business rule violation and is caught in the
API router layer to return an appropriate HTTP status code and message.
"""


class BidOnExpiredProjectError(Exception):
    """
    Raised when a freelancer attempts to bid on a project whose deadline
    has already passed or whose status is not 'open'.
    """
    def __init__(self, project_id: int, reason: str = "Project is no longer accepting bids"):
        self.project_id = project_id
        self.message = f"Cannot bid on project {project_id}: {reason}"
        super().__init__(self.message)


class DuplicateBidError(Exception):
    """
    Raised when a freelancer tries to submit a second bid on the same project.
    Enforced both at the DB level (unique constraint) and in application logic.
    """
    def __init__(self, freelancer_id: int, project_id: int):
        self.freelancer_id = freelancer_id
        self.project_id = project_id
        self.message = (
            f"Freelancer {freelancer_id} has already bid on project {project_id}"
        )
        super().__init__(self.message)


class InvalidBudgetError(Exception):
    """
    Raised when a project's budget range is invalid:
    - budget_min > budget_max
    - Either value is negative
    - budget_max is zero
    """
    def __init__(self, budget_min: float, budget_max: float):
        self.budget_min = budget_min
        self.budget_max = budget_max
        self.message = (
            f"Invalid budget range: min={budget_min}, max={budget_max}. "
            "budget_min must be >= 0 and < budget_max."
        )
        super().__init__(self.message)


class InvalidStatusTransitionError(Exception):
    """
    Raised when a project status change violates the allowed lifecycle:
        Open → InProgress → Completed
    Any other transition (e.g., Completed → Open) is illegal.
    """
    def __init__(self, current_status: str, attempted_status: str):
        self.current_status = current_status
        self.attempted_status = attempted_status
        self.message = (
            f"Cannot transition from '{current_status}' to '{attempted_status}'"
        )
        super().__init__(self.message)


class UnauthorizedActionError(Exception):
    """
    Raised when a user tries to perform an action outside their role
    (e.g., a freelancer trying to post a project).
    """
    def __init__(self, role: str, action: str):
        self.role = role
        self.action = action
        self.message = f"Users with role '{role}' cannot perform: {action}"
        super().__init__(self.message)
