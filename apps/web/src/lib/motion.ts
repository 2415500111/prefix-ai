import type { Transition } from "motion/react";

/**
 * Shared motion presets (docs/DESIGN.md, section 3). Durations stay between 150 and 350 ms.
 *
 * - snappy: a tap that answers at once (popovers, toasts, segmented control, tab indicator)
 * - gentle: a sheet settling into place (dialogs, side and bottom sheets, page entry)
 * - ease / exit: fades, and closing faster than opening
 */
export const IOS_EASE = [0.32, 0.72, 0, 1] as const;

export const spring = {
  snappy: { type: "spring", stiffness: 520, damping: 40, mass: 0.8 },
  gentle: { type: "spring", stiffness: 280, damping: 32 },
} as const satisfies Record<string, Transition>;

export const ease = {
  duration: 0.18,
  ease: IOS_EASE,
} as const satisfies Transition;
export const exit = {
  duration: 0.15,
  ease: IOS_EASE,
} as const satisfies Transition;

/** Stagger list rows by 30 ms, and only the first ten, so long lists never feel slow. */
export const STAGGER_SECONDS = 0.03;
export const STAGGER_LIMIT = 10;
