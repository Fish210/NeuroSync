"use client";

import { motion, AnimatePresence } from "framer-motion";

export default function AdaptationLog({ entries }: { entries: string[] }) {
  return (
    <section className="p-1">
      <div className="mb-3">
        <h2 className="text-base font-semibold text-white">Adaptation Log</h2>
        <p className="text-xs text-slate-500 mt-0.5">Real-time tutoring decisions</p>
      </div>

      <div className="max-h-[220px] space-y-1.5 overflow-y-auto pr-1">
        {entries.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/10 bg-slate-800/30 px-4 py-3 text-xs text-slate-600 text-center">
            Waiting for session events…
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {entries.map((entry, i) => (
              <motion.div
                key={`${entry}-${i}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
                className="rounded-xl border border-white/8 bg-slate-800/50 px-3 py-2 text-xs text-slate-300 font-mono leading-relaxed"
              >
                {entry}
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </section>
  );
}
