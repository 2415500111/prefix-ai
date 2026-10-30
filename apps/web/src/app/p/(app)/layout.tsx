import { type ReactNode, Suspense } from "react";

import { mostUrgentUnread } from "@/lib/portal-updates";
import { ApiError } from "@/lib/server/api";
import {
  getNotifications,
  getPatientSelf,
  getPortalLanguage,
  type MyUpdates,
} from "@/lib/server/portal";

import { PortalHeader } from "./shell/portal-header";
import { TabBar } from "./shell/tab-bar";
import { UrgentBanner } from "./shell/urgent-banner";

const NO_UPDATES: MyUpdates = { items: [], unread_count: 0, fetchedAt: 0 };

/** The signed-in portal: glass header, the urgent banner, the page, and the tab bar. */
export default function PortalAppLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <Suspense fallback={<HeaderFallback />}>
        <Header />
      </Suspense>
      <div className="mx-auto flex w-full max-w-xl flex-1 flex-col px-4 pt-4 pb-[calc(env(safe-area-inset-bottom)+6rem)]">
        <Suspense fallback={null}>
          <Banner />
        </Suspense>
        {children}
      </div>
      <Suspense fallback={<TabBarFallback />}>
        <Tabs />
      </Suspense>
    </>
  );
}

/** A broken feed must not take the whole portal down: the header then shows no count. */
async function updates(lang: string): Promise<MyUpdates> {
  try {
    return await getNotifications(lang);
  } catch (error) {
    if (error instanceof ApiError) return NO_UPDATES;
    throw error;
  }
}

async function Header() {
  const [self, lang] = await Promise.all([
    getPatientSelf(),
    getPortalLanguage(),
  ]);
  const feed = await updates(lang);
  return (
    <PortalHeader
      hospital={self.hospital_name}
      lang={lang}
      unread={feed.unread_count}
    />
  );
}

async function Banner() {
  const lang = await getPortalLanguage();
  const feed = await updates(lang);
  return (
    <UrgentBanner
      item={mostUrgentUnread(feed.items)}
      lang={lang}
      now={feed.fetchedAt}
    />
  );
}

async function Tabs() {
  const lang = await getPortalLanguage();
  const feed = await updates(lang);
  return <TabBar lang={lang} unread={feed.unread_count} />;
}

function HeaderFallback() {
  return (
    <div
      aria-hidden
      className="sticky top-0 z-40 h-16 border-b glass pt-[env(safe-area-inset-top)]"
    />
  );
}

function TabBarFallback() {
  return (
    <div
      aria-hidden
      className="fixed inset-x-0 bottom-0 z-40 h-16 border-t glass pb-[env(safe-area-inset-bottom)]"
    />
  );
}
