# Project Research Summary

**Project:** NeuroSync — Neuroadaptive AI Tutoring System
**Domain:** Real-time EEG-driven adaptive tutoring with voice I/O, two-agent AI, and shared whiteboard
**Researched:** 2026-03-08
**Confidence:** MEDIUM (web search unavailable during research; findings from training knowledge through August 2025)

## Executive Summary

NeuroSync is a live hardware demo system that closes a four-stage loop: Muse EEG headband → cognitive state classification → AI-driven pedagogy adaptation → voice-and-whiteboard tutor output. The architecture is well-understood — a FastAPI async backend with a dedicated EEG ingestion thread, two Featherless-hosted AI agents (a fast 7–8B speaker and a slower 70B planner), ElevenLabs TTS streamed over WebSocket to a Next.js frontend. The critical constraint is total round-trip latency under 2 seconds from EEG signal to spoken audio, which is achievable if and only if the speaker agent uses a sub-8B model, ElevenLabs Flash v2.5 is used with streaming enabled, and the Web Speech API handles STT in-browser. No exotic patterns are required: `asyncio.Queue` + a dedicated threading.Thread for EEG, a shared in-memory session dict for agent coordination, and typed WebSocket envelopes for frontend messaging.

The recommended build order is non-negotiable due to hard dependencies. The EEG pipeline must be validated first — before any AI integration — because every downstream feature depends on reliable cognitive state delivery. The two-agent architecture must be wired with a state machine that prevents planner-speaker race conditions before demo day. Voice I/O is the highest-risk integration point due to browser autoplay policy, microphone permission rules, and ElevenLabs character quota constraints; each of these fails silently and must be tested explicitly on the demo machine.

The single most dangerous failure mode is the Muse headband dropping its Bluetooth connection mid-demo. A visible EEG connection watchdog and a manual cognitive state override must be built in Phase 1, not treated as polish. All cloud dependencies (Featherless, ElevenLabs) must have explicit fallback paths because hackathon venue WiFi is unreliable. The canned demo fallback and browser-native speech synthesis fallback are not optional — they are insurance against total demo failure.

---

## Key Findings

### Recommended Stack

The backend stack centers on FastAPI 0.111 with uvicorn, pylsl for LSL ingestion, scipy for EEG bandpass filtering, and the OpenAI Python SDK pointed at Featherless's OpenAI-compatible endpoint. The EEG layer uses muselsl as the Muse-specific Bluetooth-to-LSL bridge with no viable alternative. For AI agents, the speaker must use a 7–8B model (Llama-3.1-8B-Instruct or Mistral-7B) to meet the 1.5s AI decision budget; the planner can use a 70B model since it runs asynchronously. ElevenLabs Flash v2.5 (`eleven_turbo_v2_5`) is the only TTS option that meets the 2-second voice start budget. The frontend is Next.js 14 with Recharts for EEG visualization and KaTeX/react-markdown for whiteboard equation rendering. Do not use LangChain, Socket.io, Redux, MathJax, or mne as a hard dependency — each adds complexity without proportional benefit at hackathon scale.

**Core technologies:**
- `muselsl` + `pylsl`: Muse headband → LSL stream → Python ingestion — only viable path; no alternative
- `scipy.signal.butter` + `sosfilt`: EEG bandpass and band power computation — lighter than MNE, sufficient
- `FastAPI` + `uvicorn`: Async backend with native WebSocket hub — async-first is required for concurrent EEG + AI
- `openai` SDK (base_url override): Featherless API client — eliminates HTTP boilerplate; handles streaming
- `elevenlabs` SDK with `eleven_turbo_v2_5`: TTS with ~400ms first chunk — latency-critical choice
- `Web Speech API` (browser-native): STT with zero network latency — eliminates Deepgram/Whisper complexity
- `Next.js 14` + `Recharts` + `KaTeX`: Frontend with EEG visualization and math rendering
- Native browser `WebSocket` API: Not Socket.io; typed JSON envelope with `event_type` discriminator

