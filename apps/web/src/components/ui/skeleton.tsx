import { cn } from "cn";

/** A placeholder with the shape of the content that is loading. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse rounded-lg bg-muted", className)}
    />
  );
}

/** A list of skeleton rows, announced once to screen readers as loading. */
export function SkeletonList({
  rows = 5,
  label,
}: {
  rows?: number;
  label: string;
}) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 rounded-2xl border bg-card p-4 shadow-card"
        >
          <Skeleton className="size-10 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

/** Summary-card skeletons, for the top of a dashboard. */
export function SkeletonCards({ count = 4 }: { count?: number }) {
  return (
    <div aria-hidden className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-card"
        >
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-7 w-1/3" />
        </div>
      ))}
    </div>
  );
}
