import type { Metadata } from "next";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { login } from "./actions";
import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in to Prefix AI</CardTitle>
          <CardDescription>For hospital staff.</CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm action={login} />
        </CardContent>
      </Card>
    </main>
  );
}
