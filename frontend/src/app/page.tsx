"use client";

import { useState } from "react";
import { useNeuroSyncSocket } from "@/lib/websocket/useWebSocket";
import CognitiveStateIndicator from "@/components/CognitiveStateIndicator";
import EEGBandBars from "@/components/EEGBandBars";
import AdaptationLog from "@/components/AdaptionLog";
import SessionControls from "@/components/SessionControls";
import { WhiteboardPanel } from "@/components/WhiteboardPanel";
import { ConversationTranscript } from "@/components/ConversationTranscript";

export default function HomePage() {
  const [started, setStarted] = useState(false);
  const {
    status,
    stateUpdate,
    currentState,
    adaptationLog,
    turns,
    whiteboardBlocks,
    speakingState,
  } = useNeuroSyncSocket(started);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-[1650px] px-6 py-6">
        {/* Top Bar */}
        <header className="mb-6 rounded-[28px] border border-white/10 bg-slate-900/90 px-6 py-5 shadow-[0_0_0_1px_rgba(255,255,255,0.02)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-5xl font-bold tracking-tight">NeuroSync</h1>
              <p className="mt-2 text-base text-slate-300">
                Neuroadaptive tutoring with live EEG state feedback
              </p>
            </div>

            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3">
              <div className="min-w-[110px]">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Status
                </div>
                <div className="mt-1 flex items-center gap-2 text-sm font-medium">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      status === "open"
                        ? "bg-emerald-400"
                        : status === "connecting"
                        ? "bg-amber-400"
                        : status === "error"
                        ? "bg-red-400"
                        : "bg-slate-500"
                    }`}
                  />
                  <span className="capitalize text-slate-200">{status}</span>
                </div>
              </div>

              <div className="w-px self-stretch bg-white/10" />

              <SessionControls
                started={started}
                onStart={() => setStarted(true)}
                onStop={() => setStarted(false)}
                status={status}
              />
            </div>
          </div>
        </header>

        {/* Main Layout */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left Rail */}
          <aside className="lg:col-span-2 space-y-5">
            <div className="rounded-[24px] border border-white/10 bg-slate-900/90 p-3 shadow-lg">
              <CognitiveStateIndicator
                state={currentState}
                confidence={stateUpdate?.confidence}
              />
            </div>

            <div className="rounded-[24px] border border-white/10 bg-slate-900/90 p-3 shadow-lg">
              <EEGBandBars bands={stateUpdate?.bands} />
            </div>
          </aside>

          {/* Center Whiteboard */}
          <section className="lg:col-span-7 relative">
            <div className="absolute right-5 top-5 z-10 rounded-full border border-cyan-400/20 bg-black/60 px-4 py-2 text-sm backdrop-blur shadow">
              Brain State:{" "}
              <span className="font-semibold text-cyan-300">{currentState}</span>
            </div>

            <WhiteboardPanel blocks={whiteboardBlocks} />
          </section>

          {/* Right Rail */}
          <aside className="lg:col-span-3 space-y-5">
            <div className="rounded-[24px] border border-white/10 bg-slate-900/90 p-3 shadow-lg">
              <ConversationTranscript
                turns={turns}
                speakingState={speakingState}
              />
            </div>

            <div className="rounded-[24px] border border-white/10 bg-slate-900/90 p-3 shadow-lg">
              <AdaptationLog entries={adaptationLog} />
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}