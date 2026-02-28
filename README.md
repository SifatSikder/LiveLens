# 🔍 LiveLens — Real-Time AI Infrastructure Inspector

> **Gemini Live Agent Challenge Entry** | Live Agents Category

LiveLens is a real-time, voice-interactive AI field inspection agent. Point your camera at any infrastructure — walls, pipes, concrete, steel structures — and have a natural conversation with an AI inspector that sees defects, classifies severity, and generates professional inspection reports.

## 🎥 Demo Video
[Link to demo video — TBD]

## 🏗️ Architecture
![Architecture Diagram](./docs/architecture.png)

## ✨ Features
- **Real-time vision + voice** — Hands-free inspection via camera + natural conversation
- **Defect identification** — Cracks, corrosion, water damage, spalling, exposed rebar
- **Severity classification** — 5-level grading system with standards references
- **Structured findings** — Each defect logged with type, severity, location, recommendation
- **PDF report generation** — Professional inspection reports from live session data
- **Google Search grounding** — Standards lookup to minimize hallucination
- **Session management** — Context window compression for unlimited session duration

## 🛠️ Tech Stack
| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK (Agent Development Kit) |
| Live Model | Gemini Live 2.5 Flash Native Audio |
| Report Model | Gemini 2.5 Flash |
| Backend | Python, FastAPI, WebSockets |
| Frontend | React, Vite, Tailwind CSS |
| Database | Cloud Firestore |
| Storage | Cloud Storage |
| Deployment | Cloud Run |
| IaC | Terraform |

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Google Cloud SDK (`gcloud`)
- A GCP project with billing enabled

### 1. Clone & Setup
```bash
git clone https://github.com/YOUR_USERNAME/livelens.git
cd livelens
```

### 2. GCP Configuration
```bash
# Set your project
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com

# Authenticate
gcloud auth application-default login
```

### 3. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy and edit environment file
cp .env.example .env
# Edit .env with your GCP project details

# Run
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### 5. Deploy to Cloud Run (optional)
```bash
cd terraform
terraform init
terraform plan -var="project_id=$PROJECT_ID"
terraform apply -var="project_id=$PROJECT_ID"
```

## 📁 Project Structure
```
livelens/
├── backend/          # FastAPI + ADK agent backend
│   ├── app/
│   │   ├── main.py                 # FastAPI app + WebSocket
│   │   ├── config.py               # Environment config
│   │   ├── livelens_agent/         # ADK agent definitions
│   │   │   ├── agent.py            # Inspector Agent
│   │   │   ├── prompts.py          # System instructions
│   │   │   └── tools.py            # Function calling tools
│   │   └── services/               # GCP service integrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # React + Vite UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   └── hooks/
│   └── package.json
├── terraform/        # Infrastructure as Code
│   ├── main.tf
│   └── variables.tf
├── docs/             # Architecture diagrams, demo script
└── docker-compose.yml
```

## 🏆 Competition Submission
- **Category:** Live Agents 🗣️
- **Mandatory Tech:** Gemini Live API via ADK, hosted on Google Cloud (Cloud Run)
- **GCP Services:** Vertex AI, Cloud Run, Firestore, Cloud Storage
- **Bonus:** Terraform IaC, blog post, GDG profile

## ⚠️ Disclaimer
LiveLens provides AI-assisted preliminary visual assessment only. Findings do not constitute a professional structural engineering report. For any severity 3+ findings, engage a qualified structural engineer.

## 📝 License
MIT

---
Built for the **Gemini Live Agent Challenge** | #GeminiLiveAgentChallenge
