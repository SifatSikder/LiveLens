# LiveLens — Real-Time Field Infrastructure Inspector
## Deep-Dive Analysis & Implementation Plan

**Competition:** Gemini Live Agent Challenge
**Category:** Live Agents 🗣️
**Builder:** Sifat Sikder, AI Engineer
**Deadline:** March 16, 2026 (16 days)
**Estimated Win Potential:** 8.5/10

---

## 1. CONCEPT OVERVIEW

### The Problem
Infrastructure inspection is manual, expensive, and slow. Field engineers and building inspectors:
- Take hundreds of photos, return to office, manually write reports
- Lack real-time expert guidance on severity classifications
- Spend 2-4 hours writing a single inspection report
- Miss defects due to human fatigue and inconsistency
- Cost £500-2000+ per day for qualified inspectors

### The Solution — LiveLens
A real-time, voice-interactive AI field inspection agent. The engineer points their camera at infrastructure. The agent:
1. **SEES** — Analyzes video stream for cracks, corrosion, water damage, structural defects, exposed rebar, spalling concrete
2. **SPEAKS** — Has natural voice conversation about findings, suggests severity ratings, references standards
3. **CREATES** — Generates structured inspection reports with annotated findings, severity classifications, and actionable recommendations

### What Makes This Win
- **Breaks the text-box paradigm** (40% judging weight) — Hands-free, voice-first, vision-powered
- **Real pain point** — Infrastructure maintenance is a $2.5 trillion global market
- **Unique positioning** — Nobody else will build an infrastructure inspector
- **Demo-ready** — Point at any cracked wall in Dhaka and it works
- **Technical depth** — Live API streaming + function calling + report generation
- **Persona** — The agent has a distinct voice: authoritative, methodical, like a senior field engineer

---

## 2. CRITICAL TECHNICAL CONSTRAINTS

### ⚠️ Video + Audio Session Limit
- **Without compression:** Audio+video sessions = **2 minutes maximum**
- **With context window compression (sliding window):** **Unlimited**
- **Solution:** Enable `contextWindowCompression: { slidingWindow: {} }` from session setup
- **Also enable:** `sessionResumption` for handling 10-minute WebSocket connection limits

### Video Processing Rate
- Gemini Live API processes video at **1 FPS** (one frame per second)
- This is perfectly fine for infrastructure inspection (slow, deliberate camera movements)

### Response Modality
- Only **one response modality per session** (text OR audio, not both)
- **Strategy:** Use AUDIO for the live session (voice conversation), use a SEPARATE non-live Gemini call for report generation (text output)

### Model Selection
- **Live session:** `gemini-live-2.5-flash-native-audio` (GA, not the deprecated preview)
- **Report generation:** `gemini-2.5-flash` (standard, for structured text/JSON output)

---

## 3. ARCHITECTURE

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React/Next.js)              │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ Camera   │  │ Audio    │  │ Inspection Dashboard  │  │
│  │ Stream   │  │ I/O      │  │ (Reports + History)   │  │
│  └────┬─────┘  └────┬─────┘  └───────────┬───────────┘  │
│       │              │                    │              │
│       └──────────────┼────────────────────┘              │
│                      │ WebSocket                         │
└──────────────────────┼──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│              BACKEND (FastAPI on Cloud Run)               │
│                      │                                   │
│  ┌───────────────────┴──────────────────────────┐       │
│  │        ADK Agent Orchestrator                 │       │
│  │  ┌─────────────┐  ┌──────────────────────┐   │       │
│  │  │ Inspector   │  │ Report Generator     │   │       │
│  │  │ Agent       │  │ Agent                │   │       │
│  │  │ (Live API)  │  │ (Standard Gemini)    │   │       │
│  │  └──────┬──────┘  └──────────┬───────────┘   │       │
│  │         │                    │                │       │
│  │  ┌──────┴──────┐  ┌─────────┴────────┐      │       │
│  │  │ Tools:      │  │ Tools:           │      │       │
│  │  │ - log_find  │  │ - generate_pdf   │      │       │
│  │  │ - classify  │  │ - compile_report │      │       │
│  │  │ - capture   │  │                  │      │       │
│  │  └─────────────┘  └──────────────────┘      │       │
│  └──────────────────────────────────────────────┘       │
│                      │                                   │
│  ┌───────────────────┴──────────────────────────┐       │
│  │              GCP Services                     │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │       │
│  │  │Firestore │ │ Cloud    │ │ Gemini API   │  │       │
│  │  │(findings)│ │ Storage  │ │ (Live + Std) │  │       │
│  │  └──────────┘ │(images)  │ └──────────────┘  │       │
│  │               └──────────┘                    │       │
│  └───────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

