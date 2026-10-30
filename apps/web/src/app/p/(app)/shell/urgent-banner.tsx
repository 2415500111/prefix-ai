"use client";

import type { PortalNotification } from "@prefix/shared";
import { BellRing, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { exit, spring } from "@/lib/motion";
import { PORTAL_TEXT, type PortalLang } from "@/lib/portal-i18n";
import { updateText } from "@/lib/portal-updates";

/**
 * The most urgent unread update, dropping in like an iOS notification. Tapping it opens the
 * update (which marks it read); Hide tucks it away until the next urgent update.
 */
export function UrgentBanner({
  item,
  lang,
  now,
}: {
  item: PortalNotification | null;
  lang: PortalLang;
  now: number;
}) {
  const pathname = usePathname();
  const [hiddenKey, setHiddenKey] = useState<string | null>(null);
  const t = PORTAL_TEXT[lang];
  const visible =
    item !== null &&
    item.key !== hiddenKey &&
    !pathname.startsWith("/p/updates");
  const text = item ? updateText(item, lang, now) : null;

  return (
    <AnimatePresence initial>
      {visible && text ? (
        <motion.div
          key={item.key}
          role="status"
          lang={lang}
          initial={{ y: -20, opacity: 0, scale: 0.98 }}
          animate={{ y: 0, opacity: 1, scale: 1, transition: spring.snappy }}
          exit={{ y: -12, opacity: 0, transition: exit }}
          className="mb-3 flex items-center gap-1 rounded-2xl border border-urgent/25 glass p-2 pl-3 shadow-raised"
        >
          <Link
            href={`/p/updates?open=${encodeURIComponent(item.key)}`}
            className="flex min-w-0 flex-1 items-center gap-3 rounded-xl py-1 focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
          >
            <span
              aria-hidden
              className="grid size-10 shrink-0 place-items-center rounded-full bg-urgent-soft text-urgent-foreground"
            >
              <BellRing className="size-5" strokeWidth={1.75} />
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="text-[15px] leading-5 font-semibold">
                {text.title}
              </span>
              {text.body ? (
                <span className="truncate text-[13px] leading-[18px] text-muted-foreground">
                  {text.body}
                </span>
              ) : null}
            </span>
          </Link>
          <button
            type="button"
            aria-label={t.bannerDismiss}
            onClick={() => setHiddenKey(item.key)}
            className="grid size-11 shrink-0 pressable place-items-center rounded-full text-muted-foreground hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
          >
            <X aria-hidden className="size-5" />
          </button>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
