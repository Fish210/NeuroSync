# Architecture Patterns: NeuroSync

**Domain:** Neuroadaptive AI tutoring system with real-time EEG, voice I/O, two-agent AI, shared whiteboard
**Researched:** 2026-03-08
**Confidence:** HIGH (well-understood component boundaries; latency constraints from project spec; patterns derived from established real-time streaming and multi-agent system design)

---

## Recommended Architecture

NeuroSync is a four-layer system:

```
[Hardware Layer]        Muse Headband → muselsl → LSL outlet

[Backend Layer]         LSL inlet reader → EEG processor → cognitive state classifier
                        Two-agent AI engine (planner + speaker)
                        ElevenLabs TTS caller
                        FastAPI WebSocket hub
                        Session state store (in-memory)

[Transport Layer]       WebSocket (state push, whiteboard sync, conversation)
                        REST (session start/end, lesson load, image upload)
                        HTTP streaming (audio chunks from ElevenLabs)

[Frontend Layer]        Next.js app
                        Browser mic → STT (Web Speech API or Whisper)
                        Audio playback (HTMLAudioElement or Web Audio API)
                        Whiteboard panel (text + image display)
                        Cognitive state panel + EEG band viz
                        Conversation history panel
```

The backend is the single source of truth for cognitive state, lesson strategy, and session state. The frontend is a pure display and input layer — it sends user speech/text in, receives structured updates out. No business logic lives in the browser.

---

## Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| **EEG Ingestor** | Reads LSL stream from muselsl; buffers raw EEG samples | LSL outlet (Muse → muselsl) | Raw sample buffer | EEG Processor |
| **EEG Processor** | Computes rolling-window band powers (alpha, beta, theta, delta) via FFT; maintains 1–2s window | Raw sample buffer | Band power dict per window | Cognitive State Classifier |
| **Cognitive State Classifier** | Applies heuristic thresholds to band powers; emits state on change or on timer | Band power dict | FOCUSED / OVERLOADED / DISENGAGED label + confidence | State Router |
| **State Router** | Detects state transitions; triggers planner update; pushes state to frontend | New state label | Planner update trigger, WebSocket state event | Planner Agent, WebSocket Hub |
| **Planner Agent** | Holds lesson strategy; generates lesson at session start; rewrites strategy on state change; sends updated system prompt to speaker | State change trigger, user topic | Lesson plan JSON, strategy directive for speaker | Speaker Agent, Session Store |
| **Speaker Agent** | Handles turn-by-turn conversation; applies current strategy; generates short tutor responses | User message, current strategy directive | Tutor text response | Featherless API, TTS Caller, WebSocket Hub |
| **TTS Caller** | Sends tutor text to ElevenLabs; streams audio back | Tutor text | Audio chunk stream (MP3 or PCM) | WebSocket Hub or direct REST |
| **STT Handler** | Receives browser audio or transcript; converts speech to text if needed (or accepts browser-provided transcript) | Audio blob or transcript string | User text message | Speaker Agent |
| **Session Store** | Holds in-memory session state: topic, lesson plan, current strategy, conversation history, current cognitive state | All agents read/write | Session state snapshot | All backend components |
| **Whiteboard Manager** | Accepts tutor-generated text/diagrams/images; accepts user-uploaded images; broadcasts deltas | Tutor output, user upload | Whiteboard delta events | WebSocket Hub |
| **WebSocket Hub** | Central multiplexer for all real-time pushes to the browser | State events, whiteboard deltas, conversation turns, audio URLs | WebSocket messages (typed by `event_type`) | Frontend |
| **REST API** | Session lifecycle (start, end); image uploads; static lesson retrieval | HTTP requests | HTTP responses | Frontend |
| **Frontend — State Panel** | Shows current cognitive state label; renders EEG band bar chart | WebSocket state events | None (display only) | WebSocket Hub |
| **Frontend — Whiteboard** | Renders tutor text/equations/images; accepts user text input and image uploads | WebSocket whiteboard events, user interactions | User input events → backend REST/WS | WebSocket Hub, REST API |
| **Frontend — Conversation** | Shows turn-by-turn chat history; captures browser mic | WebSocket conversation events, browser mic | Audio blob or transcript → backend | WebSocket Hub, STT Handler |
| **Frontend — Audio Player** | Plays ElevenLabs audio as it arrives | Audio URL or chunk from WebSocket | Speaker audio output | WebSocket Hub |

