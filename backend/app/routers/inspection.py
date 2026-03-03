"""WebSocket endpoint for LiveLens bidi-streaming inspection sessions.

Follows the official ADK bidi-demo pattern:
1. Application Init: Agent + SessionService + Runner (singletons)
2. Per-connection: RunConfig + LiveRequestQueue + Session
3. Concurrent upstream/downstream tasks via asyncio.gather()
4. Graceful cleanup via queue.close() in finally block
"""

import asyncio
import base64
import json
import logging
import traceback

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from google.adk.agents import LiveRequestQueue
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from google.genai import errors as genai_errors

from app.livelens_agent.agent import root_agent
from app.livelens_agent.report_agent import generate_inspection_report
from app.livelens_agent.tools import clear_frame_buffer, update_frame_buffer
from app.services import firestore as firestore_svc
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

APP_NAME = "livelens"

session_service = InMemorySessionService()

runner = Runner(
    app_name=APP_NAME,
    agent=root_agent,
    session_service=session_service,
)

logger.info(f"ADK Runner initialized: app={APP_NAME}, agent={root_agent.name}")


def _build_run_config() -> RunConfig:
    """Build RunConfig for native-audio bidi-streaming with video input.

    LiveLens uses gemini-live-2.5-flash-native-audio which supports:
    - Audio input/output (voice conversation)
    - Video input at 1 FPS
    - Function calling (tools)
    - Context window compression for unlimited sessions
    """
    settings = get_settings()
    model_name = settings.live_model.lower()
    is_native_audio = "native-audio" in model_name

    if is_native_audio:
        # Native audio model: respond with AUDIO, enable transcription
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Orus"
                    )
                )
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            # Session resumption — handles 10-min WebSocket connection limits
            session_resumption=types.SessionResumptionConfig(
                handle=None,
            ),
            # Context window compression — CRITICAL for audio+video sessions.
            # Without this, video+audio sessions are capped at ~2 minutes.
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),  # Uses API defaults for target_tokens
            ),
            # VAD — let Gemini detect when the user stops speaking
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                ),
            ),
        )
    else:
        # Half-cascade or text model: respond with TEXT
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["TEXT"],
            session_resumption=types.SessionResumptionConfig(
                handle=None,
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
        )

    return run_config


