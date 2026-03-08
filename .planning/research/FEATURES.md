# Feature Landscape

**Domain:** Neuroadaptive AI Tutoring System (voice + whiteboard + EEG)
**Project:** NeuroSync
**Researched:** 2026-03-08
**Confidence:** MEDIUM (web search unavailable; based on ITS/BCI literature and hackathon demo design principles from training data — flag areas noted inline)

---

## Table Stakes

Features where absence makes the demo fail, feel incomplete, or lose credibility with judges.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Voice input (mic)** | Tutoring is conversational — judges expect to speak to the tutor | Low | Browser WebRTC API; transcription via Whisper or similar |
| **Voice output (TTS)** | Tutor must speak, not just display text; silence breaks the tutoring illusion | Low | ElevenLabs already decided; key is latency under 2s |
| **Visible cognitive state indicator** | If EEG is the core claim, the state (FOCUSED / OVERLOADED / DISENGAGED) must be on screen at all times | Low | Three-state pill/badge with color coding is sufficient |
| **State-triggered adaptation event** | Judges need to see: brain changed → tutor responded; invisible adaptation is zero demo value | Medium | Visual flash or log entry when planner triggers strategy change |
| **Tutor response area / transcript** | Text display of what tutor said — judges read while they listen | Low | Rolling conversation view |
| **Whiteboard content area** | Shared space where tutor writes equations/text and student adds notes or images | Medium | Text + LaTeX/markdown render + image import |
| **Session start flow** | Clear entry point: topic selection, EEG connect check, session begin | Low | Single-page flow, no login |
| **EEG connection status** | If the Muse disconnects mid-demo, judges need to see it — otherwise it looks like a fake | Low | "Connected / Disconnected" badge; critical for live hardware credibility |
| **Lesson topic display** | Show what is being taught — derivatives, Newton's laws, etc. — grounds the demo | Low | Static label or planner-generated title |
| **Latency that feels live** | If AI takes 5+ seconds to respond after a state change, judges disengage | High | This is an infrastructure/optimization concern, not a UI feature — but it gates all UX |

---

## Differentiators

Features that make this stand out from a generic AI tutoring demo. These are the judging-moment features.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **EEG band power visualization** | Makes the "brain data" tangible and real; 4–5 live waveform lines (delta/theta/alpha/beta/gamma) are visually compelling and scientifically legible | Medium | Bar chart or sparklines updating at 1–2s intervals is sufficient; full scrolling EEG not required |
| **Adaptation event log / feed** | Shows timestamped log: "14:32:01 — State: OVERLOADED → Strategy: Simplify → Tutor adjusted" — gives judges a narrative of what just happened | Low | Simple chronological list; extremely high impact per effort |
| **Strategy display** | Shows the planner's current strategy: "Step-by-step", "Re-engage question", "Increase difficulty" — makes the adaptive loop transparent | Low | One line of text near tutor response area |
| **Bidirectional whiteboard interaction** | Student can type a response or import a photo of handwritten work — tutor reacts to it; demonstrates two-way adaptive session, not just one-way delivery | Medium | Image import via file picker is achievable; OCR is scope-risk (skip it) |
| **Two-agent architecture visibility** | Label speaker vs planner activity distinctly (even subtly) — "Planner updated strategy" vs "Speaker generating response" — demonstrates architectural sophistication | Low | Optional status indicators; high signal to technical judges |
| **Cognitive state history sparkline** | A 30–60 second history of state transitions plotted as a mini timeline shows the system tracking continuously, not just reacting once | Low-Medium | Simple state history array rendered as colored segments |
| **Tutor tone/style change on adaptation** | When strategy changes from "increase difficulty" to "simplify," the tutor's language should audibly shift — simpler sentences, slower pace suggestion | Medium | Prompt engineering concern; visible in transcript |
| **Live demo reliability mode** | Graceful degradation message if EEG drops during demo — "EEG signal lost, tutor holding last known state" — preserves demo narrative | Low | Single fallback state handler |

---

## Anti-Features

