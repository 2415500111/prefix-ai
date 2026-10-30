import type { ReactNode } from "react";

import { PageTransition } from "@/components/ui/animated";

/** Each portal tab fades in and rises slightly, like an iOS screen change. */
export default function PortalTemplate({ children }: { children: ReactNode }) {
  return <PageTransition>{children}</PageTransition>;
}
