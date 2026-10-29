"use client";

import { useSyncExternalStore } from "react";

function supported(): boolean {
  return (
    typeof window !== "undefined" && typeof window.matchMedia === "function"
  );
}

/** True when the media query matches. The server render (and first paint) assumes false. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (!supported()) return () => {};
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => supported() && window.matchMedia(query).matches,
    () => false,
  );
}
