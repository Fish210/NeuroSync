"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { WhiteboardDeltaPayload } from "@/lib/types";

interface Props {
  blocks?: WhiteboardDeltaPayload[];
  currentState?: string;
  onStudentInput?: (text: string) => void;
}

function StudentInput({ onSubmit }: { onSubmit: (text: string) => void }) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setValue("");
  };

  return (
    <div className="relative z-10 border-t border-white/10 px-4 py-3 flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
        placeholder="Type your response or question…"
        className="flex-1 rounded-xl border border-white/10 bg-slate-800/70 px-3 py-2 text-sm text-white placeholder-slate-600 outline-none focus:border-cyan-400/40 focus:ring-1 focus:ring-cyan-400/15 transition"
      />
      <button
        onClick={handleSubmit}
        disabled={!value.trim()}
        className="rounded-xl bg-cyan-500/20 border border-cyan-400/30 px-4 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/30 transition disabled:opacity-40 cursor-pointer"
      >
        Send
      </button>
    </div>
  );
}

const stateGradient: Record<string, string> = {
  FOCUSED:    "from-emerald-500/5 to-transparent",
  OVERLOADED: "from-rose-500/5 to-transparent",
  DISENGAGED: "from-amber-500/5 to-transparent",
};

export function WhiteboardPanel({ blocks = [], currentState, onStudentInput }: Props) {
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
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-slate-500">AI-driven content</span>
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
                  <div className="leading-relaxed">
                    {block.type === "katex" ? (
                      <code className="block text-amber-300/90 font-mono text-[13px] leading-relaxed whitespace-pre-wrap bg-amber-400/5 rounded-lg p-2">
                        {block.content}
                      </code>
                    ) : (
                      block.content
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
      {onStudentInput && (
        <StudentInput onSubmit={onStudentInput} />
      )}
    </section>
  );
}
