"""
main.py — CodeSense Entry Point
==================================

This is the file that starts everything.

When you run: uvicorn main:app --reload --port 8000
    - "main" = this file (main.py)
    - "app"  = the FastAPI instance defined below
    - "--reload" = auto-restart when you change code (dev only)
    - "--port 8000" = serve on http://localhost:8000

FastAPI gives us:
    - A web server that handles HTTP requests
    - Automatic API documentation at /docs (Swagger UI)
    - Request validation using Pydantic models
    - Async support (important for calling GitHub's API without blocking)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.webhook import router as webhook_router
from routes.dashboard import router as dashboard_router

# Create the FastAPI app
# title: Shows up in the auto-generated docs at /docs
# description: Also for docs
# version: Track your API versions
app = FastAPI(
    title="CodeSense",
    description="AI-powered automated code reviewer for GitHub Pull Requests",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the webhook route
# prefix="/api" means the webhook URL becomes /api/webhook
# tags helps organize endpoints in the docs page
app.include_router(webhook_router, prefix="/api", tags=["GitHub Webhook"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])


@app.get("/")
def health_check():
    """
    Health check endpoint.
    
    Hit http://localhost:8000/ in your browser to verify the server is running.
    This is also useful for monitoring — if this stops responding,
    you know the server is down.
    """
    return {
        "status": "✅ CodeSense is running",
        "version": "0.1.0",
        "webhook_url": "/api/webhook",
        "docs": "/docs",
    }