---

## Data Flow

### Flow 1: EEG → Cognitive State → Frontend Display (latency target: <200ms processing + ~1s push cadence)

```
Muse headband
  → [muselsl daemon, runs separately on same machine]
  → LSL outlet (localhost TCP)
  → EEG Ingestor (pylsl inlet, async thread)
  → ring buffer (last N samples, e.g. 256 samples @ 256Hz = 1s)
  → EEG Processor (FFT → band powers: alpha, beta, theta, delta)
  → Cognitive State Classifier (heuristic threshold check)
  → [IF state changed OR 1s cadence tick]
  → State Router
  → WebSocket Hub
  → browser: state panel updates, EEG band chart updates
```

### Flow 2: State Change → Planner → Speaker Strategy Update (latency target: <1.5s AI decision)

```
State Router detects transition (e.g. FOCUSED → OVERLOADED)
  → Planner Agent triggered (async, non-blocking to speaker)
  → Planner sends current lesson plan + new state to Featherless API
  → Featherless returns updated strategy directive (e.g. "simplify next explanation, use analogy")
  → Planner writes new strategy to Session Store
  → Speaker Agent reads updated strategy on next turn
  → [Optional] Planner-triggered proactive tutor utterance:
      → Speaker Agent generates brief transition phrase
      → TTS Caller → ElevenLabs
      → Audio URL pushed via WebSocket Hub → frontend plays
```

### Flow 3: User Voice → Speaker → Voice Response (latency target: voice start <2s from user speech end)

```
Browser mic (MediaRecorder API)
  → [Option A] Web Speech API: transcript string sent via WebSocket
  → [Option B] Audio blob sent via WebSocket → STT Handler (Whisper endpoint or OpenAI STT)
  → STT Handler emits user text message to Speaker Agent
  → Speaker Agent: reads current strategy from Session Store, builds prompt
  → Featherless API returns tutor text response
  → text pushed via WebSocket → Conversation panel renders
  → TTS Caller: POST text to ElevenLabs streaming endpoint
  → Audio stream URL or chunk pushed via WebSocket
  → frontend AudioPlayer plays
  → [Whiteboard update if response contains structured content]
      → Speaker Agent emits whiteboard delta
      → WebSocket Hub → Whiteboard panel renders
```

### Flow 4: Session Lifecycle

```
User clicks "Start Session" with topic
  → POST /session/start {topic}
  → Session Store initialized (empty lesson plan, FOCUSED default state)
  → Planner Agent called: generate lesson plan for topic
  → Lesson plan written to Session Store
  → EEG Ingestor starts listening to LSL stream
  → WebSocket connection established (frontend connects)
  → Frontend receives initial state event: lesson title, first content block
  → [Adaptive loop runs continuously until "End Session"]
  → POST /session/end
  → Session Store cleared, WebSocket closed, EEG Ingestor paused
```

### Flow 5: User Text / Image → Whiteboard

```
User types text in whiteboard OR uploads image
  → REST POST /whiteboard/user-input {type: text|image, content}
  → Whiteboard Manager validates, stores in session
  → Speaker Agent notified (can reference user input in next response)
  → WebSocket Hub broadcasts whiteboard delta to all connections (confirms to user)
```

---

## Latency-Critical Paths

### Path 1: EEG Processing Loop (hardest real-time constraint)

**Target:** <200ms per cycle end-to-end (EEG sample → state classification)

**Critical decisions:**
- Run EEG Ingestor in a dedicated async thread or subprocess — do NOT block the FastAPI event loop.
- Use `asyncio.Queue` to pass band power dicts from the EEG thread to the async state router.
- FFT computation on a 1–2s rolling window at 256Hz is cheap (NumPy FFT on 256–512 samples) — no GPU needed.
- State push to WebSocket should be fire-and-forget; never await TTS or AI calls inside the EEG loop.

**Risk:** LSL sample jitter from Bluetooth Muse. Mitigate by buffering with enough headroom (use 2s window, classify every 1s) to smooth over dropped packets.

### Path 2: Speaker Agent Response (user-facing latency)

**Target:** Tutor text appears <800ms after user finishes speaking; audio starts <2s.

