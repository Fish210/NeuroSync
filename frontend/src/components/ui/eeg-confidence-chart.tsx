"use client"

import { useRef } from "react"

export interface ChartDataPoint {
  time: number
  value: number
  state: string
}

interface EEGConfidenceChartProps {
  data: ChartDataPoint[]
  className?: string
}

const stateColor: Record<string, string> = {
  FOCUSED: "#34d399",
  OVERLOADED: "#fb7185",
  DISENGAGED: "#fbbf24",
}

export function EEGConfidenceChart({ data, className }: EEGConfidenceChartProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const width = 400
  const height = 120
  const padding = { top: 10, right: 8, bottom: 24, left: 32 }

  const currentPoint = data[data.length - 1]
  const currentColor = currentPoint ? (stateColor[currentPoint.state] ?? "#94a3b8") : "#94a3b8"
  const currentValue = currentPoint?.value ?? 0

  const getX = (time: number) => {
    if (data.length < 2) return padding.left
    const minTime = data[0].time
    const maxTime = data[data.length - 1].time
    const range = maxTime - minTime || 1
    return padding.left + ((time - minTime) / range) * (width - padding.left - padding.right)
  }

  const getY = (value: number) =>
    padding.top + (1 - value / 100) * (height - padding.top - padding.bottom)

  const getPath = () => {
    if (data.length < 2) return ""
    return data.map((p, i) => `${i === 0 ? "M" : "L"} ${getX(p.time)},${getY(p.value)}`).join(" ")
  }

  const getAreaPath = () => {
    if (data.length < 2) return ""
    const linePath = getPath()
    const lastX = getX(data[data.length - 1].time)
    const firstX = getX(data[0].time)
    const bottomY = height - padding.bottom
    return `${linePath} L ${lastX},${bottomY} L ${firstX},${bottomY} Z`
  }

  return (
    <div className={className}>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-white">Confidence History</div>
          <div className="text-xs text-slate-500 mt-0.5">Last {data.length} readings</div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ backgroundColor: currentColor }} />
          <span className="text-sm font-bold tabular-nums" style={{ color: currentColor }}>
            {currentValue}%
          </span>
        </div>
      </div>

      {data.length < 2 ? (
        <div className="flex h-[80px] items-center justify-center rounded-xl border border-dashed border-white/10 text-xs text-slate-600">
          Waiting for EEG data…
        </div>
      ) : (
        <svg
          ref={svgRef}
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="overflow-visible"
        >
          <defs>
            <linearGradient id="conf-area-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={currentColor} stopOpacity="0.25" />
              <stop offset="100%" stopColor={currentColor} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map((val) => (
            <g key={val}>
              <line x1={padding.left} y1={getY(val)} x2={width - padding.right} y2={getY(val)} stroke="rgba(255,255,255,0.06)" />
              <text x={padding.left - 4} y={getY(val)} fill="#475569" fontSize="9" textAnchor="end" dominantBaseline="middle">{val}</text>
            </g>
          ))}

          {/* Area fill */}
          <path d={getAreaPath()} fill="url(#conf-area-grad)" />

          {/* Main line */}
          <path d={getPath()} fill="none" stroke={currentColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            style={{ filter: `drop-shadow(0 0 4px ${currentColor}60)` }} />

          {/* Latest dot */}
          {currentPoint && (
            <circle
              cx={getX(currentPoint.time)}
              cy={getY(currentPoint.value)}
              r="4"
              fill={currentColor}
              style={{ filter: `drop-shadow(0 0 6px ${currentColor})` }}
            />
          )}
        </svg>
      )}
    </div>
  )
}
