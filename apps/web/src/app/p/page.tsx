import type { Metadata } from "next";

import { RedeemLink } from "./redeem-link";

export const metadata: Metadata = {
  title: "Opening your prep plan",
  // The link's token lives in the URL fragment; never leak this URL to other sites.
  referrer: "no-referrer",
};

export default function MagicLinkPage() {
  return (
    <main className="flex flex-1 flex-col justify-center gap-6 py-10">
      <h1 className="text-2xl font-semibold">Prefix AI</h1>
      <RedeemLink />
    </main>
  );
}
