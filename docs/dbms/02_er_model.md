# Unit 2: Entity-Relationship Model — BidForge ER Design

## 2.1 ER Diagram

```
                          ┌─────────────────┐
                          │     USER        │
                          │─────────────────│
                          │ PK id           │
                          │    username     │
                          │    email        │
                          │    password_hash│
                          │    role (d)     │ ◄── discriminator
                          │    created_at   │
                          └────────┬────────┘
                     ┌─────────────┼─────────────┐
                     │             │              │
                     │    (ISA / Generalization)  │
                     │             │              │
                ┌────▼────┐  ┌────▼─────┐        │
                │ CLIENT  │  │FREELANCER│        │
                │         │  │          │        │
                └────┬────┘  └────┬─────┘        │
                     │            │               │
            posts    │            │  has (1:1)    │
            (1:N)    │            │               │
                     │       ┌────▼──────────┐    │
                     │       │FREELANCER_    │    │
                     │       │  PROFILE      │    │
                     │       │───────────────│    │
                     │       │ PK id         │    │
                     │       │ FK user_id    │    │
                     │       │    skills[]   │    │
                     │       │    hourly_rate│    │
                     │       │    avg_rating │    │
                     │       │    total_ratings│   │
                     │       └───────────────┘    │
                     │                            │
                ┌────▼──────────┐                 │
                │   PROJECT     │                 │
                │───────────────│                 │
                │ PK id         │                 │
                │ FK client_id  │──── posted_by   │
                │    title      │                 │
                │    required_  │                 │
                │      skills[] │                 │
                │    budget_min │                 │
                │    budget_max │                 │
                │    deadline   │                 │
                │    status     │                 │
                │ FK accepted_  │                 │
                │    bid_id     │                 │
                └────┬──────────┘                 │
                     │                            │
            has (1:N)│                            │ bids_on (N:1)
                     │                            │
                ┌────▼──────────┐                 │
                │     BID       │                 │
                │───────────────│                 │
                │ PK id         │                 │
                │ FK project_id │                 │
                │ FK freelancer_│─────────────────┘
                │    id         │
                │    amount     │
                │    proposal   │
                │    match_score│
                │    created_at │
                └────┬──────────┘
                     │
                     │ (after completion)
                     │
                ┌────▼──────────┐
                │    RATING     │
                │───────────────│
                │ PK id         │
                │ FK project_id │ (UNIQUE — 1 rating per project)
                │ FK freelancer_│
                │    id         │
                │ FK client_id  │
                │    score (1-5)│
                │    review     │
                └───────────────┘
```

## 2.2 Entity Sets

| Entity | Type | Key | Description |
|--------|------|-----|-------------|
| User | **Strong** | `id` | Base entity for all platform users |
| FreelancerProfile | **Weak** (depends on User) | `id` (partial: `user_id`) | Exists only if the associated User has role='freelancer' |
| Project | **Strong** | `id` | A client-posted job with requirements and budget |
| Bid | **Strong** | `id` | A freelancer's proposal on a project |
| Rating | **Strong** | `id` | Client's review of a freelancer after project completion |
| AuditLog | **Strong** | `id` | Immutable record of state changes (security) |

## 2.3 Attribute Types

| Attribute | Type | Entity |
|-----------|------|--------|
| `id` | Simple, Key | All entities |
| `username` | Simple, Unique | User |
| `skills` | **Multivalued** (JSON array) | FreelancerProfile |
| `required_skills` | **Multivalued** (JSON array) | Project |
| `avg_rating` | **Derived** (from ratings) | FreelancerProfile |
| `budget_min`, `budget_max` | **Composite** (budget range) | Project |
| `created_at` | Simple, Timestamp | Most entities |

## 2.4 Mapping Cardinality

| Relationship | Cardinality | Participation |
|---|---|---|
| User → FreelancerProfile | **1:1** | User: partial (only freelancers), Profile: total |
| Client → Project | **1:N** | Client: partial, Project: total |
| Project → Bid | **1:N** | Project: partial (may have 0 bids), Bid: total |
| Freelancer → Bid | **1:N** | Freelancer: partial, Bid: total |
| Project → Rating | **1:1** | Both partial (not all projects get rated) |
| Client → Rating | **1:N** | Client: partial, Rating: total |
| Freelancer → Rating | **1:N** | Freelancer: partial, Rating: total |

## 2.5 Generalization / Specialization

```
        User (Generalization)
         │
    ┌────┴────┐
    │         │         Disjoint, Total
  Client  Freelancer    (every user is exactly one)
```

- **Discriminator:** `role` column (`'client'` or `'freelancer'`)
- **Disjoint:** A user cannot be both a client and a freelancer (enforced by `CHECK(role IN ('client','freelancer'))`)
- **Total:** Every user must have a role (enforced by `NOT NULL` on role)
- **Implementation:** Single-table inheritance with a discriminator column. The ABC hierarchy (`UserBase` → `ClientUser` / `FreelancerUser`) models this in Python.

## 2.6 Aggregation

The **Bid** entity is an aggregation of the relationship between **Project** and **Freelancer**:

```
Project ──── bids_on ──── Freelancer
                │
                ▼
          BID (aggregation)
          attributes: amount, proposal, match_score
```

The bid itself has attributes (`amount`, `match_score`) that belong to neither the project nor the freelancer, but to the relationship between them. This is the classic use case for aggregation in ER modeling.

## 2.7 Constraints Mapped to ER

| ER Constraint | MySQL Implementation |
|---|---|
| Key constraint | `PRIMARY KEY (id)` |
| Participation (total) | `NOT NULL` on foreign keys |
| Participation (partial) | Nullable foreign keys (e.g., `accepted_bid_id`) |
| Cardinality 1:1 | `UNIQUE` on `user_id` in `freelancer_profiles` |
| Cardinality 1:N | FK without UNIQUE (e.g., `bids.project_id`) |
| Disjoint specialization | `CHECK(role IN ('client','freelancer'))` |
