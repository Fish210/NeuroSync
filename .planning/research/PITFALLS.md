# Domain Pitfalls: NeuroSync

**Domain:** Live EEG-driven neuroadaptive AI tutoring system with real-time voice, multi-agent AI, and hardware demo
**Researched:** 2026-03-08
**Confidence note:** Based on training data through August 2025. WebSearch and Context7 unavailable during this session; confidence is MEDIUM on community-observed patterns, HIGH on architecture-level failure modes that are well-documented in EEG/BCI, LLM streaming, and WebSocket communities.

---

## Critical Pitfalls

These mistakes cause total demo failure — the loop breaks, the headband stops, or the audience sees a frozen screen.

---

### Pitfall 1: Muse Headband Bluetooth Connection Lost Mid-Demo

**What goes wrong:** The Muse headband drops its Bluetooth connection during the demo. muselsl silently fails or hangs rather than crashing, so the backend continues to run but receives no new data. The cognitive state freezes on whatever was last computed, the tutor stops adapting, and judges see a broken demo.

**Why it happens:** muselsl uses Bleak (async Bluetooth LE library) under the hood. BLE connections are sensitive to: distance from laptop (>2m degrades reliability), other BLE devices in the venue (interference), laptop suspending BLE radio after screensaver, USB hub power-throttling the BLE adapter, and the headband's own firmware dropping connections after ~20 minutes of idle.

**Consequences:** Cognitive state freezes. Planner agent never fires. The demo "works" visually but produces no adaptation — the entire loop is broken. Judges who try moving or repositioning mid-demo can trigger this.

**Prevention:**
- Write a watchdog thread in the EEG ingestion layer that tracks `last_packet_timestamp`. If no LSL sample arrives in >2 seconds, raise a `EEGConnectionLost` event and trigger visible UI warning.
- Log muselsl stderr output explicitly — it sometimes prints "Device disconnected" to stderr that gets swallowed.
- Keep the demo laptop within 1 meter of the headband wearer at all times. Tape a marker on the floor if needed.
- Disable laptop Bluetooth power saving: on Windows this is Device Manager → Bluetooth adapter → Power Management → uncheck "Allow computer to turn off this device to save power".
- Have a reconnect script ready (`muselsl.stream()` can be re-called) and wire it to a button in the UI — do NOT rely on automatic reconnect.
- Test at the venue with all other demo equipment running before the actual demo.

**Warning signs:**
- LSL inlet's `pull_sample(timeout=0.0)` returns `None` repeatedly
- `inlet.time_correction()` throws a `TimeoutError`
- EEG band power values freeze at identical numbers for >3 seconds

**Phase:** Address in Phase 1 (EEG ingestion layer). The watchdog must be built before any other layer depends on EEG data.

---

### Pitfall 2: muselsl / LSL Inlet Starves When Python GIL Is Contended

**What goes wrong:** The Python backend runs EEG processing, FastAPI request handling, and WebSocket broadcasting on the same process. When the AI agent call (HTTP to Featherless API) blocks the event loop or a thread for >500ms, the LSL inlet's internal buffer overflows and drops samples. When you next pull samples, you either get a burst of stale data or a gap — both corrupt the rolling window used to compute band powers.

**Why it happens:** LSL inlets have a bounded internal buffer (default 360 seconds, but only for samples that fit). The issue is not the buffer size but that `pull_chunk()` must be called regularly. If the calling thread is blocked, samples accumulate in the LSL network layer and may be dropped by the OS socket buffer.

**Consequences:** Band power estimates become unreliable. Cognitive state classification produces false positives — a FOCUSED user appears OVERLOADED because a burst of stale high-beta samples floods the window after a processing gap.

**Prevention:**
- Run EEG ingestion in a dedicated thread that does nothing except pull samples and write to a thread-safe ring buffer (use `collections.deque(maxlen=256)` with a `threading.Lock`).
- All other processing (band power, state classification, AI calls) reads from this ring buffer asynchronously — it never touches the LSL inlet directly.
- Set `inlet.pull_chunk(max_samples=256, timeout=0.05)` with a short timeout to avoid blocking the ingestion thread.
- Use `asyncio.to_thread()` for all blocking AI API calls so they do not starve the FastAPI event loop.

