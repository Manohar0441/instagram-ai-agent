import { apiFetch } from "./client";
import type {
  AIHealthResponse,
  AIKeyStatusResponse,
  ChatResponse,
} from "./types";

export async function chat(message: string): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/ai/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function getAIHealth(): Promise<AIHealthResponse> {
  return apiFetch<AIHealthResponse>("/ai/health");
}

export async function getKeyStatus(): Promise<AIKeyStatusResponse> {
  return apiFetch<AIKeyStatusResponse>("/ai/key");
}

export async function setKey(apiKey: string): Promise<AIKeyStatusResponse> {
  return apiFetch<AIKeyStatusResponse>("/ai/key", {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function clearKey(): Promise<void> {
  return apiFetch<void>("/ai/key", { method: "DELETE" });
}
