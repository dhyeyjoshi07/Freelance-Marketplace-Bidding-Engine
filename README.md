# BidForge — Freelance Marketplace Bidding Engine

A full-stack platform where clients post projects with a budget/deadline, freelancers submit bids, and a **ranking engine scores each bid on fit** (skill match + past rating + price) — not just lowest-bid-wins.

## Architecture

```
freelance-marketplace/
├── backend/                     # FastAPI + SQLAlchemy
│   ├── app.py                   # FastAPI factory, router registration, static mount
│   ├── config.py                # DB URL, JWT secret, match engine weights
│   ├── database.py              # SQLAlchemy engine, session, Base
│   ├── dependencies.py          # get_db, get_current_user, require_role()
│   ├── exceptions.py            # Custom exceptions (4 types)
│   ├── models/
│   │   ├── enums.py             # ProjectStatus, UserRole
│   │   ├── user.py              # User ABC hierarchy + FreelancerProfile
│   │   ├── project.py           # Project with encapsulated status machine
│   │   └── bid.py               # Bid ORM + BidRanked dataclass + Rating
│   ├── schemas/                 # Pydantic request/response models
│   ├── routers/
│   │   ├── auth.py              # Register, login (JWT), me
│   │   ├── projects.py          # CRUD + accept bid + dual-completion
│   │   ├── bids.py              # Submit bid + ranked list
│   │   └── freelancers.py       # Profile CRUD + ratings
│   └── services/
│       ├── auth_service.py      # bcrypt hashing + JWT tokens
│       ├── match_engine.py      # MatchEngine + WeightedSkillMatchEngine
│       └── ranking.py           # RankedBidQueue (heapq-based)
├── frontend/                    # Vanilla HTML/CSS/JS
│   ├── index.html               # Login / register page
│   ├── client.html              # Client dashboard
│   ├── freelancer.html          # Freelancer dashboard
│   ├── css/styles.css           # Design system
│   └── js/
│       ├── api.js               # Centralized API client
│       ├── auth.js              # Token management + UI helpers
│       ├── client.js            # Client dashboard logic
│       └── freelancer.js        # Freelancer dashboard logic
├── tests/
│   ├── test_models.py           # 40 unit tests (OOP classes)
│   ├── test_match_engine.py     # 28 unit tests (scoring algorithm)
│   └── test_api.py              # 23 integration tests (full lifecycle)
├── seed.py                      # Demo data seeder
├── run.py                       # uvicorn launcher
└── requirements.txt
```

## Quick Start

```bash
# 1. Clone and enter the project
cd freelance-marketplace

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Seed with demo data
python3 seed.py

# 5. Run the server
python3 run.py
```

Open **http://localhost:8000** in your browser.

### Demo Accounts (after seeding)

| Role | Username | Password |
|------|----------|----------|
| Client | `sarah_chen` | `password123` |
| Client | `alex_rivera` | `password123` |
| Freelancer | `dev_alice` | `password123` |
| Freelancer | `dev_charlie` | `password123` |
| Freelancer | `dev_bob` | `password123` |

## OOP Design & Data Structures

### 1. Abstraction & Inheritance — `UserBase` ABC

```
UserBase (ABC)          ← abstract get_role()
├── ClientUser          → get_role() returns "client"
└── FreelancerUser      → get_role() returns "freelancer"
```

`User` (the SQLAlchemy model) stores all users in a single table. The ABC hierarchy is used in the service layer via `user.get_user_type()` for polymorphic role checks.

### 2. Polymorphism — `MatchEngine`

The scoring formula:

```
match_score = 0.45 × skill_overlap  +  0.30 × price_fit  +  0.25 × rating
```

Each component method (`_compute_skill_overlap`, `_compute_price_fit`, `_normalize_rating`) is overridable. `WeightedSkillMatchEngine` demonstrates this by overriding `_compute_skill_overlap()` to give 1.5× weight to bonus skills.

- **Skill overlap** uses Python `set` intersection — O(min(m, n))
- **Price fit** uses linear decay outside the budget range
- **Rating** gives new freelancers a 0.1 baseline so they aren't zeroed out

### 3. Operator Overloading — `BidRanked.__lt__` / `__gt__`

`BidRanked` is a `@dataclass` with **inverted** comparison operators:

```python
def __lt__(self, other):
    return self.match_score > other.match_score  # higher = "less than"
```

This inversion trick means:
- `sorted(bids)` returns highest-score-first
- `heapq` (a min-heap) pops the highest-score bid first

### 4. Exception Handling — 4 Custom Exceptions

