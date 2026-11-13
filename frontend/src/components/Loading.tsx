import { useEffect, useState } from "react";
import { ApiError } from "../lib/api";
import { Notice, Skeleton } from "./ui";

/** Placeholder while a score loads; after a few seconds, explains why. */
export function LoadingResults({ what = "Scoring this address" }: { what?: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 5000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="space-y-4" aria-busy="true">
      <p className="text-sm text-ink-2" role="status">
        {what}…
        {slow && " Still working — right after the service restarts, the first request waits up to a minute while city-wide street data loads."}
      </p>
      <div className="grid gap-4 md:grid-cols-[260px_1fr]">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
      <Skeleton className="h-[420px]" />
    </div>
  );
}

export function ErrorNotice({ error }: { error: unknown }) {
  const message = error instanceof ApiError || error instanceof Error ? error.message : "Something went wrong.";
  return <Notice tone="bad">{message}</Notice>;
}
