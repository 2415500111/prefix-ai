"use client";

import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import { cn } from "cn";
import { motion } from "motion/react";
import type { ReactNode } from "react";

import { spring } from "@/lib/motion";

/**
 * Tabs with a sliding indicator. Arrow keys move between tabs (Base UI). The panel fades in
 * when it is shown.
 */
export function Tabs({
  tabs,
  defaultValue,
  value,
  onValueChange,
  className,
  label,
}: {
  tabs: { value: string; label: ReactNode; content: ReactNode }[];
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  label: string;
}) {
  return (
    <BaseTabs.Root
      defaultValue={defaultValue ?? tabs[0]?.value}
      value={value}
      onValueChange={
        onValueChange ? (next) => onValueChange(String(next)) : undefined
      }
      className={cn("flex min-h-0 flex-col", className)}
    >
      <BaseTabs.List
        aria-label={label}
        className="relative flex shrink-0 [scrollbar-width:none] gap-1 overflow-x-auto border-b px-4"
      >
        {tabs.map((tab) => (
          <BaseTabs.Tab
            key={tab.value}
            value={tab.value}
            className="pressable relative h-11 shrink-0 rounded-md px-3 text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/30 data-[active]:text-foreground"
          >
            {tab.label}
          </BaseTabs.Tab>
        ))}
        <BaseTabs.Indicator className="absolute bottom-0 left-(--active-tab-left) h-0.5 w-(--active-tab-width) rounded-full bg-primary transition-[left,width] duration-200 ease-[var(--ease-ios)]" />
      </BaseTabs.List>
      {tabs.map((tab) => (
        <BaseTabs.Panel
          key={tab.value}
          value={tab.value}
          className="min-h-0 flex-1 outline-none"
        >
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0, transition: spring.snappy }}
          >
            {tab.content}
          </motion.div>
        </BaseTabs.Panel>
      ))}
    </BaseTabs.Root>
  );
}
