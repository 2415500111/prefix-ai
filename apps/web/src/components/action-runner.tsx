"use client";

import {
  type ComponentProps,
  type FormEvent,
  type ReactNode,
  useTransition,
} from "react";

import type { ActionResult } from "@/app/dashboard/action-result";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";

/** Runs a server action and shows its result as a toast. */
export function useActionRunner() {
  const [pending, startTransition] = useTransition();
  function run(
    action: () => Promise<ActionResult>,
    after?: (result: ActionResult) => void,
  ): void {
    startTransition(async () => {
      const result = await action();
      if (result.ok) toast.success(result.message);
      else toast.error(result.message);
      after?.(result);
    });
  }
  return { run, pending };
}

type ButtonProps = Omit<ComponentProps<typeof Button>, "onClick" | "children">;

/**
 * A button for one staff action. With `confirm`, it first asks in a macOS-style dialog; any
 * fields in `fields` are sent with the action.
 */
export function ActionButton({
  action,
  children,
  confirm,
  ...buttonProps
}: ButtonProps & {
  action: (form: FormData) => Promise<ActionResult>;
  children: ReactNode;
  confirm?: {
    title: string;
    description?: ReactNode;
    confirmLabel: string;
    tone?: "default" | "danger";
    fields?: ReactNode;
  };
}) {
  const { run, pending } = useActionRunner();

  if (confirm) {
    return (
      <ConfirmDialog
        trigger={<Button {...buttonProps}>{children}</Button>}
        title={confirm.title}
        description={confirm.description}
        confirmLabel={confirm.confirmLabel}
        tone={confirm.tone}
        onConfirm={async (form) => {
          const result = await action(form);
          if (result.ok) toast.success(result.message);
          else toast.error(result.message);
          return result.ok;
        }}
      >
        {confirm.fields}
      </ConfirmDialog>
    );
  }

  return (
    <Button
      {...buttonProps}
      disabled={pending || buttonProps.disabled}
      onClick={() => run(() => action(new FormData()))}
    >
      {children}
    </Button>
  );
}

/** A form for one staff action: it shows the result as a toast and clears itself on success. */
export function ActionForm({
  action,
  children,
  className,
  resetOnSuccess = true,
  label,
}: {
  action: (form: FormData) => Promise<ActionResult>;
  children: ReactNode;
  className?: string;
  resetOnSuccess?: boolean;
  label?: string;
}) {
  const { run, pending } = useActionRunner();

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(
      () => action(data),
      (result) => {
        if (result.ok && resetOnSuccess) form.reset();
      },
    );
  }

  return (
    <form
      onSubmit={submit}
      className={className}
      aria-label={label}
      aria-busy={pending}
    >
      <fieldset disabled={pending} className="contents">
        {children}
      </fieldset>
    </form>
  );
}
