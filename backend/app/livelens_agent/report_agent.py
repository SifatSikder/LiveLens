"""Report Generator Agent — Non-live Gemini 2.5 Flash report synthesis.

This module implements Task 2.1 of the LiveLens implementation plan.

Unlike the Inspector Agent (which uses Gemini Live API for real-time
audio+video), the Report Generator Agent makes a single, standard
generate_content call to Gemini 2.5 Flash.

Data flow:
  1. Fetch all findings for a session from Firestore
  2. Build a structured prompt with the findings JSON
  3. Call Gemini 2.5 Flash with response_mime_type="application/json"
  4. Parse + validate the structured report JSON
  5. Persist the report to Firestore
  6. Return the full report dict to the caller
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings
from app.livelens_agent.prompts import REPORT_GENERATOR_INSTRUCTION
from app.services import firestore as firestore_svc
from app.services import storage as storage_svc
from app.services.pdf_gen import generate_pdf

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    """Lazy-init genai client (singleton).

    Supports both Vertex AI (production) and AI Studio (development)
    based on the GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_API_KEY env vars.
    """
    global _client
    if _client is None:
        settings = get_settings()
        if settings.google_genai_use_vertexai:
            _client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
            logger.info(
                "Report Agent: Vertex AI client (project=%s, location=%s)",
                settings.google_cloud_project,
                settings.google_cloud_location,
            )
        else:
            api_key = os.getenv("GOOGLE_API_KEY", "")
            _client = genai.Client(api_key=api_key)
            logger.info("Report Agent: AI Studio client")
    return _client


async def generate_inspection_report(session_id: str) -> dict[str, Any]:
    """Generate a structured JSON inspection report from all logged findings.

    Fetches every finding logged for the session from Firestore, then
    calls Gemini 2.5 Flash to synthesise a professional inspection report
    in the structured JSON format defined by REPORT_GENERATOR_INSTRUCTION.

    Args:
        session_id: Active inspection session identifier (Firestore key).

    Returns:
        Structured report dict.  Always contains at minimum:
          - status: "ok" | "empty" | "parse_error"
          - session_id
          - generated_at (ISO-8601 UTC)
        On success also contains the full report schema fields:
          executive_summary, inspection_details, findings,
          summary_statistics, recommendations, disclaimer.

    Raises:
        Exception: Re-raises any google-genai / network errors so the
            FastAPI endpoint can return a 500 with the original message.
    """
    settings = get_settings()

    # ── 1. Fetch findings ─────────────────────────────────────────────────────
    findings = await firestore_svc.get_session_findings(session_id)
    logger.info(
        "Report generation started: session=%s, findings=%d",
        session_id,
        len(findings),
    )

    if not findings:
        logger.warning("No findings found for session=%s", session_id)
        return {
            "status": "empty",
            "message": (
                "No findings have been logged for this inspection session. "
                "Start an inspection and log at least one finding before generating a report."
            ),
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── 2. Build prompt ───────────────────────────────────────────────────────
    findings_json = json.dumps(findings, indent=2, default=str)
    user_prompt = (
        f"Generate a comprehensive inspection report for session ID: {session_id}.\n\n"
        f"The following {len(findings)} finding(s) were recorded during the inspection:\n\n"
        f"{findings_json}\n\n"
        "Generate the full JSON report strictly following the structure in your instructions. "
        "Prioritise findings by severity (highest first) and ensure all recommendations are "
        "specific and actionable."
    )

    # ── 3. Call Gemini 2.5 Flash (non-live, structured JSON output) ───────────
    client = _get_genai_client()
    response = await client.aio.models.generate_content(
        model=settings.report_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=REPORT_GENERATOR_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,  # Deterministic output for professional reports
        ),
    )

    # ── 4. Parse JSON response ────────────────────────────────────────────────
    raw_text = (response.text or "").strip()
    try:
        report_data: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error(
            "Failed to parse report JSON: %s | Raw (first 500 chars): %s",
            exc,
            raw_text[:500],
        )
        return {
            "status": "parse_error",
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "raw_response": raw_text[:2000],
        }

    # ── 5. Enrich with session metadata ───────────────────────────────────────
    generated_at = datetime.now(timezone.utc).isoformat()
    report_data.update(
        {
            "status": "ok",
            "session_id": session_id,
            "generated_at": generated_at,
            "finding_count": len(findings),
        }
    )

    # ── 6. Persist to Firestore ───────────────────────────────────────────────
    report_id = await firestore_svc.save_report(session_id, report_data)
    report_data["report_id"] = report_id
    logger.info(
        "Report saved: session=%s, report_id=%s, findings=%d",
        session_id,
        report_id,
        len(findings),
    )

    # ── 7. Generate PDF and upload to Cloud Storage ───────────────────────────
    pdf_url: str | None = None
    try:
        settings = get_settings()
        if settings.gcs_bucket_name:
            pdf_bytes = await asyncio.to_thread(generate_pdf, report_data, session_id)
            pdf_url = await storage_svc.upload_pdf(session_id, report_id, pdf_bytes)
            await firestore_svc.update_report_pdf_url(session_id, report_id, pdf_url)
            report_data["pdf_url"] = pdf_url
            logger.info("PDF uploaded: session=%s, report=%s, url=%s", session_id, report_id, pdf_url)
        else:
            logger.warning(
                "GCS_BUCKET_NAME not configured — skipping PDF upload for session=%s", session_id
            )
            report_data["pdf_url"] = None
    except Exception as pdf_exc:
        # PDF generation is non-fatal: return the JSON report even if PDF fails
        logger.error(
            "PDF generation/upload failed for session=%s: %s", session_id, pdf_exc, exc_info=True
        )
        report_data["pdf_url"] = None
        report_data["pdf_error"] = str(pdf_exc)

    # ── 8. Update top-level session document with stats (Task 2.4) ────────────
    try:
        await firestore_svc.update_session_stats(
            session_id=session_id,
            finding_count=len(findings),
            report_id=report_id,
            pdf_url=report_data.get("pdf_url"),
        )
    except Exception as stats_exc:
        # Non-fatal: session stats update should not block report delivery
        logger.warning(
            "Failed to update session stats for session=%s: %s", session_id, stats_exc
        )

    return report_data