**Warning signs:**
- Band power values jump discontinuously between updates
- CPU usage on the main Python thread spikes to 100% during AI calls
- LSL sample counter shows gaps (check with `inlet.samples_since_last_call()` or equivalent)

**Phase:** Address in Phase 1 (EEG pipeline) and Phase 2 (backend integration). The threading model must be defined before adding AI calls.

---

### Pitfall 3: EEG Band Power Window Too Short — State Flickers Every Second

**What goes wrong:** If the rolling window for computing alpha/beta/theta band powers is too short (e.g., 0.5 seconds at 256 Hz = 128 samples), individual blink artifacts and muscle movement transients dominate the power estimate. The cognitive state flips between FOCUSED and OVERLOADED multiple times per second. The planner agent fires constantly. The AI pipeline is overwhelmed and the demo looks broken.

**Why it happens:** The Muse headband's electrodes pick up significant EMG (muscle artifact) from jaw clenching, eye movement (EOG), and speaking. Short windows amplify these artifacts. The Muse SDK does some artifact rejection but muselsl raw streams do not.

**Consequences:** Runaway planner agent calls → Featherless API rate limit → adaptation loop breaks → demo fails.

**Prevention:**
- Use a minimum 2-second rolling window (512 samples at 256 Hz) for band power computation.
- Apply a minimum dwell time on state transitions: the system must see the same classified state for at least 3 consecutive windows (6 seconds) before triggering a strategy change. This is a simple hysteresis filter.
- Add artifact rejection: flag and exclude samples where any channel's absolute value exceeds a threshold (e.g., >100 µV) — these are blink/muscle artifacts.
- Smooth band powers with an exponential moving average (alpha=0.3) before classification.

**Warning signs:**
- State transitions happening faster than once every 5 seconds during normal reading
- Planner agent being called more than 10 times per minute
- Beta power spikes 10x above baseline whenever the demo subject speaks

**Phase:** Address in Phase 1 (signal processing). The dwell-time filter is non-negotiable before connecting to the AI layer.

---

### Pitfall 4: ElevenLabs TTS Latency Exceeds 2-Second Budget Under Load

**What goes wrong:** ElevenLabs streaming TTS has a first-chunk latency that depends on model selection, text length sent in the first request, and server load. Using the wrong model or sending the entire response text in one request causes 3-5 second delays before audio starts — blowing the 2-second voice start budget.

**Why it happens:** `eleven_multilingual_v2` and `eleven_turbo_v2_5` have different latency profiles. Sending 200 words in one TTS request causes the server to generate a full audio file before streaming, which defeats streaming. Also: if the browser's audio context is not pre-initialized (requires a user gesture), the first audio playback is blocked by browser autoplay policy.

**Consequences:** The tutor finishes computing the response, the user sees the text appear, but there is 4 seconds of silence before audio — which looks like a crash to judges.

**Prevention:**
- Use `eleven_turbo_v2_5` (lowest latency model, ~400ms first chunk) rather than `eleven_multilingual_v2`.
- Send text to TTS in streaming chunks as the LLM generates tokens, not after the full response is complete. Use the ElevenLabs streaming endpoint with `stream=True`.
- Pre-initialize the browser's `AudioContext` on the first user click (any button press counts as the user gesture). Store the initialized context globally.
- Keep speaker agent responses to under 60 words per turn — shorter text = faster TTS.
- Cache frequently used phrases (greeting, transition phrases like "Let me simplify that") as pre-generated audio blobs to eliminate TTS latency for those.

**Warning signs:**
- Audio playback starts >2 seconds after text appears in the UI
- ElevenLabs API response headers show `x-request-id` with high latency in browser DevTools
- First demo run is fine but subsequent runs degrade (ElevenLabs server-side rate limiting)

**Phase:** Address in Phase 3 (voice output integration). Test latency explicitly with a stopwatch before demo day.

---

### Pitfall 5: Browser Autoplay Policy Blocks All Audio Silently

**What goes wrong:** Modern browsers (Chrome, Firefox, Safari) block AudioContext and audio element playback until the user has interacted with the page. In a demo, the page is loaded by a judge or demo operator who may navigate directly to the URL — no click happens before the tutor starts speaking. All audio is silently blocked. The demo shows text responses but no voice.

