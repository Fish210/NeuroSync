import type { CognitiveState } from "@/lib/types";

const styles: Record<CognitiveState, string> = {
  FOCUSED:
    "border-emerald-400/25 bg-emerald-400/10 text-emerald-200 shadow-[0_0_30px_rgba(16,185,129,0.08)]",
  OVERLOADED:
    "border-rose-400/25 bg-rose-400/10 text-rose-200 shadow-[0_0_30px_rgba(244,63,94,0.08)]",
  DISENGAGED:
    "border-amber-400/25 bg-amber-400/10 text-amber-200 shadow-[0_0_30px_rgba(251,191,36,0.08)]",
};

export default function CognitiveStateIndicator({
  state,
  confidence,
}: {
  state: CognitiveState;
  confidence?: number;
}) {
  return (
    <div className={`rounded-2xl border p-4 ${styles[state]}`}>
      <div className="text-xs uppercase tracking-[0.18em] opacity-70">
        Current State
      </div>

      <div className="mt-3 text-4xl font-bold tracking-tight">{state}</div>

      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="opacity-75">Confidence</span>
        <span className="font-semibold">
          {confidence !== undefined ? `${Math.round(confidence * 100)}%` : "--"}
        </span>
      </div>
    </div>
  );
}