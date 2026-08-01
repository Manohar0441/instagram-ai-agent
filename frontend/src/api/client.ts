import { tokenStorage } from "../auth/tokenStorage";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Fired when the session itself has expired, so the app can bounce to login. */
export const SESSION_EXPIRED_EVENT = "instalysis:session-expired";

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

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
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
    tokenStorage.clear();
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    // Never retried: there is no refresh token, so a retry fails identically.
    throw new ApiError(401, "Your session has expired. Sign in again.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
