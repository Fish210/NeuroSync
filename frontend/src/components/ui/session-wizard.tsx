"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { CircleCheck } from "lucide-react"
import { LiquidButton } from "@/components/ui/liquid-glass-button"
import { cn } from "@/lib/utils"

interface SessionWizardProps {
  onStart: (topic: string) => void
  eegStatus: "connected" | "disconnected" | "unknown"
  status: string
}

const STEP_LABELS = ["Topic", "EEG Check", "Start"]

export function SessionWizard({ onStart, eegStatus, status }: SessionWizardProps) {
  const [step, setStep] = useState(1)
  const [topic, setTopic] = useState("derivatives")

  const isStarting = status === "starting"

  const handleContinue = () => {
    if (step < 3) setStep(step + 1)
  }

  const handleBack = () => {
    if (step > 1) setStep(step - 1)
  }

  const handleStart = () => {
    if (topic.trim() && !isStarting) onStart(topic.trim())
  }

  return (
    <div className="w-full max-w-md mx-auto">
      <motion.div
        className="rounded-[28px] border border-white/10 bg-slate-900/90 shadow-2xl backdrop-blur-xl overflow-hidden"
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
      >
        {/* Header */}
        <div className="px-8 pt-8 pb-4">
          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-1">NeuroSync</div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Start a Session</h2>
          <p className="text-sm text-slate-400 mt-1">AI-powered neuroadaptive tutoring</p>
        </div>

        {/* Step dots */}
        <div className="px-8 py-4">
          <div className="relative flex items-center gap-6">
            {STEP_LABELS.map((label, i) => {
              const dotStep = i + 1
              const isActive = dotStep === step
              const isComplete = dotStep < step
              return (
                <div key={label} className="flex flex-col items-center gap-1 relative z-10">
                  <motion.div
                    className={cn(
                      "w-2.5 h-2.5 rounded-full transition-colors duration-300",
                      isComplete ? "bg-emerald-400" : isActive ? "bg-cyan-400" : "bg-slate-700"
                    )}
                    animate={{ scale: isActive ? 1.3 : 1 }}
                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                  />
                  <span className={cn("text-[9px] uppercase tracking-wider transition-colors", isActive ? "text-cyan-300" : "text-slate-600")}>
                    {label}
                  </span>
                </div>
              )
            })}
            {/* Progress line */}
            <div className="absolute top-[5px] left-[5px] right-[5px] h-[2px] bg-slate-700 -z-0" />
            <motion.div
              className="absolute top-[5px] left-[5px] h-[2px] bg-gradient-to-r from-emerald-400 to-cyan-400"
              animate={{ width: step === 1 ? "0%" : step === 2 ? "50%" : "100%" }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
            />
          </div>
        </div>

        {/* Step content */}
        <div className="px-8 pb-4 min-h-[120px]">
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.2 }}
                className="space-y-3"
              >
                <label className="block text-sm font-medium text-slate-300">What would you like to learn?</label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && topic.trim() && handleContinue()}
                  placeholder="e.g. derivatives, Newton's laws, recursion…"
                  className="w-full rounded-xl border border-white/10 bg-slate-800/70 px-4 py-3 text-sm text-white placeholder-slate-500 outline-none focus:border-cyan-400/40 focus:ring-1 focus:ring-cyan-400/20 transition"
                  autoFocus
                />
                <p className="text-xs text-slate-600">The AI tutor will adapt to your brain state in real-time.</p>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <div className="text-sm font-medium text-slate-300">EEG Headband Status</div>
                <div className={cn(
                  "flex items-center gap-3 rounded-2xl border px-4 py-4",
                  eegStatus === "connected"
                    ? "border-emerald-400/25 bg-emerald-400/5"
                    : eegStatus === "disconnected"
                    ? "border-rose-400/25 bg-rose-400/5"
                    : "border-white/10 bg-slate-800/40"
                )}>
                  <span className={cn(
                    "h-3 w-3 rounded-full flex-shrink-0",
                    eegStatus === "connected" ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" :
                    eegStatus === "disconnected" ? "bg-rose-400 animate-pulse" : "bg-slate-500 animate-pulse"
                  )} />
                  <div>
                    <div className={cn(
                      "text-sm font-semibold",
                      eegStatus === "connected" ? "text-emerald-300" :
                      eegStatus === "disconnected" ? "text-rose-300" : "text-slate-300"
                    )}>
                      {eegStatus === "connected" ? "Muse Connected" :
                       eegStatus === "disconnected" ? "Muse Disconnected" : "Looking for Muse…"}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {eegStatus === "connected"
                        ? "EEG data streaming — ready for adaptive tutoring"
                        : eegStatus === "disconnected"
                        ? "Connect your Muse headband via muselsl"
                        : "Start muselsl streaming, or proceed without EEG"}
                    </div>
                  </div>
                </div>
                {eegStatus !== "connected" && (
                  <p className="text-xs text-slate-500">You can proceed without EEG — the tutor will still adapt based on your responses.</p>
                )}
              </motion.div>
            )}

            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <div className="text-sm font-medium text-slate-300">Ready to start</div>
                <div className="rounded-2xl border border-white/10 bg-slate-800/40 px-4 py-3 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Topic</span>
                    <span className="text-white font-medium capitalize">{topic}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">EEG</span>
                    <span className={eegStatus === "connected" ? "text-emerald-300" : "text-slate-400"}>
                      {eegStatus === "connected" ? "Connected" : "No hardware"}
                    </span>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Navigation */}
        <div className="px-8 pb-8 flex items-center gap-3">
          <AnimatePresence>
            {step > 1 && (
              <motion.button
                initial={{ opacity: 0, width: 0, scale: 0.8 }}
                animate={{ opacity: 1, width: "auto", scale: 1 }}
                exit={{ opacity: 0, width: 0, scale: 0.8 }}
                transition={{ type: "spring", stiffness: 400, damping: 20 }}
                onClick={handleBack}
                className="px-5 py-2.5 rounded-full border border-white/10 bg-slate-800/60 text-sm font-semibold text-slate-300 hover:bg-slate-700/60 transition cursor-pointer whitespace-nowrap"
              >
                Back
              </motion.button>
            )}
          </AnimatePresence>

          {step < 3 ? (
            <motion.button
              className="flex-1 py-2.5 rounded-full bg-cyan-500/15 border border-cyan-400/30 text-sm font-semibold text-cyan-300 hover:bg-cyan-500/25 transition cursor-pointer"
              onClick={handleContinue}
              disabled={step === 1 && !topic.trim()}
            >
              {step === 1 && !topic.trim() ? "Enter a topic first" : "Continue →"}
            </motion.button>
          ) : (
            <div className="flex-1 flex justify-center">
              <LiquidButton
                onClick={handleStart}
                disabled={isStarting}
                className="w-full"
                size="lg"
              >
                {isStarting ? (
                  <span className="flex items-center gap-2">
                    <span className="inline-flex gap-0.5">
                      {[0, 1, 2].map((i) => (
                        <span key={i} className="w-1 h-1 rounded-full bg-current animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }} />
                      ))}
                    </span>
                    Starting…
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <CircleCheck size={16} />
                    Start Session
                  </span>
                )}
              </LiquidButton>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  )
}