**Why it happens:** Browser autoplay policy introduced in Chrome 66+ (2018) and propagated everywhere. The policy requires a user gesture (click, keypress, tap) before audio can play. `AudioContext` constructed before this gesture starts in "suspended" state and must be resumed.

**Consequences:** The tutor speaks silently. Judges see text but think voice synthesis is broken. This is one of the most embarrassing demo failures because it is invisible until you try to demo with audio.

**Prevention:**
- Show a prominent "Start Session" button as the first thing on screen. All audio context initialization happens in this button's click handler.
- In the click handler: `await audioContext.resume()` before doing anything else.
- Never auto-start the session on page load. Always require one deliberate user interaction.
- Test in an incognito Chrome window on the demo machine (same environment a judge experiences) the day before.

**Warning signs:**
- `audioContext.state === 'suspended'` in the browser console
- `play()` returns a Promise that rejects with `NotAllowedError`
- Audio works when you click a play button manually but not when triggered programmatically

**Phase:** Address in Phase 3 (frontend audio). Add a test for this in Phase 5 (demo hardening).

---

### Pitfall 6: WebSocket Reconnect Logic Missing — Frontend Freezes After Any Blip

**What goes wrong:** FastAPI WebSocket connections drop when: the backend restarts during development, the WiFi at the venue drops for 1 second, or the OS decides to reclaim the socket. If the Next.js frontend has no reconnect logic, the user sees a frozen EEG visualization and a "disconnected" state with no way to recover except a full page refresh — which resets the session.

**Why it happens:** WebSocket is not inherently self-healing. When the connection closes (for any reason), the browser's WebSocket object transitions to `CLOSED` state and will not automatically reconnect. Developers often test on localhost where this never happens, then discover it at the venue.

**Consequences:** Any demo disruption (moving tables, someone bumping into the laptop) that causes a momentary network blip permanently breaks the frontend until a manual refresh. This is unacceptable during a live demo.

**Prevention:**
- Implement exponential backoff reconnect in the frontend WebSocket hook: on `onclose`, wait 500ms then retry, capping at 5 attempts with 2x delay each.
- Show a "Reconnecting..." badge in the UI rather than silently failing.
- Design the backend WebSocket handler to be stateless per connection — session state lives in a server-side object keyed by session ID sent in the connection URL. This way, reconnecting restores state instead of starting a new session.
- Test by running `kill -SIGHUP` on the FastAPI process mid-demo and verifying the frontend recovers.

**Warning signs:**
- WebSocket `readyState` stuck at `3` (CLOSED)
- No reconnect attempt after connection drop
- Frontend shows last known state indefinitely without new updates

**Phase:** Address in Phase 2 (backend/frontend connection). Non-negotiable before any demo.

---

### Pitfall 7: Two-Agent Race Condition — Speaker Overridden Mid-Response

**What goes wrong:** The planner agent fires a strategy update at the same moment the speaker agent is generating a response. The speaker agent is mid-sentence when the planner updates the shared strategy context. The speaker may either: finish with the old strategy (incoherent response), pick up the new strategy halfway (incoherent response), or raise an exception if the context object is mutated during iteration (crash).

**Why it happens:** Shared mutable state without locking. Both agents read/write a shared `session_state` dict or object. Python dicts are not thread-safe for multi-key updates (even though individual key assignment is GIL-protected, logical consistency is not).

**Consequences:** The tutor says something like "Let me simplify— Actually, let's go deeper!" mid-sentence. Or the speaker agent crashes silently and no voice response is generated. Judges notice the incoherence.

**Prevention:**
- Never mutate `session_state` while the speaker agent is generating a response. Use a state machine with explicit transitions: `SPEAKER_RUNNING` state blocks planner updates (queues them instead).
- Use a `threading.Event` or asyncio `Lock` to signal "speaker is active." The planner updates a `pending_strategy` field; the speaker reads `current_strategy` at the start of each response turn.
- The speaker always completes the current turn before strategy switches apply. Strategy changes take effect on the next speaker invocation.

**Warning signs:**
- Truncated or contradictory responses in conversation history
- `RuntimeError: dictionary changed size during iteration` in logs
- Planner updates happening with <1 second gap between strategy changes

