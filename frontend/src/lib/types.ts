export type CognitiveState = "FOCUSED" | "OVERLOADED" | "DISENGAGED";

export type EventType =
  | "STATE_UPDATE"
  | "CONVERSATION_TURN"
  | "AUDIO_CHUNK"
  | "INTERRUPT"
  | "WHITEBOARD_DELTA"
  | "SESSION_EVENT"
  | "VAD_SIGNAL";

export interface StateUpdatePayload {
  state: CognitiveState;
  confidence: number;
  bands: {
    alpha: number;
    beta: number;
    theta: number;
    gamma: number;
    delta: number;
  };
}

export interface ConversationTurnPayload {
  speaker: "tutor" | "student";
  strategy:
    | "step_by_step"
    | "simplify"
    | "re_engage"
    | "increase_difficulty"
    | "continue"
    | "give_example"
    | "ask_question"
    | "recap";
  tone: "slow" | "encouraging" | "neutral" | "challenging";
  text: string;
  triggered_by_state: CognitiveState;
}

export interface SessionEventPayload {
  type:
    | "session_started"
    | "session_ended"
    | "eeg_connected"
    | "eeg_disconnected"
    | "eeg_reconnected"
    | "lesson_ready"
    | "contact_quality"
    | "error";
  data: Record<string, unknown>;
}

export interface AudioChunkPayload {
  chunk_index: number;
  data: string;
  is_final: boolean;
}

export interface WhiteboardDeltaPayload {
  author: "tutor" | "student";
  type: "text" | "katex" | "image";
  content: string;
  position: { x: number; y: number };
  id: string;
}

export interface VadSignalMessage {
  event_type: "VAD_SIGNAL";
  payload: { level: number };
}

export interface HumeTTSConfig {
  apiKey: string;
  voiceName?: string;
  baseUrl?: string;
  ttsPath?: string;
}

export type WebSocketMessage =
  | {
      event_type: "STATE_UPDATE";
      payload: StateUpdatePayload;
      timestamp: number;
    }
  | {
      event_type: "CONVERSATION_TURN";
      payload: ConversationTurnPayload;
      timestamp: number;
    }
  | {
      event_type: "SESSION_EVENT";
      payload: SessionEventPayload;
      timestamp: number;
    }
  | {
      event_type: "AUDIO_CHUNK";
      payload: AudioChunkPayload;
      timestamp: number;
    }
  | {
      event_type: "INTERRUPT";
      payload: {};
      timestamp: number;
    }
  | {
      event_type: "WHITEBOARD_DELTA";
      payload: WhiteboardDeltaPayload;
      timestamp: number;
    };