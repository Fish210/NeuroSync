import { motion, AnimatePresence } from "framer-motion";
import type { SessionSummary } from "@/lib/api";

const comprehensionColor: Record<string, string> = {
  strong: "text-emerald-400",
  needs_review: "text-amber-400",
  incomplete: "text-rose-400",
};

const stateColor: Record<string, string> = {
  FOCUSED: "bg-emerald-400",
  OVERLOADED: "bg-rose-400",
  DISENGAGED: "bg-amber-400",
};

export default function PostSessionSummary({
  summary,
  topic,
  onDismiss,
}: {
  summary: SessionSummary;
  topic: string;
  onDismiss: () => void;
}) {
  const totalSec = summary.duration_seconds || 1;
  const fmt = (s: number) =>
    s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <motion.div
        className="w-full max-w-2xl rounded-[28px] border border-white/10 bg-slate-900 shadow-2xl overflow-hidden"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.25 }}
      >
        <div className="border-b border-white/10 px-6 py-5">
          <h2 className="text-2xl font-bold text-white">Session Complete</h2>
          <p className="mt-1 text-sm text-slate-400">
            Topic: <span className="text-slate-200 capitalize">{topic}</span> ·{" "}
            Duration: <span className="text-slate-200">{fmt(summary.duration_seconds)}</span>
          </p>
        </div>

        <div className="px-6 py-5 space-y-6 max-h-[70vh] overflow-y-auto">
          {summary.narrative && (
            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 px-5 py-4 text-sm leading-relaxed text-slate-200">
              {summary.narrative}
            </div>
          )}

          <div>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Brain State Breakdown
            </h3>
            <div className="space-y-2">
              {Object.entries(summary.state_breakdown).map(([state, secs]) => (
                <div key={state} className="flex items-center gap-3">
                  <span className="w-24 text-sm text-slate-300 capitalize">{state.toLowerCase()}</span>
                  <div className="flex-1 h-3 rounded-full bg-slate-800">
                    <motion.div
                      className={`h-full rounded-full ${stateColor[state] || "bg-slate-500"}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.round((secs / totalSec) * 100)}%` }}
                      transition={{ duration: 0.6, ease: "easeOut" }}
                    />
                  </div>
                  <span className="w-16 text-right text-sm text-slate-400">{fmt(secs)}</span>
                </div>
              ))}
            </div>
          </div>

          {summary.topics?.length > 0 && (
            <div>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Topics Covered
              </h3>
              <div className="space-y-2">
                {summary.topics.map((t, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-800/60 px-4 py-3 text-sm"
                  >
                    <span className="text-slate-200">{t.title}</span>
                    <span className={`font-medium capitalize ${comprehensionColor[t.comprehension] || "text-slate-400"}`}>
                      {t.comprehension.replace("_", " ")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-white/10 px-6 py-4 flex justify-end">
          <button
            onClick={onDismiss}
            className="rounded-2xl bg-white px-6 py-2.5 text-sm font-semibold text-slate-950 hover:opacity-90 transition"
          >
            New Session
          </button>
        </div>
      </motion.div>
    </div>
  );
}