**Phase:** Address in Phase 2 (agent architecture). Define the state machine before implementing either agent.

---

### Pitfall 8: Featherless API Rate Limit Under Concurrent Agent Load

**What goes wrong:** The planner and speaker agents both call Featherless API. Under a state-change event, both may fire simultaneously: the planner to update strategy, the speaker to respond to user input. At hackathon demo scale, Featherless free/trial tier rate limits (typically ~60 RPM or similar) can be hit if the EEG state flickers and triggers rapid planner re-calls.

**Why it happens:** No throttling on the planner call frequency. EEG state flicker (see Pitfall 3) combined with no dwell-time filter causes the planner to call the API multiple times per minute. Combined with speaker calls, the API returns 429 errors.

**Consequences:** Planner or speaker agent silently fails (if errors are swallowed). The tutor stops responding or stops adapting. Demo appears broken.

**Prevention:**
- Enforce a minimum 10-second cooldown between planner invocations (use a timestamp check before firing).
- The dwell-time filter on EEG state transitions (Pitfall 3) is the first line of defense — fix that first.
- Add explicit 429 error handling with exponential backoff and a visible "AI thinking..." indicator so judges know it is recovering.
- Pre-generate the initial lesson plan at session start (before demo begins) to eliminate one cold-start API call during the live demo.

**Warning signs:**
- `HTTP 429 Too Many Requests` in FastAPI logs
- Planner being called more than 6 times per minute
- AI response times increasing progressively (server-side backpressure before hard rate limit)

**Phase:** Address in Phase 2 (agent layer). The throttle guard must exist before connecting to live EEG state changes.

---

### Pitfall 9: Browser Microphone Permission Denied in Demo Environment

**What goes wrong:** The demo is delivered on a shared laptop or a fresh browser profile. The browser has never been granted microphone permission for the app's origin. When the demo starts and the user tries to speak, Chrome shows a permission dialog — or worse, silently denies access if the page was loaded from `http://` (non-HTTPS). The voice input UI spins indefinitely.

**Why it happens:** Browser microphone API (`getUserMedia`) requires HTTPS except on `localhost`. Hackathons often run on local network with `http://192.168.x.x:3000` which is not localhost and is not HTTPS — microphone access is blocked by the browser.

**Consequences:** Voice input is completely non-functional. The tutor cannot receive user speech. Half the demo interaction model is broken.

**Prevention:**
- Run the frontend on `localhost:3000` from the demo laptop itself — do NOT demo from another machine connecting over LAN (breaks microphone permission on non-HTTPS origins).
- If judges need to see from their own device, use a proper HTTPS tunnel (ngrok with a custom domain, or Cloudflare Tunnel) — not plain HTTP.
- Pre-grant microphone permission in the demo browser profile before the demo starts. Open Chrome settings and set microphone to "Allow" for `localhost`.
- Show a friendly "Click to enable microphone" prompt as the first step in the session start flow, not buried after the EEG stream starts.

**Warning signs:**
- `DOMException: Permission denied` in browser console
- `getUserMedia` returns a rejected Promise with name `NotAllowedError`
- Microphone indicator in browser tab does not appear

**Phase:** Address in Phase 3 (voice input). Test explicitly on the demo machine in demo conditions (correct URL, correct browser profile).

---

### Pitfall 10: Speech-to-Text Transcription Latency Breaks Conversational Feel

**What goes wrong:** If using a cloud STT service (Whisper API, Deepgram, etc.), transcription of a 10-second utterance can take 1-3 seconds after the user finishes speaking — before the speaker agent even starts. Combined with AI generation time (~1-2s) and TTS latency (~0.5-1s), the total round-trip can reach 6-7 seconds. This feels broken in a live demo.

**Why it happens:** Waterfall pipeline: record full utterance → send to STT → wait → send to AI → wait → send to TTS → wait → play. No pipelining between stages.

**Consequences:** Judges experience long silences between user question and tutor response. The demo feels laggy and unpolished.

