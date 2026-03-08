"use client";

import { motion } from "framer-motion";

const bandConfig: Record<string, { color: string; label: string; freq: string }> = {
  alpha: { color: "from-violet-400 to-purple-500", label: "Alpha", freq: "8–13 Hz" },
  beta:  { color: "from-cyan-400 to-blue-500",    label: "Beta",  freq: "13–30 Hz" },
  theta: { color: "from-amber-400 to-orange-500", label: "Theta", freq: "4–8 Hz" },
  gamma: { color: "from-emerald-400 to-teal-500", label: "Gamma", freq: "30+ Hz" },
  delta: { color: "from-rose-400 to-pink-500",    label: "Delta", freq: "0.5–4 Hz" },
};

const ORDER = ["beta", "alpha", "theta", "gamma", "delta"];

export default function EEGBandBars({
  bands,
}: {
  bands?: Record<string, number>;
}) {
  const safe = bands ?? { alpha: 0, beta: 0, theta: 0, gamma: 0, delta: 0 };

  return (
    <div className="p-1">
      <div className="mb-4">
        <div className="text-sm font-semibold text-white">EEG Bands</div>
        <div className="text-xs text-slate-500 mt-0.5">Live spectral power</div>
      </div>

      <div className="space-y-3">
        {ORDER.map((name) => {
          const value = safe[name] ?? 0;
          const pct = Math.max(0, Math.min(value * 100, 100));
          const cfg = bandConfig[name];

          return (
            <div key={name}>
              <div className="flex items-center justify-between mb-1">
                <div>
                  <span className="text-xs font-medium text-slate-300">{cfg.label}</span>
                  <span className="ml-1.5 text-[10px] text-slate-600">{cfg.freq}</span>
                </div>
                <span className="text-xs font-mono text-slate-400">{value.toFixed(2)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800/80">
                <motion.div
                  className={`h-full rounded-full bg-gradient-to-r ${cfg.color}`}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
