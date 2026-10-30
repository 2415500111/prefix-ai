import type { Capabilities } from "@prefix/shared";
import { FlaskConical, ShieldCheck, Stethoscope } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/server/api";

import { login, loginAsGuest } from "./actions";
import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Sign in",
};

const GUEST_ERRORS: Record<string, string> = {
  unavailable: "The guest demo is not available on this server.",
  busy: "Too many demo sign-ins from this address. Please wait a few minutes.",
  error: "The demo could not be opened right now. Please try again.",
};

export default function LoginPage({ searchParams }: PageProps<"/login">) {
  return (
    <main className="relative flex flex-1 items-center justify-center overflow-hidden px-4 py-16">
      {/* A soft clinical wash behind the card; decoration only. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_30rem_at_50%_-10%,color-mix(in_oklab,var(--primary)_14%,transparent),transparent)]"
      />
      <div className="relative flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="grid size-12 place-items-center rounded-2xl bg-primary text-primary-foreground shadow-raised">
            <Stethoscope className="size-6" aria-hidden />
          </span>
          <div>
            <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
              Sign in to Prefix AI
            </h1>
            <p className="text-muted-foreground">For hospital staff.</p>
          </div>
        </div>
        <div className="flex flex-col gap-6 rounded-2xl border bg-card p-6 shadow-raised">
          <LoginForm action={login} />
          <Suspense fallback={null}>
            <GuestSection searchParams={searchParams} />
          </Suspense>
        </div>
        <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="size-3.5" aria-hidden />
          Patient details are encrypted, and every view is recorded.
        </p>
      </div>
    </main>
  );
}

async function GuestSection({
  searchParams,
}: {
  searchParams: PageProps<"/login">["searchParams"];
}) {
  const [capabilities, params] = await Promise.all([
    api<Capabilities>("/auth/capabilities", { token: null }).catch(() => ({
      guest_login: false,
    })),
    searchParams,
  ]);
  if (!capabilities.guest_login) return null;

  const code = typeof params.guest === "string" ? params.guest : undefined;
  const error = code ? GUEST_ERRORS[code] : undefined;
  return (
    <div className="flex flex-col gap-3 border-t pt-6">
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden />
        Want to look around first? The demo uses made-up patients only.
      </p>
      <form action={loginAsGuest}>
        <Button type="submit" variant="soft" size="lg" className="w-full">
          Try as Guest
        </Button>
      </form>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
