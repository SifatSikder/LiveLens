"""LiveLens Inspector Agent — Core agent definition using Google ADK.

This agent uses Gemini Live API for real-time audio+video infrastructure inspection.
Phase 1: log_finding and capture_frame tools wired in alongside Google Search grounding.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from app.livelens_agent.prompts import INSPECTOR_SYSTEM_INSTRUCTION
from app.livelens_agent.tools import capture_frame, log_finding, search_web

# Load .env so GOOGLE_GENAI_USE_VERTEXAI and other vars are set before ADK init
load_dotenv()

# Model is set via environment variable, defaulting to native-audio for live streaming
_model = os.getenv("LIVE_MODEL", "gemini-live-2.5-flash-native-audio")

root_agent = Agent(
    name="livelens_inspector",
    model=_model,
    description=(
        "Real-time infrastructure inspection agent that analyzes video feeds "
        "and provides expert assessments via voice conversation."
    ),
    instruction=INSPECTOR_SYSTEM_INSTRUCTION,
    tools=[
        FunctionTool(search_web),       # Task 1.4: real web search with actual URLs
        FunctionTool(log_finding),      # Task 1.2: persist defect findings to Firestore
        FunctionTool(capture_frame),    # Task 1.3: save video frame to Cloud Storage
    ],
)
