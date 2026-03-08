# NeuroSync — Division of Labor

**Backend:** Kavish + Aashu
**Frontend:** Vishvak + John
**Working style:** Parallel from day 1 — frontend uses the mock contract below until real backend is ready.

---

## Backend — Kavish + Aashu

### What you own end-to-end

#### EEG Pipeline (`/backend/eeg/`)
- `ingestion.py` — muselsl + pylsl stream reader; dedicated thread (never in asyncio event loop)
- `processor.py` — rolling-window band power extraction (alpha, beta, theta, gamma, delta)
- `classifier.py` — heuristic state classifier: `focus_score = beta/theta`, `cognitive_load = beta + gamma` → FOCUSED / OVERLOADED / DISENGAGED
- `filter.py` — dwell-time filter (3+ consecutive windows before firing state change event)
- `watchdog.py` — BLE watchdog; detects silent dropout by monitoring `last_packet_timestamp`; emits `SESSION_EVENT { type: "eeg_disconnected" }` on dropout

#### AI Agents (`/backend/agents/`)
- `planner.py` — Featherless API (70B model); generates initial lesson plan at session start; receives state-change trigger and produces updated strategy asynchronously
- `speaker.py` — Featherless API (7–8B model); receives student transcript + current strategy; returns `{ strategy, tone, response }` within 1.5s
- `lock.py` — `SPEAKER_RUNNING` asyncio lock; prevents planner from mutating session strategy while speaker is generating

#### Voice Pipeline (`/backend/voice/`)
- `tts.py` — ElevenLabs streaming TTS; takes speaker `response` text; streams audio chunks back over WebSocket as `AUDIO_CHUNK` messages
- `vad.py` — Voice Activity Detection; receives student audio signal level from frontend; fires `INTERRUPT` event to cut active TTS stream and re-route to speaker agent

#### Session Management (`/backend/session/`)
- `store.py` — in-memory session store; holds `{ session_id, lesson_plan, current_strategy, cognitive_state, conversation_history, topic_state_log }`
- `tracker.py` — records `(topic, timestamp, cognitive_state)` tuples throughout session for post-session analysis
- `summary.py` — on session end: computes time-per-state, per-topic comprehension inference, adaptation event log; returns `SessionSummary` object

#### API Layer (`/backend/api/`)
- `routes.py` — FastAPI route definitions (see REST contract below)
- `websocket.py` — WebSocket hub; typed message dispatcher; handles reconnection
- `main.py` — FastAPI app entry point; mounts routes + WebSocket; starts EEG ingestion thread on startup

---

## Frontend — Vishvak + John

### What you own end-to-end

#### WebSocket Client (`/src/lib/websocket/`)
- `client.ts` — WebSocket connection manager; auto-reconnect; parses incoming typed messages
- `useWebSocket.ts` — React hook; dispatches messages to state via `useReducer`; exposes `send(message)` helper

#### LiveKit Whiteboard (`/src/lib/livekit/`)
- `room.ts` — LiveKit room setup; data channel for whiteboard sync
- `whiteboard.ts` — whiteboard state manager; applies tutor deltas + student edits; resolves ordering conflicts
- `useWhiteboard.ts` — React hook exposing whiteboard state + `sendDelta(delta)` + `sendAnnotation(annotation)`

#### Voice Client (`/src/lib/voice/`)
- `microphone.ts` — browser microphone capture; Web Speech API STT; sends final transcript to backend via WebSocket `STUDENT_SPEECH` message
- `vad-client.ts` — sends audio signal level to backend every 100ms for server-side VAD
- `audio-player.ts` — receives `AUDIO_CHUNK` messages from backend; streams audio to speaker; handles interruption (stops playback immediately on `INTERRUPT` event)

