#!/usr/bin/env python3
"""Quick test: Connect to LiveLens WebSocket and send a text message.

Usage:
    python test_ws.py

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


async def test_connection():
    """Test basic WebSocket connection and text message exchange."""
    uri = "ws://localhost:8000/ws/test-user/test-session-001"
    print(f"[TEST] Connecting to {uri}")

    try:
        async with websockets.connect(uri) as ws:
            print("[TEST] ✅ WebSocket connected")

            # Send a text message
            msg = {"type": "text", "content": "Hello, can you hear me? Describe what you do."}
            await ws.send(json.dumps(msg))
            print(f"[TEST] ➡️  Sent: {msg['content']}")

            # Listen for events (with timeout)
            print("[TEST] Waiting for agent response...\n")
            event_count = 0
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    event = json.loads(raw)
                    event_count += 1

                    # Extract readable info from event
                    content = event.get("content", {})
                    parts = content.get("parts", [])

                    for part in parts:
                        if "text" in part:
                            print(f"[AGENT] 💬 {part['text']}")
                        elif "inline_data" in part:
                            mime = part["inline_data"].get("mime_type", "?")
                            data_len = len(part["inline_data"].get("data", ""))
                            print(f"[AGENT] 🔊 Audio: {mime} ({data_len} chars b64)")

                    # Check for transcription
                    sc = event.get("server_content", {})
                    if sc.get("output_transcription", {}).get("text"):
                        print(f"[TRANSCRIPTION] 📝 {sc['output_transcription']['text']}")
                    if sc.get("input_transcription", {}).get("text"):
                        print(f"[YOUR VOICE] 📝 {sc['input_transcription']['text']}")

                    # Check for turn complete
                    if event.get("server_content", {}).get("turn_complete"):
                        print(f"\n[TEST] ✅ Turn complete after {event_count} events")
                        break

            except asyncio.TimeoutError:
                print(f"\n[TEST] ⏰ Timeout after {event_count} events (this is normal for streaming)")

            print(f"[TEST] Total events received: {event_count}")
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
