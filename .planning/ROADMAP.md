# Roadmap: NeuroSync

## Overview

NeuroSync delivers a four-stage adaptive loop: Muse EEG headband streams brain signals, a Python backend classifies cognitive state in real time, two AI agents (a strategic planner and a fast speaker) adapt the tutoring strategy, and the frontend presents voice output, whiteboard content, and brain-state visualization to the learner. The build order mirrors the hard dependency chain: validate hardware first, wire the agent state machine second, add voice I/O third (the highest-risk integration layer), complete the visible UI fourth, then harden the full loop for live demo conditions. Every phase is a complete, independently verifiable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: EEG Pipeline** - Muse headband → band power extraction → cognitive state classification → WebSocket state events verified in browser
- [ ] **Phase 2: Backend Infrastructure and AI Agents** - FastAPI session lifecycle, WebSocket hub, two-agent state machine, Planner + Speaker wired to Featherless API
- [ ] **Phase 3: Voice I/O** - Browser microphone transcription, ElevenLabs TTS streaming, VAD barge-in interruption, seamless conversation resumption
- [ ] **Phase 4: Whiteboard and Full Frontend UI** - LiveKit whiteboard sync, KaTeX equation rendering, all UI panels connected to live WebSocket data
- [ ] **Phase 5: Post-Session Summary and Demo Hardening** - Planner-generated summary, state timeline, PDF export, end-to-end latency validation, canned fallback

## Phase Details

### Phase 1: EEG Pipeline
**Goal**: Reliable cognitive state signal flows from the Muse headband to the browser — EEG data is visible, classified, and stable before any AI code is written
**Depends on**: Nothing (first phase)
**Requirements**: EEG-01, EEG-02, EEG-03, EEG-04, EEG-05
**Success Criteria** (what must be TRUE):
  1. Wearing the Muse headband and running muselsl, the browser displays live alpha, beta, theta, gamma band power bars that update every 1-2 seconds
  2. The cognitive state badge in the browser shows FOCUSED, OVERLOADED, or DISENGAGED and only transitions after a stable signal across 3+ consecutive windows (no flicker on minor signal noise)
  3. When the Muse headband Bluetooth connection is severed, the UI shows a visible disconnect warning within 2 seconds — the system enters a known safe state and no AI actions fire
  4. Running the EEG processor in isolation (no AI, no voice), a person can observe state transitions by changing their mental activity (e.g., counting backwards triggers FOCUSED → state change detectable)
**Plans**: TBD

Plans:
- [ ] 01-01: EEG ingestion thread — muselsl LSL stream receiver, ring buffer, asyncio.Queue bridge
- [ ] 01-02: Band power processor — scipy bandpass filter, rolling FFT window, heuristic state classifier with dwell-time filter
- [ ] 01-03: State router and WebSocket events — BLE watchdog, state transition detection, WebSocket push of cognitive state events

### Phase 2: Backend Infrastructure and AI Agents
**Goal**: A complete session lifecycle runs in memory — session starts, the planner generates a lesson plan, the speaker responds to student input using the current strategy, and the Planner-Speaker coordination state machine prevents race conditions
**Depends on**: Phase 1
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, SESS-01, SESS-02, SESS-03, SESS-04, SESS-05
**Success Criteria** (what must be TRUE):
  1. POST /start-session returns a session ID and the planner has generated an initial lesson plan with topic blocks, progression order, and difficulty levels — all held in memory
  2. When a simulated cognitive state change fires, the planner runs as a background async task and updates the current strategy without blocking the speaker — the speaker's next response incorporates the new strategy
  3. The speaker agent returns a structured { strategy, tone, response } object within 1.5 seconds of receiving student input, using the current strategy directive from the session store
  4. Concurrent planner and speaker invocations do not corrupt the session store — SPEAKER_RUNNING lock prevents planner from mutating strategy mid-response
  5. POST /stop-session cleanly terminates EEG ingestion, agent loops, and the WebSocket connection with no hanging processes
**Plans**: TBD

Plans:
- [ ] 02-01: FastAPI app skeleton — session store, CORS middleware, REST endpoints (start/stop), WebSocket hub with typed event_type envelope
- [ ] 02-02: Planner agent — Featherless API client (70B model), lesson plan generation, async background strategy update, 10s cooldown guard
- [ ] 02-03: Speaker agent — Featherless API client (7-8B model), structured output { strategy, tone, response }, SPEAKER_RUNNING lock integration

