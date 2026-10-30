import { Skeleton } from "@/components/ui/skeleton";

/** A page's shape while its data loads: a title and two cards. */
export function PortalSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-4">
      <Skeleton className="h-9 w-48" />
      <Skeleton className="h-64 rounded-[20px]" />
      <Skeleton className="h-32 rounded-[20px]" />
    </div>
  );
}
