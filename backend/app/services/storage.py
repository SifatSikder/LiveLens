"""Cloud Storage service for uploading captured inspection frame images and PDFs.

Uses the synchronous google-cloud-storage client wrapped in asyncio.to_thread
since the library does not provide a native async API.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

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


def _upload_pdf_sync(
    bucket_name: str, blob_name: str, pdf_bytes: bytes, expiration_minutes: int
) -> str:
    """Synchronous PDF upload + signed-URL generation — called via asyncio.to_thread.

    Attempts to generate a v4 signed URL (requires a service account key or
    Application Default Credentials with signing capability).  Falls back to
    the public HTTPS URL if signing is unavailable (e.g. Workload Identity
    environments where the default SA cannot sign blobs without explicit IAM
    permission).

    Args:
        bucket_name:        GCS bucket to upload to.
        blob_name:          Full object path within the bucket.
        pdf_bytes:          Raw PDF bytes.
        expiration_minutes: Signed URL TTL in minutes.

    Returns:
        HTTPS URL (signed or public) to the uploaded PDF.
    """
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")

    try:
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )
        logger.info(f"Signed URL generated for {blob_name} (TTL={expiration_minutes}m)")
        return signed_url
    except Exception as sign_exc:
        # Workload Identity / metadata-server environments may not support signing
        logger.warning(
            "Signed URL generation failed (%s); falling back to public URL. "
            "Grant 'roles/iam.serviceAccountTokenCreator' to the SA to enable signing.",
            sign_exc,
        )
        # Make object publicly readable as a fallback
        try:
            blob.make_public()
            public_url = blob.public_url
            logger.info(f"PDF made public: {public_url}")
            return public_url
        except Exception as pub_exc:
            logger.error("Could not make PDF public: %s", pub_exc)
            # Return gs:// URI as last resort — at least the file was uploaded
            return f"gs://{bucket_name}/{blob_name}"


async def upload_pdf(session_id: str, report_id: str, pdf_bytes: bytes,
                     expiration_minutes: int = 60) -> str:
    """Upload a generated PDF report to Cloud Storage and return an HTTPS URL.

    The PDF is stored at:
        {gcs_reports_prefix}/{session_id}/{report_id}_{timestamp}.pdf

    Args:
        session_id:         Inspection session identifier (path component).
        report_id:          Report document ID (used in blob name for uniqueness).
        pdf_bytes:          Raw PDF bytes to upload.
        expiration_minutes: Signed URL TTL in minutes (default 60).

    Returns:
        HTTPS signed URL (or public URL fallback) for the uploaded PDF.

    Raises:
        ValueError: If GCS_BUCKET_NAME is not configured.
    """
    settings = get_settings()
    if not settings.gcs_bucket_name:
        raise ValueError("GCS_BUCKET_NAME is not configured in environment")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    blob_name = f"{settings.gcs_reports_prefix}/{session_id}/{report_id}_{timestamp}.pdf"

    url = await asyncio.to_thread(
        _upload_pdf_sync,
        settings.gcs_bucket_name,
        blob_name,
        pdf_bytes,
        expiration_minutes,
    )
    logger.info(f"PDF uploaded: session={session_id}, report={report_id}, size={len(pdf_bytes)} bytes")
    return url

