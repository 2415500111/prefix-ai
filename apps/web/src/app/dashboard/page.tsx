import type { Metadata } from "next";

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default function DashboardPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">
        Coordinator dashboard
      </h1>
      <Card>
        <CardHeader>
          <CardTitle>No upcoming procedures</CardTitle>
          <CardDescription>
            Scheduled procedures will appear here, sorted by cancellation risk.
          </CardDescription>
        </CardHeader>
      </Card>
    </main>
  );
}