**Prevention:**
- Use browser-native `Web Speech API` (`SpeechRecognition`) for transcription — it runs in real-time as the user speaks, with interim results, and adds zero network latency for transcription.
- Web Speech API is available in Chrome and Edge without any API key. Interim results let you start sending partial text to the AI while the user is still speaking.
- Fall back to Whisper API only if Web Speech API is unavailable (Firefox, Safari).
- Implement voice activity detection (VAD) to auto-submit when the user stops speaking — do not require a button press to end the utterance.

**Warning signs:**
- User finishes speaking and there is >2 second silence before AI starts
- Server logs show STT request arriving long after user finished speaking
- Total round-trip (user finishes speaking → tutor voice starts) exceeds 4 seconds

**Phase:** Address in Phase 3 (voice input). Choose Web Speech API in Phase 2 architecture decisions.

---

### Pitfall 11: EEG Channel Noise From Headband Fit — Signals Meaningless

**What goes wrong:** The Muse headband requires good electrode-skin contact to produce meaningful EEG. If the headband is worn loosely, hair is in the way, or the demo subject has glasses that prevent a good fit, the raw signals contain predominantly noise. The cognitive state classifier produces random outputs — or always classifies OVERLOADED because high-frequency noise appears as high beta power.

**Why it happens:** EEG is extremely low-amplitude (microvolts). Poor contact = low impedance rejection = massive noise floor. The Muse app shows a contact quality indicator that muselsl does not expose by default. Operators often skip checking contact quality.

**Consequences:** The EEG adaptation loop runs, states change, the AI adapts — but it adapts to noise, not to the person's actual cognitive state. The system works mechanically but is scientifically meaningless (which is actually fine for a hackathon demo, but only if judges don't see obviously random state flickers).

**Prevention:**
- Read the Muse HSI (Headband Status Indicator) channels from the LSL stream. These are the four contact quality channels (TP9, AF7, AF8, TP10 on the Muse 2/S). Values near 1.0 = good contact, values >1.5 = poor contact.
- Show a contact quality indicator in the UI (green/red lights per electrode). Run a 5-second contact quality check before starting the session.
- Have the demo subject remove glasses before wearing the headband.
- Wet finger and rub the temple area slightly before placing headband — reduces skin impedance.
- Practice headband placement with the demo subject before judges arrive. It takes 2-3 tries to get reliable contact.

**Warning signs:**
- HSI channel values consistently above 2.0
- Raw EEG amplitude exceeds 500 µV on any channel
- Alpha power is near-zero even when the subject is clearly relaxed with eyes closed (a sanity check: eyes closed should produce high alpha)

**Phase:** Address in Phase 1 (EEG ingestion) — build HSI monitoring. Address in Phase 5 (demo hardening) — add UI contact quality display.

---

## Moderate Pitfalls

---

### Pitfall 12: FastAPI CORS Blocks WebSocket or API Calls From Next.js Dev Server

**What goes wrong:** Next.js dev server runs on `localhost:3000`. FastAPI backend runs on `localhost:8000`. Browser blocks API calls and WebSocket upgrades from `localhost:3000` to `localhost:8000` unless CORS is explicitly configured. This silently fails — API calls return `CORS error` in the browser console with no error in the FastAPI logs.

**Prevention:**
- Add `CORSMiddleware` to FastAPI with explicit `allow_origins=["http://localhost:3000"]` and `allow_headers=["*"]` before writing any routes.
- For WebSocket, CORS does not apply to the WebSocket handshake itself — but the `Origin` header is checked. Explicitly allow the origin in the WebSocket endpoint handler if needed.
- In production/demo build (Next.js `next start`), use an API proxy in `next.config.js` to route `/api` calls to the FastAPI backend from the same origin — eliminates CORS entirely.

**Phase:** Address in Phase 2 (backend setup, day 1).

---

### Pitfall 13: ElevenLabs Character Quota Exhausted Mid-Demo

**What goes wrong:** ElevenLabs free/starter tier has a character quota per month (10,000 characters on free tier). A 30-minute demo session with voice output every 20-30 seconds burns through ~5,000-8,000 characters easily. If the quota was partially used by testing during development, the demo may hit the limit mid-session. All subsequent TTS calls return a 401 or 429, and the tutor falls silent.

