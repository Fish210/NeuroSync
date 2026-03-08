"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { CognitiveState } from "@/lib/types";
import { SegmentedProgress } from "@/components/ui/progress-bar";

const config: Record<CognitiveState, {
  label: string;
  ring: string;
  glow: string;
  dot: string;
  text: string;
  bar: string;
  description: string;
}> = {
  FOCUSED: {
    label: "Focused",
    ring: "border-emerald-400/40",
    glow: "shadow-[0_0_40px_rgba(16,185,129,0.15)]",
    dot: "bg-emerald-400",
    text: "text-emerald-300",
    bar: "bg-emerald-400",
    description: "Deep learning mode",
  },
  OVERLOADED: {
    label: "Overloaded",
    ring: "border-rose-400/40",
    glow: "shadow-[0_0_40px_rgba(244,63,94,0.15)]",
    dot: "bg-rose-400",
    text: "text-rose-300",
    bar: "bg-rose-400",
    description: "Simplifying content",
  },
  DISENGAGED: {
    label: "Disengaged",
    ring: "border-amber-400/40",
    glow: "shadow-[0_0_40px_rgba(251,191,36,0.15)]",
    dot: "bg-amber-400",
    text: "text-amber-300",
    bar: "bg-amber-400",
    description: "Re-engaging student",
  },
};

export default function CognitiveStateIndicator({
  state,
  confidence,
  strategy,
}: {
  state: CognitiveState;
  confidence?: number;
  strategy?: string;
}) {
  const c = config[state];
  const pct = confidence !== undefined ? Math.round(confidence * 100) : null;

  return (
    <div
      className={`rounded-2xl border p-4 bg-slate-900/60 ${c.ring} ${c.glow} transition-all duration-700`}
    >
      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-3">
        Cognitive State
      </div>

      <div className="flex items-center gap-3 mb-2">
        <div className="relative flex-shrink-0">
          <span className={`inline-block h-3 w-3 rounded-full ${c.dot}`} />
          <motion.span
            className={`absolute inset-0 rounded-full ${c.dot} opacity-40`}
            animate={{ scale: [1, 1.8, 1], opacity: [0.4, 0, 0.4] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            key={state}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.3 }}
            className={`text-xl font-bold tracking-tight ${c.text}`}
          >
            {c.label}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="text-xs text-slate-500 mb-4">{c.description}</div>

      {strategy && (
        <div className="mt-2 rounded-lg border border-white/8 bg-slate-800/50 px-2.5 py-1.5 text-[10px] font-mono text-slate-400">
          Strategy: <span className="text-slate-200">{strategy.replace(/_/g, " ")}</span>
        </div>
      )}

      {pct !== null && (
        <SegmentedProgress
          value={pct}
          segments={10}
          label="Confidence"
          showPercentage
          showDemo={false}
          color={c.bar}
        />
      )}
    </div>
  );
}
