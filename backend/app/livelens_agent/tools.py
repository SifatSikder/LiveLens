"""LiveLens Agent Tools — Function definitions for the Inspector Agent.

Tools implemented here are registered with the ADK Agent and invoked during
live inspection sessions via Gemini's function-calling mechanism.

Frame buffer
------------
Video frames arriving via the WebSocket upstream are stored in _frame_buffer
keyed by session_id.  inspection.py calls update_frame_buffer() whenever a
new image message is decoded.  The capture_frame tool reads from this buffer.
"""

import asyncio
import logging
import time
from typing import Any

from ddgs import DDGS
from google.adk.tools import ToolContext

from app.services import firestore as firestore_svc
from app.services import storage as storage_svc

# Import lazily inside the tool to avoid a circular import at module load time
# (report_agent imports tools indirectly via agent → tools → report_agent).
# The actual import is deferred to the first generate_report call.

logger = logging.getLogger(__name__)

# ── Per-session frame buffer
# {session_id: {"bytes": <bytes>, "ts": <float epoch>}}
_frame_buffer: dict[str, dict[str, Any]] = {}


def update_frame_buffer(session_id: str, frame_bytes: bytes) -> None:
    """Store the most recent video frame for a session.

    Called by the WebSocket upstream_task in inspection.py every time an image
    message is received from the frontend (≈1 FPS).

    Args:
        session_id: The active inspection session identifier.
        frame_bytes: Raw JPEG bytes decoded from the base64 WebSocket message.
    """
    _frame_buffer[session_id] = {"bytes": frame_bytes, "ts": time.monotonic()}


def clear_frame_buffer(session_id: str) -> None:
    """Remove the frame buffer entry when a session ends."""
    _frame_buffer.pop(session_id, None)


# Tool: search_web

async def search_web(query: str) -> dict[str, Any]:
    """Search the web for current information and return results with real URLs.

    Use this tool whenever the user asks about specific standards, codes, guidance
    documents, or technical references (e.g. BS EN 1504, CIRIA, ACI, ISO). This
    tool returns actual source URLs so you can cite them directly in your response.
    Always include the URLs from the results when answering — do not paraphrase
    without citing the source link.

    Args:
        query: A specific search query, e.g. "BS EN 1504-9 concrete repair
            principles crack classification site:bsigroup.com OR site:theconcretesociety.co.uk"

    Returns:
        Dict with a list of results, each containing title, url, and snippet.
    """
    try:
        results = await asyncio.to_thread(
            lambda: list(DDGS().text(query, max_results=5))
        )
        formatted = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:300],
            }
            for r in results
            if r.get("href")
        ]
        logger.info(f"search_web: query={repr(query)}, results={len(formatted)}")
        if not formatted:
            return {"status": "no_results", "results": []}
        return {"status": "ok", "results": formatted}
    except Exception as exc:
        logger.error(f"search_web error: {exc}", exc_info=True)
        return {"status": "error", "message": str(exc), "results": []}


# Tool: log_finding

async def log_finding(
    finding_type: str,
    severity: int,
    description: str,
    location_note: str,
    recommendation: str,
    tool_context: ToolContext,
    standard_reference: str = "",
) -> dict[str, Any]:
    """Log an infrastructure defect finding to the inspection database.

    Call this tool whenever you identify a defect worth documenting during an
    inspection session.  The finding is persisted in Firestore and a unique
    finding ID is returned for use with capture_frame.

    Args:
        finding_type: Category of defect. One of: crack, corrosion, water_damage,
            spalling, exposed_rebar, settlement, other.
        severity: Severity rating 1-5. 1=Minor, 2=Moderate, 3=Significant,
            4=Severe, 5=Critical.
        description: Detailed description of the observed defect including visible
            characteristics, extent, and any relevant measurements.
        location_note: Where on the structure (e.g. "north-facing wall, 1.5m above
            ground, left of the window frame").
        recommendation: Specific, actionable next step for remediation or monitoring.
        standard_reference: Optional reference to relevant standards or codes
            (e.g. "BS EN 1504-9", "ACI 224R").
        tool_context: ADK tool context — provides session and state access.

    Returns:
        Dict with finding_id and confirmation message.
    """
    session_id = tool_context.session.id

    finding_data = {
        "finding_type": finding_type,
        "severity": severity,
        "description": description,
        "location_note": location_note,
        "recommendation": recommendation,
        "standard_reference": standard_reference,
    }

    try:
        finding_id = await firestore_svc.save_finding(session_id, finding_data)
        logger.info(f"log_finding: saved {finding_id} (severity={severity}, type={finding_type})")
        return {
            "status": "logged",
            "finding_id": finding_id,
            "message": (
                f"Finding {finding_id} logged successfully. "
                f"Type: {finding_type}, Severity: {severity}/5."
            ),
        }
    except Exception as exc:
        logger.error(f"log_finding error: {exc}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to log finding: {exc}",
        }


# Tool: capture_frame

