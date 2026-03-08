"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { WSClient } from "./client";
import { AudioPlayer } from "@/lib/voice/audio-player";
import { Microphone } from "@/lib/voice/microphone";
import { startSession, stopSession } from "@/lib/api";
import type { SessionSummary } from "@/lib/api";
import type {
  CognitiveState,
  ConversationTurnPayload,
  StateUpdatePayload,
  WebSocketMessage,
  WhiteboardDeltaPayload,
} from "@/lib/types";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function useNeuroSyncSocket() {
  const clientRef = useRef<WSClient | null>(null);
  const audioPlayerRef = useRef<AudioPlayer | null>(null);
  const micRef = useRef<Microphone | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const [status, setStatus] = useState<"idle" | "starting" | "connecting" | "open" | "closed" | "error">("idle");
  const [stateUpdate, setStateUpdate] = useState<StateUpdatePayload | null>(null);
  const [adaptationLog, setAdaptationLog] = useState<string[]>([]);
  const [turns, setTurns] = useState<ConversationTurnPayload[]>([]);
  const [whiteboardBlocks, setWhiteboardBlocks] = useState<WhiteboardDeltaPayload[]>([]);
  const [speakingState, setSpeakingState] = useState<"idle" | "speaking" | "interrupted">("idle");
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [topic, setTopic] = useState<string>("");

  const log = useCallback((entry: string) =>
    setAdaptationLog((prev) => [entry, ...prev].slice(0, 20)), []);

  const start = useCallback(async (sessionTopic: string) => {
    setStatus("starting");
    setTopic(sessionTopic);
    setSummary(null);
    setTurns([]);
    setWhiteboardBlocks([]);
    setAdaptationLog([]);
    setSpeakingState("idle");

    let session_id: string;
    try {
      const resp = await startSession(sessionTopic);
      session_id = resp.session_id;
      sessionIdRef.current = session_id;
      log(`Session created: ${session_id}`);
    } catch (err) {
      console.error("start-session failed:", err);
      setStatus("error");
      return;
    }

    // Set up audio player
    audioPlayerRef.current = new AudioPlayer();

    // Connect WebSocket
    const url = `${WS_BASE}/ws/session/${session_id}`;
    const client = new WSClient(
      url,
      (message: WebSocketMessage) => {
        const time = new Date(message.timestamp * 1000).toLocaleTimeString();

        if (message.event_type === "STATE_UPDATE") {
          setStateUpdate(message.payload);
          log(`${time} — State: ${message.payload.state} (${Math.round(message.payload.confidence * 100)}%)`);
        }

        if (message.event_type === "CONVERSATION_TURN") {
          setTurns((prev) => [...prev, message.payload].slice(-20));
          log(`${time} — ${message.payload.triggered_by_state} → ${message.payload.strategy}`);
        }

        if (message.event_type === "WHITEBOARD_DELTA") {
          setWhiteboardBlocks((prev) => {
            const idx = prev.findIndex((b) => b.id === message.payload.id);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = message.payload;
              return next;
            }
            return [...prev, message.payload];
          });
          log(`${time} — Whiteboard: ${message.payload.author} added ${message.payload.type}`);
        }

        if (message.event_type === "AUDIO_CHUNK") {
          setSpeakingState("speaking");
          audioPlayerRef.current?.onChunk(
            message.payload.data,
            message.payload.is_final,
          );
        }

        if (message.event_type === "INTERRUPT") {
          audioPlayerRef.current?.interrupt();
          setSpeakingState("interrupted");
          log(`${time} — Audio interrupted`);
        }

        if (message.event_type === "SESSION_EVENT") {
          log(`${time} — Session: ${message.payload.type}`);
          if (message.payload.type === "session_started") setSpeakingState("idle");
        }
      },
      (s) => {
        const valid = ["connecting", "open", "closed", "error"] as const;
        if (valid.includes(s as any)) {
          setStatus(s as "connecting" | "open" | "closed" | "error");
        }
      },
    );
    clientRef.current = client;
    client.connect();

    // Start microphone
    const mic = new Microphone();
    micRef.current = mic;
    try {
      await mic.start(
        (text) => {
          client.send({ event_type: "STUDENT_SPEECH", payload: { text, session_id } });
          setTurns((prev) =>
            [...prev, {
              speaker: "student" as const,
              strategy: "ask_question" as const,
              tone: "neutral" as const,
              text,
              triggered_by_state: "FOCUSED" as const,
            }].slice(-20)
          );
        },
        (level) => {
          client.send({ event_type: "VAD_SIGNAL", payload: { level } });
        },
      );
    } catch (err) {
      console.warn("Microphone unavailable:", err);
    }
  }, [log]);

  const stop = useCallback(async () => {
    micRef.current?.stop();
    micRef.current = null;

    clientRef.current?.disconnect();
    clientRef.current = null;

    audioPlayerRef.current?.dispose();
    audioPlayerRef.current = null;

    setStatus("closed");
    setSpeakingState("idle");

    const sid = sessionIdRef.current;
    sessionIdRef.current = null;
    if (sid) {
      try {
        const resp = await stopSession(sid);
        setSummary(resp.summary);
        log("Session ended — summary ready");
      } catch (err) {
        console.error("stop-session failed:", err);
      }
    }
  }, [log]);

  // Auto-reset interrupted state
  useEffect(() => {
    if (speakingState === "interrupted") {
      const t = setTimeout(() => setSpeakingState("idle"), 1200);
      return () => clearTimeout(t);
    }
  }, [speakingState]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentState: CognitiveState = useMemo(
    () => stateUpdate?.state || "DISENGAGED",
    [stateUpdate],
  );

  return {
    status,
    stateUpdate,
    currentState,
    adaptationLog,
    turns,
    whiteboardBlocks,
    speakingState,
    summary,
    topic,
    start,
    stop,
  };
}
