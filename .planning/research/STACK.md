# Technology Stack

**Project:** NeuroSync — Neuroadaptive AI Tutoring System
**Researched:** 2026-03-08
**Research mode:** Ecosystem (Stack dimension)

> **Verification note:** External web tools (WebSearch, WebFetch, Bash) were unavailable during this
> research session. All version numbers and recommendations are drawn from training knowledge through
> August 2025. Confidence levels reflect this. Before pinning any version in a lockfile or
> `requirements.txt`, verify against PyPI (`pip index versions <package>`) and npm
> (`npm show <package> version`).

---

## Recommended Stack

### EEG Ingestion Layer

| Technology | Version (training) | Purpose | Why |
|---|---|---|---|
| muselsl | 2.2.x | Stream Muse EEG data over LSL | The canonical Muse → LSL bridge; maintained by Alexandre Barachant; works with Muse 2 and Muse S; handles Bluetooth + OSC; no alternative exists with the same Muse-specific support |
| pylsl | 1.16.x | Read LSL streams in Python | The official Python binding for Lab Streaming Layer; what muselsl pipes into; actively maintained under sccn/liblsl |
| numpy | 1.26.x / 2.0.x | Ring buffer + band power math | Required by muselsl; all EEG DSP (bandpass, FFT, band power extraction) runs on numpy arrays; numpy 2.0 introduced breaking changes — pin to `>=1.26,<2.1` until muselsl confirms 2.x compat |
| scipy | 1.13.x | Bandpass filter (butter + sosfilt) | `scipy.signal.butter` + `sosfilt` is the standard idiom for EEG bandpass (delta/theta/alpha/beta/gamma); faster than manual FFT for real-time 1–2s windows |
| mne | 1.7.x | Optional: band power PSD utilities | MNE-Python has `compute_psd` helpers; only include if heuristic thresholds need welch-based PSD. For a hackathon, raw `scipy.signal` is sufficient and lighter. |

**Confidence:** MEDIUM — muselsl/pylsl versions from training data; official Muse SDK support unchanged through August 2025.

**What NOT to use:**
- `brainflow` — broader EEG board support but adds significant complexity and a separate native library dependency; not needed when you already own a Muse headband and muselsl is the standard tool.
- Raw Bluetooth socket reads — muselsl handles the Bluetooth layer; reinventing this costs days.
- `mne` as a hard dependency — it installs 400MB of dependencies; use raw scipy for hackathon DSP.

---

### Python Backend

| Technology | Version (training) | Purpose | Why |
|---|---|---|---|
| FastAPI | 0.111.x | HTTP + WebSocket server | Best-in-class async Python web framework; native WebSocket support (`WebSocket` class); automatic OpenAPI docs; Pydantic v2 integration for validated state models |
| uvicorn | 0.29.x | ASGI server | The standard uvicorn[standard] install includes uvloop (Unix) and httptools for maximum throughput; required to run FastAPI in production and dev |
| pydantic | 2.7.x | Data validation + state models | FastAPI 0.100+ requires Pydantic v2; define `CognitiveState`, `EEGBandPowers`, `TutorAction` as Pydantic models for validated, typed data flow between components |
| asyncio | stdlib | Concurrency primitive | All EEG polling, AI calls, and WebSocket broadcasts must be async; use `asyncio.Queue` between the LSL reader task and the cognitive state classifier task |
| httpx | 0.27.x | Async HTTP client for Featherless API | Featherless uses OpenAI-compatible REST API; httpx AsyncClient with connection pooling keeps AI call latency minimal; alternative is `openai` SDK with `base_url` override |
| openai (SDK) | 1.30.x | Featherless API client | Featherless is OpenAI-API-compatible; using `openai.AsyncOpenAI(base_url="https://api.featherless.ai/v1", api_key=...)` is the simplest integration path; eliminates custom HTTP boilerplate |
| python-dotenv | 1.0.x | Environment variable loading | Load `FEATHERLESS_API_KEY`, `ELEVENLABS_API_KEY` from `.env` at startup; never hardcode secrets |

**Confidence:** MEDIUM-HIGH — FastAPI 0.111, uvicorn 0.29, pydantic 2.7 are well-established as of mid-2025; openai SDK 1.x API is stable.

**What NOT to use:**
- Django / Flask — synchronous by default; WebSocket support is bolted on; FastAPI's async-native design matches real-time latency requirements.
- Starlette directly — FastAPI is a thin wrapper over Starlette; use FastAPI for the ergonomics.
- aiohttp server — less ecosystem tooling than FastAPI for this use case; FastAPI wins on DX.
- `requests` library — synchronous; blocks the event loop during AI API calls; use `httpx` or openai SDK async client exclusively.