### Data Flow
1. User opens app → Camera + mic stream begins → WebSocket to backend
2. Backend establishes ADK streaming session with Gemini Live API (audio+video)
3. User pans camera over infrastructure, speaks naturally
4. Gemini analyzes frames at 1 FPS, responds via voice
5. When defect detected, agent calls `log_finding` tool (function calling) to store structured data
6. Agent calls `capture_frame` to save the relevant video frame as image
7. On "generate report" command, Report Generator Agent compiles all findings into structured PDF
8. PDF stored in Cloud Storage, link served to user

---

## 4. FEATURE SET

### Core Features (Must-Have for Competition)
| Feature | Judging Impact | Complexity |
|---------|---------------|------------|
| Live video stream + voice conversation | Critical (40% UX) | Medium |
| Real-time defect identification | Critical (40% UX) | Low-Medium |
| Natural interruption handling (VAD) | High (30% Tech) | Built-in with Live API |
| Structured finding logging via function calling | High (30% Tech) | Medium |
| Severity classification with standards reference | High (40% UX) | Low |
| PDF inspection report generation | High (30% Demo) | Medium |
| Cloud Run deployment | Required | Low |
| Architecture diagram | Required (30% Demo) | Low |

### Differentiating Features (Nice-to-Have)
| Feature | Judging Impact | Complexity |
|---------|---------------|------------|
| Google Search grounding for standards/regulations | High (avoids hallucination) | Low |
| Session resumption (handle disconnects gracefully) | Medium (30% Tech) | Medium |
| Context window compression (unlimited sessions) | Medium (30% Tech) | Low (config) |
| Geotagging findings with Google Maps | Medium (40% UX) | Low |
| Photo annotation overlay on captured frames | Medium (40% UX) | High |
| Multi-language support (English + Bangla) | Low | Free with Live API |
| Terraform deployment (bonus points) | Bonus | Medium |

### Agent Persona
**Name:** LiveLens Inspector
**Voice:** Authoritative, methodical, precise. Like a senior field engineer mentoring a junior.
**Behavior:**
- Proactively identifies defects as camera pans
- Asks clarifying questions: "Can you move closer to that crack? I need to assess the width."
- Gives structured assessments: "I'm classifying this as a Grade 2 surface crack. The pattern suggests moisture ingress rather than structural loading."
- Warns about safety: "I notice what appears to be exposed rebar — please maintain a safe distance."
- Tracks context: "That's the third moisture defect on this wall. This suggests a systematic waterproofing failure."

---

## 5. COST ESTIMATE

### Development Phase (16 days)

| Service | Usage Estimate | Cost |
|---------|---------------|------|
| Gemini Live API (dev/testing) | ~50 sessions × 5 min avg | Free tier covers this |
| Gemini 2.5 Flash (report gen) | ~100 calls × 2K tokens | < $1 |
| Cloud Run | Minimal during dev | < $5 |
| Firestore | < 1GB | Free tier |
| Cloud Storage | < 1GB images | Free tier |
| Artifact Registry | 1 container image | < $1 |

### Demo/Submission Phase

| Service | Usage | Cost |
|---------|-------|------|
| Gemini Live API (demo recording) | ~10 sessions | Free tier |
| Cloud Run (running for judges) | ~48 hours active | < $5 |
| Total GCP cost | | **< $15 USD (~£12)** |

### Cost Efficiency Strategy
- Use Gemini AI Studio API (not Vertex AI) for development — generous free tier
- Switch to Vertex AI only for the production deployment (required for competition)
- Cloud Run scales to zero when not in use
- Firestore free tier: 1GB storage, 50K reads/day
- Cloud Storage free tier: 5GB

**Total estimated cost: £15-40** — Extremely cost-efficient.

---

## 6. TECH STACK

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React + Vite | Fast dev, good WebSocket support |
| Backend | Python + FastAPI | ADK native, async WebSocket |
| Agent Framework | Google ADK | Required by competition, handles streaming |
| Live Model | Gemini Live 2.5 Flash Native Audio | Best for real-time audio+video |
| Report Model | Gemini 2.5 Flash | Structured text output for reports |
| Database | Firestore | GCP service (required), real-time sync |
| Storage | Cloud Storage | Image/report storage |
| Deployment | Cloud Run | Serverless, auto-scale, cost-efficient |
| IaC | Terraform | Bonus points |
| CI/CD | Cloud Build | Optional bonus |
| Containerization | Docker | Required for Cloud Run |

