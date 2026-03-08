# NeuroSync

NeuroSync is a neuroadaptive AI tutoring system that reads a student's brain state in real-time using an EEG headband (Muse) and continuously adjusts how an AI tutor teaches. When the student is focused, the tutor increases difficulty; when overloaded, it simplifies and slows down; when disengaged, it re-engages with questions and interactive content. The result is a tutoring session that adapts moment-to-moment rather than waiting for a student to ask for help.

The system combines EEG signal processing, large language model agents for planning and speaking, browser-based voice I/O with real-time interruption detection, and a live collaborative whiteboard — all presented in a single full-screen dashboard.

## How It Works

1. **EEG Ingestion** — A Muse headband streams raw EEG via muselsl/pylsl. The backend extracts rolling-window band power (alpha, beta, theta, gamma, delta) and classifies the student's cognitive state as `FOCUSED`, `OVERLOADED`, or `DISENGAGED` using a trained heuristic classifier (`focus_score = beta/theta`, `cognitive_load = beta + gamma`).

2. **AI Agents** — A planner agent (Featherless API, 70B) generates an initial lesson plan and updates the teaching strategy when the state changes. A speaker agent (7–8B) takes the student's latest speech transcript plus the current strategy and returns a response within 1.5 seconds.

3. **Voice Pipeline** — The backend converts the speaker's response to audio via Hume TTS and streams MP3 chunks over the WebSocket. The browser assembles the chunks and plays them. Voice Activity Detection (VAD) lets the student interrupt the tutor mid-sentence.

4. **Adaptive Content** — A live whiteboard displays KaTeX equations, text, and diagrams pushed by the tutor agent. The student can also type to the whiteboard and their speech is transcribed by the Web Speech API.

5. **Post-Session Summary** — On session end, the backend computes time-per-state, per-topic comprehension inference, and an adaptation event log. An AI narrative summarizes the session. The frontend displays this and provides a PDF export.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS v4 |
| Animation | Framer Motion, tsParticles |
| Voice | Web Speech API (STT), AudioContext (playback), VAD |
| Backend | Python 3.12, FastAPI, uvicorn, WebSockets |
| EEG | muselsl, pylsl, numpy, scipy, scikit-learn |
| AI Agents | Featherless API (OpenAI-compatible), Hume TTS |
| Session | In-memory store (FastAPI), Pydantic v2 models |

## Architecture Overview

```
Browser (Next.js)
  SessionWizard → POST /start-session → FastAPI
                ← session_id + lesson_plan

  WebSocket /ws/session/{session_id}
    ← STATE_UPDATE (every 1-2s from EEG classifier)
    ← CONVERSATION_TURN (tutor agent response)
    ← AUDIO_CHUNK (Hume TTS stream)
    ← WHITEBOARD_DELTA (tutor writes to board)
    ← SESSION_EVENT (lifecycle, EEG status)
    → STUDENT_SPEECH (Web Speech API transcript)
    → VAD_SIGNAL (audio level every 100ms)
    → STUDENT_WHITEBOARD_DELTA (student input)

  POST /stop-session → summary + AI narrative
                     → PostSessionSummary modal
```

The backend runs three concurrent pipelines in a single FastAPI process: the EEG ingestion thread (dedicated thread, never in the asyncio event loop), the AI agent tasks (asyncio), and the WebSocket hub that fans out messages to all connected clients for a session.

## Setup

### Prerequisites

- Node.js 20+
- Python 3.12+
- A Muse EEG headband + `muselsl` streaming (optional — the demo works without EEG using mock data)

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local if your backend runs on a different host/port
npm run dev
```

The frontend runs at `http://localhost:3000`.

### Backend (real)

```bash
cd src/backend
pip install -e ".[dev]"
cp .env.example .env
# Fill in FEATHERLESS_API_KEY and HUME_API_KEY
uvicorn api.main:app --port 8000 --reload
```

### Mock Server (for demo / frontend-only development)

The mock server requires only Node.js. It replays a scripted sequence of WebSocket events and handles the REST endpoints so the full frontend UI can be exercised without a real backend or EEG hardware.

```bash
# From project root
node mock-server.js
```

The mock server runs on port **8000** (same as the real backend), so no env changes are needed.

The default frontend env already points at `http://localhost:8000` — just run the mock server and the frontend with defaults and everything connects automatically.

Then run `npm run dev` in the `frontend/` directory.

## Environment Variables

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL for REST API calls (`/start-session`, `/stop-session`) |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | Base URL for WebSocket connections (`/ws/session/{id}`) |

### Backend (`src/backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `FEATHERLESS_API_KEY` | Yes | API key for Featherless LLM inference |
| `HUME_API_KEY` | Yes | API key for Hume TTS |
| `FEATHERLESS_PLANNER_MODEL` | No | Model ID for planner (default: a 70B model) |
| `FEATHERLESS_SPEAKER_MODEL` | No | Model ID for speaker (default: a 7–8B model) |

## Running the Full Demo

1. Start the mock server: `node mock-server.js` (from project root)
2. Start the frontend: `cd frontend && npm run dev`
4. Open `http://localhost:3000`
5. Enter a topic (e.g. "derivatives"), click through the wizard, and click "Start Session"

The dashboard will show live EEG band bars, cognitive state transitions, tutor conversation turns, and whiteboard content cycling through the scripted sequence. Click "Stop Session" to see the post-session summary with PDF export.

## Project Structure

```
BISV-Hacks/
├── frontend/               # Next.js app
│   └── src/
│       ├── app/            # Next.js pages (page.tsx = main session)
│       ├── components/     # UI components
│       │   └── ui/         # Reusable primitive components
│       └── lib/
│           ├── api.ts      # REST client
│           ├── types.ts    # Shared TypeScript types
│           ├── websocket/  # WS client + useWebSocket hook
│           └── voice/      # AudioPlayer, Microphone
├── src/backend/            # FastAPI backend
│   ├── api/                # Routes, models, WebSocket hub
│   ├── eeg/                # EEG ingestion, band power, classifier
│   ├── agents/             # Planner, speaker, summarizer
│   ├── session/            # Session store, tracker, events
│   └── voice/              # Hume TTS, VAD
├── mock-server.js          # Standalone Node.js mock WS server
├── docs/
│   ├── DIVISION_OF_LABOR.md
│   └── plans/
└── config/backend/         # Lesson plan stubs
```
