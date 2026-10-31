import { useSyncExternalStore } from "react";

/** Relative times move on in steps of this size. */
export const TICK_MS = 15_000;

function subscribe(onChange: () => void): () => void {
  // Check a few times per step, so a new step shows within a few seconds of starting.
  const timer = window.setInterval(onChange, TICK_MS / 3);
  return () => window.clearInterval(timer);
}

// Rounded to the step, so repeated reads within a step give the same value.
function getSnapshot(): number {
  return Math.floor(Date.now() / TICK_MS) * TICK_MS;
}

function getServerSnapshot(): null {
  return null;
}

/**
 * The current time for relative labels ("2 min ago"), updating every 15 seconds. Null while
 * the page hydrates, so the server's HTML and the first client render agree.
 */
export function useNow(): number | null {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
