"use client";

import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import { cn } from "cn";
import { X } from "lucide-react";
import { AnimatePresence, motion, useDragControls } from "motion/react";
import type { ReactElement, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ease, exit, spring } from "@/lib/motion";
import { useMediaQuery } from "@/lib/use-media-query";

type Side = "right" | "left" | "bottom";

const OFFSCREEN: Record<Side, { x?: string; y?: string }> = {
  right: { x: "100%" },
  left: { x: "-100%" },
  bottom: { y: "100%" },
};

const PLACEMENT: Record<Side, string> = {
  right:
    "inset-y-0 right-0 h-dvh w-[min(36rem,100vw)] rounded-l-2xl border-l sm:inset-y-2 sm:right-2 sm:h-[calc(100dvh-1rem)] sm:rounded-2xl sm:border",
  left: "inset-y-0 left-0 h-dvh w-[min(18rem,85vw)] rounded-r-2xl border-r",
  bottom: "inset-x-0 bottom-0 max-h-[92dvh] w-full rounded-t-[20px] border-t",
};

/**
 * A sheet that slides in with a spring: from the right on desktop, from the bottom on phones
 * (`side="auto"`). A bottom sheet can be dragged down by its handle or header to close: past
 * 120px or a quick flick closes, anything less springs back. Base UI handles focus and Escape.
 */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  side = "auto",
  trigger,
  headerActions,
  footer,
  children,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  side?: Side | "auto";
  trigger?: ReactElement;
  headerActions?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const phone = useMediaQuery("(max-width: 639px)");
  const resolved: Side = side === "auto" ? (phone ? "bottom" : "right") : side;
  const controls = useDragControls();
  const draggable = resolved === "bottom";

  return (
    <BaseDialog.Root open={open} onOpenChange={(next) => onOpenChange(next)}>
      {trigger ? <BaseDialog.Trigger render={trigger} /> : null}
      <AnimatePresence>
        {open ? (
          <BaseDialog.Portal keepMounted>
            <BaseDialog.Backdrop
              className="fixed inset-0 z-50 bg-[rgb(15_27_42/0.24)] backdrop-blur-[4px] dark:bg-black/50"
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
                "shadow-overlay fixed z-50 flex flex-col overflow-hidden bg-card text-foreground outline-none",
                PLACEMENT[resolved],
                className,
              )}
              render={
                <motion.div
                  initial={{ ...OFFSCREEN[resolved], opacity: 0.6 }}
                  animate={{
                    x: 0,
                    y: 0,
                    opacity: 1,
                    transition: spring.gentle,
                  }}
                  exit={{
                    ...OFFSCREEN[resolved],
                    opacity: 0.6,
                    transition: { ...exit, duration: 0.22 },
                  }}
                  drag={draggable ? "y" : false}
                  dragControls={controls}
                  dragListener={false}
                  dragConstraints={{ top: 0, bottom: 0 }}
                  dragElastic={{ top: 0, bottom: 0.9 }}
                  onDragEnd={(_, info) => {
                    if (info.offset.y > 120 || info.velocity.y > 600)
                      onOpenChange(false);
                  }}
                />
              }
            >
              <header
                className="glass sticky top-0 z-10 flex shrink-0 flex-col border-b px-5 pt-3 pb-3"
                onPointerDown={
                  draggable ? (event) => controls.start(event) : undefined
                }
                style={draggable ? { touchAction: "none" } : undefined}
              >
                {draggable ? (
                  <span
                    aria-hidden
                    className="mx-auto mb-2 h-1.5 w-10 shrink-0 rounded-full bg-muted-foreground/30"
                  />
                ) : null}
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <BaseDialog.Title className="truncate text-lg font-semibold tracking-tight">
                      {title}
                    </BaseDialog.Title>
                    {description ? (
                      <BaseDialog.Description className="text-sm text-muted-foreground">
                        {description}
                      </BaseDialog.Description>
                    ) : null}
                  </div>
                  {headerActions}
                  <BaseDialog.Close
                    render={
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Close"
                      />
                    }
                  >
                    <X aria-hidden />
                  </BaseDialog.Close>
                </div>
              </header>
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
                {children}
              </div>
              {footer ? (
                <footer className="glass shrink-0 border-t px-5 py-3">
                  {footer}
                </footer>
              ) : null}
            </BaseDialog.Popup>
          </BaseDialog.Portal>
        ) : null}
      </AnimatePresence>
    </BaseDialog.Root>
  );
}
