"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { WSClient } from "./client";
import type {
  CognitiveState,
  ConversationTurnPayload,
  StateUpdatePayload,
  WebSocketMessage,
  WhiteboardDeltaPayload,
} from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001/ws";

export function useNeuroSyncSocket(enabled: boolean) {
  const clientRef = useRef<WSClient | null>(null);

  const [status, setStatus] = useState<"connecting" | "open" | "closed" | "error">("closed");
  const [stateUpdate, setStateUpdate] = useState<StateUpdatePayload | null>(null);
  const [adaptationLog, setAdaptationLog] = useState<string[]>([]);
  const [latestTutorTurn, setLatestTutorTurn] = useState<ConversationTurnPayload | null>(null);
  const [turns, setTurns] = useState<ConversationTurnPayload[]>([]);
  const [whiteboardBlocks, setWhiteboardBlocks] = useState<WhiteboardDeltaPayload[]>([]);
  const [speakingState, setSpeakingState] = useState<"idle" | "speaking" | "interrupted">("idle");

  useEffect(() => {
    if (!enabled) return;

    const client = new WSClient(
      WS_URL,
      (message: WebSocketMessage) => {
        const time = new Date(message.timestamp * 1000).toLocaleTimeString();

        if (message.event_type === "STATE_UPDATE") {
          setStateUpdate(message.payload);
          setAdaptationLog((prev) => [
            `${time} — State: ${message.payload.state} (${Math.round(
              message.payload.confidence * 100
            )}%)`,
            ...prev,
          ].slice(0, 12));
        }

        if (message.event_type === "CONVERSATION_TURN") {
          setLatestTutorTurn(message.payload);
          setTurns((prev) => [...prev, message.payload].slice(-20));
          setAdaptationLog((prev) => [
            `${time} — ${message.payload.triggered_by_state} → ${message.payload.strategy}`,
            ...prev,
          ].slice(0, 12));
        }

        if (message.event_type === "WHITEBOARD_DELTA") {
          setWhiteboardBlocks((prev) => {
            const existingIndex = prev.findIndex((block) => block.id === message.payload.id);
            if (existingIndex >= 0) {
              const next = [...prev];
              next[existingIndex] = message.payload;
              return next;
            }
            return [...prev, message.payload];
          });

          setAdaptationLog((prev) => [
            `${time} — Whiteboard: ${message.payload.author} added ${message.payload.type}`,
            ...prev,
          ].slice(0, 12));
        }

        if (message.event_type === "AUDIO_CHUNK") {
          setSpeakingState("speaking");
        }

        if (message.event_type === "INTERRUPT") {
          setSpeakingState("interrupted");
          setAdaptationLog((prev) => [
            `${time} — Audio interrupted`,
            ...prev,
          ].slice(0, 12));
        }

        if (message.event_type === "SESSION_EVENT") {
          setAdaptationLog((prev) => [
            `${time} — Session event: ${message.payload.type}`,
            ...prev,
          ].slice(0, 12));

          if (message.payload.type === "session_started") {
            setSpeakingState("idle");
          }
        }
      },
      setStatus
    );

    clientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
    };
  }, [enabled]);

  useEffect(() => {
    if (speakingState === "interrupted") {
      const timer = setTimeout(() => setSpeakingState("idle"), 1200);
      return () => clearTimeout(timer);
    }
  }, [speakingState]);

  const currentState: CognitiveState = useMemo(() => {
    return stateUpdate?.state || "DISENGAGED";
  }, [stateUpdate]);

  return {
    status,
    stateUpdate,
    currentState,
    latestTutorTurn,
    adaptationLog,
    turns,
    whiteboardBlocks,
    speakingState,
  };
}