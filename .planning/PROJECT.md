# NeuroSync

## What This Is

NeuroSync is a neuroadaptive AI tutoring system that uses real EEG signals from a Muse headband to infer a learner's cognitive state in real time, then adapts how a two-agent AI tutor teaches based on that state. The interaction is a live, bidirectional voice + whiteboard session — like a real one-on-one tutoring session — where the AI tutor's teaching strategy is continuously adjusted by brain-derived signals.

## Core Value

The tutor adapts to the learner's brain in real time: EEG signal → cognitive state → tutor strategy change → spoken and written response.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Muse EEG headband streams data via muselsl + LSL to the backend
- [ ] Backend processes EEG band powers and classifies cognitive state (FOCUSED / OVERLOADED / DISENGAGED) using heuristic thresholds
- [ ] Two-agent AI tutoring system: fast speaker agent handles live voice interaction; planner agent holds lesson strategy and updates speaker on state changes
- [ ] Planner agent generates lesson plan at session start and auto-updates strategy when cognitive state changes
- [ ] Planner uses verified teaching methods to decide strategy: simplify, step-by-step, re-engage question, increase difficulty
- [ ] Speaker agent produces short, structured tutor responses aligned to current strategy
- [ ] Voice output via Hume AI TTS — tutor speaks responses automatically on adaptation
- [ ] Voice input via browser microphone — user speaks to tutor and is transcribed
- [ ] Shared whiteboard: tutor types text/equations and imports diagrams; user can type, speak, and import images
- [ ] Frontend shows: cognitive state indicator, EEG band visualization, tutor message area, whiteboard, conversation history
- [ ] Cognitive state updates every 1–2 seconds; AI decisions return under 1.5 seconds; voice starts within 2 seconds

### Out of Scope

- Authentication / user accounts — no login needed, hackathon demo
- Long-term session storage or analytics dashboards — no persistence beyond active session
- Complex ML EEG models — heuristic thresholds only, scientifically sufficient for demo
- Freehand drawing canvas — whiteboard is text + diagrams + images, not freehand
- Medical claims or neuroscience precision — heuristic approximation only

## Context

- **Hackathon project** — must demo live, must be reliable, complexity should be kept minimal
- **Muse headband** is the EEG device; muselsl + Lab Streaming Layer for data ingestion
- **Two-agent split**: planner (strategic, slower) and speaker (fast, conversational real-time)
- **Featherless API** for AI reasoning (both agents)
- **Hume AI** for voice synthesis (TTS REST API)
- **Next.js + TailwindCSS** frontend; **Python FastAPI** backend
- Lesson content should be lightweight (e.g., derivatives, Newton's laws) — just enough structure to demonstrate simplify / advance / re-engage transitions
- Demo success = judge observes brain signal → state inference → tutor adaptation → spoken response in one unbroken loop

## Constraints

- **Hardware**: Muse headband required; someone wears it live during demo — no simulation fallback
- **Latency**: EEG processing under 200ms per cycle; state updates ~1–2s; AI decision under 1.5s; voice start under 2s
- **Scope**: Hackathon timeline — every feature must serve the adaptive demo loop; nothing else
- **AI**: Featherless API for both planner and speaker agents
- **Voice**: Hume AI TTS for output; browser microphone for input

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Two-agent split (planner + speaker) | Speaker needs to be fast for real-time voice; planner can be slower and hold strategy state | — Pending |
| Heuristic EEG thresholds over ML model | Faster to build, easier to debug, easier to explain to judges | — Pending |
| Three cognitive states only (FOCUSED / OVERLOADED / DISENGAGED) | Simpler state machine = more reliable transitions = clearer demo | — Pending |
| Voice-first interaction with whiteboard fallback | Replicates real tutoring feel; user can also type/import images for multimodal input | — Pending |
| Lesson generated at session start, updated on state change | Gives structured starting point; planner adapts live without full regeneration | — Pending |

---
*Last updated: 2026-03-08 after initialization*
