"""Cloud Storage service for uploading captured inspection frame images.

Uses the synchronous google-cloud-storage client wrapped in asyncio.to_thread
since the library does not provide a native async API.
"""

import asyncio
import logging
from datetime import datetime, timezone

from google.cloud import storage

from app.config import get_settings

logger = logging.getLogger(__name__)

_gcs_client: storage.Client | None = None


def _get_client() -> storage.Client:
    """Lazy-init the synchronous GCS client (singleton)."""
    global _gcs_client
    if _gcs_client is None:
        settings = get_settings()
        _gcs_client = storage.Client(project=settings.google_cloud_project)
        logger.info(f"GCS Client initialised (project={settings.google_cloud_project})")
    return _gcs_client


def _upload_sync(bucket_name: str, blob_name: str, data: bytes, content_type: str) -> str:
    """Synchronous upload — called via asyncio.to_thread."""
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)
    # Return the gs:// URI; generate a signed URL in Phase 2 if needed
    return f"gs://{bucket_name}/{blob_name}"


async def upload_frame(
    session_id: str,
    frame_bytes: bytes,
    label: str = "frame",
    content_type: str = "image/jpeg",
) -> str:
    """Upload a captured video frame to Cloud Storage.

    Args:
        session_id: Inspection session identifier (used as path prefix).
        frame_bytes: Raw JPEG image bytes to upload.
        label: Short label for the blob name (e.g. finding_id or "frame").
        content_type: MIME type of the image (default: image/jpeg).

    Returns:
        gs:// URI of the uploaded object.
    """
    settings = get_settings()
    if not settings.gcs_bucket_name:
        raise ValueError("GCS_BUCKET_NAME is not configured in environment")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    blob_name = f"{settings.gcs_images_prefix}/{session_id}/{label}_{timestamp}.jpg"

    uri = await asyncio.to_thread(
        _upload_sync,
        settings.gcs_bucket_name,
        blob_name,
        frame_bytes,
        content_type,
    )
    logger.info(f"Frame uploaded: {uri} ({len(frame_bytes)} bytes)")
    return uri

