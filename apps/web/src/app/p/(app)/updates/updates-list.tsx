"use client";

import type { PortalNotification } from "@prefix/shared";
import {
  BellRing,
  CalendarCheck2,
  CalendarClock,
  CalendarSync,
  CalendarX2,
  CheckCheck,
  ChevronRight,
  CircleCheck,
  CircleDot,
  Clock,
  MessageSquareText,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type ComponentType,
  type SVGProps,
  useEffect,
  useState,
  useTransition,
} from "react";

import { StaggerItem } from "@/components/ui/animated";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { toast } from "@/components/ui/toast";
import {
  formatDateTime,
  formatRelative,
  PORTAL_TEXT,
  type PortalLang,
} from "@/lib/portal-i18n";
import { updateLink, updateText } from "@/lib/portal-updates";

import { markAllNotificationsRead, markNotificationsRead } from "../../actions";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

const FALLBACK_TIMEZONE = "Asia/Kolkata";

function iconFor(item: PortalNotification): Icon {
  switch (item.kind) {
    case "step_now":
      return item.step_done ? CircleCheck : CircleDot;
    case "step_soon":
      return Clock;
    case "care_team_message":
      return MessageSquareText;
    case "reschedule_request":
      if (item.request_status === "approved") return CalendarCheck2;
      if (item.request_status === "declined") return CalendarX2;
      return CalendarSync;
    case "appointment_moved":
      return CalendarClock;
    case "appointment_cancelled":
      return CalendarX2;
  }
}

function toneFor(item: PortalNotification, read: boolean): string {
  if (item.kind === "step_now" && item.step_done)
    return "bg-ready-soft text-ready-foreground";
  if (item.urgency === "urgent" && !read)
    return "bg-urgent-soft text-urgent-foreground";
  return "bg-primary-soft text-primary-soft-foreground";
}

/**
 * The Updates feed, newest first. Tapping an update opens it in a bottom sheet and marks it
 * read; the bell and tab badges follow once the page refreshes.
 */
