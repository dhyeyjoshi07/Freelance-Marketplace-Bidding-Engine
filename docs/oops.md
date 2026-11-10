# OOP Concepts in BidForge

This document maps every Object-Oriented Programming concept used in BidForge back to the actual source code.
All examples are drawn from the project's own codebase — no textbook snippets.

---

## Table of Contents

1. [Classes & Objects](#1-classes--objects)
2. [Encapsulation](#2-encapsulation)
3. [Inheritance](#3-inheritance)
4. [Abstraction (Abstract Base Classes)](#4-abstraction-abstract-base-classes)
5. [Polymorphism](#5-polymorphism)
6. [Operator Overloading (Dunder Methods)](#6-operator-overloading-dunder-methods)
7. [Composition & Aggregation](#7-composition--aggregation)
8. [Enumerations](#8-enumerations)
9. [Dataclasses](#9-dataclasses)
10. [Pydantic Models (Data Validation)](#10-pydantic-models-data-validation)
11. [Custom Exception Hierarchy](#11-custom-exception-hierarchy)
12. [Design Patterns](#12-design-patterns)
13. [Decorators](#13-decorators)
14. [Static & Class Methods](#14-static--class-methods)
15. [Data Structures as Classes](#15-data-structures-as-classes)
16. [Class Diagram](#16-class-diagram)

---

## 1. Classes & Objects

Every entity in BidForge is modelled as a class. Objects are created at runtime when a user registers, posts a project, or submits a bid.

| Class | File | Purpose |
|-------|------|---------|
| `User` | [`backend/models/user.py`](../backend/models/user.py) | Persistent user record (SQLAlchemy ORM) |
| `FreelancerProfile` | [`backend/models/user.py`](../backend/models/user.py) | 1:1 extension for freelancer-specific data |
| `Project` | [`backend/models/project.py`](../backend/models/project.py) | Client-posted project with lifecycle state |
| `Bid` | [`backend/models/bid.py`](../backend/models/bid.py) | A freelancer's bid on a project |
| `Rating` | [`backend/models/bid.py`](../backend/models/bid.py) | Client's 1–5 star rating of a freelancer |
| `BidRanked` | [`backend/models/bid.py`](../backend/models/bid.py) | Lightweight dataclass for heap-based ranking |
| `MatchEngine` | [`backend/services/match_engine.py`](../backend/services/match_engine.py) | Stateless scoring engine |
| `RankedBidQueue` | [`backend/services/ranking.py`](../backend/services/ranking.py) | Priority queue container |

---

## 2. Encapsulation

Encapsulation bundles data with the methods that operate on it, hiding internal state and exposing only safe interfaces.

### Project Status Machine

Status is **never mutated directly**. All transitions go through validated methods:

```python
# backend/models/project.py — Lines 89–128

def accept_bid(self, bid_id: int) -> None:
    """Transition: Open → InProgress."""
    if self.status != ProjectStatus.OPEN.value:
        raise InvalidStatusTransitionError(
            self.status, ProjectStatus.IN_PROGRESS.value
        )
    self.status = ProjectStatus.IN_PROGRESS.value
    self.accepted_bid_id = bid_id

def mark_completed_by(self, role: str) -> bool:
    """Dual-confirmation: both client and freelancer must confirm."""
    if self.status != ProjectStatus.IN_PROGRESS.value:
        raise InvalidStatusTransitionError(
            self.status, ProjectStatus.COMPLETED.value
        )
    if role == "client":
        self.client_completed = 1
    elif role == "freelancer":
        self.freelancer_completed = 1
    if self.client_completed and self.freelancer_completed:
        self.status = ProjectStatus.COMPLETED.value
        return True
    return False
```

**State diagram:**
```
Open ──accept_bid()──▶ InProgress ──mark_completed_by()──▶ Completed
```

### JSON Serialization Helpers

`FreelancerProfile` encapsulates skill storage — callers never deal with raw JSON:

```python
# backend/models/user.py — Lines 152–159

def get_skills_list(self) -> list[str]:
    return json.loads(self.skills) if self.skills else []

def set_skills_list(self, skills: list[str]) -> None:
    self.skills = json.dumps([s.lower().strip() for s in skills])
```

### Incremental Rating Update

The running average is encapsulated inside `FreelancerProfile.update_rating()`, hiding the formula from callers:

```python
# backend/models/user.py — Lines 161–175

def update_rating(self, new_score: int) -> None:
    current_avg = self.avg_rating or 0.0
    current_count = self.total_ratings or 0
    total = current_avg * current_count + new_score
    self.total_ratings = current_count + 1
    self.avg_rating = round(total / self.total_ratings, 2)
```

---

## 3. Inheritance

### ABC Hierarchy — `UserBase → ClientUser / FreelancerUser`

```python
# backend/models/user.py — Lines 38–61

class UserBase(ABC):
    """Abstract user. Subclasses must declare their role."""

    @abstractmethod
    def get_role(self) -> str: ...


class ClientUser(UserBase):
    def get_role(self) -> str:
        return UserRole.CLIENT.value    # "client"


class FreelancerUser(UserBase):
    def get_role(self) -> str:
        return UserRole.FREELANCER.value  # "freelancer"
```

### Scoring Engine — `MatchEngine → WeightedSkillMatchEngine`

```python
# backend/services/match_engine.py — Lines 158–200

class WeightedSkillMatchEngine(MatchEngine):
    """Gives bonus weight to rare/critical skills."""

    def __init__(self, bonus_skills: set[str] | None = None, **kwargs):
        super().__init__(**kwargs)       # ← calls parent constructor
        self.bonus_skills = {s.lower() for s in (bonus_skills or set())}

    def _compute_skill_overlap(self, freelancer_skills, required_skills) -> float:
        # Overrides parent method — bonus skills count 1.5×
        ...
```

### ORM Inheritance — `Base → User / Project / Bid / Rating / FreelancerProfile`

All SQLAlchemy models inherit from `Base` (the declarative base), giving them table mapping, session integration, and query capabilities:

```python
# backend/database.py
Base = declarative_base()

# backend/models/user.py
class User(Base):         # inherits table mapping from Base
    __tablename__ = "users"
```

### Exception Inheritance — `Exception → Custom Exceptions`

All five custom exceptions extend Python's built-in `Exception`:

```python
class BidOnExpiredProjectError(Exception): ...
class DuplicateBidError(Exception): ...
class InvalidBudgetError(Exception): ...
class InvalidStatusTransitionError(Exception): ...
class UnauthorizedActionError(Exception): ...
```

### Enum Inheritance — `str, enum.Enum`

```python
class ProjectStatus(str, enum.Enum):    # multiple inheritance
    OPEN = "open"
```

### Pydantic Inheritance — `BaseModel → Schema Classes`

```python
class UserRegister(BaseModel): ...
class UserOut(BaseModel): ...
class Token(BaseModel): ...
```

---

## 4. Abstraction (Abstract Base Classes)

`UserBase` uses Python's `abc.ABC` and `@abstractmethod` to define a contract that every user type must fulfil:

```python
# backend/models/user.py — Lines 38–47

from abc import ABC, abstractmethod

class UserBase(ABC):
    @abstractmethod
    def get_role(self) -> str:
        """Return the user's role identifier."""
        ...
```

- You **cannot instantiate** `UserBase()` directly — Python raises `TypeError`.
- `ClientUser` and `FreelancerUser` each provide a concrete `get_role()`.
- The service layer uses `User.get_user_type()` to get the appropriate subclass for polymorphic role checks.

---

## 5. Polymorphism

### Method Overriding (Runtime Polymorphism)

`WeightedSkillMatchEngine` overrides `_compute_skill_overlap()` from `MatchEngine`. The same `match_score()` call produces different results depending on which engine is used:

```python
# Parent — backend/services/match_engine.py L81–106
def _compute_skill_overlap(self, freelancer_skills, required_skills) -> float:
    overlap = required & offered
    return len(overlap) / len(required)      # equal weight for all skills

# Child — backend/services/match_engine.py L172–200
def _compute_skill_overlap(self, freelancer_skills, required_skills) -> float:
    weighted_score = sum(
        1.5 if skill in self.bonus_skills else 1.0
        for skill in overlap
    )
    return weighted_score / max_score         # bonus skills get 1.5× weight
```

### Factory Method (Parametric Polymorphism)

`User.get_user_type()` returns different ABC subclasses based on the stored role:

```python
# backend/models/user.py — Lines 102–109

def get_user_type(self) -> UserBase:
    if self.role == UserRole.CLIENT.value:
        return ClientUser()
    return FreelancerUser()
```

### Closure-Based Polymorphism

`require_role()` is a **factory function** that returns a different dependency function for each role:

```python
# backend/dependencies.py — Lines 66–83

def require_role(role: str):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role:
            raise HTTPException(status_code=403, ...)
        return current_user
    return role_checker
```

Usage: `Depends(require_role("client"))` vs `Depends(require_role("freelancer"))` produce two distinct checker functions.

---

## 6. Operator Overloading (Dunder Methods)

### `BidRanked` — Inverted Comparison for Max-Heap

Python's `heapq` is a **min-heap**. `BidRanked` inverts `__lt__` so that the highest score is treated as "smallest", making the heap a max-heap:

```python
# backend/models/bid.py — Lines 79–126

@dataclass(order=False)
class BidRanked:
    bid_id: int
    match_score: float

    def __lt__(self, other):   return self.match_score > other.match_score   # inverted!
    def __gt__(self, other):   return self.match_score < other.match_score   # inverted!
    def __eq__(self, other):   return self.match_score == other.match_score
    def __le__(self, other):   return self.match_score >= other.match_score
    def __ge__(self, other):   return self.match_score <= other.match_score
    def __hash__(self):        return hash(self.bid_id)
```

**Effect:**
- `sorted(bids)` → highest-score-first order
- `heapq.heappop()` → pops the highest-score bid

### `RankedBidQueue` — Container Protocol

```python
# backend/services/ranking.py — Lines 97–102

def __len__(self):     return len(self._index)     # supports len(queue)
def __bool__(self):    return len(self._index) > 0  # supports if queue:
```

### `__repr__` — Human-Readable Debugging

Every model implements `__repr__` for readable debug output:

```python
# backend/models/user.py L111
def __repr__(self): return f"<User id={self.id} username={self.username!r} role={self.role!r}>"

# backend/models/project.py L179
def __repr__(self): return f"<Project id={self.id} title={self.title!r} status={self.status!r}>"

# backend/models/bid.py L67
def __repr__(self): return f"<Bid id={self.id} project={self.project_id} ... score={self.match_score:.2f}>"
```

---

## 7. Composition & Aggregation

### Composition (strong ownership — child cannot exist without parent)

SQLAlchemy `cascade="all, delete-orphan"` means deleting a parent deletes its children:

```python
# backend/models/user.py — Lines 96–100
freelancer_profile = relationship("FreelancerProfile", ..., cascade="all, delete-orphan")
projects = relationship("Project", ..., cascade="all, delete-orphan")
bids = relationship("Bid", ..., cascade="all, delete-orphan")
```

- A `FreelancerProfile` cannot exist without its `User`.
- `Bid`s and `Project`s are destroyed when their owning `User` is deleted.

### Aggregation (weak ownership — child can exist independently)

`RankedBidQueue` holds `BidRanked` objects but doesn't own them — the same `BidRanked` could exist outside the queue:

```python
# backend/services/ranking.py
class RankedBidQueue:
    def __init__(self):
        self._heap: list[BidRanked] = []       # aggregation
        self._index: dict[int, BidRanked] = {}
```

### Composition in the Scoring Pipeline

`MatchEngine` is composed into the bid submission flow (not inherited):

```
Router (bids.py) → creates MatchEngine() → calls .match_score() → stores result in Bid
```

---

## 8. Enumerations

Python's `enum.Enum` is used for type-safe constants:

```python
# backend/models/enums.py

class ProjectStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class UserRole(str, enum.Enum):
    CLIENT = "client"
    FREELANCER = "freelancer"
```

**Why `str, enum.Enum`?** Multiple inheritance from `str` makes `.value` a string, so `ProjectStatus.OPEN.value == "open"` works directly in SQL comparisons and JSON serialization.

**Used in:** status machine guards (`project.py`), role checks (`dependencies.py`), ABC role mapping (`user.py`).

---

## 9. Dataclasses

`BidRanked` uses `@dataclass` to auto-generate `__init__` and `__repr__` from field declarations:

```python
# backend/models/bid.py — Lines 79–97

@dataclass(order=False)
class BidRanked:
    bid_id: int
    match_score: float
    freelancer_id: int = 0
    freelancer_name: str = ""
    amount: float = 0.0
    proposal: str = ""
```

`order=False` disables auto-generated comparisons, so the manually inverted `__lt__`/`__gt__` take precedence.

---

## 10. Pydantic Models (Data Validation)

Pydantic `BaseModel` subclasses validate request/response data at the API boundary:

```python
# backend/schemas/user.py

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str    = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    role: str     = Field(..., pattern="^(client|freelancer)$")  # regex validation
```

| Schema | Purpose |
|--------|---------|
| `UserRegister` | Registration request — validates username, email, password length, and role pattern |
| `UserLogin` | Login request |
| `Token` | JWT response with role and user_id |
| `UserOut` | Public user info (`from_attributes=True` for ORM integration) |
| `FreelancerProfileOut` | Profile response with skills as `list[str]` |
| `FreelancerProfileUpdate` | PATCH body with `Optional` fields and `gt=0` validation |

**ORM Integration:**
```python
class UserOut(BaseModel):
    model_config = {"from_attributes": True}  # auto-reads SQLAlchemy model attributes
```

---

## 11. Custom Exception Hierarchy

Five domain-specific exceptions extend `Exception`, each encapsulating the data needed for a clear error message:

```python
# backend/exceptions.py

class BidOnExpiredProjectError(Exception):
    def __init__(self, project_id: int, reason: str = "..."):
        self.project_id = project_id          # carries context
        self.message = f"Cannot bid on project {project_id}: {reason}"
        super().__init__(self.message)         # chains to Exception.__init__

class DuplicateBidError(Exception):       ...
class InvalidBudgetError(Exception):      ...
class InvalidStatusTransitionError(Exception): ...
class UnauthorizedActionError(Exception): ...
```

| Exception | Trigger | HTTP Status |
|-----------|---------|:-----------:|
| `BidOnExpiredProjectError` | Bid on closed/expired project | 400 |
| `DuplicateBidError` | Same freelancer bids twice | 409 |
| `InvalidBudgetError` | `budget_min ≥ budget_max` or negative | 400 |
| `InvalidStatusTransitionError` | Illegal state change | 400 |
| `UnauthorizedActionError` | Wrong role for action | 403 |

Exceptions are **raised in the model/service layer** and **caught in the router layer** to produce HTTP responses — a clean separation of concerns.

---

## 12. Design Patterns

### Factory Method — `User.get_user_type()`

Returns a different ABC subclass based on stored role:

```python
def get_user_type(self) -> UserBase:
    if self.role == UserRole.CLIENT.value:
        return ClientUser()
    return FreelancerUser()
```

### Factory (Class Method) — `RankedBidQueue.from_bids()`

Builds a fully heapified queue in O(n) instead of n × O(log n) pushes:

```python
@classmethod
def from_bids(cls, bid_ranked_list: list[BidRanked]) -> RankedBidQueue:
    queue = cls()
    queue._heap = list(bid_ranked_list)
    heapq.heapify(queue._heap)
    queue._index = {br.bid_id: br for br in bid_ranked_list}
    return queue
```

### Strategy Pattern — `MatchEngine` Scoring Components

Each scoring component (`_compute_skill_overlap`, `_compute_price_fit`, `_normalize_rating`) is a separate overridable method. Swap strategies by subclassing:

```python
engine = MatchEngine()                          # default strategy
engine = WeightedSkillMatchEngine(bonus_skills={"kubernetes"})  # custom strategy
```

Both are called via the same `engine.match_score(...)` interface.

### Singleton — `_fernet` Cipher Instance

The encryption module creates one `Fernet` instance at import time:

```python
# backend/services/encryption.py — Line 46
_fernet = Fernet(_derive_fernet_key(ENCRYPTION_KEY))    # created once, reused
```

### Dependency Injection — FastAPI `Depends()`

Services are injected into route handlers via FastAPI's DI framework:

```python
# backend/dependencies.py
def get_current_user(
    token: str = Depends(oauth2_scheme),    # injected
    db: Session = Depends(get_db),          # injected
) -> User: ...
```

### Generator-Based Context Manager — `get_db()`

Database sessions are managed with a generator that ensures cleanup:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db        # session is available to the route handler
    finally:
        db.close()      # always cleaned up, even on error
```

---

## 13. Decorators

| Decorator | Location | Purpose |
|-----------|----------|---------|
| `@abstractmethod` | `UserBase.get_role()` | Enforces implementation in subclasses |
| `@dataclass(order=False)` | `BidRanked` | Auto-generates `__init__`, `__repr__` from fields |
| `@staticmethod` | `Project.validate_budget()` | Budget validation without instance access |
| `@classmethod` | `RankedBidQueue.from_bids()` | Alternative constructor receiving `cls` |
| `@router.get/post/put` | All routers | Maps HTTP methods to handler functions |
| `Depends()` | `dependencies.py` | FastAPI dependency injection |

---

## 14. Static & Class Methods

### `@staticmethod` — `Project.validate_budget()`

Doesn't need `self` or `cls`; validates budget range before creating a `Project`:

```python
# backend/models/project.py — Lines 168–177

@staticmethod
def validate_budget(budget_min: float, budget_max: float) -> None:
    if budget_min < 0 or budget_max <= 0 or budget_min >= budget_max:
        raise InvalidBudgetError(budget_min, budget_max)
```

### `@classmethod` — `RankedBidQueue.from_bids()`

An alternative constructor that creates a pre-populated queue:

```python
# backend/services/ranking.py — Lines 112–123

@classmethod
def from_bids(cls, bid_ranked_list: list[BidRanked]) -> RankedBidQueue:
    queue = cls()                           # cls = RankedBidQueue (or subclass)
    queue._heap = list(bid_ranked_list)
    heapq.heapify(queue._heap)              # O(n) construction
    queue._index = {br.bid_id: br for br in bid_ranked_list}
    return queue
```

---

## 15. Data Structures as Classes

### `RankedBidQueue` — Heap-Backed Priority Queue

Wraps Python's `heapq` module with lazy deletion and an O(1) lookup index:

| Operation | Complexity | Implementation |
|-----------|:----------:|----------------|
| Push | O(log n) | `heapq.heappush` |
| Peek / Pop | O(log n) | Skips stale entries |
| Full ranking | O(n log n) | `sorted()` on active entries |
| Remove | O(1) | Lazy deletion via `_index` dict |
| Batch build | O(n) | `heapq.heapify` in `from_bids()` |

```python
class RankedBidQueue:
    def __init__(self):
        self._heap: list[BidRanked] = []        # min-heap (inverted comparators)
        self._index: dict[int, BidRanked] = {}  # O(1) lookup + stale detection
```

---

## 16. Class Diagram

```
┌─────────────────────┐        ┌──────────────────────┐
│     «abstract»      │        │     «enum»           │
│     UserBase (ABC)   │        │  ProjectStatus       │
│─────────────────────│        │──────────────────────│
│ + get_role(): str    │        │  OPEN                │
└────────┬────────────┘        │  IN_PROGRESS         │
         │ inherits            │  COMPLETED           │
    ┌────┴─────┐               └──────────────────────┘
    │          │
┌───┴──┐  ┌───┴──────────┐    ┌──────────────────────┐
│Client│  │Freelancer    │    │     «enum»           │
│User  │  │User          │    │  UserRole            │
└──────┘  └──────────────┘    │──────────────────────│
                               │  CLIENT              │
┌─────────────────────────┐    │  FREELANCER           │
│  User (SQLAlchemy ORM)  │    └──────────────────────┘
│─────────────────────────│
│ id, username, email     │    ┌──────────────────────┐
│ password_hash, role     │───▶│ FreelancerProfile    │
│ created_at              │ 1:1│ skills, hourly_rate  │
│ + get_user_type()       │    │ avg_rating           │
│ + __repr__()            │    │ + get/set_skills()   │
└──────┬──────────────────┘    │ + update_rating()    │
       │ 1:N                   └──────────────────────┘
       ▼
┌─────────────────────────┐    ┌──────────────────────┐
│  Project                │    │  «dataclass»         │
│─────────────────────────│    │  BidRanked           │
│ title, budget, deadline │    │──────────────────────│
│ status, required_skills │    │ bid_id, match_score  │
│ + accept_bid()          │    │ + __lt__() (inverted)│
│ + mark_completed_by()   │    │ + __gt__() (inverted)│
│ + ensure_biddable()     │    │ + __hash__()         │
│ + validate_budget()  «S»│    └──────────────────────┘
└──────┬──────────────────┘              ▲ wraps
       │ 1:N                             │
       ▼                       ┌─────────┴────────────┐
┌─────────────────────────┐    │ RankedBidQueue       │
│  Bid (ORM)              │    │──────────────────────│
│─────────────────────────│    │ _heap, _index        │
│ amount, match_score     │    │ + push(), pop()      │
│ proposal, created_at    │    │ + ranked_list()      │
└─────────────────────────┘    │ + from_bids()     «C»│
                               │ + __len__()          │
┌─────────────────────────┐    └──────────────────────┘
│  MatchEngine            │
│─────────────────────────│    ┌──────────────────────┐
│ skill/price/rating wt   │    │ «exceptions»         │
│ + match_score()         │    │──────────────────────│
│ + _compute_skill_*()    │    │ BidOnExpiredProject  │
│ + _compute_price_fit()  │    │ DuplicateBidError    │
│ + _normalize_rating()   │    │ InvalidBudgetError   │
└──────┬──────────────────┘    │ InvalidStatusTrans.  │
       │ inherits              │ UnauthorizedAction   │
       ▼                       └──────────────────────┘
┌─────────────────────────┐
│ WeightedSkillMatchEngine│    «S» = @staticmethod
│─────────────────────────│    «C» = @classmethod
│ bonus_skills: set       │
│ + _compute_skill_*()    │
└─────────────────────────┘
```

---

## Summary

| OOP Concept | Where in BidForge |
|-------------|-------------------|
| Classes & Objects | All model, service, and schema files |
| Encapsulation | `Project` status machine, `FreelancerProfile` skill/rating methods |
| Inheritance | `UserBase` → `ClientUser`/`FreelancerUser`, `MatchEngine` → `WeightedSkillMatchEngine`, ORM `Base`, Pydantic `BaseModel`, `Exception` |
| Abstraction (ABC) | `UserBase` with `@abstractmethod get_role()` |
| Polymorphism | Method overriding (`_compute_skill_overlap`), factory method (`get_user_type`), closure factory (`require_role`) |
| Operator Overloading | `BidRanked.__lt__/__gt__` (inverted), `RankedBidQueue.__len__/__bool__`, `__repr__` on all models |
| Composition | `User` → `FreelancerProfile`, `User` → `Project`, `User` → `Bid` (cascade delete) |
| Aggregation | `RankedBidQueue` → `BidRanked` objects |
| Enumerations | `ProjectStatus`, `UserRole` (multi-inheriting `str, enum.Enum`) |
| Dataclass | `BidRanked` with `@dataclass(order=False)` |
| Pydantic Models | `UserRegister`, `UserOut`, `Token`, `FreelancerProfileOut/Update`, bid/project schemas |
| Custom Exceptions | 5 domain exceptions with contextual attributes |
| Design Patterns | Factory Method, Strategy, Singleton, Dependency Injection, Context Manager |
| Decorators | `@abstractmethod`, `@dataclass`, `@staticmethod`, `@classmethod`, `@router.*` |
| Static Methods | `Project.validate_budget()` |
| Class Methods | `RankedBidQueue.from_bids()` |