### Expected Features

**Must have (P0 — demo fails without these):**
- EEG connection status badge and cognitive state indicator (FOCUSED / OVERLOADED / DISENGAGED)
- EEG band power visualization (5 bars, 1–2s update — makes EEG data credible to judges)
- Voice input via browser mic (Web Speech API)
- Voice output via ElevenLabs TTS streamed to browser
- Planner agent: lesson plan at session start, strategy updates on state change
- Speaker agent: turn-by-turn responses incorporating current strategy
- Tutor transcript / conversation history panel
- Whiteboard panel with tutor-written text and LaTeX equations
- Session start flow with topic selection (single deliberate click initializes AudioContext)

**Should have (P1 — compelling demo):**
- Adaptation event log feed with timestamps ("State: OVERLOADED → Strategy: Simplify")
- Current strategy display label (one line, near transcript)
- Cognitive state history sparkline (30–60s of transitions)
- EEG signal quality / headband contact indicator

**Defer to P2 or later:**
- Whiteboard image upload by student
- Two-agent activity labels (planner vs speaker status indicators)
- Live demo reliability mode with graceful EEG disconnect messaging

**Explicit anti-features (do not build):**
- Freehand drawing canvas, OCR of handwriting, ML-based EEG classification
- User accounts, persistent analytics, multi-student mode, animated avatar
- Scrolling raw EEG waveform, mobile-responsive layout, i18n

The UI layout must express the causal chain left-to-right or top-to-bottom: `[EEG Band Bars] → [State Badge] → [Strategy Label] → [Tutor Transcript]`. Judges need to read the loop in under 5 seconds without verbal explanation.

### Architecture Approach

NeuroSync is a four-layer system: hardware (Muse → muselsl → LSL), backend (FastAPI with EEG pipeline + agent pair + session store), transport (single WebSocket per session with typed `event_type` envelope), and frontend (Next.js display/input layer with zero business logic). The backend is the single source of truth. The EEG ingestion thread is separated from the async FastAPI event loop via `asyncio.Queue`. The planner runs as a background `asyncio.create_task` and writes strategy updates to a shared in-memory session dict; the speaker reads the current strategy at invocation time without waiting for the planner. Audio is delivered via ElevenLabs streaming endpoint — do not wait for full audio generation before playback begins.

**Major components:**
1. **EEG Ingestor** — dedicated threading.Thread pulling LSL samples into a ring buffer; watchdog monitors packet timestamp for dropout
2. **EEG Processor + State Classifier** — rolling 2s FFT window, band powers, heuristic thresholds with relative baseline and dwell-time hysteresis filter (minimum 3-window dwell before state transition)
3. **State Router** — detects transitions; triggers Planner background task; pushes state events to WebSocket Hub
4. **Session Store** — in-memory Python dict holding topic, lesson plan, current strategy, conversation history, cognitive state; all agents read/write via asyncio Lock or atomic field access
5. **Planner Agent** — async background task on state change; generates strategy directive only (not full lesson plan); 10-second minimum cooldown between invocations
6. **Speaker Agent** — per-turn Featherless API call with current strategy directive injected; reads session store at call time; responses capped at ~60 words
7. **TTS Caller** — ElevenLabs streaming endpoint; chunks pushed over WebSocket binary frames; AudioContext pre-initialized on "Start Session" click
8. **WebSocket Hub** — single connection per session; all event types multiplexed with `event_type` field; reconnect logic with exponential backoff on frontend

### Critical Pitfalls

