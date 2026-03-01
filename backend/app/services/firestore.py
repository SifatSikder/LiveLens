"""Firestore service for storing inspection findings and session data.

Collections layout:
  inspections/{session_id}                    — session metadata
  inspections/{session_id}/findings/{id}      — individual defect findings
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore_v1.async_client import AsyncClient

from app.config import get_settings

logger = logging.getLogger(__name__)

_db: AsyncClient | None = None


def _get_db() -> AsyncClient:
    """Lazy-init the Firestore async client (singleton)."""
    global _db
    if _db is None:
        settings = get_settings()
        _db = AsyncClient(project=settings.google_cloud_project)
        logger.info(f"Firestore AsyncClient initialised (project={settings.google_cloud_project})")
    return _db


async def save_finding(session_id: str, finding_data: dict[str, Any]) -> str:
    """Persist a new inspection finding under the given session.

    Args:
        session_id: The active inspection session identifier.
        finding_data: Dict containing finding fields (type, severity, description, …).

    Returns:
        The generated finding document ID (e.g. "F-abc123").
    """
    db = _get_db()
    settings = get_settings()

    finding_id = f"F-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "finding_id": finding_id,
        "session_id": session_id,
        "created_at": now,
        "image_url": None,
        **finding_data,
    }

    ref = (
        db.collection(settings.firestore_collection)
        .document(session_id)
        .collection("findings")
        .document(finding_id)
    )
    await ref.set(doc)
    logger.info(f"Finding saved: session={session_id}, finding={finding_id}, severity={finding_data.get('severity')}")
    return finding_id


async def update_finding_image(session_id: str, finding_id: str, image_url: str) -> None:
    """Attach a Cloud Storage image URL to an existing finding.

    Args:
        session_id: The active inspection session identifier.
        finding_id: The finding document ID to update.
        image_url: Public or signed GCS URL for the captured frame.
    """
    db = _get_db()
    settings = get_settings()

    ref = (
        db.collection(settings.firestore_collection)
        .document(session_id)
        .collection("findings")
        .document(finding_id)
    )
    await ref.update({"image_url": image_url, "image_captured_at": datetime.now(timezone.utc).isoformat()})
    logger.info(f"Finding image updated: finding={finding_id}, url={image_url[:60]}")


async def get_session_findings(session_id: str) -> list[dict[str, Any]]:
    """Retrieve all findings for a session, ordered by creation time.

    Args:
        session_id: The inspection session identifier.

    Returns:
        List of finding dicts, oldest first.
    """
    db = _get_db()
    settings = get_settings()

    col_ref = (
        db.collection(settings.firestore_collection)
        .document(session_id)
        .collection("findings")
        .order_by("created_at")
    )

    findings = []
    async for doc in col_ref.stream():
        findings.append(doc.to_dict())

    logger.info(f"Retrieved {len(findings)} findings for session={session_id}")
    return findings

