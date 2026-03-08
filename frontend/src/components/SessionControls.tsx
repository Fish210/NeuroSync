"use client";

import { MetalButton } from "@/components/ui/liquid-glass-button";

interface Props {
  onStop: () => void;
}

export default function SessionControls({ onStop }: Props) {
  return (
    <MetalButton variant="error" onClick={onStop}>
      Stop Session
    </MetalButton>
  );
}
