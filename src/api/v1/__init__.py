"""FastAPI v1 API router and configuration."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os

from src.db import init_db, close_db
from src.utils import get_logger
from src.api.v1.routes import (
    auth_router,
    users_router,
    organizations_router,
    printers_router,
    jobs_router,
    materials_router,
    models_router,
    analytics_router,
)

logger = get_logger("api.v1")

# API configuration
API_TITLE = "Claude Fab Lab API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
Claude Fab Lab - AI-Powered 3D Printing Platform

## Features
- **Printer Management**: Control and monitor Bambu Labs printers
- **Print Queue**: Intelligent job scheduling and prioritization
- **Material Tracking**: Inventory management and compatibility checking
- **AI Generation**: Text-to-3D model generation
- **Analytics**: Real-time monitoring and insights

## Authentication
All endpoints require authentication via:
- **JWT Bearer Token**: `Authorization: Bearer <token>`
- **API Key**: `X-API-Key: <api_key>`

## Rate Limits
- Free tier: 100 requests/hour
- Pro tier: 1,000 requests/hour
- Enterprise: Unlimited
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Claude Fab Lab API...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down Claude Fab Lab API...")
    await close_db()
    logger.info("Database connection closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:9880").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(organizations_router, prefix="/api/v1/organizations", tags=["Organizations"])
    app.include_router(printers_router, prefix="/api/v1/printers", tags=["Printers"])
    app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["Print Jobs"])
    app.include_router(materials_router, prefix="/api/v1/materials", tags=["Materials"])
    app.include_router(models_router, prefix="/api/v1/models", tags=["3D Models"])
    app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])

    # Global exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "version": API_VERSION}

    @app.get("/api/v1/health", tags=["Health"])
    async def api_health_check():
        return {"status": "healthy", "version": API_VERSION}

    return app


# Create the app instance
app = create_app()
