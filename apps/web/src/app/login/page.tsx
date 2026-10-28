import type { Capabilities } from "@prefix/shared";
import type { Metadata } from "next";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in to Prefix AI</CardTitle>
          <CardDescription>For hospital staff.</CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm action={login} />
          <Suspense fallback={null}>
            <GuestSection searchParams={searchParams} />
          </Suspense>
        </CardContent>
      </Card>
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
    <div className="mt-6 flex flex-col gap-3 border-t pt-6">
      <p className="text-sm text-muted-foreground">
        Want to look around first? The demo uses made-up patients only.
      </p>
      <form action={loginAsGuest}>
        <Button type="submit" variant="outline" size="lg" className="w-full">
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
