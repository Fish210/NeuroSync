import { ConversationTurnPayload } from "@/lib/types";

interface Props {
  turns: ConversationTurnPayload[];
  speakingState?: "idle" | "speaking" | "interrupted";
}

export function ConversationTranscript({
  turns,
  speakingState = "idle",
}: Props) {
  return (
    <section className="rounded-2xl bg-transparent p-1">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-white">
            Conversation Transcript
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            AI tutor dialogue and spoken feedback
          </p>
        </div>

        <span className="rounded-full border border-white/10 bg-slate-800 px-3 py-1 text-xs text-slate-300">
          Audio: {speakingState}
        </span>
      </div>

      <ul className="max-h-[420px] space-y-3 overflow-auto pr-1">
        {turns.length === 0 ? (
          <li className="rounded-2xl border border-dashed border-white/10 bg-slate-800/40 px-4 py-3 text-sm text-slate-500">
            Waiting for CONVERSATION_TURN events...
          </li>
        ) : (
          turns.map((turn, index) => {
            const isTutor = turn.speaker === "tutor";

            return (
              <li
                key={`${turn.speaker}-${index}-${turn.text.slice(0, 8)}`}
                className={`rounded-2xl px-4 py-3 text-sm shadow-sm ${
                  isTutor
                    ? "border border-cyan-400/20 bg-cyan-400/5 text-cyan-50"
                    : "border border-white/10 bg-slate-800 text-slate-200"
                }`}
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">
                    {turn.speaker}
                  </span>
                  <span className="rounded-full bg-black/20 px-2.5 py-1 text-[10px] uppercase tracking-wide">
                    {turn.strategy}
                  </span>
                </div>

                <p className="leading-relaxed">{turn.text}</p>
              </li>
            );
          })
        )}
      </ul>
    </section>
  );
}