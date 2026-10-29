"use client";

import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import { cn } from "cn";
import { AnimatePresence, motion } from "motion/react";
import {
  type FormEvent,
  type ReactElement,
  type ReactNode,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { ease, exit, spring } from "@/lib/motion";

/**
 * A macOS-style dialog: it scales up from 0.96 and fades in over a blurred backdrop, and closes
 * faster than it opens. Base UI provides the focus trap, Escape to close and focus return.
 */
export function Dialog({
  open,
  onOpenChange,
  trigger,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trigger?: ReactElement;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <BaseDialog.Root open={open} onOpenChange={(next) => onOpenChange(next)}>
      {trigger ? <BaseDialog.Trigger render={trigger} /> : null}
      <AnimatePresence>
        {open ? (
          <BaseDialog.Portal keepMounted>
            <BaseDialog.Backdrop
              className="fixed inset-0 z-50 bg-[rgb(15_27_42/0.28)] backdrop-blur-[6px] dark:bg-black/50"
              render={
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1, transition: ease }}
                  exit={{ opacity: 0, transition: exit }}
                />
              }
            />
            <BaseDialog.Popup
              className={cn(
                "fixed top-1/2 left-1/2 z-50 flex max-h-[calc(100dvh-2rem)] w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-y-auto rounded-2xl border bg-card p-6 text-foreground shadow-overlay outline-none",
                className,
              )}
              render={
                <motion.div
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1, transition: spring.gentle }}
                  exit={{ opacity: 0, scale: 0.98, transition: exit }}
                />
              }
            >
              <div className="flex flex-col gap-1.5">
                <BaseDialog.Title className="text-lg font-semibold tracking-tight">
                  {title}
                </BaseDialog.Title>
                {description ? (
                  <BaseDialog.Description className="text-sm text-muted-foreground">
                    {description}
                  </BaseDialog.Description>
                ) : null}
              </div>
              {children}
            </BaseDialog.Popup>
          </BaseDialog.Portal>
        ) : null}
      </AnimatePresence>
    </BaseDialog.Root>
  );
}

/**
 * Asks before an action runs. Extra fields (a reason, a new time) go in `children`; they are
 * passed to `onConfirm` as form data. The dialog closes when `onConfirm` resolves true.
 */
export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "default",
  onConfirm,
  children,
}: {
  trigger: ReactElement;
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  onConfirm: (form: FormData) => Promise<boolean> | boolean;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPending(true);
    try {
      if (await onConfirm(new FormData(event.currentTarget))) setOpen(false);
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={trigger}
      title={title}
      description={description}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {children}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => setOpen(false)}
          >
            {cancelLabel}
          </Button>
          <Button
            type="submit"
            size="lg"
            variant={tone === "danger" ? "destructive" : "default"}
            disabled={pending}
          >
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
