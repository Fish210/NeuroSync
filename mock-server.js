const WebSocket = require("ws");

const wss = new WebSocket.Server({ port: 8001, path: "/ws" });

const messages = [
  {
    event_type: "SESSION_EVENT",
    payload: {
      type: "session_started",
      data: {},
    },
    timestamp: Math.floor(Date.now() / 1000),
  },
  {
    event_type: "STATE_UPDATE",
    payload: {
      state: "FOCUSED",
      confidence: 0.82,
      bands: {
        alpha: 0.35,
        beta: 0.62,
        theta: 0.18,
        gamma: 0.41,
        delta: 0.12,
      },
    },
    timestamp: Math.floor(Date.now() / 1000),
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
    timestamp: Math.floor(Date.now() / 1000),
  },
  {
    event_type: "STATE_UPDATE",
    payload: {
      state: "OVERLOADED",
      confidence: 0.77,
      bands: {
        alpha: 0.22,
        beta: 0.49,
        theta: 0.44,
        gamma: 0.31,
        delta: 0.15,
      },
    },
    timestamp: Math.floor(Date.now() / 1000),
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
    timestamp: Math.floor(Date.now() / 1000),
  },
  {
    event_type: "STATE_UPDATE",
    payload: {
      state: "DISENGAGED",
      confidence: 0.73,
      bands: {
        alpha: 0.51,
        beta: 0.19,
        theta: 0.48,
        gamma: 0.14,
        delta: 0.21,
      },
    },
    timestamp: Math.floor(Date.now() / 1000),
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
    timestamp: Math.floor(Date.now() / 1000),
  },
];

wss.on("connection", (ws) => {
  console.log("Client connected");

  let i = 0;
  const interval = setInterval(() => {
    const msg = {
      ...messages[i % messages.length],
      timestamp: Math.floor(Date.now() / 1000),
    };

    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }

    i += 1;
  }, 2000);

  ws.on("close", () => {
    console.log("Client disconnected");
    clearInterval(interval);
  });
});

console.log("Mock WebSocket server running at ws://localhost:8001/ws");