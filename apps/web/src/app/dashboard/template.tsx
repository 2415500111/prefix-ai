import type { ReactNode } from "react";

import { PageTransition } from "@/components/ui/animated";

/** Each staff page fades in and rises slightly when you arrive on it. */
export default function DashboardTemplate({
  children,
}: {
  children: ReactNode;
}) {
  return <PageTransition>{children}</PageTransition>;
}
