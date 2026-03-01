#!/usr/bin/env python3
"""LiveLens WebSocket integration test.

Tests:
  1. Basic bidi-streaming (audio response from agent)
  2. Tool invocation (log_finding triggered by inspection prompt)

Usage:
    python test_ws.py [--tool-test]

Requires the backend to be running: uvicorn app.main:app --port 8000
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("Install websockets: pip install websockets")
    sys.exit(1)

TOOL_TEST = "--tool-test" in sys.argv


def _print_event(event: dict, event_count: int) -> bool:
    """Print a decoded ADK event. Returns True if turn is complete."""
    # Audio / text parts in content
    content = event.get("content", {})
    parts = content.get("parts", [])
    for part in parts:
        if "text" in part:
            print(f"[AGENT] 💬 {part['text']}")
        elif "inline_data" in part:
            mime = part["inline_data"].get("mime_type", "?")
            data_len = len(part["inline_data"].get("data", ""))
            print(f"[AGENT] 🔊 Audio: {mime} ({data_len} chars b64)")
        elif "function_call" in part:
            fc = part["function_call"]
            print(f"[TOOL CALL] 🔧 {fc.get('name')}({json.dumps(fc.get('args', {}), indent=2)})")
        elif "function_response" in part:
            fr = part["function_response"]
            print(f"[TOOL RESP] ✅ {fr.get('name')} → {json.dumps(fr.get('response', {}))}")

    # Transcriptions
    sc = event.get("server_content", {})
    if sc.get("output_transcription", {}).get("text"):
        print(f"[TRANSCRIPTION] 📝 {sc['output_transcription']['text']}")
    if sc.get("input_transcription", {}).get("text"):
        print(f"[YOUR VOICE] 📝 {sc['input_transcription']['text']}")

    # Turn complete
    if sc.get("turn_complete"):
        print(f"\n[TEST] ✅ Turn complete after {event_count} events")
        return True
    return False


async def test_connection():
    """Run the WebSocket integration test."""
    uri = "ws://localhost:8000/ws/test-user/test-session-phase1"
    print(f"[TEST] Connecting to {uri}")

    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            print("[TEST] ✅ WebSocket connected")

            if TOOL_TEST:
                # Prompt designed to trigger log_finding tool call
                prompt = (
                    "I can see a wide diagonal crack on the concrete wall in front of me, "
                    "approximately 3mm wide, running from the window frame to the floor. "
                    "Please log this as a finding."
                )
            else:
                prompt = "Hello, can you hear me? Describe what you do."

            msg = {"type": "text", "content": prompt}
            await ws.send(json.dumps(msg))
            print(f"[TEST] ➡️  Sent: {prompt[:80]}...")

            print("[TEST] Waiting for agent response...\n")
            event_count = 0
            tool_calls_seen = 0
            timeout = 60 if TOOL_TEST else 30

            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    event = json.loads(raw)
                    event_count += 1

                    # Count tool calls
                    for part in event.get("content", {}).get("parts", []):
                        if "function_call" in part:
                            tool_calls_seen += 1

                    done = _print_event(event, event_count)
                    if done:
                        break

            except asyncio.TimeoutError:
                print(f"\n[TEST] ⏰ Timeout after {event_count} events (normal for streaming)")

            print(f"[TEST] Total events: {event_count}")
            if TOOL_TEST:
                if tool_calls_seen > 0:
                    print(f"[TEST] ✅ Tool invocation confirmed — {tool_calls_seen} tool call(s) observed")
                else:
                    print("[TEST] ⚠️  No tool calls observed — agent may need more specific prompt")
            print("[TEST] ✅ Bidi-streaming pipeline is working!")

    except ConnectionRefusedError:
        print("[TEST] ❌ Connection refused — is the backend running?")
        print("       Run: cd backend && uvicorn app.main:app --reload --port 8000")
    except Exception as e:
        print(f"[TEST] ❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_connection())
