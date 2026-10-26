# Unit 3: Relational Model — BidForge

## 3.1 Structure of Relational Databases

BidForge's relational database consists of 6 relations (tables):

| Relation | Schema | Domain constraints |
|---|---|---|
| `users` | (id: INT, username: VARCHAR(50), email: VARCHAR(120), password_hash: VARCHAR(256), role: VARCHAR(20), created_at: DATETIME) | role ∈ {'client', 'freelancer'} |
| `freelancer_profiles` | (id: INT, user_id: INT, skills: TEXT, hourly_rate: FLOAT, avg_rating: FLOAT, total_ratings: INT) | hourly_rate ≥ 0, 0 ≤ avg_rating ≤ 5 |
| `projects` | (id: INT, client_id: INT, title: VARCHAR(200), ..., budget_min: FLOAT, budget_max: FLOAT, status: VARCHAR(20), ...) | budget_min ≥ 0, budget_max > 0, status ∈ {'open','in_progress','completed'} |
| `bids` | (id: INT, project_id: INT, freelancer_id: INT, amount: FLOAT, proposal: TEXT, match_score: FLOAT, created_at: DATETIME) | amount > 0, 0 ≤ match_score ≤ 1 |
| `ratings` | (id: INT, project_id: INT, freelancer_id: INT, client_id: INT, score: INT, review: TEXT, created_at: DATETIME) | 1 ≤ score ≤ 5 |
| `audit_log` | (id: INT, table_name: VARCHAR(64), record_id: INT, action: VARCHAR(50), old_value: TEXT, new_value: TEXT, changed_at: DATETIME) | — |

## 3.2 ER-to-Relational Mapping

| ER Concept | Relational Mapping |
|---|---|
| Strong entity **User** | Table `users` with PK `id` |
| Specialization (Client/Freelancer) | Single table with discriminator column `role` (single-table inheritance) |
| Weak entity **FreelancerProfile** | Table `freelancer_profiles` with FK `user_id` referencing `users(id)`, `UNIQUE(user_id)` |
| 1:N relationship (Client posts Project) | FK `client_id` in `projects` referencing `users(id)` |
| 1:N relationship (Project has Bids) | FK `project_id` in `bids` referencing `projects(id)` |
| 1:N relationship (Freelancer submits Bids) | FK `freelancer_id` in `bids` referencing `users(id)` |
| 1:1 relationship (Project has Rating) | FK `project_id` in `ratings` with `UNIQUE(project_id)` |
| Multivalued attribute (skills) | JSON array in TEXT column (denormalized for performance) |
| Derived attribute (avg_rating) | Stored as denormalized column, updated via trigger |
| Composite attribute (budget) | Two columns: `budget_min`, `budget_max` |

## 3.3 Relational Algebra — BidForge Queries

### Selection (σ)
```
σ_{status='open'}(projects)
```
SQL: `SELECT * FROM projects WHERE status = 'open'`

Python ORM: `db.query(Project).filter(Project.status == 'open')`

### Projection (π)
```
π_{username, email, role}(users)
```
SQL: `SELECT username, email, role FROM users`

### Join (⋈)
```
bids ⋈_{bids.freelancer_id = users.id} users
```
SQL: `SELECT * FROM bids b JOIN users u ON b.freelancer_id = u.id`

### Rename (ρ)
```
ρ_{freelancer_name/username}(π_{username}(users))
```
SQL: `SELECT username AS freelancer_name FROM users`

### Union (∪)
```
π_{id}(σ_{role='client'}(users)) ∪ π_{id}(σ_{role='freelancer'}(users))
```
SQL: `SELECT id FROM users WHERE role='client' UNION SELECT id FROM users WHERE role='freelancer'`

### Set Difference (−)
```
π_{freelancer_id}(bids) − π_{freelancer_id}(σ_{status='completed'}(bids ⋈ projects))
```
"Freelancers who have bid but never completed a project"

### Cartesian Product (×)
```
projects × bids  (rarely useful without a join condition)
```

### Complex query: "Ranked bids for project 1 with freelancer names"
```
π_{username, amount, match_score}(
    σ_{project_id=1}(bids) ⋈_{bids.freelancer_id = users.id} users
)
```
SQL:
```sql
SELECT u.username, b.amount, b.match_score
FROM bids b JOIN users u ON b.freelancer_id = u.id
WHERE b.project_id = 1
ORDER BY b.match_score DESC
```

### Aggregation
```
γ_{project_id; COUNT(*) AS num_bids, AVG(amount) AS avg_bid}(bids)
```
SQL: `SELECT project_id, COUNT(*), AVG(amount) FROM bids GROUP BY project_id`

## 3.4 Tuple Relational Calculus

**"Find all freelancers who have bid on the FastAPI Microservice project":**
```
{ u.username | users(u) ∧ u.role = 'freelancer' ∧
  ∃b(bids(b) ∧ b.freelancer_id = u.id ∧
    ∃p(projects(p) ∧ p.id = b.project_id ∧
       p.title = 'FastAPI Microservice Platform')) }
```

SQL equivalent:
```sql
SELECT u.username FROM users u
WHERE u.role = 'freelancer'
  AND EXISTS (
    SELECT 1 FROM bids b
    JOIN projects p ON b.project_id = p.id
    WHERE b.freelancer_id = u.id
      AND p.title = 'FastAPI Microservice Platform'
  );
```

**"Find projects where all required skills match the freelancer's skills":**
```
{ p.title | projects(p) ∧ p.status = 'open' ∧
  ∃b(bids(b) ∧ b.project_id = p.id ∧ b.match_score >= 0.9) }
```
"Projects that have at least one excellent-fit bid"
