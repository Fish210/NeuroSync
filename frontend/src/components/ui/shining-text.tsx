"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface ShiningTextProps {
  text: string
  className?: string
}

export function ShiningText({ text, className }: ShiningTextProps) {
  return (
    <motion.span
      className={cn(
        "bg-[linear-gradient(110deg,#94a3b8,35%,#e2e8f0,50%,#94a3b8,75%,#94a3b8)] bg-[length:200%_100%] bg-clip-text text-transparent",
        className
      )}
      initial={{ backgroundPosition: "200% 0" }}
      animate={{ backgroundPosition: "-200% 0" }}
      transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
    >
      {text}
    </motion.span>
  )
}