**Critical decisions:**
- Speaker Agent must NOT wait for Planner Agent to complete before responding. Planner runs asynchronously and writes strategy to Session Store. Speaker reads the current strategy at call time.
- Keep Speaker Agent system prompt short — strategy directive should be <200 tokens. Longer prompts increase TTFT (time-to-first-token) at Featherless API.
- Use ElevenLabs streaming endpoint (`/v1/text-to-speech/{voice_id}/stream`) — start playing as first audio chunks arrive, do not wait for full generation.
- Push audio as a URL (pre-generate full clip) if streaming is unreliable in demo environment — this trades latency for reliability. Decide at integration test time.

### Path 3: Planner Agent (background, but affects next speaker turn)

**Target:** Planner completes within ~3–5s of state change (before next user turn).

**Critical decisions:**
- Planner runs in a background `asyncio.create_task` — never blocks the main request path.
- Planner updates Session Store atomically (dict update is GIL-protected in CPython; sufficient for hackathon).
- If Planner is still running when a new state change arrives, cancel the previous Planner task and start fresh (use `asyncio.Task.cancel()`).

### Path 4: WebSocket Message Delivery

**Target:** State updates reach browser within 50ms of emission.

**Critical decisions:**
- Single WebSocket connection per session (not per component). One hub, typed messages by `event_type` field.
- Do not multiplex audio binary data over the same WebSocket as JSON events — keep audio as HTTP URL or a separate binary WebSocket message to avoid head-of-line blocking.

---

## Suggested Build Order

Components must be built in dependency order. The EEG pipeline and the voice pipeline are parallel tracks that converge at the WebSocket hub.

### Phase 1: Foundation (everything else depends on this)

1. **Session Store** — in-memory dict with typed fields; no persistence. All agents read/write this.
2. **FastAPI app skeleton** — WebSocket hub, REST endpoints (session start/end), CORS for Next.js dev server.
3. **Next.js skeleton** — WebSocket client hook, basic layout (4 panels: state, whiteboard, conversation, EEG viz).

### Phase 2: EEG Pipeline (demo's core differentiator — validate early)

4. **EEG Ingestor** — pylsl inlet reader in async thread; synthetic data mode for when headband not available during development.
5. **EEG Processor** — rolling window FFT; emit band powers.
6. **Cognitive State Classifier** — heuristic thresholds; emit state label.
7. **State Router + WebSocket push** — push state events to browser; render state panel in frontend.

Validate: headband on → JSON events arriving in browser with correct state labels. This must work before AI is integrated.

### Phase 3: AI Agent Pair

8. **Speaker Agent** — basic turn-by-turn chat with Featherless API; no strategy yet; just responds to user messages.
9. **STT Handler** — browser mic → Web Speech API transcript → WebSocket → Speaker Agent.
10. **TTS Caller** — Speaker Agent text → ElevenLabs → audio playback in browser.
11. **Planner Agent** — lesson generation at session start; strategy rewrite on state change; writes to Session Store.
12. **Wire planner strategy into Speaker Agent** — Speaker reads current strategy directive on each turn.

Validate: full adaptive loop. Wear headband, trigger state change (relax vs. concentrate), observe Speaker tone shift in next response.

### Phase 4: Whiteboard + Polish

13. **Whiteboard Manager** — tutor writes text/equations to whiteboard panel; render in frontend.
14. **User whiteboard input** — text input + image upload from frontend → backend → broadcast.
15. **EEG band visualization** — chart in frontend showing live alpha/beta/theta/delta.
16. **Conversation history panel** — scrollable turn list.
17. **Session start/end UI flow** — topic entry, start button, end button.

### Phase 5: Integration + Demo Hardening

18. End-to-end latency measurement and tuning.
19. Fallback handling: Featherless API timeout, ElevenLabs failure, LSL dropout.
20. Demo script validation: run full loop 5 times, confirm reliable state transitions.

---

## Component Interaction Diagram (ASCII)

