"""
Performance indexes (DBMS Unit 5: Query Optimization).

Each index targets a specific query pattern used by the application routers.
"""

from sqlalchemy import text


INDEX_DEFINITIONS = [
    # Covering index for bid ranking queries: given a project, sort bids by score
    "CREATE INDEX IF NOT EXISTS idx_bids_project_score ON bids (project_id, match_score DESC)",
    # Fast lookup of freelancer's bids
    "CREATE INDEX IF NOT EXISTS idx_bids_freelancer ON bids (freelancer_id)",
    # Filter projects by status (most queries filter for 'open')
    "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status)",
    # Client's own projects
    "CREATE INDEX IF NOT EXISTS idx_projects_client ON projects (client_id)",
    # Rating lookups by freelancer
    "CREATE INDEX IF NOT EXISTS idx_ratings_freelancer ON ratings (freelancer_id)",
    # Composite index for duplicate-bid check (supplements the UNIQUE constraint)
    "CREATE INDEX IF NOT EXISTS idx_bids_project_freelancer ON bids (project_id, freelancer_id)",
]


def create_indexes(connection) -> None:
    """Create performance indexes for query optimization."""
    for idx_sql in INDEX_DEFINITIONS:
        try:
            connection.execute(text(idx_sql))
        except Exception:
            pass  # Index already exists