---

### Real-Time State Transport (Backend → Frontend)

**Decision: WebSockets over SSE over polling.**

| Option | Verdict | Rationale |
|---|---|---|
| WebSockets | USE THIS | Bidirectional; FastAPI has native support; single persistent connection for both EEG state pushes AND receiving user voice transcripts; sub-5ms message delivery at LAN scale |
| Server-Sent Events (SSE) | Second choice only | Unidirectional (server → client only); simpler, but forces a separate channel for user → backend messages; adds architectural complexity for no latency benefit |
| HTTP polling | Do not use | Even at 500ms intervals, polling adds median 250ms extra latency on top of processing; violates the 1–2s EEG update constraint |

**Pattern:** Single WebSocket connection per session carrying a typed JSON message envelope:

```json
{
  "type": "eeg_state" | "tutor_message" | "whiteboard_update" | "voice_chunk",
  "payload": { ... }
}
```

Use `type` field to demultiplex on the frontend. This eliminates multiple connections and keeps Next.js state management simple.

**Confidence:** HIGH — WebSocket as primary real-time channel for this use case is the unambiguous correct choice given bidirectionality requirements.

---

### AI Agents (Two-Agent Architecture)

| Technology | Version / Config | Purpose | Why |
|---|---|---|---|
| Featherless API | OpenAI-compatible REST | Host both planner and speaker agents | Project constraint; exposes 300+ open-weight models via OpenAI-compatible endpoint; avoids managing GPU infrastructure |
| openai Python SDK | 1.30.x | API client for both agents | `base_url` override points SDK at Featherless; `AsyncOpenAI` keeps calls non-blocking; streaming (`stream=True`) enables token-by-token speaker output |
| Speaker agent model | `meta-llama/Llama-3.1-8B-Instruct` or `mistralai/Mistral-7B-Instruct-v0.3` | Fast conversational responses | 7–8B parameter models at Featherless respond in 300–800ms; speaker needs <1s to first token; larger models will blow the 1.5s AI decision budget |
| Planner agent model | `meta-llama/Llama-3.1-70B-Instruct` or `Qwen/Qwen2.5-72B-Instruct` | Strategic lesson planning | Planner runs async on state changes (not on every turn); 70B models give better pedagogical reasoning; latency budget for planner is 5–10s since it runs in background |

**Two-agent coordination pattern:**

```
CognitiveState change → Planner (async background task)
                             ↓ yields updated StrategyContext
User utterance received → Speaker (reads latest StrategyContext from shared dict)
                             ↓ streaming tokens → ElevenLabs → audio
```

Use a Python `dict` or `asyncio.Lock`-protected dataclass as the shared state store between planner output and speaker input. No message queue needed at hackathon scale.

**Confidence:** MEDIUM — Featherless model catalog and API compatibility confirmed through training; specific model performance at Featherless is unverified without live testing. Speaker model choice should be validated empirically against latency budget.

**What NOT to use:**
- LangChain / LangGraph — significant overhead, complex dependency tree, overkill for two agents with simple state handoff; direct OpenAI SDK calls are faster to build and easier to debug.
- Streaming for planner — planner output is a strategy document consumed whole; streaming adds complexity without UX benefit since the user never sees planner output directly.
- GPT-4 / Claude via Featherless — confirm which models Featherless hosts; stick to open-weight models confirmed on their catalog.

---

### Voice Output (Text-to-Speech)

| Technology | Version / Plan | Purpose | Why |
|---|---|---|---|
| ElevenLabs API | v2 (Multilingual v2 / Flash v2.5) | Convert speaker agent text to audio | Project constraint; Flash v2.5 model achieves ~300ms time-to-first-audio-chunk which satisfies the 2s voice start budget; high naturalness |
| elevenlabs Python SDK | 1.x | API client | Official SDK; supports streaming audio chunks via `client.text_to_speech.convert_as_stream()`; stream chunks to frontend over WebSocket as base64-encoded audio or ArrayBuffer |
| Audio delivery | WebSocket binary frames | Push audio to browser | Send audio chunks over the existing WebSocket connection as binary frames; browser uses Web Audio API to play chunks in sequence |

**ElevenLabs model selection:**
- `eleven_flash_v2_5` — lowest latency (~300ms first chunk); use for speaker agent output where latency is critical.
- `eleven_multilingual_v2` — higher quality, ~800ms first chunk; only use if audio quality matters more than latency (it does not for a hackathon demo).

