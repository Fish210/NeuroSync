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
  } = useNeuroSyncSocket();

  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    if (summary) setShowSummary(true);
  }, [summary]);

  const isActive = status === "open" || status === "connecting" || status === "starting";

  return (
    <main className="min-h-screen bg-slate-950 text-white overflow-hidden">
      {/* Post-session summary overlay */}
      <AnimatePresence>
        {showSummary && summary && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <PostSessionSummary
              summary={summary}
              topic={topic}
              onDismiss={() => setShowSummary(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Pre-session Sparkles hero */}
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
        {/* Header */}
        <header className="mb-4 rounded-[24px] border border-white/10 bg-slate-900/80 px-6 py-4 shadow-xl backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
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
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs">
                <span
                  className={`h-2 w-2 rounded-full ${
                    status === "open"
                      ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]"
                      : status === "connecting" || status === "starting"
                      ? "bg-amber-400 animate-pulse"
                      : status === "error"
                      ? "bg-rose-400"
                      : "bg-slate-600"
                  }`}
                />
                <span className="capitalize text-slate-300">{status}</span>
              </div>

              <SessionControls
                status={status}
                onStart={(topic) => {
                  setShowSummary(false);
                  start(topic);
                }}
                onStop={stop}
              />
            </div>
          </div>
        </header>

        {/* Main layout */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* Left rail */}
          <aside className="lg:col-span-2 space-y-4">
            <div className="rounded-[20px] border border-white/10 bg-slate-900/80 p-3 shadow-lg backdrop-blur">
              <CognitiveStateIndicator
                state={currentState}
                confidence={stateUpdate?.confidence}
              />
            </div>
            <div className="rounded-[20px] border border-white/10 bg-slate-900/80 p-3 shadow-lg backdrop-blur">
              <EEGBandBars bands={stateUpdate?.bands} />
            </div>
          </aside>

          {/* Center whiteboard */}
          <section className="lg:col-span-7">
            <WhiteboardPanel
              blocks={whiteboardBlocks}
              currentState={currentState}
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
      </div>
    </main>
  );
}
