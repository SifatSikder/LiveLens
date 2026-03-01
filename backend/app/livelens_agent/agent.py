"""LiveLens Inspector Agent — Core agent definition using Google ADK.

This agent uses Gemini Live API for real-time audio+video infrastructure inspection.
Tools and detailed instructions will be expanded in Phase 1.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import google_search

from app.livelens_agent.prompts import INSPECTOR_SYSTEM_INSTRUCTION

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
    tools=[google_search],  # Google Search grounding; custom tools added in Phase 1
)
