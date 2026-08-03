import { tokenStorage } from "../auth/tokenStorage";
import type { Token } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Fired when the session itself has expired (refresh also failed), so the
 * app can bounce to login. */
export const SESSION_EXPIRED_EVENT = "instalysis:session-expired";
/** Fired whenever apiFetch silently refreshes the access token, so
 * AuthContext's React state (and its own expiry timer) stay in sync with
 * whatever client.ts just wrote to storage. */
export const TOKEN_REFRESHED_EVENT = "instalysis:token-refreshed";

export class ApiError extends Error {
  // Declared as fields rather than constructor parameter properties: the
  // project builds with erasableSyntaxOnly, which forbids the shorthand.
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Whether a 401 came from the auth layer rather than a lapsed Instagram token.
 *
 * The backend returns 401 for two unrelated reasons: an expired session, and
 * an expired Instagram access token (InstagramTokenExpiredError). Logging the
 * user out because their *Instagram* connection lapsed would be a bad bug.
 * The two are distinguishable — the auth dependency sets WWW-Authenticate,
 * the Instagram path does not.
 */
function isSessionExpiry(response: Response): boolean {
  if (response.status !== 401) return false;
  return (response.headers.get("www-authenticate") ?? "").includes("Bearer");
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;

    if (typeof detail === "string") return detail;
    // FastAPI validation errors arrive as a list of {loc, msg, type}.
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item?.msg).filter(Boolean).join("; ");
    }
  } catch {
    // Fall through to the generic message below.
  }
  return `Request failed with status ${response.status}.`;
}

// In-flight refresh, shared across every caller that hits an expired access
// token around the same time - without this, five concurrent requests
// failing together would fire five separate refresh calls, each racing to
// overwrite the stored token pair with its own (each individually valid,
// but only the last write wins, and the other four responses trigger a
// pointless second retry each).
let refreshPromise: Promise<string | null> | null = null;

/** Exchange the stored refresh token for a new access + refresh pair.
 *
 * Exported so AuthContext can call this directly for its proactive,
 * before-expiry refresh - apiFetch below uses the same function for its
 * own reactive, after-a-401 refresh, so both paths always go through the
 * same dedup/storage logic no matter which one fires first.
 */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = tokenStorage.getRefresh();
    if (!refreshToken) return null;

    try {
      // Not routed through apiFetch: this IS apiFetch's own recovery path
      // for an expired access token, so calling back into it would recurse.
      const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) return null;

      const result = (await response.json()) as Token;
      tokenStorage.set(result.access_token);
      tokenStorage.setRefresh(result.refresh_token);
      window.dispatchEvent(
        new CustomEvent(TOKEN_REFRESHED_EVENT, { detail: result.access_token }),
      );
      return result.access_token;
    } catch {
      return null;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

/** Runs a request through auth headers, session-expiry retry, and error
 * translation, returning the raw Response. Shared by apiFetch (JSON body)
 * and apiFetchFile (binary/file download), so both benefit from the same
 * silent-refresh behavior. */
async function authorizedFetch(
  path: string,
  init: RequestInit = {},
  _isRetry = false,
): Promise<Response> {
  const token = tokenStorage.get();
  const isForm = init.body instanceof URLSearchParams;

  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      ...(init.body && !isForm ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (isSessionExpiry(response)) {
    // One silent retry with a refreshed token before giving up - this is
    // what makes a 30-minute access token invisible to the user as long as
    // the refresh token (weeks) is still valid.
    if (!_isRetry) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return authorizedFetch(path, init, true);
      }
    }
    tokenStorage.clear();
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    throw new ApiError(401, "Your session has expired. Sign in again.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }

  return response;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authorizedFetch(path, init);

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function filenameFromContentDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const match = header.match(/filename="?([^";]+)"?/);
  return match ? match[1] : fallback;
}

/** Fetches a file (e.g. a .ics download) through the same auth/retry path as apiFetch. */
export async function apiFetchFile(
  path: string,
  fallbackFilename: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await authorizedFetch(path);
  const filename = filenameFromContentDisposition(
    response.headers.get("content-disposition"),
    fallbackFilename,
  );
  return { blob: await response.blob(), filename };
}
