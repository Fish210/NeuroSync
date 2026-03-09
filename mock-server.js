const WebSocket = require("ws");
const http = require("http");

// ── Mock REST + WebSocket server for NeuroSync local development ─────────────
//
// Listens on port 8000 (same as real backend) so NEXT_PUBLIC_API_URL and
// NEXT_PUBLIC_WS_URL don't need to be changed.
//
// REST endpoints:  POST /start-session  POST /stop-session  POST /override-state  GET /health
// WebSocket path:  /ws/session/{session_id}   (matches real backend exactly)
//
// Usage:  node mock-server.js
// ─────────────────────────────────────────────────────────────────────────────

const PORT = 8000;

// ── HTTP server handling REST endpoints ──────────────────────────────────────
const httpServer = http.createServer((req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", () => {
    try {
      if (req.method === "POST" && req.url === "/start-session") {
        const { topic } = JSON.parse(body || "{}");
        const session_id = "mock-" + Math.random().toString(36).slice(2, 10);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({
          session_id,
          lesson_plan: {
            topic: topic || "Demo Topic",
            blocks: [
              { id: "block-1", title: `Introduction to ${topic || "Demo"}`, difficulty: 1 },
              { id: "block-2", title: `Core concepts of ${topic || "Demo"}`, difficulty: 2 },
              { id: "block-3", title: `Practice: ${topic || "Demo"}`, difficulty: 3 },
            ],
            current_block: "block-1",
          },
        }));
        console.log(`[REST] POST /start-session → session_id=${session_id} topic=${topic}`);

      } else if (req.method === "POST" && req.url === "/stop-session") {
        const { session_id } = JSON.parse(body || "{}");
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({
          summary: {
            duration_seconds: 120,
            state_breakdown: { FOCUSED: 60, OVERLOADED: 30, DISENGAGED: 30 },
            topics: [
              {
                title: "Demo Topic",
                duration_seconds: 120,
                dominant_state: "FOCUSED",
                comprehension: "strong",
              },
            ],
            adaptation_events: [
              {
                timestamp: Date.now() / 1000 - 60,
                from_state: "FOCUSED",
                to_state: "OVERLOADED",
                strategy_applied: "step_by_step",
              },
              {
                timestamp: Date.now() / 1000 - 30,
                from_state: "OVERLOADED",
                to_state: "DISENGAGED",
                strategy_applied: "re_engage",
              },
            ],
            narrative: "Great session! You were focused most of the time and the tutor adapted well to your cognitive state.",
          },
        }));
        console.log(`[REST] POST /stop-session → session_id=${session_id}`);

      } else if (req.method === "POST" && req.url === "/override-state") {
        const { session_id, state } = JSON.parse(body || "{}");
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ session_id, state, overridden: true }));
        console.log(`[REST] POST /override-state → session_id=${session_id} state=${state}`);

      } else if (req.method === "GET" && req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", sessions: 0, timestamp: Date.now() / 1000 }));

      } else if (req.method === "GET" && req.url === "/eeg-status") {
        res.writeHead(200, { "Content-Type": "application/json" });
        // Mock: simulate EEG connected after 5 seconds of mock server being up
        const uptime = process.uptime();
        const connected = uptime > 5;
        res.end(JSON.stringify({
          connected,
          status: connected ? "connected" : "disconnected",
          last_packet_age_seconds: connected ? 0.5 : null,
        }));
        console.log(`[REST] GET /eeg-status → connected=${connected}`);

      } else {
        res.writeHead(404);
        res.end("Not found");
      }
    } catch (err) {
      console.error("[REST] Error:", err);
      res.writeHead(500);
      res.end("Internal error");
    }
  });
});

// ── WebSocket server — path must match /ws/session/{session_id} ──────────────
const wss = new WebSocket.Server({ server: httpServer });

