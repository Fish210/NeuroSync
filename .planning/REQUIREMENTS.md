# Requirements: NeuroSync

**Defined:** 2026-03-08
**Core Value:** The tutor adapts to the learner's brain in real time: EEG signal → cognitive state → tutor strategy change → spoken and written response.

## v1 Requirements

### EEG Pipeline

- [ ] **EEG-01**: Muse headband streams EEG data via muselsl + LSL to Python FastAPI backend
- [ ] **EEG-02**: Backend extracts alpha, beta, theta, gamma band powers from a rolling time window
- [ ] **EEG-03**: Heuristic classifier maps band power ratios (focus_score = beta/theta, cognitive_load = beta+gamma) to one of three states: FOCUSED, OVERLOADED, DISENGAGED
- [ ] **EEG-04**: Dwell-time filter requires 3+ consecutive windows in the same state before triggering a strategy change (prevents signal flicker from flooding the AI layer)
- [ ] **EEG-05**: BLE watchdog detects silent Bluetooth dropout and sets system to a known safe state

### AI Tutor Agents

- [ ] **AGENT-01**: Planner agent generates a detailed initial lesson plan at session start (topic blocks, progression order, example questions, difficulty levels)
- [ ] **AGENT-02**: Speaker agent handles real-time voice conversation, responding to student input aligned to current planner strategy
- [ ] **AGENT-03**: When EEG cognitive state changes, backend prompts planner agent to update the lesson plan and current strategy (async background update)
- [ ] **AGENT-04**: Speaker agent returns structured output: { strategy, tone, response } for predictable downstream handling
- [ ] **AGENT-05**: SPEAKER_RUNNING lock prevents planner from mutating strategy while speaker is actively generating a response
- [ ] **AGENT-06**: Both agents use Featherless API; speaker uses a fast small model (7–8B), planner uses a larger model (70B)

### Voice I/O

- [ ] **VOICE-01**: Student speaks into browser microphone; Web Speech API transcribes speech to text and sends to backend
- [ ] **VOICE-02**: Tutor voice responses are synthesized via ElevenLabs TTS (streaming endpoint) and auto-played in the browser
- [ ] **VOICE-03**: Audio context is initialized inside a click handler (Start Session button) to comply with browser autoplay policy
- [ ] **VOICE-04**: Tutor voice response triggers automatically on every AI adaptation event, without student action
- [ ] **VOICE-05**: Voice Activity Detection (VAD) detects when student begins speaking mid-tutor-playback and immediately stops ElevenLabs audio output (barge-in / interruption)
- [ ] **VOICE-06**: After interruption, speaker agent receives the student's new input and responds without requiring any manual action — conversation resumes seamlessly

### Whiteboard

- [ ] **WBRD-01**: LiveKit powers real-time whiteboard data synchronization between frontend clients and backend
- [ ] **WBRD-02**: Tutor can write text and KaTeX-rendered equations to the whiteboard
- [ ] **WBRD-03**: Tutor can import and display diagrams/images on the whiteboard
- [ ] **WBRD-04**: Student can type text onto the whiteboard
- [ ] **WBRD-05**: Student can import and upload images to the whiteboard
- [ ] **WBRD-06**: Student can annotate the whiteboard (draw/mark up content) and send annotations to the tutor

### Frontend UI

- [ ] **UI-01**: Large cognitive state indicator shows current state (FOCUSED / OVERLOADED / DISENGAGED) prominently on screen
- [ ] **UI-02**: Live EEG band power bars (alpha, beta, theta, gamma, delta) update asynchronously in real time
- [ ] **UI-03**: Adaptation event log shows a timestamped feed of state transitions and strategy changes (e.g. "OVERLOADED → Simplify → Speaker adjusted")
- [ ] **UI-04**: Tutor conversation transcript panel shows the full back-and-forth exchange
- [ ] **UI-05**: Whiteboard panel occupies a prominent area of the screen alongside the conversation
- [ ] **UI-06**: Session start button initializes audio context and begins the tutoring session; session stop gracefully ends the loop

