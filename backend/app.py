"""
FastAPI application factory.

Creates the app, registers all routers, adds CORS middleware,
and initializes the database on startup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import auth, projects, bids, freelancers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="Freelance Marketplace Bidding Engine",
    description=(
        "A platform where clients post projects, freelancers bid, "
        "and a ranking engine scores bids on fit — not just lowest price."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow the frontend (served from same origin or file://) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Register routers ---
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(bids.router)
app.include_router(freelancers.router)


# Health check
@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# Serve frontend static files (must be LAST — catches all unmatched routes)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