Features to explicitly NOT build given hackathon time constraints. Each represents a real temptation that would consume time without demo value.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Freehand drawing canvas** | Canvas library integration + event sync is 2–4 hours minimum; adds little to adaptive loop narrative | Text + image import only (already decided) |
| **OCR of student handwriting** | Unreliable, hard to debug live, requires external API or model; failure during demo is catastrophic | Image import only — tutor acknowledges image was shared |
| **ML-based EEG classification** | Training data, model serving, accuracy validation — weeks of work; heuristic thresholds deliver same demo story | Heuristic band-power thresholds (already decided) |
| **User accounts / authentication** | Zero demo value; adds complexity and failure points | Single session, no login (already decided) |
| **Persistent session analytics / dashboards** | Interesting product feature but irrelevant to adaptive loop demo | Adaptation event log covers the "history" story |
| **Multi-student / classroom mode** | Scope explosion with no payoff for a single-station demo | Single learner only |
| **Curriculum builder / lesson editor** | Topic is hardcoded for demo; a UI to build lessons adds nothing | Hardcode 2–3 demo topics (derivatives, Newton's laws) |
| **Scrolling raw EEG waveform** | Raw EEG scrolling at 256Hz looks impressive but requires real-time WebSocket rendering at high frequency; band power bars are equally credible and 10x simpler | 5 band-power bars updated at 1–2s interval |
| **Animated avatar / 3D tutor** | High effort, distracts from the brain-signal story | Voice output is sufficient for the tutoring presence |
| **Mobile responsive layout** | Demo is on a single laptop; mobile optimization is wasted effort | Desktop layout only |
| **Internationalization / multi-language** | Single-language demo; i18n framework adds complexity | English only |
| **Real-time collaborative editing (OT/CRDT)** | True real-time multi-user sync (like Google Docs) requires operational transform logic | Tutor writes to whiteboard sequentially; no collision needed |

---

## Feature Dependencies

The adaptive loop has a strict dependency chain. Features upstream of a broken link make downstream features fail.

```
Muse EEG hardware connected
  → muselsl streaming to LSL
    → Backend EEG processor (band powers computed)
      → Cognitive state classifier (FOCUSED / OVERLOADED / DISENGAGED)
        → [VISIBLE] Cognitive state indicator (UI)
        → [VISIBLE] EEG band power visualization (UI)
        → Planner agent receives state change
          → [VISIBLE] Strategy display (UI)
          → [VISIBLE] Adaptation event log entry (UI)
          → Speaker agent generates response
            → [VISIBLE] Tutor response / transcript (UI)
            → ElevenLabs TTS → Voice output
              → [VISIBLE] Speaking indicator (UI)

Parallel input path:
  Browser mic → Transcription → Speaker agent context
  Student whiteboard input (type/image) → Speaker agent context
  Both feed into Speaker; Speaker feeds back to Whiteboard area
```

**Critical path:** EEG → Backend classifier → Planner → Speaker → Voice. Any broken link here collapses the demo. Every other feature is downstream narrative.

**Branching concern:** If Featherless API has cold-start latency (first call slow), the first adaptation after session start may feel sluggish. A warm-up call at session start is worth adding.

---

## MVP Recommendation

### Must ship for demo to work (P0)

1. EEG connection + cognitive state classifier (backend — this is the heart)
2. Cognitive state indicator (UI — the single most visible proof of EEG integration)
3. Voice output via ElevenLabs (tutor speaks)
4. Voice input via browser mic (student speaks)
5. Planner agent: generates lesson plan, updates strategy on state change
6. Speaker agent: responds to student input + current strategy
7. Tutor response / transcript area (UI)
8. Whiteboard text area with tutor writes (UI)

### Should ship for demo to be compelling (P1)

9. EEG band power visualization — 5 bars updating at 1–2s (UI)
10. Adaptation event log / feed (UI) — makes the loop visible
11. Strategy display (current planner strategy) (UI)
12. EEG connection status badge (UI)
13. Cognitive state history sparkline (UI) — 30s of state history

### Nice to have if time permits (P2)

14. Two-agent activity labels (subtle planner vs speaker status)
15. Live demo reliability mode / graceful EEG disconnect handling
16. Whiteboard image import by student

### Defer entirely

- Everything in Anti-Features section above

---

## Minimum Viable EEG Visualization

The minimum that communicates "this is real data" to a judge (not a simulation):

1. **Five band-power bars** (Delta, Theta, Alpha, Beta, Gamma) — labeled, updating visibly every 1–2 seconds with different values per channel. Static bars read as fake; asynchronous, non-uniform updates read as real.
2. **A numeric value on at least one bar** (e.g., Alpha: 0.42 µV²) — specific numbers signal measurement, not animation.
3. **The bars must move independently** — if all five move together uniformly, it looks like a demo animation. Natural EEG has channels that vary at different rates.
4. **Connection to state inference must be visible** — when Alpha drops and Theta rises, the DISENGAGED state should appear. If the visualization and state never correlate visibly, judges will question whether the data is real.

What is NOT needed: raw scrolling waveform, electrode impedance map, artifact rejection indicators, spectral power density plots. These are real neuroscience tools but they add complexity without increasing demo credibility for a hackathon audience.

---

## Cognitive State Indicators Expected in Live Demo UI

Based on BCI/neurofeedback demo conventions (MEDIUM confidence — well-established design pattern):

| Indicator | Format | Update Rate | Why It Matters |
|-----------|--------|-------------|----------------|
| **Current state badge** | Color-coded pill: green (FOCUSED), red (OVERLOADED), yellow (DISENGAGED) | Every 1–2s | Primary proof of EEG-to-state mapping |
| **Band power bars** | 5 vertical or horizontal bars with labels | Every 1–2s | Proves raw signal is being processed |
| **State transition log** | Timestamped text feed | On transition | Shows system is event-driven, not polling |
| **Current strategy text** | One line: "Strategy: Simplify explanation" | On transition | Closes the loop from brain to pedagogy |
| **Confidence / signal quality** | Optional: "Signal quality: Good" | Every 5s | Credibility for live hardware; low effort |

Judges at a hackathon demo typically have 3–5 minutes and need the loop explained in one visual scan. The UI should tell the story: "brain → state → action" without verbal explanation.

---

## What Makes the Adaptive Loop Visible and Understandable

The single most important UX principle for this demo: **the cause-and-effect chain must be visually traceable in under 5 seconds.**

A judge should be able to look at the screen and read: EEG bars changed → badge went red (OVERLOADED) → log says "Strategy: Simplify" → tutor is speaking simpler content.

Design implication: lay out the UI left-to-right or top-to-bottom in this causal order. Do not scatter these elements randomly.

```
[EEG Band Bars] → [State Badge] → [Strategy Label] → [Tutor Transcript / Voice]
```

If these four elements are in a single visible line or column with arrows or clear proximity, judges grasp the system in seconds. This is not a feature — it is a layout constraint that makes all features land.

---

## Whiteboard Features — Scoped for Hackathon

| Feature | Include | Notes |
|---------|---------|-------|
| Tutor writes text (equations, definitions) | Yes | Rendered as markdown or LaTeX (KaTeX) |
| Tutor imports pre-made diagrams | Yes | Static SVG or PNG assets; tutor "presents" them |
| Student types text response | Yes | Simple textarea or inline editor |
| Student imports image | Yes (P2) | File picker; tutor acknowledges receipt |
| Student freehand drawing | No | Anti-feature; see above |
| Real-time collaborative edit | No | Anti-feature; sequential is fine |
| Persistent whiteboard history | No | Session-only |

The whiteboard is a teaching surface, not a collaborative document editor. The tutor controls content; the student reacts. This framing keeps scope minimal and the tutoring metaphor intact.

---

## Sources

- **Training knowledge:** ITS literature (Anderson 1985 through VanLehn 2011 meta-analysis), BCI/neurofeedback demo conventions, hackathon judging heuristics
- **Project context:** `.planning/PROJECT.md` (2026-03-08)
- **Confidence notes:**
  - ITS table-stakes features: HIGH (well-established academic literature)
  - EEG visualization conventions: MEDIUM (practitioner consensus, not standardized)
  - Hackathon judge psychology: MEDIUM (pattern from demo design practice, not empirical study)
  - Specific latency numbers: MEDIUM (derived from WebRTC/TTS benchmarks; verify against actual ElevenLabs + Featherless measurements)
  - Web search unavailable during this research session — verify against current ElevenLabs API docs and Featherless API cold-start behavior before implementing latency-sensitive features