@router.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
):
    """Main WebSocket endpoint for LiveLens bidi-streaming sessions.

    URL pattern: /ws/{user_id}/{session_id}
    - user_id: unique user identifier
    - session_id: inspection session identifier (reuse for session resumption)

    Upstream (client → agent):
      - JSON text messages: {"type": "text", "content": "..."}
      - JSON image messages: {"type": "image", "data": "<base64>", "mime_type": "image/jpeg"}
      - Binary messages: raw PCM audio (16-bit, 16kHz, mono)

    Downstream (agent → client):
      - JSON events from runner.run_live() serialized via event.model_dump_json()
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: user={user_id}, session={session_id}")

    # Get or create ADK session
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        logger.info(f"Created new session: {session_id}")
    else:
        logger.info(f"Resumed existing session: {session_id}")

    # Persist session metadata to Firestore for inspection history (Task 2.4)
    try:
        await firestore_svc.save_session(session_id, {"user_id": user_id})
    except Exception as e:
        logger.warning(f"Failed to save session metadata: {e}")

    # Build RunConfig for native-audio streaming
    run_config = _build_run_config()

    # Create the message queue for this connection
    live_request_queue = LiveRequestQueue()

    async def upstream_task():
        """Receive messages from WebSocket client → send to LiveRequestQueue."""
        try:
            while True:
                try:
                    # Try text message first
                    raw = await websocket.receive()
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected: {user_id}/{session_id}")
                    break
                except RuntimeError as e:
                    # WebSocket already closed (e.g. downstream task closed it first)
                    logger.debug(f"Upstream receive stopped: {e}")
                    break

                if "text" in raw:
                    # Parse JSON text message
                    try:
                        msg = json.loads(raw["text"])
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from client: {raw['text'][:100]}")
                        continue

                    msg_type = msg.get("type", "text")

                    if msg_type == "text":
                        # Text content → send_content
                        text = msg.get("content", "")
                        if text:
                            content = types.Content(
                                role="user",
                                parts=[types.Part.from_text(text=text)],
                            )
                            live_request_queue.send_content(content)
                            logger.debug(f"Sent text: {text[:80]}")

                    elif msg_type == "image":
                        # Image/video frame → send_realtime as blob
                        img_data = msg.get("data", "")
                        mime_type = msg.get("mime_type", "image/jpeg")
                        if img_data:
                            decoded = base64.b64decode(img_data)
                            # Keep most recent frame available for capture_frame tool
                            update_frame_buffer(session_id, decoded)
                            blob = types.Blob(
                                mime_type=mime_type,
                                data=decoded,
                            )
                            live_request_queue.send_realtime(blob)
                            logger.debug(f"Sent image frame: {len(decoded)} bytes")

                elif "bytes" in raw:
                    # Binary message = raw PCM audio (16-bit, 16kHz, mono)
                    audio_bytes = raw["bytes"]
                    if audio_bytes:
                        blob = types.Blob(
                            mime_type="audio/pcm;rate=16000",
                            data=audio_bytes,
                        )
                        live_request_queue.send_realtime(blob)

        except Exception as e:
            logger.error(f"Upstream error: {e}\n{traceback.format_exc()}")

    async def downstream_task():
        """Receive events from runner.run_live() → send to WebSocket client."""
        try:
            async for event in runner.run_live(
                session=session,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                # Serialize event to JSON and send to client
                try:
                    event_json = event.model_dump_json(exclude_none=True)

                    # Check if WebSocket is still open before sending
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_text(event_json)
                    else:
                        logger.warning("WebSocket closed, stopping downstream")
                        break

                except Exception as send_err:
                    logger.error(f"Error sending event: {send_err}")
                    break

        except genai_errors.APIError as e:
            logger.error(f"Downstream error: {e}\n{traceback.format_exc()}")
            # Notify the frontend so it can show an error banner
            try:
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_text(json.dumps({
                        "type": "session_error",
                        "code": e.status_code,
                        "message": str(e),
                    }))
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Downstream error: {e}\n{traceback.format_exc()}")

    # Run both tasks concurrently
    try:
        await asyncio.gather(
            upstream_task(),
            downstream_task(),
            return_exceptions=False,
        )
    except Exception as e:
        logger.error(f"Session error: {e}\n{traceback.format_exc()}")
    finally:
        live_request_queue.close()
        clear_frame_buffer(session_id)
        logger.info(f"Session ended: {user_id}/{session_id}")

        try:
            await websocket.close()
        except Exception:
            pass


# ── Task 2.1: Report Generator REST endpoints ─────────────────────────────────


@router.post("/inspection/{session_id}/report")
async def trigger_report_generation(session_id: str):
    """Generate an inspection report for a completed session (Task 2.1).

    Fetches all findings logged during the session from Firestore, calls
    Gemini 2.5 Flash (non-live) to synthesise a structured JSON report, and
    persists it.  Returns the full structured report as JSON.

    Args:
        session_id: Inspection session identifier matching the WebSocket session.

    Returns:
        Structured JSON report with executive_summary, findings (sorted by
        severity), summary_statistics, recommendations, and disclaimer.
    """
    logger.info(f"Report generation requested: session={session_id}")
    try:
        report = await generate_inspection_report(session_id)
        return report
    except Exception as exc:
        logger.error(
            f"Report generation failed: session={session_id}, error={exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {exc}",
        )


@router.get("/inspection/{session_id}/report")
async def get_report(session_id: str):
    """Fetch the most recently generated inspection report for a session.

    Args:
        session_id: Inspection session identifier.

    Returns:
        The latest report dict from Firestore.

    Raises:
        404: If no report has been generated yet for this session.
    """
    logger.info(f"Report fetch requested: session={session_id}")
    report = await firestore_svc.get_session_report(session_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No report found for this session. "
                "POST to /inspection/{session_id}/report to generate one."
            ),
        )
    return report


@router.get("/inspection/{session_id}/findings")
async def get_findings(session_id: str):
    """Fetch all logged findings for an inspection session.

    Useful for debugging, testing report generation, and the frontend
    dashboard (Task 2.4 / Task 3.2).

    Args:
        session_id: Inspection session identifier.

    Returns:
        Dict with session_id, count, and list of finding dicts.
    """
    logger.info(f"Findings fetch requested: session={session_id}")
    findings = await firestore_svc.get_session_findings(session_id)
    return {
        "session_id": session_id,
        "count": len(findings),
        "findings": findings,
    }


@router.get("/inspection/{session_id}/report/pdf")
async def get_report_pdf_url(session_id: str):
    """Return the PDF download URL for the most recent inspection report (Task 2.2).

    The pdf_url is stored on the report document in Firestore after the PDF
    is generated and uploaded to Cloud Storage by the Report Generator Agent.

    Args:
        session_id: Inspection session identifier.

    Returns:
        Dict with session_id, report_id, and pdf_url (HTTPS signed URL).

    Raises:
        404: If no report has been generated yet.
        409: If a report exists but PDF generation has not completed yet.
    """
    logger.info(f"PDF URL fetch requested: session={session_id}")
    report = await firestore_svc.get_session_report(session_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No report found for this session. "
                "POST to /inspection/{session_id}/report to generate one."
            ),
        )
    pdf_url = report.get("pdf_url")
    if not pdf_url:
        raise HTTPException(
            status_code=409,
            detail=(
                "Report exists but PDF is not yet available. "
                "This may indicate GCS is not configured or PDF generation failed. "
                f"pdf_error: {report.get('pdf_error', 'unknown')}"
            ),
        )
    return {
        "session_id": session_id,
        "report_id": report.get("report_id"),
        "pdf_url": pdf_url,
        "pdf_generated_at": report.get("pdf_generated_at"),
    }


@router.get("/inspections")
async def list_inspections(limit: int = 50):
    """List all inspection sessions ordered by start time, newest first (Task 2.4).

    Returns a summary of every session that has been started via the WebSocket
    endpoint.  Sessions are persisted the moment a WebSocket connection is
    established, so this list reflects both active and completed sessions.

    Args:
        limit: Maximum number of sessions to return (default 50, max enforced
               by Firestore query).

    Returns:
        Dict with count and list of session metadata dicts.
    """
    logger.info(f"Listing inspections (limit={limit})")
    sessions = await firestore_svc.get_all_sessions(limit=limit)
    return {"count": len(sessions), "sessions": sessions}


@router.get("/inspection/{session_id}/session")
async def get_session_metadata(session_id: str):
    """Return metadata for a single inspection session (Task 2.4).

    Args:
        session_id: Inspection session identifier.

    Returns:
        Session metadata dict (started_at, status, finding_count, report_url, …).

    Raises:
        404: If the session does not exist in Firestore.
    """
    logger.info(f"Session metadata fetch: session={session_id}")
    session = await firestore_svc.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )
    return session
