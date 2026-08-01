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
import { SESSION_EXPIRED_EVENT } from "../api/client";
import { millisUntilExpiry } from "../lib/jwt";
import { tokenStorage } from "./tokenStorage";

interface AuthContextValue {
  token: string | null;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Warn this long before the token lapses, so in-progress work can be saved. */
const EXPIRY_GRACE_MS = 30_000;

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
      setToken(result.access_token);
      queryClient.clear();
    },
    [queryClient],
  );

  // A 401 from anywhere in the app lands here.
  useEffect(() => {
    const handleExpiry = () => signOut();
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpiry);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpiry);
  }, [signOut]);

  // Sign out proactively rather than waiting for the next request to fail.
  // Tokens last 30 minutes and there is no refresh flow, so this is the
  // difference between a clean redirect and losing a half-typed message.
  useEffect(() => {
    if (!token) return;

    const remaining = millisUntilExpiry(token);
    if (remaining <= EXPIRY_GRACE_MS) {
      signOut();
      return;
    }

    const timer = window.setTimeout(signOut, remaining - EXPIRY_GRACE_MS);
    return () => window.clearTimeout(timer);
  }, [token, signOut]);

  const value = useMemo(
    () => ({ token, isAuthenticated: token !== null, signIn, signOut }),
    [token, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