#### UI Components (`/src/components/`)
- `CognitiveStateIndicator.tsx` — large badge: FOCUSED (green) / OVERLOADED (red) / DISENGAGED (amber); animates on state change
- `EEGBandBars.tsx` — 5 live bar charts (alpha, beta, theta, gamma, delta); each updates independently on `STATE_UPDATE`
- `AdaptationLog.tsx` — timestamped event feed: `"14:32:01 — OVERLOADED → Simplify → Speaker adjusted"`
- `ConversationTranscript.tsx` — alternating tutor/student bubbles; auto-scrolls; marks interrupted turns
- `WhiteboardPanel.tsx` — renders whiteboard state; KaTeX for equations; `<img>` for diagrams; annotation overlay
- `SessionControls.tsx` — Start Session button (initializes AudioContext + opens WebSocket); Stop Session button
- `PostSessionSummary.tsx` — state timeline chart + per-topic comprehension table + adaptation log; "Export PDF" button
- `PDFExport.ts` — browser-side PDF generation (no server); uses `window.print()` or a client-side PDF library

#### Pages (`/src/app/`)
- `page.tsx` — main tutoring session page; composes all components; layout: [EEG sidebar] [whiteboard] [conversation + voice]
- `summary/page.tsx` — post-session summary page; receives `SessionSummary` from backend on session end

---

## Interface Contract

This is the agreed data format. Backend delivers this shape. Frontend builds against these types from day 1.

### WebSocket Messages (Backend → Frontend)

All messages follow the envelope:
```json
{ "event_type": "...", "payload": { ... }, "timestamp": 1712345678 }
```

#### `STATE_UPDATE`
Fires every 1–2 seconds (or on state change).
```json
{
  "event_type": "STATE_UPDATE",
  "payload": {
    "state": "FOCUSED" | "OVERLOADED" | "DISENGAGED",
    "confidence": 0.81,
    "bands": {
      "alpha": 0.41,
      "beta": 0.58,
      "theta": 0.22,
      "gamma": 0.35,
      "delta": 0.19
    }
  },
  "timestamp": 1712345678
}
```

#### `CONVERSATION_TURN`
Fires when speaker agent produces a response.
```json
{
  "event_type": "CONVERSATION_TURN",
  "payload": {
    "speaker": "tutor",
    "strategy": "step_by_step" | "simplify" | "re_engage" | "increase_difficulty" | "continue",
    "tone": "slow" | "encouraging" | "neutral" | "challenging",
    "text": "That seemed like a lot. Let's slow down and go step by step.",
    "triggered_by_state": "OVERLOADED"
  },
  "timestamp": 1712345678
}
```

#### `AUDIO_CHUNK`
Streams ElevenLabs TTS in chunks. Frontend assembles and plays.
```json
{
  "event_type": "AUDIO_CHUNK",
  "payload": {
    "chunk_index": 0,
    "data": "<base64-encoded PCM or MP3 chunk>",
    "is_final": false
  },
  "timestamp": 1712345678
}
```

#### `INTERRUPT`
Backend VAD detected student speaking mid-playback. Frontend stops audio immediately.
```json
{
  "event_type": "INTERRUPT",
  "payload": {},
  "timestamp": 1712345678
}
```

#### `WHITEBOARD_DELTA`
Tutor writes to whiteboard.
```json
{
  "event_type": "WHITEBOARD_DELTA",
  "payload": {
    "author": "tutor",
    "type": "text" | "katex" | "image",
    "content": "f'(x) = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}",
    "position": { "x": 120, "y": 240 },
    "id": "block-uuid"
  },
  "timestamp": 1712345678
}
```

#### `SESSION_EVENT`
Lifecycle and error events.
```json
{
  "event_type": "SESSION_EVENT",
  "payload": {
    "type": "session_started" | "session_ended" | "eeg_disconnected" | "eeg_reconnected" | "lesson_ready",
    "data": { }
  },
  "timestamp": 1712345678
}
```

---

### WebSocket Messages (Frontend → Backend)

#### `STUDENT_SPEECH`
Web Speech API final transcript.
```json
{
  "event_type": "STUDENT_SPEECH",
  "payload": {
    "text": "Wait, I don't understand why the limit goes to zero",
    "session_id": "sess-abc123"
  }
}
```

