<div align="center">

# ⚖️ BidForge

### Freelance Marketplace Bidding Engine

**Bids ranked on fit, not just price.** A full-stack marketplace where a scoring engine weighs skill match, price fit, and past ratings.

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-26.7-4479A1?logo=mysql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-106-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Overview](#-overview) · [Quick Start](#-quick-start) · [How Ranking Works](#-how-ranking-works) · [API](#-api-reference) · [DBMS Topics](#-dbms-syllabus-coverage) · [Testing](#-testing)

</div>

---

## 📖 Overview

Clients post projects with a budget and deadline. Freelancers submit bids. Instead of "lowest bid wins", a **ranking engine scores every bid on overall fit**, combining skill match, price fit, and the freelancer's past rating, so clients see the best candidates first.

## ✨ Key Features

- 🎯 **Fit-based bid ranking:** every bid is auto-scored on submission and returned in ranked order
- 🔐 **Role-based accounts:** separate client and freelancer dashboards with JWT authentication
- 🔄 **Project lifecycle:** `Open → InProgress → Completed`, enforced by a validated status machine
- 🤝 **Dual-completion:** a project completes only after both client and freelancer confirm
- ⭐ **Ratings:** clients rate freelancers (1–5 stars); averages update incrementally
- 🧩 **Extensible scoring:** swap or override scoring components via a polymorphic `MatchEngine`
- 🗄️ **MySQL backend:** triggers, stored procedures, CHECK constraints, indexes, audit log
- ✅ **Tested:** 106 tests covering models, scoring, API lifecycle, and DBMS features

## 🧮 How Ranking Works

```
match_score = 0.45 × skill_overlap  +  0.30 × price_fit  +  0.25 × rating
```

| Component | Weight | How it's computed |
|-----------|:------:|-------------------|
| Skill overlap | 0.45 | Python `set` intersection of required vs. offered skills, O(min(m, n)) |
| Price fit | 0.30 | Linear decay for bids outside the project's budget range |
| Rating | 0.25 | Freelancer's average rating; new freelancers get a 0.1 baseline so they aren't zeroed out |

Each component (`_compute_skill_overlap`, `_compute_price_fit`, `_normalize_rating`) is overridable. `WeightedSkillMatchEngine` demonstrates this by giving **1.5× weight to bonus skills**.

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.14, FastAPI, SQLAlchemy |
| Database | **MySQL 26.7** (InnoDB) via PyMySQL driver |
| Auth | bcrypt + JWT (python-jose) |
| Encryption | AES-256 via Fernet (cryptography) |
| Frontend | Vanilla HTML / CSS / JS |
| Testing | pytest + FastAPI TestClient |

### How MySQL Connects to Python

```
Python code  →  SQLAlchemy ORM  →  PyMySQL driver  →  MySQL server (port 3306)
───────────     ──────────────     ──────────────     ─────────────────────────
db.query(User)  translates to SQL  sends over TCP     executes & returns rows
```

The connection string in `backend/config.py` encodes all details:
```
mysql+pymysql://bidforge_user:bidforge_pass@localhost:3306/bidforge
^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^ ^^^^^^^^^^^^  ^^^^^^^^^  ^^^^  ^^^^^^^
dialect+driver  username       password      host       port  database
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- MySQL 8.0+ (installed via `brew install mysql` on macOS)

### Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/dhyeyjoshi07/Freelance-Marketplace-Bidding-Engine.git
cd Freelance-Marketplace-Bidding-Engine

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start MySQL and create the database
brew services start mysql
mysql -u root -e "
CREATE DATABASE IF NOT EXISTS bidforge CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS bidforge_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'bidforge_user'@'localhost' IDENTIFIED BY 'bidforge_pass';
GRANT ALL PRIVILEGES ON bidforge.* TO 'bidforge_user'@'localhost';
GRANT ALL PRIVILEGES ON bidforge_test.* TO 'bidforge_user'@'localhost';
FLUSH PRIVILEGES;
"

# 5. (Optional) Seed with demo data
python3 seed.py

# 6. Run the server
python3 run.py
```

Open **http://localhost:8000** in your browser.

### 🔑 Demo Accounts (after seeding)

| Role | Username | Password |
|------|----------|----------|
| Client | `sarah_chen` | `password123` |
| Client | `alex_rivera` | `password123` |
| Freelancer | `dev_alice` | `password123` |
| Freelancer | `dev_charlie` | `password123` |
| Freelancer | `dev_bob` | `password123` |

## 🧭 Usage Flow

1. **Register / log in** as a client or freelancer.
2. **Client** creates a project with required skills, budget range, and deadline.
3. **Freelancers** browse open projects and submit bids, which are scored automatically.
4. **Client** reviews the ranked bid list and accepts one, moving the project to `InProgress`.
5. **Both parties** mark the project complete. It becomes `Completed` once both confirm.
6. **Client** rates the freelancer (1–5 stars).

## 🔌 API Reference

<details>
<summary><b>🔐 Auth</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register (client or freelancer) |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Current user profile |

</details>

<details>
<summary><b>📁 Projects</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects` | Create a project (client only) |
| GET | `/api/projects` | List open projects (filterable) |
| GET | `/api/projects/my` | Current user's projects |
| GET | `/api/projects/{id}` | Project detail |
| POST | `/api/projects/{id}/accept-bid` | Accept a bid, moving the project to InProgress |
| POST | `/api/projects/{id}/complete` | Mark complete (dual-confirm) |
| POST | `/api/projects/{id}/rate` | Rate freelancer (1–5 stars) |

</details>

<details>
<summary><b>💼 Bids</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/{id}/bids` | Submit bid (auto-scored) |
| GET | `/api/projects/{id}/bids` | Ranked bid list |
| GET | `/api/freelancers/me/bids` | Freelancer's own bids |

</details>

<details>
<summary><b>👩‍💻 Freelancers</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/freelancers/me` | View profile |
| PUT | `/api/freelancers/me` | Update skills / rate |

</details>

<details>
<summary><b>🛡️ Admin / DBMS</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/explain?query=...` | Run EXPLAIN on a SQL query |
| GET | `/api/admin/table-stats/{table}` | Optimizer stats for a table |
| GET | `/api/admin/query-optimization-demo` | Index vs. no-index comparison |
| GET | `/api/admin/acid` | ACID property explanations |
| POST | `/api/admin/encrypt?plaintext=...` | AES-256 encrypt/decrypt demo |
| GET | `/api/admin/stored-procedure/ranked-bids/{id}` | Call sp_get_ranked_bids |
| GET | `/api/admin/stored-procedure/freelancer-stats/{id}` | Call sp_freelancer_stats |
| GET | `/api/admin/audit-log` | View audit trail |
| GET | `/api/admin/triggers` | List all MySQL triggers |
| GET | `/api/admin/stored-procedures` | List stored procedures & functions |
| GET | `/api/admin/constraints?table_name=...` | List CHECK/FK/UNIQUE constraints |

</details>

## 📚 DBMS Syllabus Coverage

This project covers all 9 units of a B.Tech DBMS syllabus — introductory concepts, ER model, relational model, normalization, query processing, transactions, SQL (DDL/DML/DCL), PL/SQL equivalents (MySQL triggers, stored procedures, cursors), and advanced topics (AES-256 encryption, audit trails, RBAC) — using BidForge's own entities instead of textbook examples. MySQL features like `CHECK` constraints, `GRANT/REVOKE`, transaction isolation levels, and `SELECT ... FOR UPDATE` locking are all demonstrated in working code.

📖 **Full documentation:** [`docs/dbms.md`](docs/dbms.md) &nbsp;|&nbsp; **SQL scripts:** [`scripts/sql/`](scripts/sql/) &nbsp;|&nbsp; **Admin API:** `/api/admin/*` endpoints

## 🏗️ Architecture

<details>
<summary><b>📂 Project structure</b></summary>

```
freelance-marketplace/
├── backend/                     # FastAPI + SQLAlchemy
│   ├── app.py                   # FastAPI factory, router registration, static mount
│   ├── config.py                # MySQL URL, JWT secret, match engine weights, encryption key
│   ├── database.py              # SQLAlchemy engine, triggers, stored procedures, indexes
│   ├── dependencies.py          # get_db, get_current_user, require_role()
│   ├── exceptions.py            # Custom exceptions (4 types)
│   ├── models/
│   │   ├── enums.py             # ProjectStatus, UserRole
│   │   ├── user.py              # User ABC hierarchy + FreelancerProfile + CHECK constraints
│   │   ├── project.py           # Project with encapsulated status machine + CHECK constraints
│   │   └── bid.py               # Bid ORM + BidRanked dataclass + Rating + CHECK constraints
│   ├── schemas/                 # Pydantic request/response models
│   ├── routers/
│   │   ├── auth.py              # Register, login (JWT), me
│   │   ├── projects.py          # CRUD + accept bid + dual-completion
│   │   ├── bids.py              # Submit bid + ranked list
│   │   ├── freelancers.py       # Profile CRUD + ratings
│   │   └── admin.py             # DBMS educational endpoints (EXPLAIN, ACID, triggers, etc.)
│   └── services/
│       ├── auth_service.py      # bcrypt hashing + JWT tokens
│       ├── match_engine.py      # MatchEngine + WeightedSkillMatchEngine
│       ├── ranking.py           # RankedBidQueue (heapq-based)
│       ├── encryption.py        # AES-256 column-level encryption
│       ├── query_analyzer.py    # EXPLAIN, table stats, index analysis
│       └── transaction_manager.py # ACID demo, savepoints, isolation levels
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
├── docs/
│   └── dbms.md                  # DBMS syllabus coverage (all 9 units)
├── scripts/sql/                 # Raw SQL reference scripts
│   ├── ddl.sql                  # CREATE TABLE, ALTER, constraints
│   ├── dml.sql                  # SELECT, INSERT, UPDATE, DELETE, JOINs, subqueries
│   ├── dcl.sql                  # GRANT, REVOKE, roles
│   ├── triggers.sql             # BEFORE/AFTER triggers with SIGNAL
│   ├── procedures.sql           # Stored procedures, functions, cursors
│   └── transactions.sql         # BEGIN, COMMIT, ROLLBACK, SAVEPOINT, isolation levels
├── tests/
│   ├── test_models.py           # 40 unit tests (OOP classes)
│   ├── test_match_engine.py     # 28 unit tests (scoring algorithm)
│   ├── test_api.py              # 23 integration tests (full lifecycle)
│   └── test_dbms.py             # 15 DBMS feature tests (constraints, transactions, encryption)
├── seed.py                      # Demo data seeder
├── run.py                       # uvicorn launcher
├── report.tex                   # LaTeX project report
├── requirements.txt
└── LICENSE                      # MIT License
```

</details>

<details>
<summary><b>🗄️ Database schema</b> (6 tables, MySQL InnoDB)</summary>

```
users (id, username, email, password_hash, role, created_at)
  │    CHECK: role IN ('client', 'freelancer')
  │
  ├──→ freelancer_profiles (user_id FK, skills JSON, hourly_rate, avg_rating, total_ratings)
  │    CHECK: hourly_rate >= 0, 0 <= avg_rating <= 5
  │
  ├──→ projects (client_id FK, title, description, required_skills JSON,
  │              budget_min, budget_max, deadline, status, accepted_bid_id FK,
  │              client_completed, freelancer_completed, created_at)
  │    CHECK: budget_min >= 0, budget_max > 0, status IN ('open','in_progress','completed')
  │
  ├──→ bids (project_id FK, freelancer_id FK, amount, proposal, match_score, created_at)
  │    UNIQUE(project_id, freelancer_id), CHECK: amount > 0, 0 <= match_score <= 1
  │
  ├──→ ratings (project_id FK, freelancer_id FK, client_id FK, score, review, created_at)
  │    UNIQUE(project_id), CHECK: 1 <= score <= 5
  │
  └──→ audit_log (table_name, record_id, action, old_value, new_value, changed_at)
       Populated by trg_after_update_project_status trigger
```

**Triggers:** `trg_before_insert_bid` (validation), `trg_before_insert_project` (budget validation), `trg_after_insert_rating` (auto-update avg), `trg_after_update_project_status` (audit log)

**Indexes:** `idx_bids_project_score` (covering), `idx_bids_freelancer`, `idx_projects_status`, `idx_projects_client`, `idx_ratings_freelancer`

**Stored Procedures:** `sp_get_ranked_bids()`, `sp_freelancer_stats()`, `sp_bid_summary_cursor()`

**Stored Functions:** `fn_price_fit()`

</details>

## 🧠 OOP Design & Data Structures

| Concept | Where | Summary |
|---------|-------|---------| 
| **Abstraction & Inheritance** | `UserBase` (ABC) | `ClientUser` and `FreelancerUser` implement abstract `get_role()`; used in the service layer for polymorphic role checks |
| **Polymorphism** | `MatchEngine` | Overridable scoring components; `WeightedSkillMatchEngine` overrides skill overlap |
| **Operator overloading** | `BidRanked.__lt__` / `__gt__` | Inverted comparison so `sorted()` and `heapq` yield highest score first |
| **Exception handling** | `exceptions.py` | 4 custom exceptions mapped to HTTP responses (see below) |
| **Encapsulation** | `Project` status machine | Status changes only via validated methods |
| **Containers** | `RankedBidQueue` | `heapq`-backed priority queue with lazy deletion |

<details>
<summary><b>🔀 Operator overloading: the inversion trick</b></summary>

`BidRanked` is a `@dataclass` with **inverted** comparison operators:

```python
def __lt__(self, other):
    return self.match_score > other.match_score  # higher = "less than"
```

Because of this:
- `sorted(bids)` returns highest-score-first
- `heapq` (a min-heap) pops the highest-score bid first

</details>

<details>
<summary><b>🚨 Custom exceptions</b></summary>

| Exception | When raised | HTTP status |
|-----------|-------------|:-----------:|
| `BidOnExpiredProjectError` | Bidding on a closed or past-deadline project | 400 |
| `DuplicateBidError` | Same freelancer bids twice on one project | 409 |
| `InvalidBudgetError` | `budget_min ≥ budget_max` or negative values | 400 |
| `InvalidStatusTransitionError` | Illegal state change (e.g., Open → Completed) | 400 |

Each is raised in the model/service layer and caught in the router layer to produce the correct HTTP response.

</details>

<details>
<summary><b>🔒 Project status machine</b></summary>

```
Open ──accept_bid()──▶ InProgress ──mark_completed_by()──▶ Completed
```

Status is **never mutated directly**. All transitions go through validated methods that check the current state and raise `InvalidStatusTransitionError` on illegal transitions. Both client and freelancer must call `mark_completed_by()` before the project becomes `Completed`.

</details>

<details>
<summary><b>⚡ RankedBidQueue complexity</b></summary>

| Operation | Complexity | Notes |
|-----------|:----------:|-------|
| Push | O(log n) | `heapq.heappush` |
| Peek / Pop | O(log n) | Skips stale entries via lazy deletion |
| Full ranking | O(n log n) | `sorted()` on active entries |
| Remove | O(1) | Lazy deletion via `_index` dict |
| Batch construction | O(n) | `heapq.heapify` in `from_bids()` factory |

The `_index` dict provides O(1) bid lookup by ID and enables lazy deletion without restructuring the heap.

</details>

## 🧪 Testing

106 tests: 40 model unit tests, 28 match-engine unit tests, 23 API integration tests, and 15 DBMS feature tests.

```bash
# Run all tests
python3 -m pytest tests/ -v

# Unit tests only
python3 -m pytest tests/test_models.py tests/test_match_engine.py -v

# Integration tests only
python3 -m pytest tests/test_api.py -v

# DBMS feature tests only
python3 -m pytest tests/test_dbms.py -v
```

## 🎨 Frontend Design

- **Palette:** deep forest black (`#06120e`) base, emerald gradients (`#10b981` → `#047857`), gold accent (`#fbbf24`)
- **Typography:** Inter (body) and Outfit (headings) from Google Fonts
- **Components:** glassmorphism cards, animated score-breakdown bars (emerald = skill, gold = rating, teal = price), status badges, skill chips with match highlighting, interactive star ratings
- **Pages:** Landing (auth), Client Dashboard, Freelancer Dashboard

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.