### Session Management

- [ ] **SESS-01**: POST /start-session triggers planner to generate initial lesson plan and returns session ID
- [ ] **SESS-02**: WebSocket (FastAPI) pushes real-time cognitive state, whiteboard deltas, conversation turns, and audio events to the frontend
- [ ] **SESS-03**: All session state (lesson plan, cognitive state, conversation history) is held in memory — no database required
- [ ] **SESS-04**: POST /stop-session cleanly ends EEG ingestion, agent loops, and WebSocket connection
- [ ] **SESS-05**: Backend tracks cognitive state per active topic throughout the session (timestamps + state at each topic transition)
- [ ] **SESS-06**: On session end, planner generates a post-session summary: total time per state (FOCUSED/OVERLOADED/DISENGAGED), topics covered, and per-topic comprehension inference (derived from cognitive state during that topic)
- [ ] **SESS-07**: Post-session summary screen displays: state timeline chart, topics list with comprehension rating, key adaptation events
- [ ] **SESS-08**: User can export the post-session summary to a PDF from the browser

## v2 Requirements

### Reliability & Polish

- **DEMO-01**: Manual cognitive state override button for demo emergencies (force-set state without EEG)
- **DEMO-02**: Graceful "EEG disconnected" indicator with reconnect prompt
- **DEMO-03**: Canned demo fallback (pre-recorded adaptation sequence if hardware fails)

### Enhanced Interaction

- **ENH-01**: Video feed of student (via LiveKit) visible to tutor context
- **ENH-02**: Student voice sentiment analysis to supplement EEG state signal
- **ENH-03**: Session replay / export of adaptation log

## Out of Scope

| Feature | Reason |
|---------|--------|
| User authentication / accounts | Hackathon demo — no login needed |
| Database / persistent storage | In-memory only; no long-term session data |
| Freehand drawing canvas | Whiteboard is text + diagrams + annotations; not a full drawing app |
| ML-based EEG classification | Heuristic thresholds only — faster to build, easier to explain to judges |
| Medical accuracy claims | Project uses EEG as approximation only |
| Mobile app | Web-first demo only |
| Multi-user rooms | Single student + AI tutor session |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EEG-01 | Phase 1 | Pending |
| EEG-02 | Phase 1 | Pending |
| EEG-03 | Phase 1 | Pending |
| EEG-04 | Phase 1 | Pending |
| EEG-05 | Phase 1 | Pending |
| AGENT-01 | Phase 2 | Pending |
| AGENT-02 | Phase 2 | Pending |
| AGENT-03 | Phase 2 | Pending |
| AGENT-04 | Phase 2 | Pending |
| AGENT-05 | Phase 2 | Pending |
| AGENT-06 | Phase 2 | Pending |
| VOICE-01 | Phase 3 | Pending |
| VOICE-02 | Phase 3 | Pending |
| VOICE-03 | Phase 3 | Pending |
| VOICE-04 | Phase 3 | Pending |
| WBRD-01 | Phase 4 | Pending |
| WBRD-02 | Phase 4 | Pending |
| WBRD-03 | Phase 4 | Pending |
| WBRD-04 | Phase 4 | Pending |
| WBRD-05 | Phase 4 | Pending |
| WBRD-06 | Phase 4 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |
| UI-06 | Phase 4 | Pending |
| SESS-01 | Phase 2 | Pending |
| SESS-02 | Phase 2 | Pending |
| SESS-03 | Phase 2 | Pending |
| SESS-04 | Phase 2 | Pending |
| VOICE-05 | Phase 3 | Pending |
| VOICE-06 | Phase 3 | Pending |
| SESS-05 | Phase 2 | Pending |
| SESS-06 | Phase 5 | Pending |
| SESS-07 | Phase 5 | Pending |
| SESS-08 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after adding voice interruption + post-session summary*
