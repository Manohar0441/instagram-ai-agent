import { apiFetch } from "./client";
import type {
  InsightsResponse,
  InstagramAccountResponse,
  InstagramConnectResponse,
  InstagramMediaResponse,
} from "./types";

export async function getConnectUrl(): Promise<InstagramConnectResponse> {
  return apiFetch<InstagramConnectResponse>("/instagram/connect");
}

export async function getProfile(): Promise<InstagramAccountResponse> {
  return apiFetch<InstagramAccountResponse>("/instagram/profile");
}

/**
 * Fetch posts from the Graph API and persist them.
 *
 * This WRITES: it pulls fresh media from Meta into the database rather than
 * reading what is already stored. Treat it as an explicit sync action, never
 * as a page-load fetch.
 */
export async function syncMedia(limit = 25): Promise<InstagramMediaResponse[]> {
  return apiFetch<InstagramMediaResponse[]>(`/instagram/media?limit=${limit}`);
}

/**
 * Fetch account and per-post insights from the Graph API and persist them.
 *
 * Also a write, and it requires syncMedia to have run first — insights are
 * keyed to stored media.
 */
export async function syncInsights(): Promise<InsightsResponse> {
  return apiFetch<InsightsResponse>("/instagram/insights");
}

export async function disconnect(): Promise<void> {
  return apiFetch<void>("/instagram/disconnect", { method: "DELETE" });
}
