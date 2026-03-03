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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.adk.agents import LiveRequestQueue
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from google.genai import errors as genai_errors

from app.livelens_agent.agent import root_agent
from app.livelens_agent.tools import clear_frame_buffer, update_frame_buffer
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
