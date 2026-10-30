import type { Metadata } from "next";

import { PortalCard } from "./_portal/portal-card";
import { RedeemLink } from "./redeem-link";

export const metadata: Metadata = {
  title: "Opening your prep plan",
  // The link's token lives in the URL fragment; never leak this URL to other sites.
  referrer: "no-referrer",
};

export default function MagicLinkPage() {
  return (
    <PortalCard>
      <RedeemLink />
    </PortalCard>
  );
}
