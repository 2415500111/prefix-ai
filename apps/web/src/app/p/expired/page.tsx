import type { Metadata } from "next";

import { PortalCard } from "../_portal/portal-card";

export const metadata: Metadata = { title: "Link expired" };

export default function ExpiredPage() {
  return (
    <PortalCard>
      <p>
        Your session has ended or this link is no longer valid. Please ask your
        care team for a new link.
      </p>
      <p lang="hi">
        आपका सत्र समाप्त हो गया है या यह लिंक अब मान्य नहीं है। कृपया अपनी
        देखभाल टीम से नया लिंक माँगें।
      </p>
    </PortalCard>
  );
}
