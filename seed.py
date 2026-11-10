"""
Seed script — populates the database with rich, realistic marketplace data.

Creates:
  - 8 clients across diverse industries (Tech, AI, Agency, FinTech, Health, EdTech, Cyber, E-Commerce)
  - 15 freelancers with varied tech stacks, hourly rates, and ratings
  - 18 projects across all lifecycle states (10 Open, 4 In Progress, 4 Completed)
  - 50+ scored bids showing the fit-based ranking algorithm in action
  - 4 completed projects with dual confirmations, ratings, and reviews

Run:  python3 seed.py
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

# Ensure project root is importable
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


def reset_database():
    """Cleanly truncate all tables for an idempotent reset."""
    print("🧹 Resetting existing database tables...")
    db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    tables = ["audit_log", "ratings", "bids", "projects", "freelancer_profiles", "users"]
    for t in tables:
        try:
            db.execute(text(f"TRUNCATE TABLE {t}"))
        except Exception:
            pass
    db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    db.commit()


def seed():
    """Main seed function — idempotent (drops and recreates all data)."""
    print("🌱 Seeding BidForge database with rich demo data...\n")

    # 1. Initialize schema, triggers, stored procs
    init_db()

    # 2. Reset tables cleanly
    reset_database()

    # --- Clients ---
    print("👤 Creating clients...")
    clients_info = [
        ("sarah_chen", "sarah@techcorp.com", "TechCorp — Senior Product Manager"),
        ("alex_rivera", "alex@nextgenai.io", "NextGen AI — Founder & CEO"),
        ("morgan_wu", "morgan@pixelforge.design", "PixelForge Agency — Creative Director"),
        ("elena_rostova", "elena@finpulse.com", "FinPulse — Head of Engineering"),
        ("marcus_vance", "marcus@medicloud.health", "MediCloud Health — VP Product"),
        ("priya_patel", "priya@edusphere.learn", "EduSphere — Learning Tech Director"),
        ("david_kim", "david@cybershield.sec", "CyberShield — Security Architecture Lead"),
        ("rachel_green", "rachel@bloombrand.co", "Bloom & Co — E-Commerce Brand Founder"),
    ]

    client_map = {}
    for username, email, desc in clients_info:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password("password123"),
            role=UserRole.CLIENT.value,
        )
        db.add(user)
        client_map[username] = user
        print(f"  👤 Client: {username:15} | {desc}")

    db.flush()

    # --- Freelancers ---
    print("\n🛠️  Creating freelancers...")
    freelancers_info = [
        ("dev_alice", "alice@dev.io", ["python", "fastapi", "sql", "docker", "aws", "postgresql"], 85.0),
        ("dev_bob", "bob@code.dev", ["javascript", "react", "node.js", "typescript", "css", "tailwind"], 70.0),
        ("dev_charlie", "charlie@fullstack.io", ["python", "react", "sql", "redis", "graphql", "docker"], 95.0),
        ("dev_diana", "diana@ml.ai", ["python", "pytorch", "tensorflow", "sql", "docker", "fastapi"], 125.0),
        ("dev_evan", "evan@web.dev", ["html", "css", "javascript", "figma", "tailwind", "ui/ux"], 55.0),
        ("dev_fiona", "fiona@cloudops.net", ["go", "kubernetes", "docker", "microservices", "sql", "aws"], 110.0),
        ("dev_george", "george@mobiledev.io", ["flutter", "react native", "ios", "android", "firebase", "typescript"], 80.0),
        ("dev_hannah", "hannah@systems.rs", ["rust", "webassembly", "c++", "linux", "docker", "python"], 135.0),
        ("dev_ian", "ian@frontend.dev", ["vue.js", "nuxt", "typescript", "tailwind", "node.js", "javascript"], 65.0),
        ("dev_julia", "julia@dataflow.io", ["python", "sql", "spark", "kafka", "snowflake", "aws"], 115.0),
        ("dev_kevin", "kevin@secops.io", ["python", "security", "pentesting", "owasp", "cryptography", "docker"], 130.0),
        ("dev_leo", "leo@devops.co", ["terraform", "aws", "kubernetes", "ci/cd", "docker", "linux"], 105.0),
        ("dev_maya", "maya@fullstack.dev", ["next.js", "react", "typescript", "graphql", "tailwind", "supabase"], 90.0),
        ("dev_noah", "noah@enterprise.io", ["java", "spring boot", "sql", "kafka", "microservices", "docker"], 95.0),
        ("dev_olivia", "olivia@uxdesign.studio", ["figma", "ui/ux", "html", "css", "wireframing", "design systems"], 60.0),
    ]

    freelancer_map = {}
    for username, email, skills, rate in freelancers_info:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password("password123"),
            role=UserRole.FREELANCER.value,
        )
        db.add(user)
        db.flush()

        profile = FreelancerProfile(user_id=user.id, hourly_rate=rate)
        profile.set_skills_list(skills)
        db.add(profile)

        freelancer_map[username] = (user, profile)
        print(f"  🛠️  {username:15} | ${rate:5.1f}/hr | skills: {', '.join(skills[:4])}...")

    db.flush()

    # Pre-seed initial rating impressions for top freelancers
    freelancer_map["dev_alice"][1].update_rating(5)
    freelancer_map["dev_alice"][1].update_rating(5)
    freelancer_map["dev_charlie"][1].update_rating(5)
    freelancer_map["dev_charlie"][1].update_rating(4)
    freelancer_map["dev_diana"][1].update_rating(5)
    freelancer_map["dev_fiona"][1].update_rating(5)
    freelancer_map["dev_bob"][1].update_rating(4)
    freelancer_map["dev_maya"][1].update_rating(5)
    freelancer_map["dev_george"][1].update_rating(4)
    db.flush()

    # --- Projects (18 total: 10 Open, 4 In Progress, 4 Completed) ---
    print("\n📋 Creating projects...")
    future = lambda days: datetime.now(timezone.utc) + timedelta(days=days)
    past = lambda days: datetime.now(timezone.utc) - timedelta(days=days)

    # Specification:
    # (key, client_user, title, description, skills, budget_min, budget_max, deadline, target_status)
    projects_specs = [
        # --- OPEN PROJECTS (10) ---
        (
            "p_fastapi", "sarah_chen",
            "FastAPI High-Throughput Microservice Platform",
            "Build an event-driven microservice backend using FastAPI and PostgreSQL. Requires JWT authentication, Redis rate-limiting, async background tasks, and Docker containerization with CI/CD pipeline.",
            ["python", "fastapi", "sql", "docker", "aws"],
            3000, 12000, future(45), "open"
        ),
        (
            "p_react_admin", "sarah_chen",
            "React Enterprise Analytics Dashboard",
            "Develop a responsive admin portal with interactive charts, user permissions, audit trail views, and dark mode theme. Must use TypeScript and Tailwind CSS.",
            ["react", "typescript", "css", "node.js", "tailwind"],
            2500, 8500, future(30), "open"
        ),
        (
            "p_ml_infer", "alex_rivera",
            "Production ML Model Inference Engine",
            "Package a pre-trained PyTorch transformer as a scalable REST inference API. Requires batch prediction, model versioning, GPU acceleration, and Prometheus metrics monitoring.",
            ["python", "pytorch", "fastapi", "docker"],
            6000, 22000, future(60), "open"
        ),
        (
            "p_landing", "alex_rivera",
            "SaaS Landing Page Redesign & Conversion Optimization",
            "Redesign marketing landing page with modern typography, interactive product tour animations, customer testimonial carousel, and high-converting CTA sections.",
            ["html", "css", "javascript", "figma", "tailwind"],
            1000, 3500, future(20), "open"
        ),
        (
            "p_storefront", "rachel_green",
            "Modern Next.js E-Commerce Storefront",
            "Create a lightning-fast headless e-commerce store with product variant filtering, instant cart drawer, Stripe payment checkout, and Supabase integration.",
            ["next.js", "react", "typescript", "tailwind", "supabase"],
            4500, 16000, future(50), "open"
        ),
        (
            "p_mobile_app", "morgan_wu",
            "Cross-Platform Courier Delivery Mobile App",
            "Build a Flutter mobile application for delivery couriers. Real-time GPS driver tracking, push notifications, offline parcel scanning, and Firebase backend synchronization.",
            ["flutter", "firebase", "android", "ios", "typescript"],
            5000, 18000, future(40), "open"
        ),
        (
            "p_fintech_stream", "elena_rostova",
            "Real-Time Trading WebSocket Gateway",
            "High-concurrency Go service to multiplex cryptocurrency and equity orderbook feeds over WebSockets. Sub-millisecond latency target, lockless ring buffers.",
            ["go", "microservices", "docker", "sql", "aws"],
            7000, 25000, future(55), "open"
        ),
        (
            "p_telehealth", "marcus_vance",
            "HIPAA-Compliant Patient Telehealth Portal",
            "Secure video consultation and encrypted patient document exchange portal. Requires end-to-end audit logging, WebRTC signaling, and role-based physician access.",
            ["python", "fastapi", "react", "sql", "security"],
            8000, 28000, future(65), "open"
        ),
        (
            "p_edtech_portal", "priya_patel",
            "Interactive STEM Course Platform & Quiz Engine",
            "Build a modular Vue 3 frontend for interactive programming exercises, automated code execution grading, and live student progress telemetry.",
            ["vue.js", "typescript", "node.js", "tailwind"],
            3000, 10000, future(35), "open"
        ),
        (
            "p_cloud_infra", "david_kim",
            "Multi-Region AWS Infrastructure Automation",
            "Provision multi-region VPC peering, EKS clusters, RDS read-replicas, and CloudFront distributions using modular Terraform with automated GitHub Actions verification.",
            ["terraform", "aws", "kubernetes", "ci/cd", "linux"],
            4000, 14000, future(45), "open"
        ),

        # --- IN PROGRESS PROJECTS (4) ---
        (
            "p_graphql_gw", "morgan_wu",
            "GraphQL Gateway & Schema Stitching",
            "Consolidate 4 legacy microservice REST APIs into a unified Apollo GraphQL federated gateway with Redis query caching and subscription support.",
            ["python", "graphql", "sql", "redis"],
            3500, 11000, future(25), "in_progress"
        ),
        (
            "p_sec_audit", "david_kim",
            "API Security Audit & Penetration Hardening",
            "Comprehensive blackbox and whitebox security assessment of BidForge API endpoints. Vulnerability remediation for OWASP Top 10, JWT replay attacks, and SQL injection checks.",
            ["python", "security", "pentesting", "owasp", "docker"],
            5000, 15000, future(18), "in_progress"
        ),
        (
            "p_data_pipe", "elena_rostova",
            "Financial Transaction Spark & Kafka Pipeline",
            "Real-time streaming pipeline processing 50k transactions/sec. Anomaly detection, ledger deduplication, and automated archival to Snowflake data warehouse.",
            ["python", "sql", "spark", "kafka", "aws"],
            6000, 20000, future(30), "in_progress"
        ),
        (
            "p_fitness_mobile", "priya_patel",
            "Mobile Wellness & Workout Tracking App",
            "Cross-platform React Native app with custom audio workout timer, Apple Health & Google Fit integrations, and community leaderboards.",
            ["react native", "typescript", "firebase", "ios"],
            4000, 12000, future(22), "in_progress"
        ),

        # --- COMPLETED PROJECTS (4) ---
        (
            "p_observability", "sarah_chen",
            "Microservices Observability & Prometheus Stack",
            "Deployment of Grafana, Prometheus, and OpenTelemetry distributed tracing across all containerized production services with PagerDuty escalation policies.",
            ["go", "kubernetes", "docker", "aws"],
            4000, 13000, past(5), "completed"
        ),
        (
            "p_brand_system", "morgan_wu",
            "Design System & Component Library Overhaul",
            "Complete design system creation in Figma with accompanying React + Tailwind component library, Storybook documentation, and automated accessibility auditing.",
            ["figma", "ui/ux", "html", "css", "tailwind"],
            1500, 5000, past(12), "completed"
        ),
        (
            "p_rust_resizer", "alex_rivera",
            "High-Throughput Image Processing Microservice in Rust",
            "Blazing-fast image transformation service using Rust and WebAssembly. Supports dynamic resizing, AVIF/WebP transcoding, and memory-safe image caching.",
            ["rust", "webassembly", "docker", "linux"],
            5000, 16000, past(20), "completed"
        ),
        (
            "p_spring_split", "marcus_vance",
            "Enterprise Monolith Decomposition into Spring Boot",
            "Migrated core medical claims module from a monolithic legacy system into autonomous Spring Boot microservices with Kafka message brokers.",
            ["java", "spring boot", "microservices", "sql"],
            7000, 24000, past(30), "completed"
        ),
    ]

    project_map = {}
    for pkey, cuser, title, desc, skills, bmin, bmax, deadline, target_status in projects_specs:
        client = client_map[cuser]
        p = Project(
            client_id=client.id,
            title=title,
            description=desc,
            budget_min=bmin,
            budget_max=bmax,
            deadline=deadline,
            status=ProjectStatus.OPEN.value,  # All start open to allow bidding
        )
        p.set_required_skills_list(skills)
        db.add(p)
        project_map[pkey] = (p, target_status)
        print(f"  📄 [{target_status.upper():11}] {title[:40]:40} | ${bmin}-${bmax}")

    db.flush()

    # --- Bids (50+ bids across projects) ---
    print("\n💰 Submitting bids with dynamic match scoring...")

    # Specification:
    # (project_key, freelancer_key, amount, proposal, is_accepted)
    bids_specs = [
        # --- Project: FastAPI Platform (Open) ---
        ("p_fastapi", "dev_alice", 7500, "I've built 4 production FastAPI microservice platforms with Docker and AWS. Full test coverage included.", False),
        ("p_fastapi", "dev_charlie", 8900, "Full-stack architect with deep Python/SQL skills. I'll include automated OpenAPI documentation and Redis caching.", False),
        ("p_fastapi", "dev_fiona", 11000, "Kubernetes and microservice specialist. Will deliver high-availability multi-container architecture.", False),
        ("p_fastapi", "dev_diana", 10500, "Senior backend engineer with strong async Python skills and container orchestration experience.", False),

        # --- Project: React Admin (Open) ---
        ("p_react_admin", "dev_bob", 5200, "React is my primary focus. Built 12+ enterprise analytics dashboards with TypeScript and Tailwind.", False),
        ("p_react_admin", "dev_maya", 6800, "Next.js and React specialist. I build responsive, highly accessible dashboards with crisp visualizations.", False),
        ("p_react_admin", "dev_ian", 4500, "Frontend developer with strong TypeScript and UI component experience. Fast turnaround guaranteed.", False),
        ("p_react_admin", "dev_charlie", 7500, "Full-stack engineer with React expertise. Can handle both dashboard UI and complex API integrations.", False),

        # --- Project: ML Inference (Open) ---
        ("p_ml_infer", "dev_diana", 16000, "PhD in Machine Learning. Deployed 8+ PyTorch models to production with low-latency TensorRT optimizations.", False),
        ("p_ml_infer", "dev_alice", 14500, "Extensive experience packaging machine learning APIs using FastAPI, Docker, and GPU instances.", False),
        ("p_ml_infer", "dev_hannah", 19500, "Systems and ML engineer. Can optimize model serving latency with C++/Python bindings.", False),

        # --- Project: SaaS Landing (Open) ---
        ("p_landing", "dev_evan", 1800, "Specialist in conversion-focused landing pages. Figma-to-code workflow with fluid animations and Tailwind.", False),
        ("p_landing", "dev_olivia", 2400, "UI/UX designer and frontend coder. I'll provide full wireframes, user testing, and responsive implementation.", False),
        ("p_landing", "dev_bob", 2800, "Will deliver pixel-perfect responsive HTML/CSS/Tailwind with micro-interactions and high Lighthouse scores.", False),

        # --- Project: Storefront (Open) ---
        ("p_storefront", "dev_maya", 9800, "Next.js and Supabase are my daily stack. I've delivered 5 high-converting e-commerce web storefronts.", False),
        ("p_storefront", "dev_bob", 8500, "Modern React and Tailwind specialist with Stripe checkout and product catalog expertise.", False),
        ("p_storefront", "dev_ian", 7200, "Skilled frontend builder ready to craft an intuitive shopping flow and cart experience.", False),

        # --- Project: Mobile Delivery App (Open) ---
        ("p_mobile_app", "dev_george", 12500, "Senior Flutter developer. Published 7 apps on App Store & Google Play with real-time GPS tracking.", False),
        ("p_mobile_app", "dev_maya", 15000, "Experienced in real-time mobile interfaces, Firebase real-time database, and offline caching.", False),
        ("p_mobile_app", "dev_charlie", 16500, "Cross-platform engineer with deep background in dispatch algorithms and mobile APIs.", False),

        # --- Project: FinTech Stream (Open) ---
        ("p_fintech_stream", "dev_fiona", 18000, "Go and high-concurrency network engineer. Built financial market feeds with zero allocation designs.", False),
        ("p_fintech_stream", "dev_hannah", 22000, "High-performance systems engineer. Expert in lockless concurrency and low-latency socket pipelines.", False),
        ("p_fintech_stream", "dev_alice", 15000, "Proficient in backend data streaming, AWS infrastructure, and scalable socket architectures.", False),

        # --- Project: Telehealth Portal (Open) ---
        ("p_telehealth", "dev_alice", 18500, "Healthcare systems engineer. Experienced with HIPAA compliance, encrypted databases, and video services.", False),
        ("p_telehealth", "dev_kevin", 22000, "Security engineer with deep cryptography and healthcare access-control background.", False),
        ("p_telehealth", "dev_charlie", 19000, "Full-stack developer adept with patient records security and WebRTC physician dashboards.", False),

        # --- Project: EdTech Portal (Open) ---
        ("p_edtech_portal", "dev_ian", 6200, "Vue 3 and TypeScript advocate. Built interactive quiz modules and educational learning portals.", False),
        ("p_edtech_portal", "dev_evan", 4800, "Passionate about interactive frontend experiences and accessible learning interfaces.", False),
        ("p_edtech_portal", "dev_bob", 7500, "Strong frontend developer with Node.js backend experience for code evaluation sandboxes.", False),

        # --- Project: Cloud Infra (Open) ---
        ("p_cloud_infra", "dev_leo", 9500, "DevOps architect with 6 years AWS/Terraform experience. Built zero-downtime multi-region systems.", False),
        ("p_cloud_infra", "dev_fiona", 11500, "Kubernetes and cloud infrastructure specialist. EKS clustering and CI/CD automation are core skills.", False),
        ("p_cloud_infra", "dev_kevin", 12500, "DevSecOps engineer. I ensure all Terraform modules adhere to CIS benchmarks and security standards.", False),

        # --- Project: GraphQL Gateway (IN PROGRESS) ---
        ("p_graphql_gw", "dev_charlie", 8200, "I've handled 4 REST-to-GraphQL schema migrations. Apollo federation and Redis caching included.", True),
        ("p_graphql_gw", "dev_alice", 9500, "Python and GraphQL specialist. Can build clean strawberry/ariadne microservice federations.", False),
        ("p_graphql_gw", "dev_maya", 10200, "Expert with GraphQL client-server architectures and high-performance schema design.", False),

        # --- Project: Security Audit (IN PROGRESS) ---
        ("p_sec_audit", "dev_kevin", 11500, "Certified ethical hacker (OSCP). Thorough penetration testing, code review, and remediation guide.", True),
        ("p_sec_audit", "dev_hannah", 13000, "Systems security researcher. Deep expertise in memory safety, token validation, and binary inspection.", False),
        ("p_sec_audit", "dev_alice", 9800, "Backend security reviewer with expertise in FastAPI auth hardening and database injection defenses.", False),

        # --- Project: Data Pipeline (IN PROGRESS) ---
        ("p_data_pipe", "dev_julia", 14000, "Big Data engineer with 5 years Spark/Kafka streaming experience. Built resilient Snowflake pipelines.", True),
        ("p_data_pipe", "dev_fiona", 16500, "Cloud data architect. Expertise in AWS Kinesis, EMR, and scalable streaming workers.", False),
        ("p_data_pipe", "dev_diana", 17000, "Data science and pipeline specialist. Handles high-velocity financial streams with Pandas and Spark.", False),

        # --- Project: Fitness Mobile (IN PROGRESS) ---
        ("p_fitness_mobile", "dev_george", 7800, "React Native and Firebase expert. Delivered 4 fitness and wellness applications on both app stores.", True),
        ("p_fitness_mobile", "dev_maya", 9200, "Mobile UI engineer with React Native, Supabase, and real-time state synchronization mastery.", False),
        ("p_fitness_mobile", "dev_bob", 8400, "Cross-platform mobile developer with rich animation experience and sensor integrations.", False),

        # --- Project: Observability Stack (COMPLETED) ---
        ("p_observability", "dev_fiona", 9500, "Complete Prometheus, Grafana, Alertmanager, and Jaeger distributed tracing setup.", True),
        ("p_observability", "dev_leo", 10500, "DevOps monitoring lead. I deploy complete metrics and centralized logging solutions.", False),
        ("p_observability", "dev_alice", 8500, "Python microservice monitoring specialist with OpenTelemetry instrumentation.", False),

        # --- Project: Brand System (COMPLETED) ---
        ("p_brand_system", "dev_evan", 2800, "Comprehensive design system with Figma token export, accessible Tailwind components, and Storybook.", True),
        ("p_brand_system", "dev_olivia", 3800, "Senior UX designer. Complete UI kit, design guidelines, and production-ready component code.", False),

        # --- Project: Rust Resizer (COMPLETED) ---
        ("p_rust_resizer", "dev_hannah", 12000, "Ultra-fast image pipeline in Rust using image-rs, multithreaded Rayon, and Docker deployment.", True),
        ("p_rust_resizer", "dev_fiona", 13500, "Systems architect with Go/Rust experience for high-throughput containerized utilities.", False),

        # --- Project: Spring Monolith Split (COMPLETED) ---
        ("p_spring_split", "dev_noah", 16500, "Enterprise Java architect. Decomposed 3 monoliths into Spring Boot + Kafka event-driven services.", True),
        ("p_spring_split", "dev_alice", 18000, "Experienced enterprise backend engineer for domain-driven service decomposition.", False),
        ("p_spring_split", "dev_charlie", 19500, "Full-stack architect with relational database migration and message broker experience.", False),
    ]

    bid_count = 0
    accepted_bids_map = {}  # project_key -> Bid object

    for pkey, fuser, amount, proposal, is_accepted in bids_specs:
        project, _ = project_map[pkey]
        user, profile = freelancer_map[fuser]

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
        db.flush()  # assign bid.id
        bid_count += 1

        if is_accepted:
            accepted_bids_map[pkey] = bid

        status_marker = "🌟 ACCEPTED" if is_accepted else "  BID"
        print(f"  {status_marker} | {user.username:15} → {project.title[:30]:30}... | ${amount:5} | score={score:.3f}")

    # --- Transition In-Progress and Completed Projects ---
    print("\n🔄 Updating project lifecycles (In Progress / Completed)...")

    # In-Progress Projects: Accept the chosen bid
    for pkey, (project, target_status) in project_map.items():
        if target_status == "in_progress":
            accepted_bid = accepted_bids_map[pkey]
            project.accept_bid(accepted_bid.id)
            print(f"  ▶️  Project [{project.title[:35]}...] moved to IN_PROGRESS (Accepted: {accepted_bid.freelancer_id})")

    db.flush()

    # Completed Projects: Accept bid + dual confirmation
    completed_reviews = {
        "p_observability": (
            5,
            "Exceptional delivery! Fiona containerized all services, integrated Prometheus/Grafana alerts, and cut our deployment latency significantly. Highly recommended!"
        ),
        "p_brand_system": (
            5,
            "Evan delivered pixel-perfect Figma components and accessible Tailwind patterns ahead of schedule. Outstanding communication throughout the project."
        ),
        "p_rust_resizer": (
            5,
            "Incredible engineering. The Rust microservice easily processes 10,000+ images/min with negligible memory footprint. A true systems expert."
        ),
        "p_spring_split": (
            4,
            "Solid architecture and great test coverage throughout the claims service split. Noah is a dependable enterprise Java engineer."
        ),
    }

    for pkey, (project, target_status) in project_map.items():
        if target_status == "completed":
            accepted_bid = accepted_bids_map[pkey]
            project.accept_bid(accepted_bid.id)
            project.mark_completed_by("client")
            project.mark_completed_by("freelancer")

            score, review = completed_reviews[pkey]
            rating = Rating(
                project_id=project.id,
                freelancer_id=accepted_bid.freelancer_id,
                client_id=project.client_id,
                score=score,
                review=review,
            )
            db.add(rating)
            print(f"  ✅ Project [{project.title[:35]}...] COMPLETED & RATED ({score}★)")

    db.commit()

    # --- Summary ---
    print("\n" + "=" * 65)
    print("🎉 SEED COMPLETED SUCCESSFULLY!")
    print("=" * 65)
    print(f"👥 Clients:     {len(clients_info):2} users")
    print(f"🛠️  Freelancers: {len(freelancers_info):2} users with verified skills")
    print(f"📋 Projects:    {len(projects_specs):2} projects (10 Open, 4 In Progress, 4 Completed)")
    print(f"💰 Bids:        {bid_count:2} scored bids")
    print(f"⭐ Ratings:     {len(completed_reviews):2} verified reviews")
    print("-" * 65)
    print("🔑 All demo accounts use password: password123")
    print("\nRecommended Demo Logins:")
    print("  • Client Dashboard:     sarah_chen  or  alex_rivera  or  elena_rostova")
    print("  • Freelancer Dashboard: dev_alice   or  dev_charlie  or  dev_fiona")
    print("=" * 65)

    db.close()


if __name__ == "__main__":
    seed()
