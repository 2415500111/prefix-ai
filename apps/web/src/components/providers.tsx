"use client";

import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";

import { Toaster } from "@/components/ui/toast";

/** App-wide client setup: reduced-motion handling for every animation, and the toaster. */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      {children}
      <Toaster />
    </MotionConfig>
  );
}
