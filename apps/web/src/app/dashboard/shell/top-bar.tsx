"use client";

import type { Badges, Me } from "@prefix/shared";
import { cn } from "cn";
import {
  Bell,
  CalendarClock,
  ChevronRight,
  CircleUserRound,
  LogOut,
  Menu,
  Search,
  ShieldAlert,
  ListChecks,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { logout } from "@/app/login/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover } from "@/components/ui/popover";
import { Sheet } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

import {
  loadNotifications,
  type PatientHit,
  searchPatients,
  type StaffNotification,
} from "./actions";
import { pageTitle } from "./nav";
import { Brand, SidebarNav } from "./sidebar";

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

const KIND_ICON = {
  escalation: ShieldAlert,
  task: ListChecks,
  request: CalendarClock,
} as const;
const TONE_CLASS = {
  urgent: "bg-urgent-soft text-urgent-foreground",
  attention: "bg-attention-soft text-attention-foreground",
  info: "bg-primary-soft text-primary-soft-foreground",
} as const;

function NotificationList({ close }: { close: () => void }) {
  const [items, setItems] = useState<StaffNotification[] | null>(null);
  useEffect(() => {
    let live = true;
    void loadNotifications().then((loaded) => {
      if (live) setItems(loaded);
    });
    return () => {
      live = false;
    };
  }, []);

  if (items === null) {
    return (
      <div
        role="status"
        aria-label="Loading notifications"
        className="flex flex-col gap-2 p-1"
      >
        <Skeleton className="h-12" />
        <Skeleton className="h-12" />
        <Skeleton className="h-12" />
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <p className="px-2 py-6 text-center text-sm text-muted-foreground">
        Nothing needs you right now.
      </p>
    );
  }
  return (
    <ul className="flex max-h-96 flex-col overflow-y-auto">
      {items.map((item) => {
        const Icon = KIND_ICON[item.kind];
        return (
          <li key={item.id}>
            <Link
              href={item.href}
              onClick={close}
              className="flex pressable items-start gap-3 rounded-lg px-2 py-2 hover:bg-muted"
            >
              <span
                className={cn(
                  "grid size-8 shrink-0 place-items-center rounded-full",
                  TONE_CLASS[item.tone],
                )}
              >
                <Icon className="size-4" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {item.title}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  {item.detail}
                </span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function TopBar({
  user,
  badges,
  canResetDemo,
}: {
  user: Me;
  badges: Badges;
  canResetDemo: boolean;
}) {
  const pathname = usePathname();
  const { group, title } = pageTitle(pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const attention = badges.open_escalations + badges.pending_requests;

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

      <Popover
        title="Needs attention"
        trigger={
          <Button
            variant="ghost"
            size="icon"
            className="relative"
            aria-label={
              attention > 0
                ? `Notifications, ${attention} need attention`
                : "Notifications"
            }
          >
            <Bell aria-hidden />
            {attention > 0 ? (
              <span className="absolute top-1 right-1 size-2.5 rounded-full bg-urgent ring-2 ring-card" />
            ) : null}
          </Button>
        }
      >
        {(close) => <NotificationList close={close} />}
      </Popover>

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
