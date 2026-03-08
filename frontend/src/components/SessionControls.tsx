"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  status: string;
  onStart: (topic: string) => void;
  onStop: () => void;
}

export default function SessionControls({ status, onStart, onStop }: Props) {
  const [topic, setTopic] = useState("derivatives");
  const isActive = status === "open" || status === "connecting" || status === "starting";

  return (
    <div className="flex items-center gap-3">
      <AnimatePresence mode="wait">
        {!isActive ? (
          <motion.div
            key="start"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.2 }}
            className="flex items-center gap-3"
          >
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Topic (e.g. derivatives)"
              className="rounded-xl border border-white/10 bg-slate-800/80 px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition w-48"
            />
            <button
              onClick={() => topic.trim() && onStart(topic.trim())}
              disabled={!topic.trim() || status === "starting"}
              className="rounded-2xl bg-white px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:opacity-90 disabled:opacity-40"
            >
              {status === "starting" ? "Starting…" : "Start Session"}
            </button>
          </motion.div>
        ) : (
          <motion.div
            key="stop"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.2 }}
          >
            <button
              onClick={onStop}
              className="rounded-2xl bg-rose-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-400"
            >
              Stop Session
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
