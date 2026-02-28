"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # App
    app_name: str = "LiveLens"
    app_version: str = "0.1.0"
    debug: bool = False

    # GCP
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True

    # Gemini Models
    live_model: str = "gemini-live-2.5-flash-native-audio"
    report_model: str = "gemini-2.5-flash"

    # Firestore
    firestore_collection: str = "inspections"

    # Cloud Storage
    gcs_bucket_name: str = ""
    gcs_images_prefix: str = "inspection-images"
    gcs_reports_prefix: str = "inspection-reports"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
