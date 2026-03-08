export default function SessionControls({
  started,
  onStart,
  onStop,
}: {
  started: boolean;
  onStart: () => void;
  onStop: () => void;
  status: string;
}) {
  return (
    <div className="flex items-center gap-3">
      {!started ? (
        <button
          onClick={onStart}
          className="rounded-2xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:opacity-90"
        >
          Start Session
        </button>
      ) : (
        <button
          onClick={onStop}
          className="rounded-2xl bg-rose-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-rose-400"
        >
          Stop Session
        </button>
      )}
    </div>
  );
}