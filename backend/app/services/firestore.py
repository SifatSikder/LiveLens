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


async def save_report(session_id: str, report_data: dict[str, Any]) -> str:
    """Persist a generated inspection report to Firestore.

    Stored at: inspections/{session_id}/reports/{report_id}

    Args:
        session_id: The inspection session identifier.
        report_data: The full structured report dict produced by the
            Report Generator Agent.

    Returns:
        The generated report document ID (e.g. "R-abc12345").
    """
    db = _get_db()
    settings = get_settings()

    report_id = f"R-{uuid.uuid4().hex[:8]}"
    doc = {
        "report_id": report_id,
        "session_id": session_id,
        **report_data,
    }

    ref = (
        db.collection(settings.firestore_collection)
        .document(session_id)
        .collection("reports")
        .document(report_id)
    )
    await ref.set(doc)
    logger.info(f"Report saved: session={session_id}, report={report_id}")
    return report_id


async def get_session_report(session_id: str) -> dict[str, Any] | None:
    """Retrieve the most recently generated report for a session.

    Args:
        session_id: The inspection session identifier.

    Returns:
        The most recent report dict, or None if no reports exist.
    """
    db = _get_db()
    settings = get_settings()

    col_ref = (
        db.collection(settings.firestore_collection)
        .document(session_id)
        .collection("reports")
    )

    reports: list[dict[str, Any]] = []
    async for doc in col_ref.stream():
        reports.append(doc.to_dict())

    if not reports:
        logger.info(f"No reports found for session={session_id}")
        return None

    # Sort in Python — sessions have at most a handful of reports
    reports.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
    logger.info(f"Retrieved latest report for session={session_id}")
    return reports[0]


async def save_session(session_id: str, session_meta: dict[str, Any]) -> None:
    """Create or overwrite the top-level session metadata document.

    Stored at: inspections/{session_id}

    Called when a WebSocket inspection session starts so the session appears
    in the inspection history list even before any findings are logged.

    Args:
        session_id:   Inspection session identifier (also the document ID).
        session_meta: Dict containing at minimum ``started_at`` (ISO-8601 UTC).
                      May include ``user_id``, ``location``, etc.
    """
    db = _get_db()
    settings = get_settings()

    doc = {
        "session_id": session_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "finding_count": 0,
        "report_url": None,
        **session_meta,
    }
    ref = db.collection(settings.firestore_collection).document(session_id)
    await ref.set(doc, merge=True)
    logger.info(f"Session saved: session={session_id}")


async def update_session_stats(
    session_id: str,
    finding_count: int,
    report_id: str | None = None,
    pdf_url: str | None = None,
) -> None:
    """Update session-level stats after a report is generated.

    Patches finding_count, status, report_id, report_url, and completed_at
    on the top-level session document so the history list stays current.

    Args:
        session_id:    Inspection session identifier.
        finding_count: Total number of findings logged for the session.
        report_id:     Report document ID (optional).
        pdf_url:       PDF download URL (optional).
    """
    db = _get_db()
    settings = get_settings()

    update: dict[str, Any] = {
        "finding_count": finding_count,
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if report_id:
        update["report_id"] = report_id
    if pdf_url:
        update["report_url"] = pdf_url

    ref = db.collection(settings.firestore_collection).document(session_id)
    await ref.update(update)
    logger.info(
        f"Session stats updated: session={session_id}, findings={finding_count}, "
        f"report={report_id}, pdf={'yes' if pdf_url else 'no'}"
    )


async def get_all_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve all inspection sessions ordered by start time (newest first).

    Args:
        limit: Maximum number of sessions to return (default 50).

    Returns:
        List of session metadata dicts, newest first.
    """
    db = _get_db()
    settings = get_settings()

    col_ref = (
        db.collection(settings.firestore_collection)
        .order_by("started_at", direction="DESCENDING")
        .limit(limit)
    )

    sessions: list[dict[str, Any]] = []
    async for doc in col_ref.stream():
        sessions.append(doc.to_dict())

    logger.info(f"Retrieved {len(sessions)} inspection sessions")
    return sessions


async def get_session(session_id: str) -> dict[str, Any] | None:
    """Fetch the top-level session metadata document.

    Args:
        session_id: Inspection session identifier (document ID).

    Returns:
        Session metadata dict, or None if the document does not exist.
    """
    db = _get_db()
    settings = get_settings()

    ref = db.collection(settings.firestore_collection).document(session_id)
    snap = await ref.get()
    if not snap.exists:
        return None
    return snap.to_dict()


async def update_report_pdf_url(session_id: str, report_id: str, pdf_url: str) -> None:
    """Patch the pdf_url field on an existing report document.

    Called after PDF generation so the report document links to the
    downloadable PDF stored in Cloud Storage.

    Args:
        session_id: The inspection session identifier.
        report_id:  The report document ID (e.g. "R-abc12345").
        pdf_url:    HTTPS URL (signed or public) of the uploaded PDF.
    """
    db = _get_db()
    settings = get_settings()

    ref = (
        db.collection(settings.firestore_collection)
        .document(session_id)
        .collection("reports")
        .document(report_id)
    )
    await ref.update({"pdf_url": pdf_url, "pdf_generated_at": datetime.now(timezone.utc).isoformat()})
    logger.info(f"Report PDF URL saved: report={report_id}, url={pdf_url[:80]}")

