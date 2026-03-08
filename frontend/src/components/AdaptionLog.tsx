export default function AdaptationLog({ entries }: { entries: string[] }) {
  return (
    <section className="rounded-2xl bg-transparent p-1">
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-white">Adaptation Log</h2>
        <p className="mt-1 text-sm text-slate-400">
          Real-time tutoring decisions and session events
        </p>
      </div>

      <div className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
        {entries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-slate-800/40 px-4 py-3 text-sm text-slate-500">
            Waiting for session events...
          </div>
        ) : (
          entries.map((entry, i) => (
            <div
              key={`${entry}-${i}`}
              className="rounded-2xl border border-white/10 bg-slate-800/60 px-4 py-3 text-sm text-slate-200"
            >
              {entry}
            </div>
          ))
        )}
      </div>
    </section>
  );
}