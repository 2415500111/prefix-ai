const DAY = 24 * 60 * 60 * 1000;

function isoDay(time: number): string {
  return new Date(time).toISOString().slice(0, 10);
}

/** The last thirty days, as YYYY-MM-DD, when the page is opened without dates. */
export function lastThirtyDays(): { start: string; end: string } {
  const now = Date.now();
  return { start: isoDay(now - 29 * DAY), end: isoDay(now) };
}
