"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNeuroSyncSocket } from "@/lib/websocket/useWebSocket";
import { SparklesCore } from "@/components/ui/sparkles";
import CognitiveStateIndicator from "@/components/CognitiveStateIndicator";
import EEGBandBars from "@/components/EEGBandBars";
import AdaptationLog from "@/components/AdaptionLog";
import SessionControls from "@/components/SessionControls";
import { WhiteboardPanel } from "@/components/WhiteboardPanel";
import { ConversationTranscript } from "@/components/ConversationTranscript";
import PostSessionSummary from "@/components/PostSessionSummary";
import { SessionWizard } from "@/components/ui/session-wizard";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { EEGConfidenceChart } from "@/components/ui/eeg-confidence-chart";
import type { ChartDataPoint } from "@/components/ui/eeg-confidence-chart";

export default function HomePage() {
  const {
    status,
    stateUpdate,
    currentState,
    adaptationLog,
    turns,
    whiteboardBlocks,
    speakingState,
    summary,
    topic,
    start,
    stop,
    eegStatus,
    currentStrategy,
    overrideState,
    sendWhiteboardText,
  } = useNeuroSyncSocket();

  const [showSummary, setShowSummary] = useState(false);
  const [confidenceHistory, setConfidenceHistory] = useState<ChartDataPoint[]>([]);

  useEffect(() => {
    if (summary) setShowSummary(true);
  }, [summary]);

  useEffect(() => {
    if (stateUpdate) {
      setConfidenceHistory((prev) => [
        ...prev.slice(-30),
        {
          time: Date.now(),
          value: Math.round(stateUpdate.confidence * 100),
          state: stateUpdate.state,
        },
      ]);
    }
  }, [stateUpdate]);

  const isActive = status === "open" || status === "connecting" || status === "starting";

  return (
    <main className="min-h-screen bg-slate-950 dark:bg-slate-950 text-white overflow-hidden transition-colors duration-300">
      {/* Post-session summary overlay */}
      <AnimatePresence>
        {showSummary && summary && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <PostSessionSummary summary={summary} topic={topic} onDismiss={() => setShowSummary(false)} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sparkles hero — always behind everything */}
      <AnimatePresence>
        {!isActive && (
          <motion.div
            key="hero-sparkles"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.8 } }}
            className="fixed inset-0 z-0 pointer-events-none"
          >
            <SparklesCore
              id="hero-sparkles"
              background="transparent"
              minSize={0.4}
              maxSize={1.2}
              particleDensity={60}
              className="w-full h-full"
              particleColor="#67e8f9"
              speed={1.5}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative z-10 mx-auto max-w-[1700px] px-4 py-4">
        {/* Header — always visible */}
        <header className="mb-4 rounded-[24px] border border-white/10 bg-slate-900/80 px-6 py-4 shadow-xl backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            {/* Left: Logo + title + topic */}
            <div className="flex items-center gap-4">
              <div className="relative h-10 w-10 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                <svg viewBox="0 0 24 24" className="w-5 h-5 text-white" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white">NeuroSync</h1>
                <p className="text-xs text-slate-400 mt-0.5">Neuroadaptive AI tutoring</p>
              </div>
              {isActive && topic && (
                <div className="rounded-lg border border-cyan-400/20 bg-cyan-400/5 px-3 py-1 text-xs text-cyan-300">
                  {topic}
                </div>
              )}
            </div>

            {/* Right: EEG badge + status badge + theme toggle + stop button */}
            <div className="flex items-center gap-3">
              <ThemeToggle />

              <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs">
                <span className={`h-2 w-2 rounded-full ${
                  eegStatus === "connected"
                    ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]"
                    : eegStatus === "disconnected"
                    ? "bg-rose-400 animate-pulse"
                    : "bg-slate-600"
                }`} />
                <span className="text-slate-300">
                  EEG {eegStatus === "connected" ? "Connected" : eegStatus === "disconnected" ? "Disconnected" : "—"}
                </span>
              </div>

              <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs">
                <span className={`h-2 w-2 rounded-full ${
                  status === "open"
                    ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]"
                    : status === "connecting" || status === "starting"
                    ? "bg-amber-400 animate-pulse"
                    : status === "error"
                    ? "bg-rose-400"
                    : "bg-slate-600"
                }`} />
                <span className="capitalize text-slate-300">{status}</span>
              </div>

              {isActive && (
                <SessionControls onStop={stop} />
              )}
            </div>
          </div>
        </header>

        {/* ── PRE-SESSION: centered wizard ──────────────────────────────── */}
        <AnimatePresence mode="wait">
          {!isActive && (
            <motion.div
              key="wizard"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16, transition: { duration: 0.3 } }}
              transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
              className="flex items-center justify-center min-h-[75vh]"
            >
              <SessionWizard
                onStart={(t) => { setShowSummary(false); start(t); }}
                eegStatus={eegStatus}
                status={status}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── ACTIVE SESSION: full dashboard ────────────────────────────── */}
        <AnimatePresence mode="wait">
          {isActive && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {/* Demo override buttons */}
              <AnimatePresence>
                {status === "open" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="mb-4 overflow-hidden"
                  >
                    <div className="rounded-[20px] border border-white/10 bg-slate-900/80 px-4 py-3 backdrop-blur flex items-center gap-3">
                      <span className="text-[10px] uppercase tracking-[0.15em] text-slate-500">Demo Override:</span>
                      {(["FOCUSED", "OVERLOADED", "DISENGAGED"] as const).map((s) => (
                        <button
                          key={s}
                          onClick={() => overrideState(s)}
                          className={`rounded-xl border px-3 py-1.5 text-xs font-semibold transition cursor-pointer ${
                            s === "FOCUSED"
                              ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300 hover:bg-emerald-400/20"
                              : s === "OVERLOADED"
                              ? "border-rose-400/30 bg-rose-400/10 text-rose-300 hover:bg-rose-400/20"
                              : "border-amber-400/30 bg-amber-400/10 text-amber-300 hover:bg-amber-400/20"
                          }`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Main dashboard grid */}
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
                {/* Left rail */}
                <aside className="lg:col-span-2 space-y-4">
                  <div className="rounded-[20px] border border-white/10 bg-slate-900/80 p-3 shadow-lg backdrop-blur">
                    <CognitiveStateIndicator
                      state={currentState}
                      confidence={stateUpdate?.confidence}
                      strategy={currentStrategy || undefined}
                    />
                  </div>
                  <div className="rounded-[20px] border border-white/10 bg-slate-900/80 p-3 shadow-lg backdrop-blur">
                    <EEGBandBars bands={stateUpdate?.bands} />
                  </div>
                  <div className="rounded-[20px] border border-white/10 bg-slate-900/80 p-4 shadow-lg backdrop-blur">
                    <EEGConfidenceChart data={confidenceHistory} />
                  </div>
                </aside>

                {/* Center whiteboard */}
                <section className="lg:col-span-7">
                  <WhiteboardPanel
                    blocks={whiteboardBlocks}
                    currentState={currentState}
                    onStudentInput={sendWhiteboardText}
                  />
                </section>

                {/* Right rail */}
                <aside className="lg:col-span-3 space-y-4">
                  <div className="rounded-[20px] border border-white/10 bg-slate-900/80 p-3 shadow-lg backdrop-blur">
                    <ConversationTranscript turns={turns} speakingState={speakingState} />
                  </div>
                  <div className="rounded-[20px] border border-white/10 bg-slate-900/80 p-3 shadow-lg backdrop-blur">
                    <AdaptationLog entries={adaptationLog} />
                  </div>
                </aside>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
