# Shruti Samvad: Agentic RSS Reader + AI Podcast Generator

**Shruti Samvad** (श्रुति संवाद) is a hybrid local application designed for Apple Silicon that merges an enterprise-grade RSS Reader with an agentic AI Podcast Generator. Articles flow in from RSS feeds, pass through a rules engine, and can be automatically (or manually) converted into polished narrated podcasts using a local LLM + TTS pipeline — all offline, no cloud required.

---

## 🎨 Design Vision: "Anti-AI Warmth"
We reject cold, clinical blue/black UI. Shruti Samvad's interface feels like a warm, leather-bound notebook or a cozy podcast studio, using a palette of burnt orange, terracotta, and parchment cream.

---

## 🏗 System Architecture

The project is built as a modular monorepo with the following components:

- **Next.js 15 Web Client**: A modern, responsive dashboard for reading and managing feeds.
- **api-rss (FastAPI)**: Manages feed ingestion, article extraction, and the rules engine.
- **api-podcast (FastAPI)**: Orchestrates the AI pipeline using LangGraph.
- **arq Workers**: Background processing for RSS refreshing and podcast generation.
- **Local AI Stack**: Ollama (Gemma 2 12B) for summarization/scripting and Kokoro for TTS.
- **Offline First**: All data and processing stay on your machine. No mandatory cloud accounts (like Clerk or OpenAI) are required.

---

## 🛠 Tech Stack

- **Frontend**: Next.js 15, Tailwind CSS, shadcn/ui.
- **Backend**: Python 3.12, FastAPI, SQLModel.
- **Database**: PostgreSQL with `pgvector`.
- **Queue/Cache**: Redis + `arq`.
- **AI**: LangGraph, Ollama, Kokoro TTS.

---

## 🚀 Getting Started

### Prerequisites

- **Ollama**: [Download and install](https://ollama.com/)
- **Python**: 3.12+
- **Node.js**: 18+
- **Docker**: For running PostgreSQL and Redis.

### 1. Environment Configuration

Copy the example environment file and fill in the necessary keys:

```bash
cp .env.example .env
```

### 2. Infrastructure Setup

#### Option A: With Docker (Recommended)
Start the database and cache using Docker Compose:

```bash
docker compose up -d
```

#### Option B: Without Docker (Local Services)
If you prefer running services directly on your host:
1. Install and start **PostgreSQL 16** (with `pgvector` extension).
2. Install and start **Redis 7**.
3. Update `DATABASE_URL` and `REDIS_URL` in your `.env` to point to your local instances.

### 3. AI Service Setup (Ollama)

Pull the required LLM model:

```bash
ollama pull gemma2:12b-instruct:q4_K_M
```

### 4. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r core/database/requirements.txt
pip install -r services/rss/requirements.txt
pip install -r services/podcast/requirements.txt

# Run database migrations
cd core/database && alembic upgrade head
```

### 5. Frontend Setup

```bash
cd frontend/web
npm install
```

---

## 🏃 Running the Application

You will need multiple terminal windows (or tabs) to run all services:

### T1: RSS API & Workers
```bash
cd backend && source .venv/bin/activate
cd services/rss && uvicorn main:app --reload --port 8000
```

### T2: Podcast API & Workers
```bash
cd backend && source .venv/bin/activate
cd services/podcast && uvicorn main:app --reload --port 8001
```

### T3: Frontend
```bash
cd frontend/web
npm run dev
```

### T4: Ollama
```bash
ollama serve
```

---

## 📁 Directory Structure

- `backend/core/database`: Shared database models and migrations.
- `backend/services/rss`: RSS ingestion service and workers.
- `backend/services/podcast`: AI podcast generation service and LangGraph pipeline.
- `frontend/web`: Next.js 15 web application.
- `storage/audio`: Local storage for generated MP3 files.
