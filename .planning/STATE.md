# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-08)

**Core value:** The tutor adapts to the learner's brain in real time: EEG signal → cognitive state → tutor strategy change → spoken and written response.
**Current focus:** Phase 1 — EEG Pipeline

## Current Position

Phase: 1 of 5 (EEG Pipeline)
Plan: 0 of 3 in current phase
Status: Ready to plan
Last activity: 2026-03-08 — Roadmap created, all 37 v1 requirements mapped to 5 phases

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Two-agent split (planner 70B + speaker 7-8B) to meet 1.5s AI decision latency budget
- [Pre-Phase 1]: Heuristic EEG thresholds over ML — faster to build, debuggable, explainable to judges
- [Pre-Phase 1]: Three cognitive states only (FOCUSED / OVERLOADED / DISENGAGED) for reliable demo transitions
- [Pre-Phase 1]: ElevenLabs Flash v2.5 (eleven_turbo_v2_5) — only TTS option meeting 2s voice start budget

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Muse headband Bluetooth dropout is the single most dangerous demo failure mode — BLE watchdog is mandatory in Phase 1, not polish
- [Phase 1]: Heuristic EEG thresholds are individual-dependent — requires 15-minute calibration session with demo subject before demo day
- [Phase 3]: ElevenLabs eleven_turbo_v2_5 model ID must be verified against live dashboard before implementation (model IDs have changed in past releases)
- [Phase 3]: Featherless cold-start latency for 7-8B models must be measured empirically — training-data TTFT figures (300-800ms) may not reflect current server load
- [All phases]: Venue WiFi unreliable — all cloud API calls must be tested from mobile hotspot before demo

## Session Continuity

Last session: 2026-03-08
Stopped at: Roadmap created — ROADMAP.md and STATE.md written, REQUIREMENTS.md traceability updated
Resume file: None