const messages = [
  {
    event_type: "SESSION_EVENT",
    payload: { type: "session_started", data: {} },
  },
  {
    event_type: "STATE_UPDATE",
    payload: {
      state: "FOCUSED",
      confidence: 0.82,
      bands: { alpha: 0.35, beta: 0.62, theta: 0.18, gamma: 0.41, delta: 0.12 },
    },
  },
  {
    event_type: "CONVERSATION_TURN",
    payload: {
      speaker: "tutor",
      strategy: "increase_difficulty",
      tone: "challenging",
      text: "You seem focused, so let's try a harder derivative example.",
      triggered_by_state: "FOCUSED",
    },
  },
  {
    event_type: "STATE_UPDATE",
    payload: {
      state: "OVERLOADED",
      confidence: 0.77,
      bands: { alpha: 0.22, beta: 0.49, theta: 0.44, gamma: 0.31, delta: 0.15 },
    },
  },
  {
    event_type: "CONVERSATION_TURN",
    payload: {
      speaker: "tutor",
      strategy: "step_by_step",
      tone: "slow",
      text: "Let's slow down and break this into smaller steps.",
      triggered_by_state: "OVERLOADED",
    },
  },
  {
    event_type: "STATE_UPDATE",
    payload: {
      state: "DISENGAGED",
      confidence: 0.73,
      bands: { alpha: 0.51, beta: 0.19, theta: 0.48, gamma: 0.14, delta: 0.21 },
    },
  },
  {
    event_type: "CONVERSATION_TURN",
    payload: {
      speaker: "tutor",
      strategy: "re_engage",
      tone: "encouraging",
      text: "Let's reset with a quick question. What does a derivative represent?",
      triggered_by_state: "DISENGAGED",
    },
  },
  {
    event_type: "WHITEBOARD_DELTA",
    payload: {
      author: "tutor",
      type: "katex",
      content: "f'(x) = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}",
      position: { x: 120, y: 240 },
      id: "block-limit-def",
    },
  },
  {
    event_type: "WHITEBOARD_DELTA",
    payload: {
      author: "tutor",
      type: "text",
      content: "The derivative measures the instantaneous rate of change.",
      position: { x: 120, y: 160 },
      id: "block-intro-text",
    },
  },
  {
    event_type: "SESSION_EVENT",
    payload: { type: "eeg_connected", data: {} },
  },
  {
    event_type: "SESSION_EVENT",
    payload: {
      type: "contact_quality",
      data: { TP9: 1.0, AF7: 1.1, AF8: 1.0, TP10: 1.2, overall: "good" },
    },
  },
];

wss.on("connection", (ws, req) => {
  // Extract session_id from URL path /ws/session/{session_id}
  const pathname = req.url || "";
  const match = pathname.match(/^\/ws\/session\/(.+)$/);
  const session_id = match ? match[1] : "unknown";
  console.log(`[WS] Client connected: path=${pathname} session_id=${session_id}`);

  let i = 0;
  const interval = setInterval(() => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const msg = {
      ...messages[i % messages.length],
      timestamp: Math.floor(Date.now() / 1000),
    };
    ws.send(JSON.stringify(msg));
    i += 1;
  }, 2000);

  ws.on("message", (data) => {
    try {
      const msg = JSON.parse(data.toString());
      console.log(`[WS] Received from client: event_type=${msg.event_type}`);
    } catch (_) { }
  });

  ws.on("close", () => {
    console.log(`[WS] Client disconnected: session_id=${session_id}`);
    clearInterval(interval);
  });
});

httpServer.listen(PORT, () => {
  console.log(`Mock NeuroSync server running on port ${PORT}`);
  console.log(`  REST: http://localhost:${PORT}/start-session`);
  console.log(`  REST: http://localhost:${PORT}/stop-session`);
  console.log(`  REST: http://localhost:${PORT}/override-state`);
  console.log(`  WS:   ws://localhost:${PORT}/ws/session/{session_id}`);
});
