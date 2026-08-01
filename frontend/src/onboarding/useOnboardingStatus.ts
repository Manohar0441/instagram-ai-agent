import { useQuery } from "@tanstack/react-query";

import { getKeyStatus } from "../api/ai";
import { ApiError } from "../api/client";
import { getProfile } from "../api/instagram";
import type { InstagramAccountResponse } from "../api/types";

export const AI_KEY_QUERY = ["ai-key-status"] as const;
export const INSTAGRAM_PROFILE_QUERY = ["instagram-profile"] as const;

/** Distinguishes "not connected" from "connected but the token lapsed". */
type ProfileState = InstagramAccountResponse | null | "expired";

export function useOnboardingStatus() {
  const aiKey = useQuery({
    queryKey: AI_KEY_QUERY,
    queryFn: getKeyStatus,
    staleTime: Infinity,
  });

  const instagram = useQuery<ProfileState>({
    queryKey: INSTAGRAM_PROFILE_QUERY,
    // GET /instagram/profile refreshes from the Graph API on every call, so
    // it is cached for the session and invalidated explicitly after a
    // connect or disconnect rather than refetched on every navigation.
    staleTime: Infinity,
    retry: false,
    queryFn: async () => {
      try {
        return await getProfile();
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        // A 401 here means the *Instagram* token lapsed, not the session —
        // apiFetch already proved that by not firing the expiry event.
        if (error instanceof ApiError && error.status === 401) return "expired";
        throw error;
      }
    },
  });

  const profile = instagram.data;
  const account: InstagramAccountResponse | null =
    profile && profile !== "expired" ? profile : null;

  return {
    isLoading: aiKey.isLoading || instagram.isLoading,
    isError: aiKey.isError || instagram.isError,
    aiConfigured: aiKey.data?.configured ?? false,
    aiStatus: aiKey.data,
    instagramConnected: account !== null,
    instagramTokenExpired: profile === "expired",
    account,
  };
}
