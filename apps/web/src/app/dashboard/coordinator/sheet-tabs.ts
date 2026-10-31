/** The patient sheet's tabs, so a link (e.g. from a notification) can open the right one. */
export const SHEET_TABS = [
  "overview",
  "timeline",
  "messages",
  "requests",
  "activity",
] as const;

export type SheetTab = (typeof SHEET_TABS)[number];

export function readSheetTab(value: string | string[] | undefined): SheetTab {
  return SHEET_TABS.find((tab) => tab === value) ?? "overview";
}