#### `STUDENT_WHITEBOARD_DELTA`
Student types or imports to whiteboard.
```json
{
  "event_type": "STUDENT_WHITEBOARD_DELTA",
  "payload": {
    "author": "student",
    "type": "text" | "image" | "annotation",
    "content": "Is this the same as the slope formula?",
    "position": { "x": 80, "y": 300 },
    "id": "block-uuid"
  }
}
```

#### `VAD_SIGNAL`
Sent every 100ms; backend uses to detect barge-in.
```json
{
  "event_type": "VAD_SIGNAL",
  "payload": {
    "level": 0.73
  }
}
```

---

### REST Endpoints

#### `POST /start-session`
Request:
```json
{ "topic": "derivatives" }
```
Response:
```json
{
  "session_id": "sess-abc123",
  "lesson_plan": {
    "topic": "derivatives",
    "blocks": [
      { "id": "block-1", "title": "What is a derivative?", "difficulty": 1 },
      { "id": "block-2", "title": "The limit definition", "difficulty": 2 },
      { "id": "block-3", "title": "Power rule", "difficulty": 2 },
      { "id": "block-4", "title": "Practice problem", "difficulty": 3 }
    ],
    "current_block": "block-1"
  }
}
```

#### `POST /stop-session`
Request:
```json
{ "session_id": "sess-abc123" }
```
Response:
```json
{
  "summary": {
    "duration_seconds": 1240,
    "state_breakdown": {
      "FOCUSED": 680,
      "OVERLOADED": 320,
      "DISENGAGED": 240
    },
    "topics": [
      {
        "title": "What is a derivative?",
        "duration_seconds": 320,
        "dominant_state": "FOCUSED",
        "comprehension": "strong"
      },
      {
        "title": "The limit definition",
        "duration_seconds": 480,
        "dominant_state": "OVERLOADED",
        "comprehension": "needs_review"
      }
    ],
    "adaptation_events": [
      {
        "timestamp": 1712345900,
        "from_state": "FOCUSED",
        "to_state": "OVERLOADED",
        "strategy_applied": "step_by_step"
      }
    ]
  }
}
```

---

## Mock Contract for Parallel Development

Backend must deliver this by end of **Day 1** so frontend can work without a real backend.

### File: `/backend/mock_server.py`

A standalone FastAPI app that:
1. Serves all REST endpoints with hardcoded example responses (matching the shapes above exactly)
2. Opens a WebSocket at `/ws` and emits a scripted sequence every few seconds:
   - t=0: `SESSION_EVENT { type: "session_started" }`
   - t=2: `STATE_UPDATE { state: "FOCUSED", bands: {...} }`
   - t=5: `CONVERSATION_TURN { strategy: "continue", text: "Let's start with what a derivative means geometrically." }`
   - t=10: `STATE_UPDATE { state: "OVERLOADED" }`
   - t=12: `CONVERSATION_TURN { strategy: "step_by_step", text: "Let's slow down. Step one only." }`
   - t=15: `WHITEBOARD_DELTA { type: "katex", content: "f'(x) = ..." }`
   - t=30: `STATE_UPDATE { state: "DISENGAGED" }`
   - loop back

Run with: `uvicorn mock_server:app --port 8001`
Frontend points to `ws://localhost:8001/ws` during local development.

---

## Integration Checkpoints

| When | What backend delivers | What frontend needs it for |
|------|----------------------|---------------------------|
| Day 1 end | `mock_server.py` running on port 8001 | All UI components can be built and wired |
| Phase 1 complete | Real `STATE_UPDATE` messages from live EEG | Replace mock; verify band bars + state badge |
| Phase 2 complete | Real `/start-session`, `CONVERSATION_TURN` messages | Wire session start flow + transcript |
| Phase 3 complete | Real `AUDIO_CHUNK` + `INTERRUPT` messages | Wire audio playback + barge-in |
| Phase 5 complete | Real `/stop-session` summary response | Wire post-session summary page + PDF export |
