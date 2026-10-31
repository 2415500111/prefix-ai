import { FlaskConical } from "lucide-react";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import {
  canSeeNotifications,
  getBadges,
  getCurrentUser,
} from "@/lib/server/dal";

import { Sidebar } from "./shell/sidebar";
import { TopBar } from "./shell/top-bar";

/** Guests must always know that the data is made up. One slim line, always visible. */
async function DemoBanner() {
  const user = await getCurrentUser();
  if (user.role !== "DEMO_VIEWER") return null;
  return (
    <div
      role="status"
      className="flex h-8 shrink-0 items-center justify-center gap-2 bg-attention-soft px-4 text-xs font-medium text-attention-foreground"
    >
      <FlaskConical className="size-3.5" aria-hidden />
      Demo mode: every patient is made up, no messages are sent, and the demo
      starts fresh every night.
    </div>
  );
}

async function SidebarSlot() {
  const [user, badges] = await Promise.all([getCurrentUser(), getBadges()]);
  return <Sidebar badges={badges} canResetDemo={user.role === "ADMIN"} />;
}

async function TopBarSlot() {
  const [user, badges] = await Promise.all([getCurrentUser(), getBadges()]);
  return (
    <TopBar
      user={user}
      badges={badges}
      canResetDemo={user.role === "ADMIN"}
      canSeeNotifications={canSeeNotifications(user.role)}
    />
  );
}

function SidebarFallback() {
  return (
    <aside
      aria-hidden
      className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-3 border-r bg-sidebar px-3 py-5 md:flex"
    >
      <Skeleton className="h-7 w-32" />
      {Array.from({ length: 8 }, (_, index) => (
        <Skeleton key={index} className="h-8" />
      ))}
    </aside>
  );
}

export default function DashboardLayout({
  children,
}: LayoutProps<"/dashboard">) {
  return (
    <div className="flex min-h-dvh flex-1 bg-background">
      <Suspense fallback={<SidebarFallback />}>
        <SidebarSlot />
      </Suspense>
      <div className="flex min-w-0 flex-1 flex-col">
        <Suspense fallback={null}>
          <DemoBanner />
        </Suspense>
        <Suspense
          fallback={
            <div className="h-14 shrink-0 border-b glass" aria-hidden />
          }
        >
          <TopBarSlot />
        </Suspense>
        {children}
      </div>
    </div>
  );
}