**Confidence:** MEDIUM — ElevenLabs Flash v2.5 latency figures from training data (announced late 2024); verify current model IDs in ElevenLabs dashboard before using.

**What NOT to use:**
- OpenAI TTS via Featherless — non-standard, less natural voice; ElevenLabs is explicitly the project constraint.
- Caching TTS responses — tutor responses are dynamic; caching does not apply.
- WebRTC audio — adds NAT traversal complexity with no benefit for same-LAN hackathon demo.

---

### Voice Input (Speech-to-Text)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| Web Speech API (browser-native) | SpeechRecognition spec | Capture and transcribe user speech | Zero dependency; available in Chrome/Edge without any API key; interim results enable UI feedback while user speaks; final result sent to backend over WebSocket |
| Fallback: Whisper API (OpenAI-compatible) | v1 endpoint | If Web Speech API is unreliable in demo venue | Web Speech API requires stable internet (Chrome sends audio to Google servers); if venue has poor connectivity, record audio blob and send to Whisper transcription endpoint |

**Web Speech API pattern (preferred for hackathon):**

```javascript
const recognition = new webkitSpeechRecognition();
recognition.continuous = false;
recognition.interimResults = true;
recognition.onresult = (event) => {
  const transcript = event.results[0][0].transcript;
  ws.send(JSON.stringify({ type: 'user_speech', payload: { text: transcript } }));
};
```

**Confidence:** HIGH for Web Speech API in Chrome — it is stable and widely used. MEDIUM for reliability at demo venue (internet dependency is the risk).

**What NOT to use:**
- Deepgram / AssemblyAI — real-time streaming STT services add API key management and WebSocket complexity; Web Speech API eliminates this for a hackathon.
- MediaRecorder + manual chunking — complex to implement correctly for real-time; Web Speech API handles this.

---

### Frontend

| Technology | Version (training) | Purpose | Why |
|---|---|---|---|
| Next.js | 14.x (App Router) | React framework + dev server | Project constraint; App Router with `use client` for WebSocket-connected components; built-in API routes can proxy if needed; Vercel deploy path if required |
| React | 18.x | UI component model | Bundled with Next.js 14; `useReducer` for WebSocket message handling is the correct pattern (not useState cascade) |
| TailwindCSS | 3.4.x | Styling | Project constraint; JIT mode; pair with `clsx` for conditional class composition |
| Recharts | 2.12.x | EEG band power visualization | Lightweight, React-native charting library; `AreaChart` or `RadarChart` for delta/theta/alpha/beta/gamma band powers; renders at 60fps with memoized data arrays |
| KaTeX | 0.16.x | Math equation rendering on whiteboard | Renders LaTeX math in-browser; tutor can include `$f(x) = x^2$` in messages; integrate via `react-katex` wrapper |
| react-markdown | 9.x | Render tutor markdown responses | Tutor responses may include bullet lists, bold text; react-markdown with remark-math + rehype-katex renders both prose and equations |

**Confidence:** MEDIUM-HIGH — Next.js 14/React 18/Tailwind 3.4 are the confirmed standard stack as of mid-2025.

**What NOT to use:**
- Next.js 15 App Router with React Server Components for WebSocket state — RSC cannot hold client-side WebSocket state; explicitly mark all real-time components with `'use client'` directive.
- Redux / Zustand for global state — overkill for a single-session hackathon app; `useReducer` + Context is sufficient.
- D3.js directly — too much low-level work for simple band power charts; Recharts wraps D3 with a React-friendly API.
- Canvas-based whiteboard libraries (tldraw, Excalidraw) — out of scope per PROJECT.md (no freehand drawing); a div-based text + image layout is sufficient.
- Socket.io — abstracts WebSocket but adds a large client bundle; native browser WebSocket API is simpler and sufficient.

---

### Frontend WebSocket Client Pattern

Use the native browser WebSocket API, not Socket.io or a library wrapper.

```typescript
// hooks/useNeuroSyncWS.ts
const ws = useRef<WebSocket | null>(null);

useEffect(() => {
  ws.current = new WebSocket('ws://localhost:8000/ws/session');
  ws.current.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    dispatch({ type: msg.type, payload: msg.payload });
  };
  return () => ws.current?.close();
}, []);
```

All backend-to-frontend pushes (EEG state, tutor text, audio chunks, whiteboard content) flow through the same WebSocket using the typed envelope described in the transport section.

