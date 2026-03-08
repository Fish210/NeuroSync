"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { ConversationTurnPayload } from "@/lib/types";
import { ShiningText } from "@/components/ui/shining-text";
import { TextGenerateEffect } from "@/components/ui/text-generate-effect";

const strategyBadge: Record<string, string> = {
  continue:            "bg-slate-700 text-slate-300",
  step_by_step:        "bg-blue-900/60 text-blue-300",
  simplify:            "bg-violet-900/60 text-violet-300",
  re_engage:           "bg-amber-900/60 text-amber-300",
  increase_difficulty: "bg-emerald-900/60 text-emerald-300",
  give_example:        "bg-teal-900/60 text-teal-300",
  ask_question:        "bg-cyan-900/60 text-cyan-300",
  recap:               "bg-pink-900/60 text-pink-300",
};

export function ConversationTranscript({
  turns,
  speakingState = "idle",
}: {
  turns: ConversationTurnPayload[];
  speakingState?: "idle" | "speaking" | "interrupted";
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  return (
    <section className="p-1">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white">Conversation</h2>
          <p className="text-xs text-slate-500 mt-0.5">AI tutor · student dialogue</p>
        </div>
        <span
          className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide border ${
            speakingState === "speaking"
              ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-300"
              : speakingState === "interrupted"
              ? "border-rose-400/30 bg-rose-400/10 text-rose-300"
              : "border-white/10 bg-slate-800 text-slate-500"
          }`}
        >
          {speakingState === "speaking" && (
            <span className="inline-flex gap-0.5">
              {[0, 0.15, 0.3].map((d) => (
                <motion.span
                  key={d}
                  className="w-0.5 h-2.5 rounded-full bg-cyan-400"
                  animate={{ scaleY: [1, 1.8, 1] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: d }}
                />
              ))}
            </span>
          )}
          {speakingState === "speaking" ? (
            <ShiningText text="Speaking" className="text-[10px] font-medium uppercase tracking-wide" />
          ) : (
            <span>{speakingState}</span>
          )}
        </span>
      </div>

      <ul className="max-h-[380px] space-y-2.5 overflow-y-auto pr-1">
        {turns.length === 0 ? (
          <li className="rounded-2xl border border-dashed border-white/10 bg-slate-800/30 px-4 py-3 text-xs text-slate-600 text-center">
            Conversation will appear here once session starts
          </li>
        ) : (
          <AnimatePresence initial={false}>
            {turns.map((turn, i) => {
              const isTutor = turn.speaker === "tutor";
              return (
                <motion.li
                  key={`${turn.speaker}-${i}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className={`rounded-2xl px-4 py-3 text-sm ${
                    isTutor
                      ? "border border-cyan-400/15 bg-cyan-950/40 text-cyan-50"
                      : "border border-white/8 bg-slate-800/60 text-slate-200 ml-4"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-widest opacity-50">
                      {isTutor ? "NeuroSync AI" : "You"}
                    </span>
                    {isTutor && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-[9px] uppercase tracking-wide font-medium ${strategyBadge[turn.strategy] || strategyBadge.continue}`}
                      >
                        {turn.strategy.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  {isTutor && i === turns.length - 1 ? (
                    <TextGenerateEffect
                      key={turn.text}
                      words={turn.text}
                      duration={0.3}
                      filter={false}
                      className="text-sm font-normal"
                    />
                  ) : (
                    <p className="leading-relaxed">{turn.text}</p>
                  )}
                </motion.li>
              );
            })}
          </AnimatePresence>
        )}
        <div ref={bottomRef} />
      </ul>
    </section>
  );
}
