"use client";

import { cn } from "cn";
import { motion, useSpring, useTransform } from "motion/react";
import { type ReactNode, useEffect } from "react";

import { spring, STAGGER_LIMIT, STAGGER_SECONDS } from "@/lib/motion";

/** A number that springs from its old value to its new one. Tabular figures, so it never jumps. */
export function AnimatedNumber({
  value,
  suffix = "",
  className,
}: {
  value: number;
  suffix?: string;
  className?: string;
}) {
  const motionValue = useSpring(value, { stiffness: 180, damping: 26 });
  const text = useTransform(
    motionValue,
    (latest) => `${Math.round(latest)}${suffix}`,
  );
  useEffect(() => {
    motionValue.set(value);
  }, [motionValue, value]);
  return (
    <motion.span className={cn("tabular-nums", className)}>{text}</motion.span>
  );
}

const TONE = {
  primary: "bg-primary",
  ready: "bg-ready",
  attention: "bg-attention",
  urgent: "bg-urgent",
} as const;

export type Tone = keyof typeof TONE;

/** A progress bar that fills with a spring. */
export function ProgressBar({
  value,
  label,
  tone = "primary",
  className,
}: {
  value: number;
  label: string;
  tone?: Tone;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className={cn(
        "h-2 w-full overflow-hidden rounded-full bg-muted",
        className,
      )}
    >
      <motion.div
        className={cn("h-full rounded-full", TONE[tone])}
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%`, transition: spring.gentle }}
      />
    </div>
  );
}

const RING_STROKE = {
  primary: "stroke-primary",
  ready: "stroke-ready",
  attention: "stroke-attention",
  urgent: "stroke-urgent",
} as const;

/** A readiness ring, like the Apple Watch activity rings: it draws itself to the value. */
export function ProgressRing({
  value,
  label,
  tone = "primary",
  size = 120,
  children,
}: {
  value: number;
  label: string;
  tone?: Tone;
  size?: number;
  children?: ReactNode;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const stroke = 10;
  const radius = (size - stroke) / 2;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="-rotate-90"
        aria-hidden
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-muted"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className={RING_STROKE[tone]}
          initial={{ pathLength: 0 }}
          animate={{ pathLength: clamped / 100, transition: spring.gentle }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        {children}
      </div>
    </div>
  );
}

/** Fades and lifts list rows in, 30 ms apart, for the first ten rows only. */
export function StaggerItem({
  index,
  children,
  className,
  as = "li",
}: {
  index: number;
  children: ReactNode;
  className?: string;
  as?: "li" | "div";
}) {
  const Component = as === "li" ? motion.li : motion.div;
  return (
    <Component
      className={className}
      initial={{ opacity: 0, y: 6 }}
      animate={{
        opacity: 1,
        y: 0,
        transition: {
          ...spring.gentle,
          delay: Math.min(index, STAGGER_LIMIT) * STAGGER_SECONDS,
        },
      }}
    >
      {children}
    </Component>
  );
}

/** Pages fade in and rise 6px. Used by the app's template files. */
export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div
      className="flex min-h-0 flex-1 flex-col"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0, transition: spring.gentle }}
    >
      {children}
    </motion.div>
  );
}