1. **Muse Bluetooth dropout during demo** — Build a watchdog thread in Phase 1 that tracks `last_packet_timestamp`; trigger visible UI warning if no sample in >2s; disable laptop BLE power saving; test at venue hardware before demo
2. **EEG state flicker causing runaway Planner calls** — Apply 2s rolling window for band powers, exponential moving average smoothing, and 3-window dwell-time filter; enforce 10-second minimum cooldown on Planner invocations; without this, Featherless hits rate limits and the demo collapses
3. **Browser autoplay policy silently blocks all audio** — Require an explicit "Start Session" button click as the first interaction; call `audioContext.resume()` in that handler; test in incognito Chrome the day before demo
4. **Microphone permission denied on non-localhost URLs** — Demo from `localhost:3000` only; never from `http://192.168.x.x:3000` (microphone blocked on non-HTTPS non-localhost); pre-grant mic permission in demo browser profile
5. **Planner-Speaker race condition on shared state** — Speaker reads `current_strategy` at invocation start; Planner writes to `pending_strategy`; strategy swap applies at next Speaker turn, never mid-response; implement `asyncio.Lock` around session store writes

---

## Implications for Roadmap

Based on the architecture's hard dependency chain and the pitfall severity map, the recommended phase structure mirrors the dependency order from ARCHITECTURE.md with pitfall mitigations integrated into the phases where failures are most likely.

### Phase 1: EEG Pipeline Foundation
**Rationale:** Everything depends on reliable EEG data delivery. Validate the hardware loop before writing a single line of AI code. The Bluetooth watchdog must exist before the AI layer is added — once the AI layer is in, a silent EEG failure will be blamed on AI bugs.
**Delivers:** muselsl → pylsl → band power computation → cognitive state classifier → WebSocket state events visible in browser. Includes: watchdog for disconnect detection, relative baseline computation, dwell-time hysteresis filter, HSI contact quality monitoring, manual state override hotkey.
**Features addressed (FEATURES.md P0/P1):** EEG connection status badge, cognitive state indicator, EEG band power visualization
**Pitfalls avoided:** Pitfall 1 (Bluetooth dropout), Pitfall 2 (LSL starvation), Pitfall 3 (state flicker), Pitfall 11 (headband noise/fit), Pitfall 15 (asyncio deadlock), Pitfall 17 (LSL clock drift)
**Research flag:** Standard patterns — LSL threading model and scipy DSP are well-documented

### Phase 2: Backend Infrastructure and Agent Architecture
**Rationale:** The agent state machine must be designed before either agent is implemented. Retrofitting race condition prevention after agents are wired together is expensive. CORS and WebSocket reconnect must be configured on day 1 — both fail silently and will waste hours of debugging if added later.
**Delivers:** FastAPI app with session store, REST endpoints (session start/end), WebSocket hub with typed `event_type` envelope, CORS middleware, frontend WebSocket reconnect hook with exponential backoff, Planner-Speaker coordination state machine (pending_strategy / current_strategy split), Featherless API client with 429 handling and planner cooldown guard.
**Features addressed:** Two-agent architecture (Planner + Speaker wired), session lifecycle
**Pitfalls avoided:** Pitfall 6 (no WebSocket reconnect), Pitfall 7 (race condition), Pitfall 8 (API rate limit), Pitfall 12 (CORS), Pitfall 15 (asyncio deadlock)
**Research flag:** Standard patterns — FastAPI WebSocket, asyncio task management are well-documented

### Phase 3: Voice I/O Integration
**Rationale:** Voice is the highest-risk integration layer. Browser autoplay policy, microphone permissions, ElevenLabs latency, and character quota are all silent failure modes that require explicit testing on the demo machine. This phase must be isolated so failures are clearly attributable.
**Delivers:** Speaker Agent generating text responses via Featherless API, ElevenLabs Flash v2.5 TTS with streaming audio chunks over WebSocket, AudioContext pre-initialization on "Start Session" click, Web Speech API transcription with VAD, browser speechSynthesis fallback if ElevenLabs quota is exhausted, STT fallback path documented.
**Features addressed (FEATURES.md P0):** Voice input, voice output, tutor response/transcript area
**Pitfalls avoided:** Pitfall 4 (ElevenLabs latency), Pitfall 5 (autoplay block), Pitfall 9 (microphone permission), Pitfall 10 (STT latency), Pitfall 13 (ElevenLabs quota)
**Research flag:** Needs validation — ElevenLabs streaming endpoint path and current latency figures for `eleven_turbo_v2_5` must be verified against live API on demo machine; Featherless first-call cold-start latency must be measured empirically

