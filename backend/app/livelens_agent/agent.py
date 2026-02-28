"""LiveLens Inspector Agent — Core agent definition using Google ADK.

This agent uses Gemini Live API for real-time audio+video infrastructure inspection.
Tools and detailed instructions will be added in Phase 1.
"""

import os

from google.adk.agents import Agent
from google.adk.tools import google_search

from app.livelens_agent.prompts import INSPECTOR_SYSTEM_INSTRUCTION

# Agent will be fully configured in Phase 1 (Task 1.1 - 1.4)
# For now, this is the minimal ADK agent with streaming support

root_agent = Agent(
    name="livelens_inspector",
    model=os.getenv("LIVE_MODEL", "gemini-live-2.5-flash-native-audio"),
    description="Real-time infrastructure inspection agent that analyzes video feeds and provides expert assessments via voice.",
    instruction=INSPECTOR_SYSTEM_INSTRUCTION,
    tools=[google_search],  # Google Search for standards grounding; custom tools added in Phase 1
)
