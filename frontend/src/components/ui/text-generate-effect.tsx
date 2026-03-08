"use client"

import { useEffect } from "react"
import { motion, stagger, useAnimate } from "framer-motion"
import { cn } from "@/lib/utils"

export function TextGenerateEffect({
  words,
  className,
  filter = false,
  duration = 0.4,
}: {
  words: string
  className?: string
  filter?: boolean
  duration?: number
}) {
  const [scope, animate] = useAnimate()
  const wordsArray = words.split(" ")

  useEffect(() => {
    animate(
      "span",
      { opacity: 1, filter: filter ? "blur(0px)" : "none" },
      { duration, delay: stagger(0.08) }
    )
  }, [scope.current])

  return (
    <div className={cn("leading-relaxed", className)}>
      <motion.div ref={scope}>
        {wordsArray.map((word, idx) => (
          <motion.span
            key={word + idx}
            className="text-slate-100 opacity-0"
            style={{ filter: filter ? "blur(6px)" : "none" }}
          >
            {word}{" "}
          </motion.span>
        ))}
      </motion.div>
    </div>
  )
}
