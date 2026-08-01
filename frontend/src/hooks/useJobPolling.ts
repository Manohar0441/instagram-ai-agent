import { useQuery } from "@tanstack/react-query";

import { getJob } from "../api/jobs";
import type { JobStatusResponse } from "../api/types";

const POLL_INTERVAL_MS = 2000;
/** Stop polling after this long so a wedged worker cannot spin forever. */
const POLL_CEILING_MS = 5 * 60 * 1000;

const TERMINAL_STATUSES = ["finished", "failed", "stopped", "canceled"];

export function useJobPolling(jobId: string | null, startedAt: number | null) {
  const query = useQuery<JobStatusResponse>({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && TERMINAL_STATUSES.includes(status)) return false;
      if (startedAt && Date.now() - startedAt > POLL_CEILING_MS) return false;
      return POLL_INTERVAL_MS;
    },
  });

  const status = query.data?.status;
  const timedOut =
    startedAt !== null &&
    Date.now() - startedAt > POLL_CEILING_MS &&
    !(status && TERMINAL_STATUSES.includes(status));

  return {
    job: query.data ?? null,
    error: query.error,
    isPolling:
      jobId !== null && !timedOut && !(status && TERMINAL_STATUSES.includes(status)),
    timedOut,
  };
}
