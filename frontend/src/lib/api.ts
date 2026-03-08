const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface LessonBlock {
  id: string;
  title: string;
  difficulty: number;
}

export interface LessonPlan {
  topic: string;
  blocks: LessonBlock[];
  current_block: string;
}

export interface StartSessionResponse {
  session_id: string;
  lesson_plan: LessonPlan;
}

export interface SessionSummary {
  duration_seconds: number;
  state_breakdown: Record<string, number>;
  topics: Array<{
    title: string;
    duration_seconds: number;
    dominant_state: string;
    comprehension: string;
  }>;
  adaptation_events: Array<{
    timestamp: number;
    from_state: string;
    to_state: string;
    strategy_applied: string;
  }>;
  narrative?: string;
}

export interface StopSessionResponse {
  summary: SessionSummary;
}

export async function startSession(topic: string): Promise<StartSessionResponse> {
  const res = await fetch(`${API_BASE}/start-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`start-session failed: ${res.status} ${text}`);
  }
  return res.json();
}

export async function stopSession(session_id: string): Promise<StopSessionResponse> {
  const res = await fetch(`${API_BASE}/stop-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`stop-session failed: ${res.status} ${text}`);
  }
  return res.json();
}
