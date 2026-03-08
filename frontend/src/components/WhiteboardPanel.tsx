"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { WhiteboardDeltaPayload } from "@/lib/types";

interface Props {
  blocks?: WhiteboardDeltaPayload[];
  currentState?: string;
}

const stateGradient: Record<string, string> = {
  FOCUSED:    "from-emerald-500/5 to-transparent",
  OVERLOADED: "from-rose-500/5 to-transparent",
  DISENGAGED: "from-amber-500/5 to-transparent",
};

export function WhiteboardPanel({ blocks = [], currentState }: Props) {
  return (
    <section className="relative h-full overflow-hidden rounded-[28px] border border-white/10 bg-slate-900 shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
      {/* Ambient gradient */}
      <div
        className={`absolute inset-0 bg-gradient-to-br ${stateGradient[currentState || ""] || "from-transparent"} pointer-events-none transition-all duration-1000`}
      />

      {/* Header */}
      <div className="relative z-10 flex items-center justify-between border-b border-white/10 px-6 py-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Live Whiteboard</h2>
          <p className="text-xs text-slate-500 mt-0.5">Shared tutoring workspace</p>
        </div>
        <div className="flex items-center gap-2">
          {["Pen", "Text", "Erase", "Clear"].map((tool) => (
            <button
              key={tool}
              className="rounded-lg border border-white/10 bg-slate-800/80 px-3 py-1.5 text-xs text-slate-400 transition hover:bg-slate-700 hover:text-white"
            >
              {tool}
            </button>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <div className="relative min-h-[720px] cursor-crosshair">
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: "radial-gradient(rgba(255,255,255,0.15) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />

        {blocks.length === 0 ? (
          <div className="absolute inset-0 flex items-start p-6">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="rounded-2xl border border-white/10 bg-slate-950/80 px-6 py-5 shadow-lg backdrop-blur max-w-sm"
            >
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">
                Waiting for lesson
              </div>
              <div className="text-2xl font-semibold text-white mb-2">NeuroSync</div>
              <p className="text-sm text-slate-400 leading-relaxed">
                Start a session to begin. The tutor AI will write equations and diagrams here in real-time based on your brain state.
              </p>
            </motion.div>
          </div>
        ) : (
          <div className="relative h-full w-full">
            <AnimatePresence>
              {blocks.map((block) => (
                <motion.div
                  key={block.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3 }}
                  className={`absolute max-w-[400px] rounded-2xl border px-4 py-3 text-sm shadow-lg backdrop-blur-sm ${
                    block.author === "tutor"
                      ? "border-cyan-400/20 bg-slate-950/85 text-slate-100"
                      : "border-white/10 bg-slate-800/85 text-slate-200"
                  }`}
                  style={{ left: block.position.x, top: block.position.y }}
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span
                      className={`text-[9px] uppercase tracking-wider font-semibold ${
                        block.author === "tutor" ? "text-cyan-400" : "text-slate-500"
                      }`}
                    >
                      {block.author}
                    </span>
                    <span className="text-[9px] text-slate-600">{block.type}</span>
                  </div>
                  <div className="leading-relaxed">{block.content}</div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </section>
  );
}
