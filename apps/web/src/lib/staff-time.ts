/** How staff lists say when a patient raised something. */

const FORMATS = new Map<string, Intl.DateTimeFormat>();

function formatIn(timeZone: string): Intl.DateTimeFormat {
  let format = FORMATS.get(timeZone);
  if (!format) {
    format = new Intl.DateTimeFormat("en-IN", {
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone,
    });
    FORMATS.set(timeZone, format);
  }
  return format;
}

/** The date and time in the facility's time zone, e.g. "30 Oct, 1:02 pm". */
export function raisedAt(iso: string, timeZone: string): string {
  return formatIn(timeZone).format(new Date(iso));
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** How long ago, e.g. "just now", "2 min ago", "3 h ago", "yesterday", "4 days ago". */
export function timeAgo(iso: string, now: number): string {
  const elapsed = Math.max(0, now - new Date(iso).getTime());
  if (elapsed < MINUTE) return "just now";
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)} min ago`;
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)} h ago`;
  const days = Math.floor(elapsed / DAY);
  return days === 1 ? "yesterday" : `${days} days ago`;
}
