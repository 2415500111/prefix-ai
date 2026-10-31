"use client";

import type { Badges, Me } from "@prefix/shared";
import { cn } from "cn";
import {
  Bell,
  ChevronRight,
  CircleUserRound,
  LogOut,
  Menu,
  Search,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { logout } from "@/app/login/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover } from "@/components/ui/popover";
import { Sheet } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

import { spring } from "@/lib/motion";

import { type PatientHit, searchPatients } from "./actions";
import { pageTitle } from "./nav";
import { NotificationPanel } from "./notification-panel";
import { bellLabel } from "./notification-state";
import { Brand, SidebarNav } from "./sidebar";
import { useStaffNotifications } from "./use-staff-notifications";

const WHEN = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

function PatientSearch({ close }: { close: () => void }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<PatientHit[] | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (!query.trim()) return;
    const timer = window.setTimeout(() => {
      startTransition(async () => setHits(await searchPatients(query)));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [query]);

  const shown = query.trim() ? hits : null;
  return (
    <div className="flex flex-col gap-2">
      <Input
        autoFocus
        type="search"
        aria-label="Search patients"
        placeholder="Name or procedure"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <p className="px-1 text-xs text-muted-foreground">
        Procedures in the next 7 days
      </p>
      {pending && !shown ? <Skeleton className="h-10" /> : null}
      {shown && shown.length === 0 ? (
        <p className="px-1 py-2 text-sm text-muted-foreground">
          No patient matches.
        </p>
      ) : null}
      {shown && shown.length > 0 ? (
        <ul className="flex flex-col">
          {shown.map((hit) => (
            <li key={hit.appointment_id}>
              <Link
                href={`/dashboard?appointment=${hit.appointment_id}`}
                onClick={close}
                className="flex pressable items-center gap-3 rounded-lg px-2 py-2 hover:bg-muted"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">
                    {hit.patient_name}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {hit.procedure_name} ·{" "}
                    {WHEN.format(new Date(hit.scheduled_at))}
                  </span>
                </span>
                <ChevronRight
                  className="size-4 text-muted-foreground"
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** The count on the bell: urgent items in red, otherwise the unread total. */
function BellCount({ unread, urgent }: { unread: number; urgent: number }) {
  const count = urgent > 0 ? urgent : unread;
  return (
    <AnimatePresence initial={false}>
      {count > 0 ? (
        <motion.span
          key={`${urgent > 0 ? "urgent" : "unread"}-${count}`}
          aria-hidden
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1, transition: spring.snappy }}
          exit={{ scale: 0.5, opacity: 0 }}
          className={cn(
            "absolute -top-0.5 -right-0.5 grid h-4.5 min-w-4.5 place-items-center rounded-full px-1 text-[11px] leading-none font-semibold tabular-nums ring-2 ring-card",
            urgent > 0
              ? "bg-urgent text-white dark:text-[#1a0606]"
              : "bg-primary text-primary-foreground",
          )}
        >
          {count > 99 ? "99+" : count}
        </motion.span>
      ) : null}
    </AnimatePresence>
  );
}

export function TopBar({
  user,
  badges,
  canResetDemo,
  canSeeNotifications,
}: {
  user: Me;
  badges: Badges;
  canResetDemo: boolean;
  canSeeNotifications: boolean;
}) {
  const pathname = usePathname();
  const { group, title } = pageTitle(pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const notifications = useStaffNotifications(canSeeNotifications);
  const { summary } = notifications;

  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 border-b glass px-3 sm:px-5">
      <Sheet
        open={menuOpen}
        onOpenChange={setMenuOpen}
        side="left"
        title={<Brand />}
        trigger={
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open navigation"
          >
            <Menu aria-hidden />
          </Button>
        }
      >
        <div className="px-3 py-4">
          <SidebarNav
            badges={badges}
            canResetDemo={canResetDemo}
            onNavigate={() => setMenuOpen(false)}
          />
        </div>
      </Sheet>

      <p className="flex min-w-0 flex-1 items-center gap-1.5 text-sm">
        <span className="hidden text-muted-foreground sm:inline">{group}</span>
        <ChevronRight
          className="hidden size-3.5 text-muted-foreground sm:inline"
          aria-hidden
        />
        <span className="truncate font-semibold">{title}</span>
      </p>

      <Popover
        title="Find a patient"
        trigger={
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-muted-foreground"
            aria-label="Search patients"
          >
            <Search aria-hidden />
            <span className="hidden lg:inline">Search patients</span>
          </Button>
        }
      >
        {(close) => <PatientSearch close={close} />}
      </Popover>

      {canSeeNotifications ? (
        <Popover
          title="Notifications"
          className="w-96"
          // The list names patients, so it is fetched when someone looks at it.
          onOpenChange={(open) => {
            if (open) notifications.loadFeed();
          }}
          trigger={
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              aria-label={bellLabel(summary)}
            >
              <Bell aria-hidden />
              <BellCount
                unread={summary?.unread_count ?? 0}
                urgent={summary?.urgent_count ?? 0}
              />
            </Button>
          }
        >
          {(close) => (
            <NotificationPanel
              feed={notifications.feed}
              onOpen={(item) => {
                close();
                notifications.open(item);
              }}
              onMarkAllRead={notifications.markAllRead}
            />
          )}
        </Popover>
      ) : null}

      <Popover
        className="w-64"
        trigger={
          <Button variant="ghost" size="icon" aria-label="Your account">
            <CircleUserRound aria-hidden />
          </Button>
        }
      >
        <div className="flex flex-col gap-1 px-2 py-1">
          <p className="truncate text-sm font-semibold">{user.full_name}</p>
          <p className="text-xs text-muted-foreground capitalize">
            {user.role.toLowerCase().replace("_", " ")}
          </p>
        </div>
        <div className="my-1 border-t" />
        <form action={logout}>
          <Button
            type="submit"
            variant="ghost"
            className="w-full justify-start gap-2"
          >
            <LogOut aria-hidden />
            Sign out
          </Button>
        </form>
      </Popover>
    </header>
  );
}