```
                        ┌──────────────────────────────────────────────────────────┐
                        │                    BACKEND (FastAPI)                      │
                        │                                                            │
  Muse Headband         │  ┌──────────┐    ┌──────────┐    ┌───────────────────┐   │
  ──→ muselsl ──────────┼──│  EEG     │───▶│  EEG     │───▶│ Cognitive State   │   │
       (LSL outlet)     │  │ Ingestor │    │Processor │    │   Classifier      │   │
                        │  └──────────┘    └──────────┘    └────────┬──────────┘   │
                        │                                            │               │
                        │                                    ┌───────▼──────────┐   │
                        │                                    │  State Router    │   │
                        │                                    └──┬────────────┬──┘   │
                        │                                       │            │       │
                        │                          ┌────────────▼──┐  ┌─────▼────┐  │
                        │                          │ Planner Agent  │  │WebSocket │  │
                        │                          │(Featherless API│  │   Hub    │◀─┼──┐
                        │                          │ async task)    │  └─────┬────┘  │  │
                        │                          └───────┬────────┘        │       │  │
                        │                                  │                 │       │  │
                        │                        ┌─────────▼──────┐          │       │  │
                        │                        │  Session Store  │          │       │  │
                        │                        │ (in-memory dict)│          │       │  │
                        │                        └─────────┬───────┘          │       │  │
                        │                                  │                  │       │  │
  Browser Mic           │  ┌────────────┐  ┌──────────────▼────┐             │       │  │
  ──→ Web Speech API ───┼─▶│STT Handler │─▶│  Speaker Agent    │             │       │  │
                        │  └────────────┘  │ (Featherless API) │             │       │  │
                        │                  └─────┬─────────────┘             │       │  │
                        │                        │                            │       │  │
                        │                  ┌─────▼──────────┐                │       │  │
                        │                  │  TTS Caller    │                │       │  │
                        │                  │  (ElevenLabs)  │                │       │  │
                        │                  └─────┬──────────┘                │       │  │
                        │                        │  audio URL/chunk          │       │  │
                        │                        └──────────────────────────▶│       │  │
                        │                                                     │       │  │
  Whiteboard Input      │  ┌─────────────────┐                               │       │  │
  ──→ REST POST ────────┼─▶│ Whiteboard Mgr  │──────────────────────────────▶│       │  │
                        │  └─────────────────┘                               │       │  │
                        └────────────────────────────────────────────────────┴───────┘  │
                                                                             │           │
                                                                    WebSocket│           │
                                                                    messages  │           │
                                                                             ▼           │
                        ┌──────────────────────────────────────────────────────────┐    │
                        │                 FRONTEND (Next.js)                        │    │
                        │                                                            │    │
                        │  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐   │    │
                        │  │ State Panel │  │ EEG Band   │  │  Whiteboard       │   │    │
                        │  │ (FOCUSED /  │  │  Viz       │  │ (text, equations, │   │    │
                        │  │  OVERLOADED │  │ (bar chart)│  │  images)          │   │    │
                        │  │  DISENGAGED)│  └────────────┘  └──────────────────┘   │    │
                        │  └─────────────┘                                          │    │
                        │                                                            │    │
                        │  ┌─────────────────────────┐  ┌───────────────────────┐  │    │
                        │  │  Conversation History    │  │    Audio Player       │  │    │
                        │  │  (tutor + user turns)    │  │ (ElevenLabs playback) │  │    │
                        │  └─────────────────────────┘  └───────────────────────┘  │    │
                        │                                                            │    │
                        │  Browser Mic (MediaRecorder) ──→ Web Speech API ──────────┼────┘
                        └──────────────────────────────────────────────────────────┘
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: EEG Loop Blocking the FastAPI Event Loop

**What:** Calling `inlet.pull_sample()` (blocking LSL call) directly in an `async def` FastAPI handler or without threading.
**Why bad:** Blocks all WebSocket and HTTP handling. Sub-200ms EEG cycle becomes sub-X-second everything else.
**Instead:** Run the LSL reader in a `threading.Thread` or `asyncio.to_thread`. Use `asyncio.Queue` to hand results to the async event loop.

### Anti-Pattern 2: Planner Blocking Speaker

**What:** Making Speaker Agent await Planner Agent completion before generating a response.
**Why bad:** Planner can take 3–5s (LLM call + strategy reasoning). User sees multi-second silence after speaking.
**Instead:** Planner runs as a background task. Speaker reads whatever strategy is in Session Store at call time. Stale strategy for one turn is acceptable.

### Anti-Pattern 3: One WebSocket Message Type for Everything

**What:** Sending all events (state, whiteboard, conversation, audio) as generic JSON blobs without an `event_type` discriminator.
**Why bad:** Frontend must defensively parse every message. Adding new event types causes frontend regressions.
**Instead:** All WebSocket messages have a top-level `event_type` field. Frontend switches on this. Define an enum: `STATE_UPDATE | WHITEBOARD_DELTA | CONVERSATION_TURN | AUDIO_READY | SESSION_EVENT`.

### Anti-Pattern 4: Generating Full Audio Before Playback

**What:** Waiting for ElevenLabs to return a complete MP3 before sending to frontend.
**Why bad:** ElevenLabs can take 1–3s for full generation. Voice start target is <2s — full-generation wait burns that budget.
**Instead:** Use ElevenLabs streaming endpoint. Send audio chunk URL or binary chunk frames to frontend as they arrive. Frontend uses Web Audio API or MediaSource Extensions to play incrementally.

### Anti-Pattern 5: Rebuilding Full Lesson Plan on Every State Change

**What:** Planner regenerates the entire lesson plan (topic intro, examples, exercises) from scratch each time cognitive state changes.
**Why bad:** Full lesson plan generation is slow (many tokens). State can change every 1–2s under active use.
**Instead:** Generate lesson plan once at session start. On state change, Planner generates only a strategy directive (e.g., "for the next 2 minutes, use simpler vocabulary and shorter sentences"). Speaker injects this directive into its system prompt.

### Anti-Pattern 6: Browser STT Over WebSocket for Long Utterances

**What:** Streaming raw audio binary over WebSocket to a backend Whisper endpoint for every user utterance.
**Why bad:** Adds latency (audio upload + Whisper inference). WebSocket binary frames compete with JSON event frames.
**Instead:** Use Web Speech API (built into Chrome/Edge) for in-browser STT with near-zero latency. Send only the final transcript string over WebSocket. Fall back to Whisper only if demo device lacks Web Speech API support.

---

## Scalability Considerations

This is a hackathon demo — single session, single user. Scale targets are not relevant to NeuroSync. However, the architecture naturally allows:

| Concern | At 1 user (target) | If extended post-hackathon |
|---------|-------------------|---------------------------|
| EEG streams | 1 LSL inlet, 1 thread | Multiple LSL inlets with session-keyed threads |
| WebSocket connections | 1 per session | Rooms pattern (FastAPI + Redis pub/sub) |
| Session state | In-memory dict | Redis with session TTL |
| AI agent calls | Direct HTTP to Featherless | Queue-backed worker pool |
| Audio delivery | ElevenLabs direct | CDN-backed cached clips for repeated phrases |

---

## Technology Binding

| Concern | Technology | Binding Rationale |
|---------|-----------|-------------------|
| EEG ingestion | pylsl (Python LSL binding) | Direct LSL integration; muselsl outputs LSL streams |
| Band power computation | NumPy FFT | Fast, dependency-free, sufficient for 256Hz EEG |
| Backend framework | FastAPI + uvicorn | Async-native, WebSocket support, fast for hackathon |
| WebSocket server | FastAPI WebSocket (Starlette) | Built-in, no additional layer |
| AI agents | Featherless API (project constraint) | Specified in PROJECT.md |
| Voice synthesis | ElevenLabs streaming API | Specified in PROJECT.md; streaming endpoint is critical |
| STT | Web Speech API (primary), Whisper (fallback) | Web Speech API has ~0ms latency penalty |
| Frontend | Next.js + TailwindCSS | Specified in PROJECT.md |
| Audio playback | HTMLAudioElement (simple) or MediaSource Extensions (streaming) | Choose at integration test: simple if full-clip latency acceptable |
| Session state | Python dict (in-memory) | No persistence needed; hackathon scope |

---

## Sources

- PROJECT.md (primary requirements and constraints)
- FastAPI WebSocket documentation patterns (HIGH confidence — core framework knowledge)
- LSL (Lab Streaming Layer) architecture: pylsl blocking I/O model requires threading (HIGH confidence — well-documented LSL design constraint)
- ElevenLabs streaming API endpoint design: `/v1/text-to-speech/{id}/stream` (MEDIUM confidence — known from training data; verify endpoint path against current ElevenLabs docs at integration time)
- Web Speech API browser support: Chrome/Edge native support (HIGH confidence — stable W3C API)
- Multi-agent background task pattern with asyncio: asyncio.create_task for non-blocking agent calls (HIGH confidence — Python async pattern)
- MediaSource Extensions for incremental audio playback (MEDIUM confidence — browser support is broad but MSE setup is non-trivial; validate at integration time)