export function UpdatesList({
  items,
  lang,
  now,
  openKey,
}: {
  items: PortalNotification[];
  lang: PortalLang;
  now: number;
  openKey: string | null;
}) {
  const t = PORTAL_TEXT[lang];
  const router = useRouter();
  const opened = items.find((item) => item.key === openKey) ?? null;
  const [selectedKey, setSelectedKey] = useState(opened?.key ?? null);
  const [sheetOpen, setSheetOpen] = useState(opened !== null);
  const [readKeys, setReadKeys] = useState<ReadonlySet<string>>(
    () => new Set(opened ? [opened.key] : []),
  );
  const [, startTransition] = useTransition();

  const isRead = (item: PortalNotification) =>
    item.read || readKeys.has(item.key);
  const unread = items.filter((item) => !isRead(item)).length;
  const selected = items.find((item) => item.key === selectedKey) ?? null;

  // An update opened from the banner is marked read as it arrives.
  const arrivedUnread = opened && !opened.read ? opened.key : null;
  useEffect(() => {
    if (arrivedUnread) void markNotificationsRead([arrivedUnread]);
  }, [arrivedUnread]);

  function openItem(item: PortalNotification): void {
    setSelectedKey(item.key);
    setSheetOpen(true);
    if (isRead(item)) return;
    setReadKeys((previous) => new Set(previous).add(item.key));
    startTransition(async () => {
      const result = await markNotificationsRead([item.key]);
      if (!result.ok) toast.error(t.updatesFailed);
    });
  }

  function onOpenChange(next: boolean): void {
    setSheetOpen(next);
    if (!next && openKey) router.replace("/p/updates", { scroll: false });
  }

  function markAll(): void {
    setReadKeys(new Set(items.map((item) => item.key)));
    startTransition(async () => {
      const result = await markAllNotificationsRead();
      if (!result.ok) toast.error(t.updatesFailed);
    });
  }

  const selectedText = selected ? updateText(selected, lang, now) : null;
  const selectedLink = selected ? updateLink(selected) : null;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-[28px] leading-[34px] font-semibold tracking-tight">
            {t.updatesTitle}
          </h1>
          {unread > 0 ? (
            <p className="text-[15px] text-muted-foreground">
              {t.unreadBadge(unread)}
            </p>
          ) : null}
        </div>
        {unread > 0 ? (
          <Button variant="soft" className="h-11 text-[15px]" onClick={markAll}>
            <CheckCheck aria-hidden className="size-5" />
            {t.markAllRead}
          </Button>
        ) : null}
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-[20px] border bg-card p-8 text-center shadow-card">
          <span
            aria-hidden
            className="grid size-12 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground"
          >
            <BellRing className="size-6" strokeWidth={1.75} />
          </span>
          <p className="text-muted-foreground">{t.noUpdates}</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item, index) => {
            const text = updateText(item, lang, now);
            const read = isRead(item);
            const ItemIcon = iconFor(item);
            return (
              <StaggerItem key={item.key} index={index}>
                <button
                  type="button"
                  onClick={() => openItem(item)}
                  className={`flex w-full pressable items-start gap-3 rounded-[20px] border bg-card p-4 text-left shadow-card focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none ${
                    item.urgency === "urgent" && !read ? "border-urgent/30" : ""
                  }`}
                >
                  <span
                    aria-hidden
                    className={`grid size-10 shrink-0 place-items-center rounded-full ${toneFor(item, read)}`}
                  >
                    <ItemIcon className="size-5" strokeWidth={1.75} />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="flex items-start justify-between gap-2">
                      <span className={read ? "font-medium" : "font-semibold"}>
                        {text.title}
                      </span>
                      {read ? null : (
                        <span className="mt-2 size-2.5 shrink-0 rounded-full bg-primary">
                          <span className="sr-only">{t.newLabel}</span>
                        </span>
                      )}
                    </span>
                    {text.body ? (
                      <span className="line-clamp-2 text-[15px] leading-[22px] text-muted-foreground">
                        {text.body}
                      </span>
                    ) : null}
                    <span className="text-[13px] text-muted-foreground">
                      <time dateTime={item.created_at}>
                        {formatRelative(item.created_at, now, lang)}
                      </time>
                    </span>
                  </span>
                </button>
              </StaggerItem>
            );
          })}
        </ul>
      )}

      <Sheet
        open={sheetOpen && selected !== null}
        onOpenChange={onOpenChange}
        side="bottom"
        className="sm:inset-x-[max(1rem,calc(50%-18rem))]"
        title={selectedText?.title ?? t.updatesTitle}
        closeLabel={t.close}
      >
        {selected && selectedText ? (
          <div
            lang={lang}
            className="flex flex-col gap-4 p-5 pb-[calc(env(safe-area-inset-bottom)+1.25rem)]"
          >
            <p className="text-[15px] text-muted-foreground">
              <time dateTime={selected.created_at}>
                {formatDateTime(
                  selected.created_at,
                  selected.timezone ?? FALLBACK_TIMEZONE,
                  lang,
                )}
              </time>
            </p>
            {selectedText.body ? (
              <p className="whitespace-pre-line">{selectedText.body}</p>
            ) : null}
            {selectedLink ? (
              <Link
                href={selectedLink}
                onClick={() => setSheetOpen(false)}
                className="inline-flex h-12 pressable items-center justify-center gap-1 rounded-xl bg-primary px-5 text-[17px] font-semibold text-primary-foreground shadow-card focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
              >
                {selected.kind === "step_now" || selected.kind === "step_soon"
                  ? t.goToStep
                  : t.helpTitle}
                <ChevronRight aria-hidden className="size-5" />
              </Link>
            ) : null}
          </div>
        ) : null}
      </Sheet>
    </>
  );
}
