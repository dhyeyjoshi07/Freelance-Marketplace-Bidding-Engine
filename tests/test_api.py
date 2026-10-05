"""
API integration tests — end-to-end test of the full request lifecycle.

Uses FastAPI's TestClient (backed by httpx) with an in-memory SQLite
database, so tests are fast and isolated from the production DB.

Test flow mirrors the real user journey:
  1. Register client + freelancer
  2. Freelancer sets up profile
  3. Client posts a project
  4. Freelancer submits a bid
  5. Client views ranked bids
  6. Client accepts the best bid
  7. Both parties mark complete
  8. Client rates the freelancer
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import app
from backend.database import Base
from backend.dependencies import get_db


# ---- In-memory test database setup ----

TEST_DATABASE_URL = "sqlite:///./test_marketplace.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


# Override the DB dependency for all tests
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


# ---- Helper functions ----

def register_user(client: TestClient, username: str, role: str) -> dict:
    resp = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "password123",
        "role": role,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def login_user(client: TestClient, username: str) -> str:
    resp = client.post("/api/auth/login", json={
        "username": username,
        "password": "password123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def future_deadline() -> str:
    """Return an ISO-format datetime 30 days from now."""
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


# ====================================================================
# Auth Tests
# ====================================================================

class TestAuth:
    def test_register_client(self, client):
        data = register_user(client, "alice_client", "client")
        assert data["username"] == "alice_client"
        assert data["role"] == "client"

    def test_register_freelancer(self, client):
        data = register_user(client, "bob_freelancer", "freelancer")
        assert data["role"] == "freelancer"

    def test_register_duplicate_username(self, client):
        register_user(client, "dup_user", "client")
        resp = client.post("/api/auth/register", json={
            "username": "dup_user",
            "email": "other@test.com",
            "password": "password123",
            "role": "client",
        })
        assert resp.status_code == 409

    def test_register_duplicate_email(self, client):
        register_user(client, "user1", "client")
        resp = client.post("/api/auth/register", json={
            "username": "user2",
            "email": "user1@test.com",
            "password": "password123",
            "role": "client",
        })
        assert resp.status_code == 409

    def test_login_success(self, client):
        register_user(client, "login_test", "client")
        resp = client.post("/api/auth/login", json={
            "username": "login_test",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "client"

    def test_login_wrong_password(self, client):
        register_user(client, "wp_test", "client")
        resp = client.post("/api/auth/login", json={
            "username": "wp_test",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_me_endpoint(self, client):
        register_user(client, "me_test", "freelancer")
        token = login_user(client, "me_test")
        resp = client.get("/api/auth/me", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["username"] == "me_test"

    def test_me_unauthorized(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


# ====================================================================
# Freelancer Profile Tests
# ====================================================================

class TestFreelancerProfile:
    def test_get_profile(self, client):
        register_user(client, "fp_test", "freelancer")
        token = login_user(client, "fp_test")
        resp = client.get("/api/freelancers/me", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["skills"] == []

    def test_update_profile(self, client):
        register_user(client, "fp_update", "freelancer")
        token = login_user(client, "fp_update")
        resp = client.put("/api/freelancers/me", headers=auth_header(token), json={
            "skills": ["Python", "React", "SQL"],
            "hourly_rate": 75.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["skills"] == ["python", "react", "sql"]
        assert data["hourly_rate"] == 75.0

    def test_client_cannot_access_freelancer_profile(self, client):
        register_user(client, "c_nofp", "client")
        token = login_user(client, "c_nofp")
        resp = client.get("/api/freelancers/me", headers=auth_header(token))
        assert resp.status_code == 403


# ====================================================================
# Project Tests
# ====================================================================

class TestProjects:
    def test_create_project(self, client):
        register_user(client, "proj_client", "client")
        token = login_user(client, "proj_client")
        resp = client.post("/api/projects", headers=auth_header(token), json={
            "title": "Build a website",
            "description": "Need a landing page",
            "required_skills": ["html", "css", "javascript"],
            "budget_min": 500,
            "budget_max": 2000,
            "deadline": future_deadline(),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Build a website"
        assert data["status"] == "open"
        assert data["required_skills"] == ["html", "css", "javascript"]

    def test_freelancer_cannot_create_project(self, client):
        register_user(client, "f_nopost", "freelancer")
        token = login_user(client, "f_nopost")
        resp = client.post("/api/projects", headers=auth_header(token), json={
            "title": "Test",
            "budget_min": 100,
            "budget_max": 500,
            "deadline": future_deadline(),
        })
        assert resp.status_code == 403

    def test_invalid_budget(self, client):
        register_user(client, "bad_budget", "client")
        token = login_user(client, "bad_budget")
        resp = client.post("/api/projects", headers=auth_header(token), json={
            "title": "Bad budget",
            "budget_min": 1000,
            "budget_max": 500,
            "deadline": future_deadline(),
        })
        assert resp.status_code == 400

    def test_list_open_projects(self, client):
        register_user(client, "list_client", "client")
        token = login_user(client, "list_client")
        # Create 2 projects
        for i in range(2):
            client.post("/api/projects", headers=auth_header(token), json={
                "title": f"Project {i}",
                "budget_min": 100,
                "budget_max": 500,
                "deadline": future_deadline(),
            })
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_project_detail(self, client):
        register_user(client, "detail_client", "client")
        token = login_user(client, "detail_client")
        create_resp = client.post("/api/projects", headers=auth_header(token), json={
            "title": "Detail test",
            "budget_min": 100,
            "budget_max": 500,
            "deadline": future_deadline(),
        })
        pid = create_resp.json()["id"]
        resp = client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Detail test"

    def test_my_projects_client(self, client):
        register_user(client, "my_c", "client")
        token = login_user(client, "my_c")
        client.post("/api/projects", headers=auth_header(token), json={
            "title": "My project",
            "budget_min": 100,
            "budget_max": 500,
            "deadline": future_deadline(),
        })
        resp = client.get("/api/projects/my", headers=auth_header(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ====================================================================
# Bidding Tests
# ====================================================================

class TestBids:
    def _setup_project(self, client):
        """Create a client, a project, and a freelancer with skills."""
        register_user(client, "bid_client", "client")
        client_token = login_user(client, "bid_client")

        register_user(client, "bid_freelancer", "freelancer")
        fl_token = login_user(client, "bid_freelancer")

        # Set up freelancer profile
        client.put("/api/freelancers/me", headers=auth_header(fl_token), json={
            "skills": ["python", "react", "sql"],
            "hourly_rate": 60.0,
        })

        # Create project
        resp = client.post("/api/projects", headers=auth_header(client_token), json={
            "title": "Bid test project",
            "required_skills": ["python", "react"],
            "budget_min": 500,
            "budget_max": 2000,
            "deadline": future_deadline(),
        })
        project_id = resp.json()["id"]
        return client_token, fl_token, project_id

    def test_submit_bid(self, client):
        client_token, fl_token, pid = self._setup_project(client)
        resp = client.post(
            f"/api/projects/{pid}/bids",
            headers=auth_header(fl_token),
            json={"amount": 1000, "proposal": "I can do this!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 1000
        assert data["match_score"] > 0

    def test_duplicate_bid_rejected(self, client):
        client_token, fl_token, pid = self._setup_project(client)
        client.post(
            f"/api/projects/{pid}/bids",
            headers=auth_header(fl_token),
            json={"amount": 1000},
        )
        resp = client.post(
            f"/api/projects/{pid}/bids",
            headers=auth_header(fl_token),
            json={"amount": 1200},
        )
        assert resp.status_code == 409

    def test_client_cannot_bid(self, client):
        client_token, fl_token, pid = self._setup_project(client)
        resp = client.post(
            f"/api/projects/{pid}/bids",
            headers=auth_header(client_token),
            json={"amount": 1000},
        )
        assert resp.status_code == 403

    def test_ranked_bids(self, client):
        """Submit multiple bids and verify ranking order."""
        register_user(client, "rank_client", "client")
        ct = login_user(client, "rank_client")

        # Create project
        resp = client.post("/api/projects", headers=auth_header(ct), json={
            "title": "Rank test",
            "required_skills": ["python", "react"],
            "budget_min": 500,
            "budget_max": 2000,
            "deadline": future_deadline(),
        })
        pid = resp.json()["id"]

        # Freelancer A: full skill match, good rate
        register_user(client, "fl_a", "freelancer")
        ta = login_user(client, "fl_a")
        client.put("/api/freelancers/me", headers=auth_header(ta), json={
            "skills": ["python", "react"],
            "hourly_rate": 50,
        })
        client.post(f"/api/projects/{pid}/bids", headers=auth_header(ta), json={
            "amount": 1000,
        })

        # Freelancer B: no skill match, expensive
        register_user(client, "fl_b", "freelancer")
        tb = login_user(client, "fl_b")
        client.put("/api/freelancers/me", headers=auth_header(tb), json={
            "skills": ["java", "c++"],
            "hourly_rate": 100,
        })
        client.post(f"/api/projects/{pid}/bids", headers=auth_header(tb), json={
            "amount": 3000,
        })

        # Get ranked bids
        resp = client.get(f"/api/projects/{pid}/bids")
        assert resp.status_code == 200
        bids = resp.json()
        assert len(bids) == 2
        # First bid should have higher match_score (full skill match)
        assert bids[0]["match_score"] > bids[1]["match_score"]
        assert bids[0]["rank"] == 1
        assert bids[1]["rank"] == 2

    def test_my_bids(self, client):
        client_token, fl_token, pid = self._setup_project(client)
        client.post(
            f"/api/projects/{pid}/bids",
            headers=auth_header(fl_token),
            json={"amount": 800},
        )
        resp = client.get("/api/freelancers/me/bids", headers=auth_header(fl_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ====================================================================
# Full Lifecycle Test
# ====================================================================

class TestFullLifecycle:
    """
    End-to-end test of the complete workflow:
    register → profile → post project → bid → accept → complete → rate
    """

    def test_complete_workflow(self, client):
        # 1. Register users
        register_user(client, "lifecycle_client", "client")
        register_user(client, "lifecycle_fl", "freelancer")
        ct = login_user(client, "lifecycle_client")
        ft = login_user(client, "lifecycle_fl")

        # 2. Freelancer sets up profile
        client.put("/api/freelancers/me", headers=auth_header(ft), json={
            "skills": ["python", "fastapi", "sql"],
            "hourly_rate": 65,
        })

        # 3. Client posts a project
        resp = client.post("/api/projects", headers=auth_header(ct), json={
            "title": "Build API",
            "description": "Need a FastAPI backend",
            "required_skills": ["python", "fastapi"],
            "budget_min": 1000,
            "budget_max": 5000,
            "deadline": future_deadline(),
        })
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # 4. Freelancer bids
        resp = client.post(f"/api/projects/{pid}/bids", headers=auth_header(ft), json={
            "amount": 3000,
            "proposal": "Expert in FastAPI",
        })
        assert resp.status_code == 201
        bid_id = resp.json()["id"]
        assert resp.json()["match_score"] > 0.5  # good match expected

        # 5. Client accepts the bid
        resp = client.post(
            f"/api/projects/{pid}/accept-bid",
            headers=auth_header(ct),
            json={"bid_id": bid_id},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"
        assert resp.json()["accepted_bid_id"] == bid_id

        # 6a. Freelancer marks complete
        resp = client.post(f"/api/projects/{pid}/complete", headers=auth_header(ft))
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"  # waiting for client
        assert resp.json()["freelancer_completed"] is True

        # 6b. Client marks complete → transitions to completed
        resp = client.post(f"/api/projects/{pid}/complete", headers=auth_header(ct))
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        # 7. Client rates the freelancer
        resp = client.post(f"/api/projects/{pid}/rate", headers=auth_header(ct), json={
            "score": 5,
            "review": "Excellent work!",
        })
        assert resp.status_code == 200
        assert resp.json()["score"] == 5

        # 8. Verify freelancer's rating was updated
        resp = client.get("/api/freelancers/me", headers=auth_header(ft))
        assert resp.status_code == 200
        assert resp.json()["avg_rating"] == 5.0
        assert resp.json()["total_ratings"] == 1

        # 9. Duplicate rating rejected
        resp = client.post(f"/api/projects/{pid}/rate", headers=auth_header(ct), json={
            "score": 3,
        })
        assert resp.status_code == 409