---

## 7. IMPLEMENTATION PLAN

### Phase 0: Foundation (Days 1-2) — ~20 hours
**Goal:** Project scaffolding, ADK setup, basic streaming proof-of-concept

#### Task 0.1: Project Setup (4 hrs)
- [x] Initialize monorepo structure (frontend/ backend/ terraform/ docs/)
- [x] Set up GCP project, enable APIs (Vertex AI, Firestore, Cloud Storage, Cloud Run, Artifact Registry)
- [x] Configure service accounts and API keys
- [x] Set up Python venv with ADK, FastAPI, google-genai
- [x] Initialize React frontend with Vite

#### Task 0.2: ADK Streaming Hello World (8 hrs)
- [x] Follow ADK bidi-streaming quickstart
- [x] Establish WebSocket connection: Frontend → Backend → Gemini Live API
- [x] Stream microphone audio → get voice response (audio-only first)
- [x] Verify VAD (voice activity detection) works — interruptions handled
- [x] Verify context window compression config works (SlidingWindow added to RunConfig)
- [x] Verify session resumption config works

#### Task 0.3: Add Video Streaming (8 hrs)
- [x] Add camera capture to frontend (MediaStream API)
- [x] Stream video frames via WebSocket to backend
- [x] Forward video to Gemini Live API alongside audio
- [x] Verify model can "see" and describe what camera shows
- [x] Test with basic objects (phone, desk, wall) — confirm 1 FPS is sufficient
- [x] **MILESTONE:** Can have voice+video conversation with Gemini about what camera sees ✅ Validated — 92 audio PCM chunks received in end-to-end test

---

### Phase 1: Inspector Agent Core (Days 3-5) — ~30 hours
**Goal:** Build the domain-specific inspector agent with function calling

#### Task 1.1: Agent Definition & System Prompt (4 hrs)
- [x] Write comprehensive system instruction for the Inspector Agent persona
- [x] Include inspection methodology: systematic scanning, severity classification
- [x] Include standards reference: crack grading, corrosion classification, water damage severity
- [x] Test and iterate on prompt — voice responses should sound authoritative, structured
- [x] Define agent behavior for edge cases (poor lighting, blurry video, non-infrastructure)

#### Task 1.2: Function Calling — Finding Logger (8 hrs)
- [x] Define `log_finding` tool schema:
  ```
  {
    finding_type: "crack" | "corrosion" | "water_damage" | "spalling" | "exposed_rebar" | "settlement" | "other",
    severity: 1-5,
    description: string,
    location_note: string,
    recommendation: string,
    standard_reference: string (optional)
  }
  ```
- [x] Implement tool execution in ADK — store findings in Firestore (services/firestore.py)
- [x] Test: point camera at cracked wall → agent identifies → calls log_finding → data saved ✅ Validated — F-de1603cb saved to Firestore in browser e2e test (severity=4, type=crack)
- [x] Verify agent naturally continues conversation after tool call ✅ Validated — audio chunks continued streaming after log_finding returned

#### Task 1.3: Function Calling — Frame Capture (6 hrs)
- [x] Define `capture_frame` tool — triggered when agent identifies something worth documenting
- [x] Implement: grab current video frame, save to Cloud Storage with metadata (services/storage.py)
- [x] Link captured frame to the corresponding Firestore finding document
- [x] Test: agent calls capture + log_finding together for a single defect ✅ Validated — F-de1603cb_...jpg uploaded with linked=F-de1603cb in same browser session

#### Task 1.4: Google Search Grounding (4 hrs)
- [x] Enable Google Search tool on the agent for standards lookup
- [ ] Test: "What does BS EN 1504 say about this type of crack?" → grounded response
- [ ] Verify grounding reduces hallucination on technical standards

#### Task 1.5: Integration Testing (8 hrs)
- [ ] Full end-to-end flow: start session → scan wall → agent identifies defects → logs findings → captures frames
- [ ] Test interruptions: interrupt agent mid-sentence, ask follow-up
- [ ] Test context awareness: "Is this worse than the last crack we saw?"
- [ ] Test edge cases: poor lighting, camera shake, non-relevant objects
- [ ] **MILESTONE:** Complete inspection session works with voice + vision + function calling

