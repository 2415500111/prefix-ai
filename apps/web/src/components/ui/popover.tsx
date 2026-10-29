"use client";

import { Popover as BasePopover } from "@base-ui/react/popover";
import { cn } from "cn";
import { AnimatePresence, motion } from "motion/react";
import { type ReactElement, type ReactNode, useState } from "react";

import { exit, spring } from "@/lib/motion";

/** A glass popover that grows out of its trigger, like macOS. */
export function Popover({
  trigger,
  title,
  children,
  align = "end",
  className,
}: {
  trigger: ReactElement;
  title?: string;
  children: ReactNode | ((close: () => void) => ReactNode);
  align?: "start" | "center" | "end";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <BasePopover.Root open={open} onOpenChange={(next) => setOpen(next)}>
      <BasePopover.Trigger render={trigger} />
      <AnimatePresence>
        {open ? (
          <BasePopover.Portal keepMounted>
            <BasePopover.Positioner
              sideOffset={8}
              align={align}
              className="z-50"
            >
              <BasePopover.Popup
                className={cn(
                  "glass shadow-raised w-80 max-w-[calc(100vw-1.5rem)] origin-(--transform-origin) rounded-2xl border p-2 text-foreground outline-none",
                  className,
                )}
                render={
                  <motion.div
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{
                      opacity: 1,
                      scale: 1,
                      transition: spring.snappy,
                    }}
                    exit={{ opacity: 0, scale: 0.98, transition: exit }}
                  />
                }
              >
                {title ? (
                  <BasePopover.Title className="px-2 pt-1 pb-2 text-sm font-semibold">
                    {title}
                  </BasePopover.Title>
                ) : null}
                {typeof children === "function" ? children(close) : children}
              </BasePopover.Popup>
            </BasePopover.Positioner>
          </BasePopover.Portal>
        ) : null}
      </AnimatePresence>
    </BasePopover.Root>
  );
}
