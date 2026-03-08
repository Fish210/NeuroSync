"use client"

import { useEffect, useState } from "react"
import { useTheme } from "next-themes"
import { Moon, Sun } from "lucide-react"
import { cn } from "@/lib/utils"

interface ThemeToggleProps {
  className?: string
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  if (!mounted) {
    return <div className="w-16 h-8 rounded-full bg-slate-800 border border-slate-700 animate-pulse" />
  }

  const isDark = resolvedTheme === "dark"

  return (
    <div
      className={cn(
        "relative flex w-16 h-8 p-1 rounded-full cursor-pointer transition-all duration-300 items-center",
        isDark
          ? "bg-slate-950 border border-slate-700"
          : "bg-white border border-slate-200 shadow-sm",
        className
      )}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      role="button"
      tabIndex={0}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onKeyDown={(e) => e.key === "Enter" && setTheme(isDark ? "light" : "dark")}
    >
      {/* Static background icons */}
      <Sun className="absolute left-1.5 w-3.5 h-3.5 text-slate-500 pointer-events-none" strokeWidth={1.5} />
      <Moon className="absolute right-1.5 w-3.5 h-3.5 text-slate-500 pointer-events-none" strokeWidth={1.5} />

      {/* Sliding pill */}
      <div
        className={cn(
          "absolute w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300",
          isDark
            ? "translate-x-0 bg-slate-700"
            : "translate-x-8 bg-slate-100"
        )}
      >
        {isDark
          ? <Moon className="w-3.5 h-3.5 text-cyan-300" strokeWidth={1.5} />
          : <Sun className="w-3.5 h-3.5 text-amber-500" strokeWidth={1.5} />
        }
      </div>
    </div>
  )
}
