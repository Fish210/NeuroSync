import { WhiteboardDeltaPayload } from "@/lib/types";

interface Props {
  blocks?: WhiteboardDeltaPayload[];
}

export function WhiteboardPanel({ blocks = [] }: Props) {
  return (
    <section className="relative h-full overflow-hidden rounded-[28px] border border-white/10 bg-slate-900 shadow-[0_20px_50px_rgba(0,0,0,0.25)]">
      <div className="flex flex-col gap-3 border-b border-white/10 px-5 py-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Live Whiteboard</h2>
          <p className="mt-1 text-sm text-slate-400">
            Shared tutoring workspace
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button className="rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-700">
            Pen
          </button>
          <button className="rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-700">
            Text
          </button>
          <button className="rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-700">
            Erase
          </button>
          <button className="rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-700">
            Clear
          </button>
        </div>
      </div>

      <div className="relative min-h-[760px] flex-1 cursor-crosshair bg-slate-900">
        <div
          className="absolute inset-0 opacity-35"
          style={{
            backgroundImage:
              "radial-gradient(rgba(255,255,255,0.13) 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
        />

        {blocks.length === 0 ? (
          <>
            <div className="absolute left-6 top-6 rounded-2xl border border-white/10 bg-slate-950/85 px-5 py-4 shadow-lg backdrop-blur">
              <div className="text-xs uppercase tracking-[0.22em] text-slate-400">
                Current Lesson
              </div>
              <div className="mt-2 text-3xl font-semibold text-white">
                Derivatives
              </div>
              <p className="mt-3 max-w-xl text-sm leading-relaxed text-slate-300">
                Whiteboard shell ready. Waiting for WHITEBOARD_DELTA events.
              </p>
            </div>

            <div className="absolute left-10 top-44 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 px-6 py-5 text-slate-100 shadow-lg">
              <div className="mb-2 text-sm text-cyan-300">Worked Example</div>
              <div className="text-4xl font-semibold tracking-tight">
                d/dx [(2x + 5)^3]
              </div>
            </div>
          </>
        ) : (
          <div className="relative h-full w-full p-6">
            {blocks.map((block) => (
              <div
                key={block.id}
                className="absolute max-w-[420px] rounded-2xl border border-white/10 bg-slate-950/85 px-4 py-3 text-sm text-slate-100 shadow-lg"
                style={{
                  left: block.position.x,
                  top: block.position.y,
                }}
              >
                <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-400">
                  {block.author} · {block.type}
                </div>
                <div className="leading-relaxed">{block.content}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}