**Prevention:**
- Check remaining character quota before the demo. ElevenLabs dashboard shows this.
- Keep a `ELEVENLABS_FALLBACK=true` mode that uses browser-native `speechSynthesis` (Web Speech API TTS, built into all browsers, zero cost) as fallback if ElevenLabs fails.
- During testing, use browser TTS instead of ElevenLabs — save ElevenLabs quota for the actual demo.
- Cap speaker agent responses to 50 words maximum — reduces character burn per turn.

**Phase:** Address in Phase 3 (voice output) and Phase 5 (demo hardening).

---

### Pitfall 14: Next.js State Management Causes Stale EEG Data in UI

**What goes wrong:** React component state holding EEG band powers and cognitive state may display stale values if the WebSocket message handler uses a closure that captures the initial state (the classic React stale closure problem). The UI shows the cognitive state from 30 seconds ago while the EEG processing layer is correctly computing the current state.

**Why it happens:** `useEffect` with a WebSocket `onmessage` handler captures the initial render's closure. When EEG state updates arrive, the handler has a stale reference to the previous state.

**Prevention:**
- Use `useRef` for the WebSocket instance (not `useState`).
- Use `useReducer` or Zustand for EEG state — both handle concurrent updates correctly without stale closure issues.
- Or use the `functional update` pattern in `setState`: `setEegState(prev => ({ ...prev, ...newData }))`.

**Phase:** Address in Phase 4 (frontend EEG visualization).

---

### Pitfall 15: Python asyncio Deadlock When Mixing Sync and Async LSL Calls

**What goes wrong:** muselsl and pylsl are synchronous libraries. Calling `inlet.pull_sample()` (blocking) inside an `async def` function without `await asyncio.to_thread()` blocks the entire FastAPI event loop. All WebSocket broadcasts freeze. All HTTP requests time out.

**Prevention:**
- Never call blocking LSL functions directly in `async def` coroutines.
- Use `asyncio.to_thread(inlet.pull_chunk, max_samples=256)` to run LSL calls in a thread pool.
- Or run the entire EEG ingestion loop in a dedicated `threading.Thread` (non-async) and communicate with the async event loop via `asyncio.Queue` (thread-safe with `loop.call_soon_threadsafe`).

**Phase:** Address in Phase 1 (EEG ingestion architecture).

---

### Pitfall 16: Demo WiFi at Hackathon Venue Is Unreliable — All Cloud APIs Break

**What goes wrong:** Hackathon venues have notoriously congested WiFi from hundreds of developers all demoing simultaneously. Cloud API calls (Featherless, ElevenLabs, STT) may take 5-10x longer than tested, or fail entirely during peak demo hours.

**Prevention:**
- Test with a mobile hotspot as primary connection rather than venue WiFi. Share from a phone not connected to venue WiFi.
- Pre-generate a "canned demo" fallback: a recorded session where EEG state changes, strategy updates, and voice responses all play back from files. Can be activated with a hotkey if all cloud services fail.
- Have offline fallback TTS (browser `speechSynthesis`) and a local Whisper model (faster-whisper) for STT if internet is down. These are lower quality but keep the demo alive.
- Store the Featherless API key in an environment variable and test it from the venue hotspot before the demo starts.

**Phase:** Address in Phase 5 (demo hardening). Design the fallback mode explicitly.

---

## Minor Pitfalls

---

### Pitfall 17: LSL Clock Drift Corrupts Timestamps

**What goes wrong:** LSL timestamps from the Muse headband and the Python backend system clock can drift apart by 10-50ms over a 20-minute session. If timestamps are used for alignment (e.g., correlating voice input timing with EEG state timestamps), drift causes apparent misalignment.

**Prevention:** Always use `inlet.time_correction()` to compute the offset between LSL clock and local clock at session start. Apply this offset to all LSL timestamps before using them for anything timing-sensitive. For a hackathon demo, this only matters if you display raw timestamps — the adaptation loop does not require precise absolute timestamps.

**Phase:** Minor concern — note in Phase 1 but do not over-engineer.

---

### Pitfall 18: Whiteboard Equation Rendering Breaks on Special Characters

**What goes wrong:** If the tutor writes LaTeX equations (e.g., `\frac{dy}{dx}`) and the frontend renders them with KaTeX or MathJax, certain characters or edge cases in AI-generated LaTeX cause rendering errors that show raw LaTeX strings instead of formatted equations, or throw React rendering exceptions.