**Confidence:** HIGH — this is idiomatic React/WebSocket integration.

---

### Infrastructure (Hackathon)

| Technology | Purpose | Why |
|---|---|---|
| Local machine (no cloud) | Run backend + frontend | Muse headband Bluetooth requires physical proximity; muselsl streams locally; cloud hosting adds latency and Bluetooth routing complexity |
| Concurrent terminal processes | Run backend, frontend, muselsl streamer separately | Three processes: `muselsl stream`, `uvicorn main:app --reload`, `npm run dev`; no Docker needed at hackathon scale |
| .env file | Secret storage | `FEATHERLESS_API_KEY`, `ELEVENLABS_API_KEY`; never committed |

**What NOT to use:**
- Docker Compose — adds startup complexity without benefit for a same-machine demo.
- Cloud deployment during demo — Bluetooth does not traverse the internet; backend must be local.
- Redis / message queue — not needed for a single-session demo; `asyncio.Queue` is sufficient.

---

## Alternatives Considered

| Category | Recommended | Alternative Considered | Why Not |
|---|---|---|---|
| EEG bridge | muselsl + pylsl | brainflow | brainflow is broader but heavier; muselsl is Muse-specific and simpler |
| Backend framework | FastAPI | Flask, aiohttp, Django | Flask/Django are sync-first; aiohttp has worse DX; FastAPI is purpose-built for async + WebSocket |
| Real-time transport | WebSocket (native) | Socket.io, SSE | Socket.io adds bundle size; SSE is unidirectional; native WS is sufficient |
| AI client | openai SDK (base_url override) | httpx raw calls, LangChain | LangChain is overkill; raw httpx works but openai SDK handles retries and streaming |
| TTS | ElevenLabs Flash v2.5 | Google TTS, OpenAI TTS | Project constraint; ElevenLabs has lowest latency among high-quality TTS services |
| STT | Web Speech API | Deepgram, Whisper live | Web Speech API has zero setup; Deepgram/Whisper add API keys and WebSocket complexity |
| Frontend charting | Recharts | D3, Chart.js, Victory | Recharts is the lightest React-native option with acceptable performance for 1–2s update intervals |
| Math rendering | KaTeX + react-markdown | MathJax | KaTeX renders 10x faster than MathJax; critical for whiteboard responsiveness |

---

## Installation Reference

```bash
# Backend (Python 3.11+)
pip install muselsl pylsl numpy scipy fastapi "uvicorn[standard]" pydantic python-dotenv httpx "openai>=1.30" elevenlabs

# Frontend
npx create-next-app@14 neurosync-frontend --typescript --tailwind --app
cd neurosync-frontend
npm install recharts react-markdown remark-math rehype-katex react-katex clsx
```

---

## Latency Budget Mapping

| Stage | Budget | Technology | Notes |
|---|---|---|---|
| EEG sample → band power | <200ms | pylsl + scipy butter/sosfilt on 2s rolling window | At 256Hz Muse sample rate, 512 samples per window; scipy sosfilt on 512 samples is <5ms |
| Band power → cognitive state | <10ms | Python heuristic thresholds | Simple threshold comparison; negligible |
| State change → AI decision (speaker) | <1.5s | Featherless API + 7–8B model | First-token latency drives this; 7B models at Featherless typically 200–600ms; full response 800–1200ms |
| State change → planner update | <10s (background) | Featherless API + 70B model | Runs async; does not block speaker; user never waits on planner |
| AI text → first audio chunk | <500ms | ElevenLabs Flash v2.5 | Flash v2.5 ~300ms time-to-first-chunk |
| Audio chunk → browser playback | <50ms | WebSocket binary frame + Web Audio API | Local network; negligible |
| Total loop (EEG → spoken audio) | <2s target | All of the above | Achievable if model selection stays at 7–8B for speaker |

---

## Sources

All findings from training knowledge (cutoff August 2025). No external sources could be fetched during this session.

**Verify before pinning:**
- muselsl version: https://pypi.org/project/muselsl/
- pylsl version: https://pypi.org/project/pylsl/
- FastAPI version: https://pypi.org/project/fastapi/ and https://fastapi.tiangolo.com/release-notes/
- openai SDK version: https://pypi.org/project/openai/
- ElevenLabs models: https://elevenlabs.io/docs/models
- Featherless model catalog: https://featherless.ai/models
- Next.js 14 docs: https://nextjs.org/docs
- Recharts API: https://recharts.org/en-US/api
