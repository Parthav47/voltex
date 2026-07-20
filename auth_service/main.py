"""
Auth service entry point.

This file:
  1. Initializes Django ORM (so models work)
  2. Creates the FastAPI app
  3. Mounts the auth router
  4. Starts the server when run directly

Run with:
  uvicorn main:app --reload --port 8001

Then visit: http://localhost:8001/docs
  → FastAPI auto-generates interactive API documentation from your code!
"""

import os
import django
from dotenv import load_dotenv

# Load .env BEFORE anything else
load_dotenv()

# Tell Django where settings are — MUST happen before any model imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django ORM — this sets up the DB connection pool
# Must run before importing any Django models
django.setup()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.users.routes import router as auth_router

# ──────────────────────────────────────────────
# Create FastAPI app
# ──────────────────────────────────────────────

app = FastAPI(
    title="Auth Service",
    description="Handles user registration, login, JWT tokens, and refresh logic.",
    version="1.0.0",
    # These tell FastAPI where to serve the auto-generated docs
    docs_url="/docs",
    redoc_url="/redoc",
)

# ──────────────────────────────────────────────
# CORS middleware
# ──────────────────────────────────────────────
# CORS = Cross-Origin Resource Sharing
# Without this, your React frontend (localhost:3000) cannot
# call your API (localhost:8001) — browsers block it by default.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
                   "http://192.168.0.126:3000",],  # React dev server and other allowed origins
    allow_credentials=True,                   # Required for cookies (refresh token)
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Mount routers
# ──────────────────────────────────────────────

app.include_router(auth_router)

# ──────────────────────────────────────────────
# Health check endpoint
# ──────────────────────────────────────────────
# Every service should have this. Your API gateway
# (and later, Docker health checks) will ping this
# to know if the service is alive.

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "auth"}


# ──────────────────────────────────────────────
# Run directly (development only)
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,    # Auto-restart on file changes during development
    )