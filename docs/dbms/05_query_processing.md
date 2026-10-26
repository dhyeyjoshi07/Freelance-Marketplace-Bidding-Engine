# Unit 5: Query Processing & Optimization — BidForge

## 5.1 Query Processing Steps

When BidForge runs `GET /api/projects/1/bids`, here's the full journey:

```
Python code                    SQLAlchemy                  PyMySQL              MySQL Server
───────────                    ──────────                  ──────               ────────────
db.query(Bid)                  
  .filter(project_id==1)   →  Compiles to SQL         →  Sends via TCP    →  1. Parser
  .order_by(match_score.desc())                                               2. Optimizer
                                                                               3. Executor
                                                                           ←  Result rows
                               ←  Maps rows to Bid objects  ←  Receives bytes
Returns [Bid, Bid, ...]
```

### MySQL Query Processing Pipeline:

1. **Parser:** Tokenizes and parses the SQL, validates syntax, checks table/column existence
2. **Optimizer:** Generates candidate execution plans, estimates cost, selects cheapest
3. **Executor:** Runs the chosen plan, reads data pages from buffer pool or disk

## 5.2 BidForge Indexes

Indexes are created in `database.py` via `create_indexes()`:

```sql
-- Covering index for the core bid-ranking query
CREATE INDEX idx_bids_project_score ON bids (project_id, match_score DESC);

-- Lookup indexes
CREATE INDEX idx_bids_freelancer ON bids (freelancer_id);
CREATE INDEX idx_projects_status ON projects (status);
CREATE INDEX idx_projects_client ON projects (client_id);
CREATE INDEX idx_ratings_freelancer ON ratings (freelancer_id);

-- Composite index for duplicate-bid check
CREATE INDEX idx_bids_project_freelancer ON bids (project_id, freelancer_id);
```

## 5.3 EXPLAIN Analysis

### Query: Ranked bids for a project

```sql
EXPLAIN SELECT b.*, u.username
FROM bids b
JOIN users u ON b.freelancer_id = u.id
WHERE b.project_id = 1
ORDER BY b.match_score DESC;
```

**With index `idx_bids_project_score`:**
```
+----+-------------+-------+------+------------------------+-----------------------+---------+-------+------+-------+
| id | select_type | table | type | possible_keys          | key                   | key_len | ref   | rows | Extra |
+----+-------------+-------+------+------------------------+-----------------------+---------+-------+------+-------+
|  1 | SIMPLE      | b     | ref  | idx_bids_project_score | idx_bids_project_score| 4       | const | 3    |       |
|  1 | SIMPLE      | u     | eq_ref| PRIMARY               | PRIMARY               | 4       | b.fid | 1    |       |
+----+-------------+-------+------+------------------------+-----------------------+---------+-------+------+-------+
```

**Key observations:**
- `type=ref`: Index lookup (not a full table scan)
- `key=idx_bids_project_score`: MySQL chose our composite index
- `rows=3`: Only 3 rows need to be examined (vs. scanning all bids)
- The `DESC` in the index avoids a filesort for `ORDER BY match_score DESC`

**Without index (hypothetical):**
```
+----+-------------+-------+------+---------------+------+---------+------+------+-----------------------------+
| id | select_type | table | type | possible_keys | key  | key_len | ref  | rows | Extra                       |
+----+-------------+-------+------+---------------+------+---------+------+------+-----------------------------+
|  1 | SIMPLE      | b     | ALL  | NULL          | NULL | NULL    | NULL | 13   | Using where; Using filesort |
|  1 | SIMPLE      | u     | ALL  | NULL          | NULL | NULL    | NULL | 8    | Using where                 |
+----+-------------+-------+------+---------------+------+---------+------+------+-----------------------------+
```

- `type=ALL`: Full table scan (reads every row)
- `Using filesort`: MySQL has to sort all matching rows in memory
- `rows=13`: Must examine all 13 bids

## 5.4 Access Types (from best to worst)

| Type | Meaning | BidForge Example |
|---|---|---|
| `system` | Table has exactly 1 row | — |
| `const` | Match on PRIMARY KEY or UNIQUE with constant | `WHERE id = 1` |
| `eq_ref` | 1 row per join (unique index) | `JOIN users ON bid.freelancer_id = users.id` |
| `ref` | Non-unique index lookup | `WHERE project_id = 1` (via `idx_bids_project_score`) |
| `range` | Index range scan | `WHERE amount BETWEEN 5000 AND 10000` |
| `index` | Full index scan (all rows, from index) | — |
| `ALL` | **Full table scan** (worst) | Query without any applicable index |

## 5.5 B+ Tree Index Structure

MySQL InnoDB uses B+ trees for all indexes:

```
                    ┌───────────────┐
                    │  Root Node    │
                    │  [5]  [10]    │
                    └──┬────┬────┬──┘
                       │    │    │
              ┌────────┘    │    └────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Leaf [1,3]│→│ Leaf [5,7]│→│ Leaf [10] │    ← Leaf nodes linked
        │ data ptrs │  │ data ptrs │  │ data ptrs│       for range scans
        └──────────┘  └──────────┘  └──────────┘
```

For `idx_bids_project_score(project_id, match_score DESC)`:
- Internal nodes contain `project_id` values for routing
- Leaf nodes contain `(project_id, match_score)` pairs plus row pointers
- Leaves are linked left-to-right for efficient range scans
- `ORDER BY match_score DESC` follows the leaf chain backward

## 5.6 Live Demo via API

BidForge exposes query analysis through the admin API:

```bash
# View EXPLAIN output for any query
curl "http://localhost:8000/api/admin/explain?query=SELECT%20*%20FROM%20bids%20WHERE%20project_id=1"

# View table statistics
curl "http://localhost:8000/api/admin/table-stats/bids"

# Full optimization demo (index vs. no index comparison)
curl "http://localhost:8000/api/admin/query-optimization-demo"
```

**Python code:** `backend/services/query_analyzer.py`