async def capture_frame(
    reason: str,
    tool_context: ToolContext,
    finding_id: str = "",
) -> dict[str, Any]:
    """Capture and save the current video frame as visual evidence.

    Call this tool immediately after (or alongside) log_finding when you want
    to preserve a photographic record of the defect.  The frame is uploaded to
    Cloud Storage and, if a finding_id is provided, the image URL is linked to
    that finding document.

    Args:
        reason: Brief description of why this frame is being captured
            (e.g. "wide crack on north wall pier").
        finding_id: Optional finding document ID returned by log_finding.  When
            provided, the image URL is written back to the finding record.
        tool_context: ADK tool context — provides session and state access.

    Returns:
        Dict with image_url and capture confirmation, or error details.
    """
    session_id = tool_context.session.id

    entry = _frame_buffer.get(session_id)
    if not entry:
        return {
            "status": "error",
            "message": "No video frame available. Ensure the camera is streaming.",
        }

    frame_bytes: bytes = entry["bytes"]
    age_s = time.monotonic() - entry["ts"]
    if age_s > 5.0:
        logger.warning(f"capture_frame: frame is {age_s:.1f}s old for session={session_id}")

    label = finding_id if finding_id else f"frame_{int(time.time())}"

    try:
        image_url = await storage_svc.upload_frame(session_id, frame_bytes, label=label)

        # If linked to a finding, update Firestore record
        if finding_id:
            await firestore_svc.update_finding_image(session_id, finding_id, image_url)

        logger.info(f"capture_frame: uploaded {image_url} (age={age_s:.1f}s, linked={finding_id or 'none'})")
        return {
            "status": "captured",
            "image_url": image_url,
            "finding_id": finding_id or None,
            "frame_age_seconds": round(age_s, 2),
            "message": (
                f"Frame captured and saved. "
                + (f"Linked to finding {finding_id}." if finding_id else "")
            ),
        }
    except Exception as exc:
        logger.error(f"capture_frame error: {exc}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to capture frame: {exc}",
        }


# Tool: generate_report (Task 2.3)

async def generate_report(tool_context: ToolContext) -> dict[str, Any]:
    """Generate a full inspection report for the current session.

    Call this tool when the user asks to generate, create, or produce an
    inspection report (e.g. "Generate the report", "Create my report",
    "I'm done — make the report").

    This tool:
    1. Counts all findings logged so far for the session.
    2. Calls the Report Generator Agent (Gemini 2.5 Flash) to synthesise a
       structured JSON report from those findings.
    3. Generates a professional PDF and uploads it to Cloud Storage.
    4. Returns the report summary and a PDF download link for the frontend.

    Before calling, you should confirm verbally with the user:
    "I've logged N findings for this session. Generating your inspection
    report now — this will take a few seconds."

    Args:
        tool_context: ADK tool context — provides session and state access.

    Returns:
        Dict with status, finding_count, report_id, pdf_url (if available),
        executive_summary snippet, and a human-readable message for the agent
        to read aloud to the user.
    """
    # Deferred import to avoid circular dependency at module load time.
    # agent.py → tools.py → report_agent.py → tools (indirectly via firestore_svc)
    from app.livelens_agent.report_agent import generate_inspection_report  # noqa: PLC0415

    session_id = tool_context.session.id
    logger.info(f"generate_report tool invoked: session={session_id}")

    # ── 1. Count current findings for the user-facing confirmation message ────
    try:
        findings = await firestore_svc.get_session_findings(session_id)
        finding_count = len(findings)
    except Exception as exc:
        logger.error(f"generate_report: failed to count findings: {exc}", exc_info=True)
        finding_count = 0

    if finding_count == 0:
        return {
            "status": "empty",
            "finding_count": 0,
            "message": (
                "No findings have been logged for this session yet. "
                "Please inspect the structure and log at least one finding before generating a report."
            ),
        }

    # ── 2. Generate JSON report + PDF ─────────────────────────────────────────
    try:
        report = await generate_inspection_report(session_id)
    except Exception as exc:
        logger.error(f"generate_report: report generation failed: {exc}", exc_info=True)
        return {
            "status": "error",
            "finding_count": finding_count,
            "message": f"Report generation failed: {exc}",
        }

    # ── 3. Build a concise result for the agent to relay to the user ──────────
    pdf_url = report.get("pdf_url")
    report_id = report.get("report_id", "")
    summary = report.get("executive_summary", "")
    # Trim summary to ~200 chars so the agent can read a brief snippet aloud
    summary_snippet = (summary[:200] + "…") if len(summary) > 200 else summary

    if pdf_url:
        message = (
            f"Your inspection report is ready. I logged {finding_count} finding(s) "
            f"during this session. {summary_snippet} "
            f"The PDF report is available for download."
        )
    else:
        message = (
            f"Your inspection report has been generated with {finding_count} finding(s). "
            f"{summary_snippet} "
            f"Note: PDF download is not available — Cloud Storage may not be configured."
        )

    logger.info(
        f"generate_report: complete — session={session_id}, findings={finding_count}, "
        f"report_id={report_id}, pdf={'yes' if pdf_url else 'no'}"
    )
    return {
        "status": report.get("status", "ok"),
        "finding_count": finding_count,
        "report_id": report_id,
        "pdf_url": pdf_url,
        "executive_summary_snippet": summary_snippet,
        "message": message,
    }
