export default function EEGBandBars({
  bands,
}: {
  bands?: {
    alpha: number;
    beta: number;
    theta: number;
    gamma: number;
    delta: number;
  };
}) {
  const safeBands = bands ?? {
    alpha: 0,
    beta: 0,
    theta: 0,
    gamma: 0,
    delta: 0,
  };

  return (
    <div className="rounded-2xl bg-transparent p-1">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-white">EEG Bands</div>
          <div className="text-sm text-slate-400">Live signal overview</div>
        </div>
      </div>

      <div className="space-y-4">
        {Object.entries(safeBands).map(([name, value]) => {
          const width = `${Math.max(0, Math.min(value * 100, 100))}%`;

          return (
            <div key={name}>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="capitalize text-slate-200">{name}</span>
                <span className="font-medium text-slate-400">
                  {value.toFixed(2)}
                </span>
              </div>

              <div className="h-3 overflow-hidden rounded-full bg-slate-800/90">
                <div
                  className="h-full rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(103,232,249,0.35)]"
                  style={{
                    width,
                    transition: "width 0.45s ease",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}