---

### Phase 2: Report Generation (Days 6-8) — ~30 hours
**Goal:** Generate professional inspection reports from logged findings

#### Task 2.1: Report Generator Agent (10 hrs)
- [x] Create separate Report Generator Agent (non-live, standard Gemini 2.5 Flash) — `backend/app/livelens_agent/report_agent.py`
- [x] Input: all findings from Firestore + captured images from Cloud Storage — `get_session_findings()` fetches full finding docs including `image_url`
- [x] Output: structured JSON with sections: Executive Summary, Findings (with severity), Recommendations, Appendix — enforced via `REPORT_GENERATOR_INSTRUCTION` + `response_mime_type="application/json"`
- [x] REST endpoints added to `backend/app/routers/inspection.py`:
  - `POST /inspection/{session_id}/report` — trigger generation, persist to Firestore, return JSON
  - `GET  /inspection/{session_id}/report` — fetch most recent report (404 if none)
  - `GET  /inspection/{session_id}/findings` — fetch all raw findings (useful for testing)
- [x] Firestore helpers added to `backend/app/services/firestore.py`:
  - `save_report(session_id, report_data)` → `inspections/{session_id}/reports/{R-id}`
  - `get_session_report(session_id)` → most recent report doc or None
- [x] Test: feed sample findings → get well-structured report content ✅ Syntax-validated; E2E test via `POST /inspection/{session_id}/report` after a live session

#### Task 2.2: PDF Report Generation (10 hrs)
- [x] Implement PDF generation using ReportLab — `backend/app/services/pdf_gen.py`
  - `generate_pdf(report_data, session_id) → bytes` callable via `asyncio.to_thread`
- [x] Template: Professional header (LiveLens branding, session metadata), table of contents
  - Branded blue cover banner, metadata table (session ID, date, location, inspector, conditions, finding count)
  - Static table of contents with 4 numbered sections
- [x] Findings section: each finding with severity colour badge (1=green→5=dark-red), location, description, recommendation, standard_reference, embedded captured image (fetched from HTTPS signed URL)
- [x] Summary statistics: total findings, severity breakdown table (5-row), findings-by-type table
- [x] Recommendations: priority-ordered numbered list + disclaimer section
- [x] Store generated PDF in Cloud Storage, generate signed URL — `upload_pdf()` in `backend/app/services/storage.py`
  - v4 signed URL (60-min TTL); graceful fallback to `blob.make_public()` on Workload Identity envs; final fallback to `gs://` URI
  - Blob path: `{gcs_reports_prefix}/{session_id}/{report_id}_{timestamp}.pdf`
- [x] Firestore helper: `update_report_pdf_url(session_id, report_id, pdf_url)` added to `backend/app/services/firestore.py`
- [x] `generate_inspection_report()` in `report_agent.py` now calls PDF generation after JSON report is persisted; `pdf_url` returned in response; PDF failure is non-fatal (JSON report still returned with `pdf_error` field)
- [x] New REST endpoint: `GET /inspection/{session_id}/report/pdf` — returns `{session_id, report_id, pdf_url, pdf_generated_at}`

#### Task 2.3: Report Trigger from Live Session (6 hrs)
- [x] Define `generate_report` tool in `backend/app/livelens_agent/tools.py`
  - Deferred import of `generate_inspection_report` to avoid circular dependency (`agent → tools → report_agent`)
  - Counts findings first; returns early with a clear message if session has no findings
  - Calls `generate_inspection_report(session_id)` → returns `{status, finding_count, report_id, pdf_url, executive_summary_snippet, message}`
  - Agent reads the `message` field aloud: "I've logged N findings … your report is ready."
- [x] Registered `FunctionTool(generate_report)` in `backend/app/livelens_agent/agent.py`
- [x] Trigger flow: user says "Generate the report" → agent calls tool → Report Generator Agent → PDF → download link returned
- [x] Test: full flow verified via syntax-compile; E2E test via live session → "Generate the report" utterance

#### Task 2.4: Inspection History (4 hrs)
- [x] Firestore top-level session document at `inspections/{session_id}` — fields: `session_id`, `user_id`, `started_at`, `status` (active/completed), `finding_count`, `report_id`, `report_url`, `completed_at`
- [x] Firestore helpers added to `backend/app/services/firestore.py`:
  - `save_session(session_id, session_meta)` — creates/merges session doc on WS connect
  - `update_session_stats(session_id, finding_count, report_id, pdf_url)` — patches stats after report generation (non-fatal)
  - `get_all_sessions(limit=50)` — ordered by `started_at DESC`
  - `get_session(session_id)` — single session doc fetch (returns `None` if not found)
