# PressureLab AI

**Why did this football moment happen?**

PressureLab AI is a tactical replay and investigation platform for football matches. It combines event-level match data, pressure and momentum analytics, and IBM Granite–powered explanations so coaches and analysts can explore key moments—not just watch them.

[![Repository](https://img.shields.io/badge/GitHub-PressureLab--AI-blue)](https://github.com/RachanaB5/PressureLab-AI)

---

## What it does

1. **Import a match** — Search StatsBomb competitions or pick from the built-in library.
2. **Explore the timeline** — Scrub through key events with pressure and momentum context.
3. **Replay on the pitch** — Digital Match Twin syncs player positions, ball movement, and match state.
4. **Investigate with Tactical Detective** — Grounded AI walks through what happened and why, with coach-style recommendations.
5. **Ask the AI Copilot** — Natural-language questions about the current moment, tied to real event data.

The core question the product answers: *What led to this moment, and what could a coach take away from it?*

---

## Tech stack

| Layer | Technologies |
|-------|----------------|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS 4, Motion |
| **Backend** | FastAPI, SQLAlchemy, pandas, scikit-learn, XGBoost |
| **Data** | StatsBomb Open Data, custom pressure/momentum engines |
| **AI** | IBM Granite 3.3 (Hugging Face or watsonx.ai), optional Langflow |
| **Realtime** | WebSockets for match analysis progress |

---

## Quick start

### Prerequisites

- **Python 3.11+**
- **Node.js 20+** and npm
- **Hugging Face API key** (for Granite explanations) — [get one here](https://huggingface.co/settings/tokens)

PostgreSQL and Redis are optional; the app falls back to SQLite for local development.

### 1. Clone and enter the project

```bash
git clone https://github.com/RachanaB5/PressureLab-AI.git
cd PressureLab-AI
```

> Always run `git` commands from the project root (`PressureLab-AI/`), not from a parent directory.

### 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set HF_API_KEY
```

### 3. Frontend setup

```bash
cd ../frontend
npm ci
```

### 4. Start development servers

From the project root:

```bash
bash scripts/start-dev.sh
```

This script frees stale ports, starts the API and Vite dev server, and writes `frontend/.env.local` with the backend port. Open the URL printed in the terminal (typically **http://127.0.0.1:5173**).

To stop stale processes:

```bash
bash scripts/kill-dev-ports.sh
```

---

## Demo flow

1. Open the app → confirm the API health indicator is green.
2. Search for a match (e.g. a World Cup or Premier League fixture) or browse **Match Library**.
3. Wait for analysis to complete (progress via WebSocket).
4. In the workspace:
   - Click a key event on the **timeline**.
   - Use **play / pause / seek** on the replay transport—the pitch and match state stay in sync.
   - Open **Tactical Detective** for a grounded breakdown and coach recommendations.
   - Use **AI Copilot** to ask follow-up questions about the selected moment.

Pre-computed demo caches can be warmed with:

```bash
cd backend
source .venv/bin/activate
python scripts/precompute_demo.py
```

---

## Project structure

```
PressureLab-AI/
├── backend/
│   ├── main.py              # FastAPI app (11 production routes)
│   ├── config.py            # Environment settings
│   ├── engine/              # Pressure, momentum, replay, moment workspace
│   ├── ai/                  # Granite client, prompts, LLM providers
│   ├── data/                # StatsBomb loader, match catalog
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           # Home, Match Library, Workspace, Settings
│   │   ├── hooks/           # useMomentEngine (replay + moment state)
│   │   ├── components/      # Digital Match Twin, Detective, Copilot
│   │   └── services/api.ts  # Typed API client
│   └── package.json
├── scripts/
│   ├── start-dev.sh         # One-command dev startup
│   └── kill-dev-ports.sh    # Free ports 8000 / 5173+
└── DEPENDENCY_GRAPH.md      # Module dependency map
```

---

## API reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/matches/suggest` | Match search autocomplete |
| `POST` | `/api/matches/import` | Import match from StatsBomb |
| `GET` | `/api/matches/{id}` | Match metadata |
| `GET` | `/api/matches/{id}/status` | Analysis progress |
| `GET` | `/api/matches/{id}/key-events` | Timeline key events |
| `GET` | `/api/matches/{id}/moments/{event_id}` | Moment payload (replay + context) |
| `POST` | `/api/matches/{id}/moments/{event_id}/detective` | Tactical Detective analysis |
| `GET` | `/api/library/catalog` | Curated match library |
| `POST` | `/api/explain/query` | AI Copilot Q&A |
| `WS` | `/ws/match/{id}` | Real-time analysis updates |

Full client ↔ server mapping is documented in [DEPENDENCY_GRAPH.md](./DEPENDENCY_GRAPH.md).

---

## Configuration

Copy `backend/.env.example` to `backend/.env`. Key variables:

| Variable | Description |
|----------|-------------|
| `HF_API_KEY` | Hugging Face token for IBM Granite |
| `GRANITE_MODEL_ID` | Default: `ibm-granite/granite-3.3-8b-instruct` |
| `LLM_PROVIDER` | `huggingface` or `watsonx` |
| `WATSONX_*` | Optional watsonx.ai credentials |
| `DATABASE_URL` | PostgreSQL connection (SQLite fallback if unavailable) |
| `CORS_ORIGINS` | Allowed frontend origins |

---

## Production build

**Backend** — run with uvicorn behind your process manager:

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Frontend** — build static assets and serve via your CDN or reverse proxy:

```bash
cd frontend
npm run build
# Output in frontend/dist/
```

Configure the frontend proxy (or `VITE_BACKEND_PORT`) so API calls reach the backend. Do not commit `.env`, `.venv`, `node_modules`, or generated cache directories—they are listed in `.gitignore`.

---

## Architecture notes

- **Moment workspace** (`backend/engine/moment_workspace.py`) assembles replay frames, tactical context, and AI-ready grounding for each event.
- **Replay controller** (`frontend/src/hooks/useMomentEngine.ts`) owns play/pause/seek so the pitch, timeline, and transport stay synchronized.
- **Event grounding** (`backend/engine/event_grounding.py`) keeps AI responses tied to actual match data rather than free-form speculation.

See [DEPENDENCY_GRAPH.md](./DEPENDENCY_GRAPH.md) for the active module graph after production cleanup.

---

## License

This project is provided as-is for demonstration and research. Check the repository for license details.

---

## Acknowledgments

- [StatsBomb Open Data](https://github.com/statsbomb/open-data) for event-level match data
- [IBM Granite](https://www.ibm.com/granite) for tactical language understanding