**Prevention:** Sanitize AI-generated equation strings before passing to the renderer. Wrap KaTeX render in a try/catch and fall back to plain text if rendering fails. Set a strict system prompt instruction: "Format equations as LaTeX inside $...$ delimiters only."

**Phase:** Address in Phase 4 (whiteboard component).

---

### Pitfall 19: Cognitive State "FOCUSED" Is Never Triggered

**What goes wrong:** The heuristic threshold for FOCUSED state (high alpha, moderate beta, low theta) is tuned on the developer's own brain while sitting still. Different people have wildly different baseline EEG spectra. During a live demo, the person wearing the headband may never reach the FOCUSED classification threshold — the system always shows DISENGAGED or OVERLOADED. Judges never see a strategy transition to "increase difficulty."

**Prevention:**
- Design the thresholds to be relative, not absolute: compute a 10-second baseline at session start (user sits still with eyes closed), then classify state as deviations from that individual baseline.
- Alternatively, expose the thresholds as environment variables so they can be quickly adjusted between demo runs.
- Build a manual override: a hidden keyboard shortcut (or admin panel) that forces a specific cognitive state for demo purposes. This is not cheating — it ensures judges can see all three states even if the signal is noisy.

**Phase:** Address in Phase 1 (classifier design). The manual override must exist before demo day.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: EEG ingestion | Bluetooth drop, LSL buffer starvation, noisy signal, state flicker | Watchdog thread, dedicated ingestion thread, dwell-time filter, HSI monitoring |
| Phase 1: Signal classifier | Absolute thresholds never fire, artifacts dominate | Relative baseline, manual override, artifact rejection |
| Phase 2: Agent architecture | Race condition on shared state, API rate limits | State machine with SPEAKER_RUNNING lock, throttle guard on planner calls |
| Phase 2: Backend/frontend | CORS blocks, WebSocket no reconnect, asyncio deadlock | CORS middleware day 1, reconnect hook, asyncio.to_thread for LSL |
| Phase 3: Voice output | ElevenLabs latency, autoplay block, character quota burn | Turbo model, Start Session button, browser TTS fallback |
| Phase 3: Voice input | Microphone permission denied, STT latency | localhost-only demo, Web Speech API, VAD |
| Phase 4: Frontend state | Stale React closures for EEG data | useReducer/Zustand, functional state updates |
| Phase 5: Demo hardening | Venue WiFi failure, all cloud services unreliable, headband fit | Mobile hotspot, canned demo fallback, pre-demo contact quality check |

---

## The Single Most Dangerous Failure Mode

The entire demo depends on one physical object: the Muse headband maintaining a Bluetooth connection. If the headband drops, nothing adapts, and the demo dies silently (no error visible to judges). Every other pitfall is secondary to this.

**The one thing to build first:** A visible connection status indicator that shows EEG stream health (green = receiving data, red = no data for >2s). Judges should always be able to see "the brain is connected." This turns a silent failure into a visible, recoverable state.

---

## Sources

- Architecture-level analysis based on muselsl GitHub repository patterns (https://github.com/alexandrebarachant/muse-lsl), known issues and community-observed BLE stability problems — MEDIUM confidence
- LSL/pylsl threading model: https://github.com/sccn/liblsl — core library behavior, HIGH confidence from library design
- ElevenLabs streaming API: https://docs.elevenlabs.io/api-reference/text-to-speech-stream — latency model based on training knowledge, MEDIUM confidence (verify current latency on demo day)
- Browser autoplay policy: https://developer.chrome.com/blog/autoplay — HIGH confidence, well-documented platform behavior
- Web Speech API microphone permissions: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia — HIGH confidence, MDN documentation
- FastAPI CORS and WebSocket: https://fastapi.tiangolo.com/tutorial/cors/ — HIGH confidence, official docs
- React stale closure problem: well-documented React behavior — HIGH confidence
- Python asyncio + blocking calls: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor — HIGH confidence, official docs
- Hackathon live hardware demo failure patterns: MEDIUM confidence, synthesized from community post-mortems and developer forum discussions through August 2025
