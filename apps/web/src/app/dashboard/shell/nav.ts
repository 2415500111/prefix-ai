import type { Badges } from "@prefix/shared";
import {
  CalendarClock,
  ChartColumn,
  ClipboardList,
  Inbox,
  LayoutDashboard,
  ListChecks,
  type LucideIcon,
  Upload,
  Users,
} from "lucide-react";

/** Where every staff feature lives (docs/DESIGN.md, section 4), grouped by the job at hand. */
export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: keyof Badges;
  badgeLabel?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Today",
    items: [
      { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
      {
        href: "/dashboard/tasks",
        label: "Tasks",
        icon: ListChecks,
        badge: "open_tasks",
        badgeLabel: "open tasks",
      },
      {
        href: "/dashboard/requests",
        label: "Requests",
        icon: CalendarClock,
        badge: "pending_requests",
        badgeLabel: "pending requests",
      },
    ],
  },
  {
    label: "Patients",
    items: [
      {
        href: "/dashboard/inbox",
        label: "Inbox",
        icon: Inbox,
        badge: "open_escalations",
        badgeLabel: "open escalations",
      },
      { href: "/dashboard/waitlist", label: "Waitlist", icon: Users },
    ],
  },
  {
    label: "Clinical",
    items: [
      { href: "/dashboard/protocols", label: "Protocols", icon: ClipboardList },
    ],
  },
  {
    label: "Insights",
    items: [
      { href: "/dashboard/analytics", label: "Analytics", icon: ChartColumn },
    ],
  },
  {
    label: "Admin",
    items: [{ href: "/dashboard/imports", label: "Import", icon: Upload }],
  },
];

/** The current page's group and title, for the top bar. */
export function pageTitle(pathname: string): { group: string; title: string } {
  let best: { group: string; title: string; length: number } | null = null;
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const matches =
        pathname === item.href ||
        (item.href !== "/dashboard" && pathname.startsWith(`${item.href}/`));
      if (matches && (!best || item.href.length > best.length)) {
        best = {
          group: group.label,
          title: item.label,
          length: item.href.length,
        };
      }
    }
  }
  return best ?? { group: "Today", title: "Overview" };
}

export function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}
