import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as authApi from "../api/auth";
import { refreshAccessToken, SESSION_EXPIRED_EVENT, TOKEN_REFRESHED_EVENT } from "../api/client";
import { millisUntilExpiry } from "../lib/jwt";
import { tokenStorage } from "./tokenStorage";

interface AuthContextValue {
  token: string | null;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Refresh this long before the access token lapses, so it never actually
 * reaches the server expired under normal use. */
const REFRESH_GRACE_MS = 30_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => tokenStorage.get());
  const queryClient = useQueryClient();

  const signOut = useCallback(() => {
    tokenStorage.clear();
    setToken(null);
    // Onboarding and analytics data are per-user; leaving them cached would
    // show the previous user's figures to whoever signs in next.
    queryClient.clear();
  }, [queryClient]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const result = await authApi.login(email, password);
      tokenStorage.set(result.access_token);
      tokenStorage.setRefresh(result.refresh_token);
      setToken(result.access_token);
      queryClient.clear();
    },
    [queryClient],
  );

  // A 401 that survived apiFetch's own silent-refresh attempt (the refresh
  // token itself is gone or expired) lands here.
  useEffect(() => {
    const handleExpiry = () => signOut();
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpiry);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpiry);
  }, [signOut]);

  // apiFetch can refresh the access token on its own (reacting to a 401
  // from some unrelated request) without this component ever knowing -
  // this is what keeps `token` (and the proactive-refresh timer below,
  // since it depends on `token`) in sync with whatever it just wrote to
  // storage, instead of still counting down against the now-stale one.
  useEffect(() => {
    const handleRefreshed = (event: Event) => {
      setToken((event as CustomEvent<string>).detail);
    };
    window.addEventListener(TOKEN_REFRESHED_EVENT, handleRefreshed);
    return () => window.removeEventListener(TOKEN_REFRESHED_EVENT, handleRefreshed);
  }, []);

  // Refresh proactively, before the access token actually lapses, so a
  // request in flight right at that boundary never has to wait on it - the
  // refresh token (weeks, see JWT_REFRESH_TOKEN_EXPIRE_DAYS) is what keeps
  // this going indefinitely without ever prompting for credentials again,
  // as long as the app is opened at least once within that window. Only
  // signs out if the refresh itself fails (refresh token gone or expired).
  useEffect(() => {
    if (!token) return;

    const attemptRefresh = async () => {
      // refreshAccessToken already updates storage and fires
      // TOKEN_REFRESHED_EVENT (which the listener above turns into
      // setToken) on success - only a genuine failure needs handling here.
      const newToken = await refreshAccessToken();
      if (!newToken) signOut();
    };

    const remaining = millisUntilExpiry(token);
    if (remaining <= REFRESH_GRACE_MS) {
      void attemptRefresh();
      return;
    }

    const timer = window.setTimeout(attemptRefresh, remaining - REFRESH_GRACE_MS);
    return () => window.clearTimeout(timer);
  }, [token, signOut]);

  const value = useMemo(
    () => ({ token, isAuthenticated: token !== null, signIn, signOut }),
    [token, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
