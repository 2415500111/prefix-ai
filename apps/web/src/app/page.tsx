import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const pillars = [
  {
    title: "Clinician-approved protocols",
    description:
      "Every prep instruction comes from a protocol your clinicians signed off. Nothing is invented.",
  },
  {
    title: "A timeline for every patient",
    description:
      "Steps are anchored to the procedure time and delivered as reminders in the patient's language.",
  },
  {
    title: "Risk you can act on",
    description:
      "Readiness check-ins feed a cancellation risk score, so coordinators can step in or backfill the slot.",
  },
] as const;

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-16 px-4 py-16 sm:px-6 sm:py-24">
      <section className="flex flex-col items-start gap-6">
        <Badge variant="secondary">Patient preparation, handled</Badge>
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Prefix AI
        </h1>
        <p className="max-w-2xl text-lg text-pretty text-muted-foreground">
          Stop losing OR slots to poor prep. Prefix AI keeps patients on track
          for surgeries, colonoscopies, and imaging scans, and warns your team
          early when someone is not ready.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/dashboard" className={buttonVariants({ size: "lg" })}>
            Open coordinator dashboard
          </Link>
        </div>
      </section>

      <section
        aria-label="How Prefix AI works"
        className="grid gap-4 sm:grid-cols-3"
      >
        {pillars.map((pillar) => (
          <Card key={pillar.title}>
            <CardHeader>
              <CardTitle>{pillar.title}</CardTitle>
              <CardDescription>{pillar.description}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </section>
    </main>
  );
}