### Phase 4: Whiteboard and UI Completion
**Rationale:** Whiteboard and polish features have no upstream dependencies except the WebSocket hub established in Phase 2. This phase delivers the visible narrative UI and can be parallelized with Phase 3 if team size allows.
**Delivers:** Whiteboard panel with tutor text/LaTeX/image rendering (KaTeX + react-markdown), user text input on whiteboard, adaptation event log feed, current strategy display, cognitive state history sparkline, conversation history panel, session start/end UI flow, EEG band power bar chart in frontend.
**Features addressed (FEATURES.md P0 + P1):** Full UI feature set including adaptation event log, strategy display, sparkline
**Pitfalls avoided:** Pitfall 14 (stale React closures — use `useReducer`), Pitfall 18 (KaTeX rendering errors — wrap in try/catch)
**Research flag:** Standard patterns — React useReducer, Recharts, KaTeX are well-documented

### Phase 5: Integration Testing and Demo Hardening
**Rationale:** Demo hardening is a distinct phase, not an afterthought. Venue WiFi unreliability, headband fit variance across demo subjects, and cold-start API latency are not discoverable until the full system runs on the actual demo machine with the actual hardware.
**Delivers:** End-to-end latency measurement (all five flows timed with stopwatch), mobile hotspot as primary connectivity, canned demo fallback mode (pre-recorded state changes + responses activate on hotkey), pre-demo contact quality check procedure, full loop stress test (5 runs minimum), ElevenLabs quota check in pre-demo checklist.
**Features addressed:** Live demo reliability mode (P2), graceful EEG disconnect handling
**Pitfalls avoided:** Pitfall 16 (venue WiFi failure), Pitfall 1 (headband reconnect procedure), Pitfall 5 (autoplay — final incognito test), Pitfall 9 (microphone — final demo machine test)
**Research flag:** No research needed — this is operational execution

### Phase Ordering Rationale

- **EEG before AI:** The cognitive state signal is the input to the AI layer. Integrating AI before the EEG pipeline is stable means bugs in one layer appear as bugs in the other. Validate EEG in isolation first.
- **Agent architecture before agent code:** The Planner-Speaker state machine is a design artifact, not an implementation artifact. It must be defined in Phase 2 so both agents are implemented against the same contract.
- **Voice I/O isolated in Phase 3:** The three silent failure modes (autoplay, microphone permission, ElevenLabs latency) each require explicit test procedures. Bundling them with whiteboard work hides failures.
- **Whiteboard last:** No upstream dependencies except WebSocket hub. Can be built in parallel with Phase 3 if bandwidth allows.
- **Demo hardening is a real phase:** It delivers the canned fallback, latency measurements, and pre-demo checklists. Skipping this phase is the most common reason hackathon demos fail in front of judges.

### Research Flags

