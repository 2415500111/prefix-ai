"use client";

import { cn } from "cn";

import { raisedAt, timeAgo } from "@/lib/staff-time";
import { useNow } from "@/lib/use-now";

/** "30 Oct, 1:02 pm · 2 min ago": the facility's time, and how long ago, updating live. */
export function RaisedTime({
  iso,
  timeZone,
  className,
}: {
  iso: string;
  timeZone: string;
  className?: string;
}) {
  const now = useNow();
  return (
    <span className={cn("text-xs text-muted-foreground", className)}>
      <time dateTime={iso}>{raisedAt(iso, timeZone)}</time>
      {now === null ? null : <> · {timeAgo(iso, now)}</>}
    </span>
  );
}
