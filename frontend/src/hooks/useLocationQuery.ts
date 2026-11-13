import { useQuery, type QueryFunction } from "@tanstack/react-query";
import { useCallback } from "react";
import { useSearchParams } from "react-router";
import { locationKey, readLocation, writeLocation } from "../lib/location";
import type { LocationQuery } from "../lib/types";

/**
 * The location in the URL (optionally prefixed, for compare slots), a setter
 * that pushes a history entry, and the score query for it.
 */
export function useLocationQuery<T>(tool: string, fetcher: (q: LocationQuery) => Promise<T>, prefix = "") {
  const [params, setParams] = useSearchParams();
  const location = readLocation(params, prefix);

  const setLocation = useCallback(
    (q: LocationQuery | null) => setParams((p) => writeLocation(p, q, prefix)),
    [setParams, prefix],
  );

  const queryFn: QueryFunction<T> = () => fetcher(location!);
  const query = useQuery({
    queryKey: [tool, ...locationKey(location)],
    queryFn,
    enabled: location !== null,
  });

  return { location, setLocation, query };
}
