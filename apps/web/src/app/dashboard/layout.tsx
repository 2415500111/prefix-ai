import Link from "next/link";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";
import { logout } from "@/app/login/actions";
import { getCurrentUser } from "@/lib/server/dal";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/protocols", label: "Protocols" },
  { href: "/dashboard/inbox", label: "Inbox" },
  { href: "/dashboard/tasks", label: "Tasks" },
  { href: "/dashboard/analytics", label: "Analytics" },
] as const;

/** Guests must always know that the data is made up. */
async function DemoBanner() {
  const user = await getCurrentUser();
  if (user.role !== "DEMO_VIEWER") return null;
  return (
    <div
      role="status"
      className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-950"
    >
      Demo mode: every patient is made up, no messages are sent, and the demo
      starts fresh every night.
    </div>
  );
}

async function UserMenu() {
  const user = await getCurrentUser();
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="hidden text-muted-foreground sm:inline">
        {user.full_name} · {user.role.toLowerCase()}
      </span>
      <form action={logout}>
        <Button type="submit" variant="outline" size="sm">
          Sign out
        </Button>
      </form>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: LayoutProps<"/dashboard">) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <nav aria-label="Dashboard" className="flex items-center gap-1">
            <Link href="/dashboard" className="mr-3 font-semibold">
              Prefix AI
            </Link>
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <Suspense fallback={<div className="h-7 w-24" aria-hidden="true" />}>
            <UserMenu />
          </Suspense>
        </div>
      </header>
      <Suspense fallback={null}>
        <DemoBanner />
      </Suspense>
      {children}
    </div>
  );
}