Phases needing deeper research during implementation:
- **Phase 3 (Voice I/O):** ElevenLabs `eleven_turbo_v2_5` streaming endpoint path, current latency figures, and character quota tiers must be verified against live API. Featherless cold-start latency for 7–8B models must be measured empirically before demo day — the 300–800ms TTFT figure is from training data and may not reflect current server load.
- **Phase 1 (EEG classifier thresholds):** Heuristic thresholds for FOCUSED/OVERLOADED/DISENGAGED are individual-dependent. The relative baseline approach (10s eyes-closed baseline at session start) needs empirical tuning on the actual demo subject.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Backend infrastructure):** FastAPI WebSocket, asyncio task management, CORS middleware — all well-documented with official sources.
- **Phase 4 (Frontend):** React useReducer, Recharts, KaTeX, react-markdown — stable, well-documented APIs.
- **Phase 5 (Demo hardening):** Operational execution; no domain research needed.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | muselsl/pylsl/FastAPI/Next.js versions from training data (Aug 2025); verify against PyPI/npm before pinning. Featherless model catalog unverified without live API access. ElevenLabs model ID `eleven_turbo_v2_5` needs dashboard verification. |
| Features | MEDIUM | ITS table-stakes features HIGH confidence from academic literature. EEG visualization conventions and judge psychology MEDIUM — practitioner consensus, not empirical study. Latency budget figures need live measurement. |
| Architecture | HIGH | Component boundaries, threading model, asyncio patterns, and WebSocket message design are well-established. No exotic patterns used. The four-layer architecture is the natural fit for this hardware/software combination. |
| Pitfalls | HIGH (architecture-level) / MEDIUM (hardware-specific) | Browser autoplay, CORS, asyncio deadlock, React stale closures are HIGH confidence — documented platform behaviors. Bluetooth dropout characteristics and Featherless rate limit behavior are MEDIUM — community-observed patterns that may vary. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Featherless model availability and cold-start latency:** Cannot be validated without a live API call. Make a test request to Featherless at session start (warm-up call) and measure TTFT on `Llama-3.1-8B-Instruct` before committing to that model for the speaker agent. If TTFT exceeds 800ms, the voice start budget is blown.
- **ElevenLabs current model IDs and quota tiers:** `eleven_turbo_v2_5` is the correct model ID as of training data (mid-2025). Verify in ElevenLabs dashboard before implementing — model IDs have changed in past releases. Check remaining character quota before demo day.
- **Muse headband firmware and muselsl compatibility:** muselsl version must match the Muse device firmware. Test the full muselsl → pylsl chain on the actual Muse headband before Phase 2 begins — Bluetooth pairing issues are faster to resolve early.
- **Cognitive state threshold calibration:** Thresholds cannot be tuned in advance. Schedule a 15-minute calibration session with the demo subject before the hackathon demo window. The manual override hotkey is mandatory insurance.
- **Venue connectivity:** Test all cloud API calls from a mobile hotspot at the venue before demo time. Do not assume venue WiFi is usable for API calls.

---

## Sources

### Primary (HIGH confidence)
- FastAPI WebSocket documentation — WebSocket hub patterns, CORS middleware configuration
- Python asyncio official docs — `asyncio.to_thread`, `asyncio.create_task`, `asyncio.Queue` patterns
- MDN Web Docs: MediaDevices.getUserMedia — microphone permission behavior
- Chrome Autoplay Policy documentation — AudioContext suspended state, user gesture requirement
- W3C Web Speech API spec — SpeechRecognition browser support (Chrome/Edge)
- pylsl/liblsl GitHub — LSL blocking I/O model, threading requirements

### Secondary (MEDIUM confidence)
- muselsl GitHub (alexandrebarachant/muse-lsl) — Bluetooth reliability patterns, HSI channel behavior
- ElevenLabs API reference — streaming TTS endpoint, latency figures for turbo model
- ITS academic literature (Anderson 1985, VanLehn 2011) — intelligent tutoring system table-stakes features
- Featherless API documentation — OpenAI-compatible endpoint, model catalog
- BCI/neurofeedback practitioner community — EEG visualization conventions, artifact patterns

### Tertiary (LOW confidence / needs live validation)
- Featherless TTFT figures for 7–8B models — synthesized from general LLM inference benchmarks; verify empirically
- ElevenLabs character quota tiers — training data; verify in dashboard before demo
- Hackathon judge psychology heuristics — synthesized from demo design practice, not empirical study

---
*Research completed: 2026-03-08*
*Ready for roadmap: yes*
