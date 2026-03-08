"use client"

import { useState, useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

interface SegmentedProgressProps {
  value?: number
  segments?: number
  label?: string
  showPercentage?: boolean
  showDemo?: boolean
  className?: string
  color?: string
}

export function SegmentedProgress({
  value: initialValue = 80,
  segments = 10,
  label,
  showPercentage = true,
  showDemo = false,
  className,
  color,
}: SegmentedProgressProps) {
  const [progress, setProgress] = useState(initialValue)
  const value = showDemo ? progress : initialValue
  const [displayValue, setDisplayValue] = useState(0)
  const [hoveredSegment, setHoveredSegment] = useState<number | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)
  const animationRef = useRef<number | null>(null)
  const startValueRef = useRef(0)
  const startTimeRef = useRef(0)
  const filledSegments = Math.round((displayValue / 100) * segments)

  useEffect(() => {
    if (!isInitialized) {
      const t = setTimeout(() => setIsInitialized(true), 50)
      return () => clearTimeout(t)
    }
    const duration = 600
    startValueRef.current = displayValue
    startTimeRef.current = performance.now()
    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTimeRef.current
      const p = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setDisplayValue(startValueRef.current + (value - startValueRef.current) * eased)
      if (p < 1) animationRef.current = requestAnimationFrame(animate)
    }
    animationRef.current = requestAnimationFrame(animate)
    return () => { if (animationRef.current) cancelAnimationFrame(animationRef.current) }
  }, [value, isInitialized])

  const getSegmentStyle = (index: number) => {
    let scale = 1; let translateY = 0
    if (hoveredSegment !== null) {
      const distance = Math.abs(hoveredSegment - index)
      if (distance === 0) { scale = 1.3; translateY = -1 }
      else if (distance <= 3) {
        const falloff = Math.cos((distance / 3) * (Math.PI / 2))
        scale = 1 + 0.2 * falloff; translateY = -0.5 * falloff
      }
    }
    return { transform: `scaleY(${scale}) translateY(${translateY}px)`, transitionDelay: `${isInitialized ? index * 20 : 0}ms` }
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center justify-between">
        {label && <span className="text-xs text-slate-500 tracking-wide">{label}</span>}
        {showPercentage && (
          <span className="text-xs font-semibold tabular-nums text-slate-200">
            {Math.round(displayValue)}%
          </span>
        )}
      </div>
      <div className="flex gap-[2px] py-0.5" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
        {Array.from({ length: segments }).map((_, index) => {
          const isFilled = index < filledSegments
          return (
            <div
              key={index}
              onMouseEnter={() => setHoveredSegment(index)}
              onMouseLeave={() => setHoveredSegment(null)}
              className={cn(
                "h-2 flex-1 rounded-[3px] cursor-pointer origin-center",
                "transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
                isFilled ? (color ?? "bg-cyan-400") : "bg-slate-700/60",
              )}
              style={getSegmentStyle(index)}
            />
          )
        })}
      </div>
      {showDemo && (
        <input type="range" min={0} max={100} value={progress}
          onChange={(e) => setProgress(Number(e.target.value))}
          className="w-full h-1 bg-slate-700 rounded-full appearance-none cursor-pointer mt-1"
        />
      )}
    </div>
  )
}
