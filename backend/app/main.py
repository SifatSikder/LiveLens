"""LiveLens — Real-Time Field Infrastructure Inspector.

FastAPI backend with WebSocket support for ADK bidi-streaming.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"GCP Project: {settings.google_cloud_project}")
    logger.info(f"Live Model: {settings.live_model}")
    logger.info(f"Vertex AI: {settings.google_genai_use_vertexai}")
    yield
    logger.info("Shutting down LiveLens")


app = FastAPI(
    title="LiveLens API",
    description="Real-Time Field Infrastructure Inspector powered by Gemini Live API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/")
async def root():
    return {
        "message": "LiveLens API — Real-Time Field Infrastructure Inspector",
        "docs": "/docs",
        "health": "/health",
        "ws": "/ws/{user_id}/{session_id}",
    }


# Register WebSocket router
from app.routers.inspection import router as inspection_router

app.include_router(inspection_router)
