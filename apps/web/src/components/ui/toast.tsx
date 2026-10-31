"use client";

import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useSyncExternalStore } from "react";

import { exit, spring } from "@/lib/motion";

/**
 * iOS-style notifications for the result of an action. They drop in from the top, stay four
 * seconds (failures six, urgent ones until dismissed), and can be swiped up to dismiss.
 * Successes are announced politely; failures interrupt (role="alert").
 */
export type ToastTone = "success" | "error" | "info";

/** A button on the toast, e.g. "Open" on an urgent notification. Pressing it dismisses it. */
export interface ToastAction {
  label: string;
  onClick: () => void;
}

interface ToastOptions {
  description?: string;
  sticky?: boolean;
  action?: ToastAction;
}

interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
  sticky: boolean;
  action?: ToastAction;
}

const VISIBLE = 3;
let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

function push(tone: ToastTone, title: string, options?: ToastOptions): number {
  const id = nextId++;
  items = [
    {
      id,
      tone,
      title,
      description: options?.description,
      sticky: options?.sticky ?? false,
      action: options?.action,
    },
    ...items,
  ].slice(0, VISIBLE);
  emit();
  return id;
}

export function dismissToast(id: number): void {
  items = items.filter((item) => item.id !== id);
  emit();
}

export const toast = {
  success: (title: string, options?: { description?: string }) =>
    push("success", title, options),
  error: (title: string, options?: ToastOptions) =>
    push("error", title, options),
  info: (title: string, options?: ToastOptions) => push("info", title, options),
};

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const EMPTY: ToastItem[] = [];

const ICON = { success: CircleCheck, error: CircleAlert, info: Info } as const;
const ICON_CLASS = {
  success: "text-ready",
  error: "text-urgent",
  info: "text-primary",
} as const;

function ToastCard({ item }: { item: ToastItem }) {
  const Icon = ICON[item.tone];

  useEffect(() => {
    if (item.sticky) return;
    const timer = window.setTimeout(
      () => dismissToast(item.id),
      item.tone === "error" ? 6000 : 4000,
    );
    return () => window.clearTimeout(timer);
  }, [item]);

  return (
    <motion.div
      layout
      role={item.tone === "error" ? "alert" : "status"}
      initial={{ opacity: 0, y: -24, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1, transition: spring.snappy }}
      exit={{ opacity: 0, y: -16, scale: 0.98, transition: exit }}
      drag="y"
      dragConstraints={{ top: 0, bottom: 0 }}
      dragElastic={{ top: 0.6, bottom: 0.1 }}
      onDragEnd={(_, info) => {
        if (info.offset.y < -24 || info.velocity.y < -400)
          dismissToast(item.id);
      }}
      className="pointer-events-auto flex w-full items-start gap-3 rounded-2xl border glass px-4 py-3 shadow-raised"
    >
      <Icon
        className={`mt-0.5 size-5 shrink-0 ${ICON_CLASS[item.tone]}`}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">{item.title}</p>
        {item.description ? (
          <p className="text-sm text-muted-foreground">{item.description}</p>
        ) : null}
      </div>
      {item.action ? (
        <button
          type="button"
          onClick={() => {
            dismissToast(item.id);
            item.action?.onClick();
          }}
          className="shrink-0 pressable self-center rounded-full bg-primary-soft px-3 py-1 text-sm font-semibold text-primary-soft-foreground hover:bg-primary-soft/80"
        >
          {item.action.label}
        </button>
      ) : null}
      <button
        type="button"
        onClick={() => dismissToast(item.id)}
        className="-mr-1 pressable rounded-full p-1 text-muted-foreground hover:bg-muted"
        aria-label="Dismiss"
      >
        <X className="size-4" aria-hidden />
      </button>
    </motion.div>
  );
}

export function Toaster() {
  const current = useSyncExternalStore(
    subscribe,
    () => items,
    () => EMPTY,
  );
  return (
    // An explicit live region: modal dialogs and sheets hide everything outside them from
    // assistive technology except elements with aria-live, so toasts are still announced.
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-3 z-[100] mx-auto flex w-[min(28rem,calc(100vw-1.5rem))] flex-col gap-2"
    >
      <AnimatePresence initial={false}>
        {current.map((item) => (
          <ToastCard key={item.id} item={item} />
        ))}
      </AnimatePresence>
    </div>
  );
}
