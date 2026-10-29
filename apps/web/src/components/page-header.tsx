import type { ReactNode } from "react";

/** An iOS-style large title for a staff page, with an optional line of help and actions. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div className="flex flex-col gap-1">
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">
          {title}
        </h1>
        {description ? (
          <p className="text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex gap-2">{actions}</div> : null}
    </header>
  );
}

/** The standard width and padding for a staff page. */
export function PageBody({
  children,
  wide = false,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <main
      className={`mx-auto flex w-full flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8 ${
        wide ? "max-w-6xl" : "max-w-5xl"
      }`}
    >
      {children}
    </main>
  );
}
