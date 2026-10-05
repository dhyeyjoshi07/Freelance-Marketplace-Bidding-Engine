"""
Seed script — populates the database with realistic demo data.

Creates:
  - 3 clients
  - 5 freelancers with varied skills and ratings
  - 6 projects across different domains
  - 12+ bids with computed match scores
  - 2 completed projects with ratings

Run:  python seed.py
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal, init_db
from backend.models.user import User, FreelancerProfile
from backend.models.project import Project
from backend.models.bid import Bid, Rating
from backend.models.enums import ProjectStatus, UserRole
from backend.services.auth_service import hash_password
from backend.services.match_engine import MatchEngine

engine = MatchEngine()
db = SessionLocal()


def seed():
    """Main seed function — idempotent (drops and recreates all data)."""
    print("🌱 Seeding database...")

    # Initialize tables
    init_db()

    # Check if already seeded
    if db.query(User).count() > 0:
        print("⚠️  Database already has data. Delete freelance_marketplace.db and retry.")
        print("   Run: rm freelance_marketplace.db && python seed.py")
        return

    # --- Clients ---
    clients = []
    client_data = [
        ("sarah_chen", "sarah@techcorp.com", "TechCorp product manager"),
        ("alex_rivera", "alex@startupxyz.com", "Startup founder"),
        ("morgan_wu", "morgan@agency.co", "Digital agency owner"),
    ]
    for username, email, desc in client_data:
        user = User(
            username=username, email=email,
            password_hash=hash_password("password123"),
            role=UserRole.CLIENT.value,
        )
        db.add(user)
        clients.append(user)
        print(f"  👤 Client: {username} ({desc})")

    db.flush()

    # --- Freelancers ---
    freelancers = []
    freelancer_data = [
        ("dev_alice", "alice@dev.io", ["python", "fastapi", "sql", "docker", "aws"], 85.0),
        ("dev_bob", "bob@code.dev", ["javascript", "react", "node.js", "typescript", "css"], 70.0),
        ("dev_charlie", "charlie@fullstack.io", ["python", "react", "sql", "redis", "graphql"], 95.0),
        ("dev_diana", "diana@ml.ai", ["python", "pytorch", "tensorflow", "sql", "docker"], 120.0),
        ("dev_evan", "evan@web.dev", ["html", "css", "javascript", "figma", "tailwind"], 55.0),
    ]
    for username, email, skills, rate in freelancer_data:
        user = User(
            username=username, email=email,
            password_hash=hash_password("password123"),
            role=UserRole.FREELANCER.value,
        )
        db.add(user)
        db.flush()

        profile = FreelancerProfile(user_id=user.id, hourly_rate=rate)
        profile.set_skills_list(skills)
        db.add(profile)

        freelancers.append((user, profile))
        print(f"  🛠️  Freelancer: {username} | skills={skills} | ${rate}/hr")

    db.flush()

    # Give some freelancers pre-existing ratings
    freelancers[0][1].update_rating(5)  # Alice: 5.0
    freelancers[0][1].update_rating(4)  # Alice: 4.5
    freelancers[1][1].update_rating(4)  # Bob: 4.0
    freelancers[1][1].update_rating(3)  # Bob: 3.5
    freelancers[2][1].update_rating(5)  # Charlie: 5.0
    freelancers[2][1].update_rating(5)  # Charlie: 5.0
    freelancers[2][1].update_rating(4)  # Charlie: 4.67

    print("\n📋 Creating projects...")

    # --- Projects ---
    future = lambda days: datetime.now(timezone.utc) + timedelta(days=days)

    projects_data = [
        # (client_idx, title, description, skills, budget_min, budget_max, deadline_days, status)
        (0, "FastAPI Microservice Platform",
         "Build a production-ready microservice platform with FastAPI. Needs auth, rate limiting, background tasks, and Postgres integration. Must include Docker containerization and CI/CD pipeline setup.",
         ["python", "fastapi", "sql", "docker"], 3000, 12000, 45, "open"),

        (0, "React Admin Dashboard",
         "Modern admin dashboard with real-time analytics, user management, and role-based access control. Material UI preferred. Must be responsive and include dark mode.",
         ["react", "typescript", "css", "node.js"], 2000, 8000, 30, "open"),

        (1, "ML Prediction API",
         "Deploy a trained PyTorch model as a REST API with batch prediction support, model versioning, and A/B testing capabilities. Need monitoring dashboards.",
         ["python", "pytorch", "fastapi", "docker"], 5000, 20000, 60, "open"),

        (1, "Landing Page Redesign",
         "Complete redesign of our startup landing page. Need modern, conversion-optimized design with animations, testimonials section, and CTA optimization.",
         ["html", "css", "javascript", "figma"], 800, 3000, 21, "open"),

        (2, "E-Commerce Backend",
         "Scalable e-commerce backend with product catalog, cart, checkout, Stripe payments, and order management. REST API with comprehensive documentation.",
         ["python", "fastapi", "sql", "stripe"], 4000, 15000, 50, "open"),

        (2, "GraphQL API Migration",
         "Migrate existing REST API to GraphQL. Includes schema design, resolver implementation, subscriptions for real-time updates, and performance optimization.",
         ["python", "graphql", "sql", "redis"], 3000, 10000, 40, "open"),
    ]

    projects = []
    for cidx, title, desc, skills, bmin, bmax, days, status in projects_data:
        p = Project(
            client_id=clients[cidx].id,
            title=title, description=desc,
            budget_min=bmin, budget_max=bmax,
            deadline=future(days),
            status=status,
        )
        p.set_required_skills_list(skills)
        db.add(p)
        projects.append(p)
        print(f"  📄 {title} [${bmin}-${bmax}]")

    db.flush()

    print("\n💰 Submitting bids with match scoring...")

    # --- Bids ---
    # (project_idx, freelancer_idx, amount, proposal)
    bids_data = [
        # FastAPI Microservice — Alice (full match), Charlie (partial), Diana (partial)
        (0, 0, 8000, "I've built 3 production FastAPI platforms with Docker+AWS. Can deliver in 4 weeks."),
        (0, 2, 9500, "Full-stack expert — I'll architect a scalable solution with Redis caching and async workers."),
        (0, 3, 11000, "ML infrastructure specialist. I can build robust APIs with monitoring and auto-scaling."),

        # React Dashboard — Bob (full match), Evan (partial), Charlie (partial)
        (1, 1, 5500, "React is my specialty — built 10+ admin dashboards with Material UI and real-time features."),
        (1, 4, 3000, "I can create a beautiful, responsive dashboard with modern CSS and smooth animations."),
        (1, 2, 6000, "Full-stack developer — I'll handle both the React frontend and any backend needs."),

        # ML Prediction API — Diana (great match), Alice (good), Charlie (partial)
        (2, 3, 15000, "PhD in ML, deployed 5+ PyTorch models to production. This is exactly my wheelhouse."),
        (2, 0, 12000, "Strong Python+FastAPI skills. I've containerized ML models with Docker before."),

        # Landing Page — Evan (good match), Bob (partial)
        (3, 4, 1800, "I specialize in conversion-optimized landing pages with modern animations."),
        (3, 1, 2500, "I'll create a stunning page with React for interactivity and smooth transitions."),

        # E-Commerce Backend — Alice (great), Charlie (good)
        (4, 0, 10000, "Built 2 e-commerce platforms with Stripe integration. Can handle the full scope."),
        (4, 2, 12000, "Experienced with payment systems and scalable backends. GraphQL subscriptions included."),

        # GraphQL Migration — Charlie (great match)
        (5, 2, 7000, "I've done 3 REST-to-GraphQL migrations. Expert in schema design and performance tuning."),
    ]

    bids = []
    for pidx, fidx, amount, proposal in bids_data:
        project = projects[pidx]
        user, profile = freelancers[fidx]

        score = engine.match_score(
            bid_amount=amount,
            freelancer_skills=profile.get_skills_list(),
            freelancer_avg_rating=profile.avg_rating or 0.0,
            required_skills=project.get_required_skills_list(),
            budget_min=project.budget_min,
            budget_max=project.budget_max,
        )

        bid = Bid(
            project_id=project.id,
            freelancer_id=user.id,
            amount=amount,
            proposal=proposal,
            match_score=score,
        )
        db.add(bid)
        bids.append(bid)
        print(f"  💰 {user.username} → {project.title[:30]}... | ${amount} | score={score:.3f}")

    db.flush()

    print("\n✅ Seed complete!")
    print(f"   {len(clients)} clients | {len(freelancers)} freelancers")
    print(f"   {len(projects)} projects | {len(bids)} bids")
    print(f"\n🔑 All accounts use password: password123")
    print(f"   Clients:     sarah_chen, alex_rivera, morgan_wu")
    print(f"   Freelancers: dev_alice, dev_bob, dev_charlie, dev_diana, dev_evan")

    db.commit()
    db.close()


if __name__ == "__main__":
    seed()