### Phase 3: Voice I/O
**Goal**: The tutor speaks automatically and the student speaks back — voice interaction is bidirectional, browser autoplay policy is handled correctly, and the student can interrupt the tutor mid-speech and have the conversation resume seamlessly
**Depends on**: Phase 2
**Requirements**: VOICE-01, VOICE-02, VOICE-03, VOICE-04, VOICE-05, VOICE-06
**Success Criteria** (what must be TRUE):
  1. Clicking "Start Session" initializes the AudioContext and the tutor's first spoken response auto-plays in the browser without any additional user action — no autoplay policy errors occur
  2. The student speaks a question into the browser microphone; Web Speech API transcribes it and the speaker agent responds via ElevenLabs voice within 2 seconds of the student finishing speech
  3. While the tutor is speaking, the student begins talking — VAD detects the interruption, ElevenLabs audio stops immediately, and the speaker agent processes the new student input and responds without manual intervention
  4. The browser microphone functions correctly when the app is served from localhost:3000 (microphone permission pre-granted in demo browser profile)
**Plans**: TBD

Plans:
- [ ] 03-01: ElevenLabs TTS integration — eleven_turbo_v2_5 streaming endpoint, WebSocket binary audio chunk delivery, AudioContext pre-initialization on Start Session click
- [ ] 03-02: Web Speech API transcription — browser microphone capture, STT to backend, VAD barge-in detection and ElevenLabs audio stop, conversation resumption after interruption

### Phase 4: Whiteboard and Full Frontend UI
**Goal**: The full demo UI is visible — the causal chain EEG band bars → state badge → strategy label → tutor transcript is readable in under 5 seconds, the whiteboard supports tutor text/equations and student input, and all panels update in real time from the WebSocket
**Depends on**: Phase 2
**Requirements**: WBRD-01, WBRD-02, WBRD-03, WBRD-04, WBRD-05, WBRD-06, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06
**Success Criteria** (what must be TRUE):
  1. The tutor writes a KaTeX equation to the whiteboard and it renders correctly in the student's browser — math notation is legible and not broken
  2. The student types text on the whiteboard and imports an image; both appear on the whiteboard panel in real time via LiveKit sync
  3. A judge looking at the screen can read the cognitive state badge, the current strategy label, the adaptation event log entry, and the conversation transcript without scrolling or verbal explanation
  4. The EEG band power bar chart updates live (every 1-2 seconds) and the adaptation event log appends new entries with timestamps each time a state transition fires
  5. Session start and stop buttons work correctly — start initializes audio and begins the loop, stop ends all processes cleanly with no UI errors
**Plans**: TBD

Plans:
- [ ] 04-01: LiveKit whiteboard — real-time sync, tutor text/KaTeX/image rendering, student text input and image upload
- [ ] 04-02: Frontend UI panels — cognitive state indicator, EEG band power bars (Recharts), adaptation event log, conversation transcript panel
- [ ] 04-03: Session start/stop flow, WebSocket reconnect hook, layout wiring (all panels connected to live WebSocket data)

### Phase 5: Post-Session Summary and Demo Hardening
**Goal**: The session produces a readable post-session summary with per-topic comprehension inference and exportable PDF; the full adaptive loop runs reliably end-to-end under demo conditions with a canned fallback available if hardware fails
**Depends on**: Phase 4
**Requirements**: SESS-06, SESS-07, SESS-08
**Success Criteria** (what must be TRUE):
  1. After stopping a session, the post-session summary screen shows a state timeline chart, a list of topics covered with per-topic comprehension ratings, and a log of key adaptation events — all derived from in-memory session data
  2. Clicking "Export PDF" in the browser produces a downloadable PDF containing the state timeline, topics list, and adaptation event log — no server-side processing required
  3. The complete EEG → state → strategy → voice loop runs 5 consecutive times in a row on the demo machine without error, with voice start confirmed under 2 seconds each time
**Plans**: TBD

Plans:
- [ ] 05-01: Post-session summary — planner-generated summary (time per state, topics covered, per-topic comprehension inference), summary screen with state timeline chart
- [ ] 05-02: PDF export — browser-side PDF generation from summary data
- [ ] 05-03: End-to-end demo hardening — latency measurement across all five flows, mobile hotspot connectivity test, ElevenLabs quota check, headband calibration procedure

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. EEG Pipeline | 0/3 | Not started | - |
| 2. Backend Infrastructure and AI Agents | 0/3 | Not started | - |
| 3. Voice I/O | 0/2 | Not started | - |
| 4. Whiteboard and Full Frontend UI | 0/3 | Not started | - |
| 5. Post-Session Summary and Demo Hardening | 0/3 | Not started | - |
