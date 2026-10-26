# Unit 4: Relational Database Design (Normalization) — BidForge

## 4.1 Functional Dependencies

### Table: `users`
```
id → username, email, password_hash, role, created_at
username → id, email, password_hash, role, created_at
email → id, username, password_hash, role, created_at
```
Candidate keys: `{id}`, `{username}`, `{email}`
Primary key: `id`

### Table: `freelancer_profiles`
```
id → user_id, skills, hourly_rate, avg_rating, total_ratings
user_id → id, skills, hourly_rate, avg_rating, total_ratings
```
Candidate keys: `{id}`, `{user_id}`

### Table: `projects`
```
id → client_id, title, description, required_skills, budget_min, budget_max, 
     deadline, status, accepted_bid_id, client_completed, freelancer_completed, created_at
```
Candidate key: `{id}`

### Table: `bids`
```
id → project_id, freelancer_id, amount, proposal, match_score, created_at
{project_id, freelancer_id} → id, amount, proposal, match_score, created_at
```
Candidate keys: `{id}`, `{project_id, freelancer_id}`

### Table: `ratings`
```
id → project_id, freelancer_id, client_id, score, review, created_at
project_id → id, freelancer_id, client_id, score, review, created_at
```
Candidate keys: `{id}`, `{project_id}`

## 4.2 Trivial vs. Non-Trivial FDs

**Trivial FDs** (RHS ⊆ LHS):
- `{project_id, freelancer_id} → project_id` ✓ trivial
- `{id, username} → username` ✓ trivial

**Non-trivial FDs** (RHS ⊄ LHS):
- `id → username` in users ✓ non-trivial
- `{project_id, freelancer_id} → amount, match_score` in bids ✓ non-trivial
- `project_id → score` in ratings ✓ non-trivial

## 4.3 Closure of Attributes

For `bids` with FDs:
- F = { id → all, {project_id, freelancer_id} → all }

Closure of `{project_id, freelancer_id}`:
```
{project_id, freelancer_id}⁺ = {project_id, freelancer_id, id, amount, 
                                 proposal, match_score, created_at}
```
Since the closure contains all attributes, `{project_id, freelancer_id}` is a superkey.

## 4.4 Normalization Analysis

### First Normal Form (1NF)

A relation is in 1NF if all attributes contain only atomic (indivisible) values.

| Table | 1NF? | Notes |
|---|---|---|
| users | ✅ Yes | All columns are atomic |
| freelancer_profiles | ⚠️ Technically no | `skills` is a JSON array (multivalued) |
| projects | ⚠️ Technically no | `required_skills` is a JSON array |
| bids | ✅ Yes | All columns are atomic |
| ratings | ✅ Yes | All columns are atomic |

**Design decision:** `skills` and `required_skills` are stored as JSON arrays instead of a normalized junction table. This is a deliberate denormalization:

**Normalized version (strict 1NF):**
```sql
-- Junction tables for skills
CREATE TABLE freelancer_skills (
    freelancer_id INT, skill VARCHAR(50),
    PRIMARY KEY (freelancer_id, skill),
    FOREIGN KEY (freelancer_id) REFERENCES freelancer_profiles(id)
);
CREATE TABLE project_skills (
    project_id INT, skill VARCHAR(50),
    PRIMARY KEY (project_id, skill),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

**Why we chose JSON:** The MatchEngine computes `set(required) ∩ set(offered)` in Python. Loading skills as a JSON array and doing the intersection in Python is faster than a `JOIN` + `GROUP BY` + `HAVING COUNT = N` query, especially since the skill lists are small (< 20 items).

### Second Normal Form (2NF)

A relation is in 2NF if it is in 1NF and every non-key attribute is fully functionally dependent on the entire primary key (no partial dependencies).

| Table | PK | 2NF? | Analysis |
|---|---|---|---|
| users | {id} | ✅ | Single-column PK → no partial deps possible |
| freelancer_profiles | {id} | ✅ | Single-column PK |
| projects | {id} | ✅ | Single-column PK |
| bids | {id} | ✅ | Single-column PK. Note: the candidate key {project_id, freelancer_id} has no partial deps since all non-key attrs depend on the full pair |
| ratings | {id} | ✅ | Single-column PK |

### Third Normal Form (3NF)

A relation is in 3NF if it is in 2NF and no non-key attribute transitively depends on the primary key.

| Table | 3NF? | Analysis |
|---|---|---|
| users | ✅ | No transitive deps: id → username, id → email, etc. are all direct |
| freelancer_profiles | ⚠️ | `avg_rating` is derivable from `ratings` table (transitive via total_ratings). This is intentional denormalization for query performance |
| projects | ✅ | No transitive deps |
| bids | ✅ | `match_score` could be computed from project + profile, but storing it avoids recomputation |
| ratings | ✅ | No transitive deps |

**Denormalization trade-off (avg_rating):**
```
                  3NF (normalized)              Denormalized (actual)
Ratings table:    id → score                    id → score
Profile table:    user_id → skills, rate        user_id → skills, rate, avg_rating, total_ratings
Read query:       SELECT AVG(score) FROM        SELECT avg_rating FROM freelancer_profiles
                  ratings WHERE freelancer_id=X  WHERE user_id = X
Complexity:       O(n) — scans all ratings      O(1) — single column read
Write overhead:   None                          Update avg on each new rating
```

### Boyce-Codd Normal Form (BCNF)

A relation is in BCNF if for every non-trivial FD X → Y, X is a superkey.

All BidForge tables are in **BCNF** because every determinant (LHS of an FD) is a candidate key:
- `users`: {id}, {username}, {email} are all candidate keys
- `bids`: {id} and {project_id, freelancer_id} are both candidate keys
- `ratings`: {id} and {project_id} are both candidate keys

### 4NF and 5NF

**4NF (Multivalued Dependencies):** No table in BidForge has independent multivalued dependencies. The JSON arrays (`skills`, `required_skills`) would create MVDs if normalized into junction tables, but since they're stored as JSON, the MVDs don't apply in the relational sense.

**5NF (Join Dependencies):** All BidForge tables can be reconstructed from their natural decompositions without loss. No spurious tuples arise from joining the tables back together.

## 4.5 Decomposition Summary

BidForge's schema is **lossless-join decomposable** — the original data can be perfectly reconstructed by joining the normalized tables on their foreign keys:

```sql
-- Full reconstruction
SELECT u.*, fp.skills, fp.hourly_rate, fp.avg_rating,
       p.title, p.status, b.amount, b.match_score, r.score
FROM users u
LEFT JOIN freelancer_profiles fp ON u.id = fp.user_id
LEFT JOIN bids b ON u.id = b.freelancer_id
LEFT JOIN projects p ON b.project_id = p.id
LEFT JOIN ratings r ON p.id = r.project_id;
```

**Dependency preservation:** All FDs are preserved within individual tables — no FD spans multiple tables after decomposition.