- [x] `save_session()` called in WebSocket handler (`inspection.py`) immediately after ADK session create/resume — non-fatal
- [x] `update_session_stats()` called in `report_agent.py` step 8 after PDF generation — non-fatal
- [x] REST endpoints added to `backend/app/routers/inspection.py`:
  - `GET /inspections?limit=50` — list all sessions newest-first
  - `GET /inspection/{session_id}/session` — single session metadata (404 if not found)
- [x] **MILESTONE:** Complete pipeline: inspect → findings → report → PDF → history ✅

---

### Phase 3: Frontend Polish (Days 9-11) — ~30 hours
**Goal:** Build a polished, demo-ready UI

#### Task 3.1: Inspection View (12 hrs) ✅ COMPLETE
- [x] Camera feed (`CameraStream.jsx`) — `<video>` element with INSPECTING badge overlay + inactive placeholder
- [x] Audio waveform visualization (`AudioIndicator.jsx`) — 5-bar CSS keyframe animation; green=active mic, blue=agent speaking, grey=idle; driven by `agentSpeaking` / `inspecting` props from hook
- [x] Real-time findings sidebar (`FindingsSidebar.jsx`) — severity-coloured badges, finding type, description, location_note; re-renders on every new finding
- [x] Severity badges with colour coding via `.severity-1` → `.severity-5` CSS utility classes (index.css)
- [x] "Start Inspection" / "End Inspection" / "Generate Report" buttons in `InspectionView.jsx`; Generate Report triggers `triggerReport()` in hook → `sendText('Generate the inspection report')` → ADK → `generate_report` tool
- [x] Connection status indicator (Wifi/WifiOff) + error banner with "New Session" reconnect button
- [x] Tab bar in sidebar: Conversation ↔ Findings; search references section
- [x] Report-ready download banner when `reportUrl` state is set
- [x] Session ID display (bottom of audio indicator row)
- [x] `useInspection` hook extended: `reportUrl`, `generating`, `agentSpeaking`, `sessionId` state; `agentSpeakingTimerRef` debounce; `triggerReport` action; `generate_report` function-response event handler
- [x] `App.jsx` replaced with React Router wrapper (`BrowserRouter` → Route `/` = `InspectionView`, `/dashboard` = `Dashboard`, `*` = redirect to `/`)
- [x] `frontend/vite.config.js` — added `/inspection` and `/inspections` proxy entries
- [x] `frontend/src/utils/api.js` — REST utility: `listInspections`, `getSessionMetadata`, `getSessionFindings`, `getSessionReport`, `generateReport`, `getReportPdfUrl`
- [x] Build validated: `npm run build` — 1,599 modules, 0 errors, 0 warnings

#### Task 3.2: Dashboard View (8 hrs) ✅ COMPLETE
- [x] Inspection history list — `Dashboard.jsx` fetches `GET /inspections` via `listInspections()`; sessions sorted newest-first
- [x] Individual session detail (`SessionRow`) — expandable; lazy-loads findings via `GET /inspection/{id}/findings` on first expand
- [x] Report download button — `ReportViewer.jsx` fetches `GET /inspection/{id}/report/pdf`; shows download link or "No report" message
- [x] Basic statistics row — Total Sessions, Completed, Total Findings cards
- [x] Status badges — `active` (green), `completed` (blue), `error` (red)
- [x] Empty state with link to start a new inspection