| Exception | When Raised | HTTP Status |
|-----------|-------------|-------------|
| `BidOnExpiredProjectError` | Bidding on a closed/past-deadline project | 400 |
| `DuplicateBidError` | Same freelancer bids twice on one project | 409 |
| `InvalidBudgetError` | budget_min ≥ budget_max or negative values | 400 |
| `InvalidStatusTransitionError` | Illegal state change (e.g., Open → Completed) | 400 |

Each is raised in the model/service layer and caught in the router layer to produce the correct HTTP response.

### 5. Encapsulation — Project Status Machine

```
Open ──accept_bid()──▶ InProgress ──mark_completed_by()──▶ Completed
```

Status is **never mutated directly**. All transitions go through validated methods that check the current state and raise `InvalidStatusTransitionError` on illegal transitions.

**Dual-completion**: both client and freelancer must call `mark_completed_by()`. The project transitions to `Completed` only when both have confirmed.

### 6. Containers — `heapq` + `RankedBidQueue`

`RankedBidQueue` wraps Python's `heapq` module:
- **Push**: O(log n) via `heapq.heappush`
- **Peek/Pop**: O(log n), skips stale entries via lazy deletion
- **Full ranking**: O(n log n) via `sorted()` on active entries
- **Remove**: O(1) lazy deletion via `_index` dict
- **Batch construction**: O(n) via `heapq.heapify` in `from_bids()` factory

The `_index` dict provides O(1) bid lookup by ID and enables efficient lazy deletion without heap restructuring.

## Database Schema

5 tables in SQLite via SQLAlchemy:

```
users (id, username, email, password_hash, role, created_at)
  │
  ├──→ freelancer_profiles (user_id FK, skills JSON, hourly_rate, avg_rating, total_ratings)
  ├──→ projects (client_id FK, title, description, required_skills JSON,
  │              budget_min, budget_max, deadline, status, accepted_bid_id FK,
  │              client_completed, freelancer_completed, created_at)
  ├──→ bids (project_id FK, freelancer_id FK, amount, proposal, match_score, created_at)
  │         UNIQUE(project_id, freelancer_id)
  └──→ ratings (project_id FK, freelancer_id FK, client_id FK, score, review, created_at)
                UNIQUE(project_id)
```

Key design choices:
- **Skills as JSON**: stored as JSON arrays for flexible matching via `set` intersection
- **Denormalized rating**: `avg_rating` is incrementally updated on each new rating (avoids expensive aggregation queries)
- **Dual-completion flags**: `client_completed` / `freelancer_completed` integers (0/1) on the project

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register (client or freelancer) |
| POST | `/api/auth/login` | Login → returns JWT |
| GET | `/api/auth/me` | Current user profile |

### Projects
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects` | Create a project (client only) |
| GET | `/api/projects` | List open projects (filterable) |
| GET | `/api/projects/my` | Current user's projects |
| GET | `/api/projects/{id}` | Project detail |
| POST | `/api/projects/{id}/accept-bid` | Accept a bid → InProgress |
| POST | `/api/projects/{id}/complete` | Mark complete (dual-confirm) |
| POST | `/api/projects/{id}/rate` | Rate freelancer (1–5 stars) |

### Bids
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/{id}/bids` | Submit bid (auto-scored) |
| GET | `/api/projects/{id}/bids` | Ranked bid list |
| GET | `/api/freelancers/me/bids` | Freelancer's own bids |

### Freelancers
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/freelancers/me` | View profile |
| PUT | `/api/freelancers/me` | Update skills / rate |

## Testing

```bash
# Run all 91 tests
python3 -m pytest tests/ -v

# Unit tests only
python3 -m pytest tests/test_models.py tests/test_match_engine.py -v

# Integration tests only
python3 -m pytest tests/test_api.py -v
```

## Frontend Design

- **Color palette**: Deep forest black (#06120e) base, emerald gradients (#10b981 → #047857), gold accent (#fbbf24)
- **Typography**: Inter (body) + Outfit (headings) from Google Fonts
- **Components**: Glassmorphism cards, animated score breakdown bars (emerald=skill, gold=rating, teal=price), status badges, skill chips with match highlighting, interactive star ratings
- **Three pages**: Landing (auth), Client Dashboard, Freelancer Dashboard

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.14, FastAPI, SQLAlchemy |
| Database | SQLite |
| Auth | bcrypt + JWT (python-jose) |
| Frontend | Vanilla HTML/CSS/JS |
| Testing | pytest + FastAPI TestClient |
