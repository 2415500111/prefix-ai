"use client";

import {
  Bell,
  ClipboardList,
  House,
  LifeBuoy,
  type LucideIcon,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { spring } from "@/lib/motion";
import {
  PORTAL_TEXT,
  type PortalLang,
  type PortalTab,
} from "@/lib/portal-i18n";

const TABS = [
  { tab: "home", href: "/p/home", Icon: House },
  { tab: "prep", href: "/p/prep", Icon: ClipboardList },
  { tab: "updates", href: "/p/updates", Icon: Bell },
  { tab: "help", href: "/p/help", Icon: LifeBuoy },
] as const satisfies readonly {
  tab: PortalTab;
  href: string;
  Icon: LucideIcon;
}[];

/** The iOS-style tab bar. The pill behind the active icon glides between tabs. */
export function TabBar({ lang, unread }: { lang: PortalLang; unread: number }) {
  const pathname = usePathname();
  const t = PORTAL_TEXT[lang];

  return (
    <nav
      aria-label={t.tabBar}
      lang={lang}
      className="fixed inset-x-0 bottom-0 z-40 border-t glass pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="mx-auto grid h-16 max-w-xl grid-cols-4">
        {TABS.map(({ tab, href, Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          const badge = tab === "updates" && unread > 0;
          return (
            <li key={tab} className="flex">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-1 pressable flex-col items-center justify-center gap-0.5 text-[12px] font-medium focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none focus-visible:ring-inset ${
                  active ? "text-primary" : "text-muted-foreground"
                }`}
              >
                <span className="relative grid h-8 w-14 place-items-center">
                  {active ? (
                    <motion.span
                      layoutId="portal-tab"
                      className="absolute inset-0 rounded-full bg-primary-soft"
                      transition={spring.snappy}
                    />
                  ) : null}
                  <Icon
                    aria-hidden
                    className="relative size-6"
                    strokeWidth={active ? 2 : 1.75}
                  />
                  {badge ? (
                    <span
                      aria-hidden
                      className="absolute -top-1 right-1.5 h-[18px] min-w-[18px] rounded-full bg-urgent px-1 text-center text-[11px] leading-[18px] font-semibold text-white tabular-nums dark:text-[#1a0606]"
                    >
                      {unread > 9 ? "9+" : unread}
                    </span>
                  ) : null}
                </span>
                <span>{t.tabs[tab]}</span>
                {badge ? (
                  <span className="sr-only">{`, ${t.unreadBadge(unread)}`}</span>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