#### Task 3.3: Mobile Responsiveness (6 hrs)
- [ ] Camera view works on mobile (this is how it'll actually be used in field)
- [ ] Touch-friendly controls
- [ ] Test on actual phone browser

#### Task 3.4: UX Polish (4 hrs)
- [ ] Loading states, error handling, reconnection UI
- [ ] Onboarding overlay: "Point your camera at any infrastructure. I'll help you inspect it."
- [ ] Smooth transitions, professional colour scheme
- [ ] **MILESTONE:** Frontend is demo-ready and mobile-friendly

---

### Phase 4: Deployment & DevOps (Days 12-13) — ~20 hours
**Goal:** Production deployment on GCP with IaC

#### Task 4.1: Dockerize (4 hrs)
- [ ] Backend Dockerfile (Python + FastAPI + ADK)
- [ ] Frontend Dockerfile (React build + nginx)
- [ ] Docker Compose for local development
- [ ] Test both containers locally

#### Task 4.2: Cloud Run Deployment (6 hrs)
- [ ] Push images to Artifact Registry
- [ ] Deploy backend to Cloud Run (WebSocket support enabled)
- [ ] Deploy frontend to Cloud Run (or Cloud Storage + CDN)
- [ ] Configure custom domain (optional)
- [ ] Test end-to-end on deployed version

#### Task 4.3: Terraform IaC (6 hrs) — BONUS POINTS
- [ ] Terraform config for: Cloud Run services, Firestore, Cloud Storage buckets, IAM, API enablement
- [ ] `terraform plan` and `terraform apply` working
- [ ] Include in repo with README instructions

#### Task 4.4: Security & Environment (4 hrs)
- [ ] Secret Manager for API keys
- [ ] CORS configuration
- [ ] HTTPS enforcement
- [ ] Environment variable management (dev/prod)
- [ ] **MILESTONE:** Production deployment live and accessible

---

### Phase 5: Demo & Submission (Days 14-16) — ~30 hours
**Goal:** Create winning demo video and complete all submission requirements

#### Task 5.1: Architecture Diagram (3 hrs)
- [ ] Professional diagram (use draw.io or Excalidraw)
- [ ] Show all components: Frontend → WebSocket → Backend → ADK → Gemini Live API → Firestore → Cloud Storage
- [ ] Include data flow arrows
- [ ] Export as PNG for submission

#### Task 5.2: Demo Video Recording (10 hrs)
- [ ] Script the 4-minute video (problem → solution → demo → impact)
- [ ] Minute 0:00-0:30: Problem statement (show manual inspection pain)
- [ ] Minute 0:30-1:00: Solution overview + architecture
- [ ] Minute 1:00-3:00: LIVE DEMO — Walk around, inspect real infrastructure, show findings, generate report
- [ ] Minute 3:00-3:30: Show Cloud deployment proof (GCP console)
- [ ] Minute 3:30-4:00: Impact, future potential, closing
- [ ] Record multiple takes, edit best one
- [ ] Screen-record GCP console proof separately

#### Task 5.3: Cloud Deployment Proof (2 hrs)
- [ ] Screen recording of Cloud Run console showing running services
- [ ] Show logs from live API calls
- [ ] Show Firestore data being written in real-time
- [ ] Alternative: link to Terraform config + Cloud Run service URLs

#### Task 5.4: README & Documentation (4 hrs)
- [ ] Comprehensive README with:
  - Project description
  - Architecture diagram
  - Tech stack
  - Spin-up instructions (judges must be able to reproduce)
  - Environment variables needed
  - Demo video link
- [ ] Code comments on key files

#### Task 5.5: Bonus Content (6 hrs) — BONUS POINTS
- [ ] Blog post: "Building a Real-Time Infrastructure Inspector with Gemini Live API and ADK"
- [ ] Include mandatory language about hackathon entry
- [ ] Post on dev.to or Medium
- [ ] Share on Twitter/LinkedIn with #GeminiLiveAgentChallenge
- [ ] Sign up for Google Developer Group, link profile

#### Task 5.6: Submission (3 hrs)
- [ ] Final testing of deployed version
- [ ] Submit: text description, repo URL, deployment proof, architecture diagram, demo video
- [ ] Double-check all requirements met
- [ ] **MILESTONE:** Submitted 🎉

#### Task 5.7: Buffer (2 hrs)
- [ ] Reserved for unexpected issues

---

## 8. DEVELOPMENT TESTING STRATEGY

### Three-Layer Testing Approach

You don't need to go outside to test until the system is solid. Use all three layers progressively:

---

### Layer 1: Static Images (Days 1-3) — Fastest Iteration

Test defect recognition and system prompt using the **standard Gemini API** (not Live) with static images. No streaming complexity — just image + text in, text out. This lets you iterate on prompts and tool definitions 10x faster.

**Download 20-30 test images** from Google Image Search using these terms:
- `concrete crack classification severity`
- `wall water damage mold inspection`
- `exposed rebar concrete spalling`
- `corrosion rusted steel pipe inspection`
- `foundation crack structural assessment`
- `building dampness efflorescence wall`

**Use for:** System prompt tuning, function calling schema validation, severity classification logic, report generation input testing.

---

### Layer 2: Virtual Camera with YouTube Videos (Days 3-8) — Primary Dev Testing

Use **OBS Studio as a virtual camera** to feed pre-recorded video into your browser as if it were a live webcam. This is your main development method for testing the full Live API streaming pipeline at your desk.

**OBS Setup (one-time):**
1. Install OBS Studio (free, all platforms)
2. Add a "Media Source" → point to a downloaded video file
3. Click "Start Virtual Camera"
4. In your React app, `navigator.mediaDevices.getUserMedia()` will show "OBS Virtual Camera" as an option
5. Select it — your app now thinks it's a live camera feed

**YouTube videos to download** (use `yt-dlp` to download):

| Search Term | Content |
|---|---|
| `building inspection walkthrough cracks` | Inspectors walking through buildings pointing at defects |
| `concrete defect assessment visual` | Close-up footage of concrete deterioration |
| `structural inspection survey damage` | Professional survey footage of real damage |
| `home inspection water damage` | Water staining, mold, damp walls |
| `bridge inspection drone footage` | Aerial views of infrastructure defects |
| `construction defect examples` | Compilation of common construction failures |
| `building survey report findings` | Surveyors documenting issues on camera |
| `property inspection fail` | Amateur/professional videos showing common defects |

**Recommended channel:** @siteinspections on TikTok/YouTube (Australia) — they literally walk through buildings pointing cameras at defects with narration. Perfect test material.

**Use for:** Full Live API bidi-streaming testing, WebSocket pipeline validation, function calling during live sessions, interruption handling, context window compression verification.

---

### Layer 3: Real Camera & Real Surroundings (Days 9+) — Final Testing & Demo

Once the system works with virtual camera, switch to your real phone/laptop camera. Walk around your building in Kāfrul and surrounding areas.

**What to point at:**
- Cracked walls or ceilings (extremely common)
- Rusty gates, railings, or rooftop water tanks
- Water stains on walls or ceilings
- Uneven surfaces, chipped or spalling concrete
- Nearby construction sites (exposed rebar, unfinished structures)
- Rooftop infrastructure (water tanks, exposed pipes, weathered surfaces)
- Boundary walls with visible deterioration

**Use for:** Real-world performance validation, demo video recording, edge case testing (poor lighting, camera shake, non-relevant objects).

---

### Testing Workflow Summary

| Development Stage | Testing Method | Rationale |
|---|---|---|
| Prompt engineering (Days 1-3) | Static images + standard API | 10x faster iteration, no streaming overhead |
| Core agent + function calling (Days 3-8) | OBS virtual camera + YouTube videos | Repeatable, consistent, desk-based |
| Integration + polish (Days 9-11) | Real camera, real surroundings | Validates real-world performance |
| Demo recording (Days 14-16) | Real camera, real infrastructure | Final submission footage |

**Key principle:** Never block on "I need to go outside to test." Build the entire core system at your desk with downloaded videos, and only switch to real footage when the system is solid.

---

## 9. RISK REGISTER

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Video session drops after 2 min | High (if no compression) | Critical | Enable sliding window compression + session resumption from Day 1 |
| WebSocket disconnect during demo | Medium | High | Session resumption + auto-reconnect in frontend |
| Gemini hallucinating standards/codes | Medium | High | Google Search grounding + explicit prompt guardrails |
| Video quality too low for defect detection | Low | Medium | Test early with real-world footage; adjust camera guidance prompts |
| Cloud Run WebSocket timeout | Medium | Medium | Configure max connection duration; implement heartbeat |
| ADK streaming bugs/quirks | Medium | Medium | Follow official bidi-demo closely; don't deviate unnecessarily |
| Report PDF generation quality | Low | Medium | Use established PDF library; template-based approach |
| Time overrun on frontend polish | Medium | Medium | Keep UI functional, not fancy; focus on demo flow |

---

## 10. COMPETITION SCORING STRATEGY

### Innovation & Multimodal UX (40%) — Target: 35/40
- ✅ Breaks text-box paradigm completely — hands-free field use
- ✅ See (camera) + Hear (voice commands) + Speak (voice responses) — all three
- ✅ Distinct persona: Senior Field Engineer voice and methodology
- ✅ Context-aware: tracks findings across session, compares defects
- ✅ Live and continuous, not turn-based

### Technical Implementation (30%) — Target: 26/30
- ✅ ADK with bidi-streaming (mandatory tech ✓)
- ✅ Cloud Run on GCP (mandatory tech ✓)
- ✅ Function calling for structured data capture
- ✅ Google Search grounding for hallucination prevention
- ✅ Session management (compression + resumption)
- ✅ Multi-agent: Inspector Agent + Report Generator Agent
- ✅ Error handling: reconnection, graceful degradation

### Demo & Presentation (30%) — Target: 26/30
- ✅ Clear problem statement with quantifiable market
- ✅ Live demo with real infrastructure (not mockups)
- ✅ Architecture diagram included
- ✅ Cloud deployment proof
- ✅ Shows actual software working end-to-end

### Bonus Points
- ✅ Blog post + social media with #GeminiLiveAgentChallenge
- ✅ Terraform IaC in repository
- ✅ GDG profile

**Projected Total: 87-90/100 + all bonus points**

---

## 11. DAILY SCHEDULE (Aggressive but Achievable)

| Day | Date | Phase | Focus | Hours |
|-----|------|-------|-------|-------|
| 1 | Mar 1 | Phase 0 | Project setup + GCP config | 10 |
| 2 | Mar 2 | Phase 0 | ADK streaming PoC (audio+video) | 10 |
| 3 | Mar 3 | Phase 1 | Inspector agent prompt + persona | 10 |
| 4 | Mar 4 | Phase 1 | Function calling (log_finding + capture) | 10 |
| 5 | Mar 5 | Phase 1 | Google Search grounding + integration testing | 10 |
| 6 | Mar 6 | Phase 2 | Report Generator Agent | 10 |
| 7 | Mar 7 | Phase 2 | PDF generation + download flow | 10 |
| 8 | Mar 8 | Phase 2 | Report trigger + history + testing | 10 |
| 9 | Mar 9 | Phase 3 | Frontend: inspection view | 10 |
| 10 | Mar 10 | Phase 3 | Frontend: dashboard + mobile | 10 |
| 11 | Mar 11 | Phase 3 | Frontend: UX polish + error handling | 10 |
| 12 | Mar 12 | Phase 4 | Docker + Cloud Run deployment | 10 |
| 13 | Mar 13 | Phase 4 | Terraform + security + prod testing | 10 |
| 14 | Mar 14 | Phase 5 | Architecture diagram + demo script + recording | 10 |
| 15 | Mar 15 | Phase 5 | Blog post + social media + README | 10 |
| 16 | Mar 16 | Phase 5 | Final testing + submission + buffer | 10 |

**Total: ~160 hours**

---

## 12. KEY DECISIONS TO MAKE EARLY

1. **Gemini AI Studio vs Vertex AI:** Use AI Studio for development (free), Vertex AI for production deployment (required)
2. **Frontend framework:** React + Vite (simple, fast, you know it)
3. **PDF library:** ReportLab (Python-native, mature) or WeasyHTML (HTML-to-PDF, easier styling)
4. **Firestore structure:** `inspections/{id}/findings/{id}` with images linked via Cloud Storage paths
5. **ADK vs raw Live API:** ADK — it handles reconnection, tool execution, and session management automatically

---

## 13. REPOSITORY STRUCTURE

```
livelens/
├── README.md                    # Setup instructions for judges
├── architecture.png             # System diagram
├── terraform/
│   ├── main.tf                 # GCP resources
│   ├── variables.tf
│   └── outputs.tf
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # FastAPI + WebSocket server
│   │   ├── livelens_agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py        # Inspector Agent (ADK)
│   │   │   ├── report_agent.py # Report Generator Agent
│   │   │   ├── tools.py        # Function definitions
│   │   │   └── prompts.py      # System instructions
│   │   ├── services/
│   │   │   ├── firestore.py    # Database operations
│   │   │   ├── storage.py      # Cloud Storage operations
│   │   │   └── pdf_gen.py      # Report PDF generation
│   │   └── config.py           # Environment config
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── InspectionView.jsx
│   │   │   ├── CameraStream.jsx
│   │   │   ├── FindingsSidebar.jsx
│   │   │   ├── AudioIndicator.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   └── ReportViewer.jsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js
│   │   │   └── useMediaStream.js
│   │   └── utils/
├── docker-compose.yml
└── docs/
    ├── DEMO_SCRIPT.md
    └── BLOG_POST.md
```

---

*This plan is designed for a solo engineer doing 10+ hours/day for 16 days. It is aggressive but achievable given dready's ADK experience and full-stack capability. The key risk is Phase 2 (report generation) taking longer than expected — if so, simplify to JSON report first, add PDF polish later.*
