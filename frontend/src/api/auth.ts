import { apiFetch } from "./client";
import type { Token, UserResponse } from "./types";

export async function login(email: string, password: string): Promise<Token> {
  // The backend uses FastAPI's OAuth2PasswordRequestForm, so this endpoint
  // is application/x-www-form-urlencoded and names the identity field
  // "username". Instalysis authenticates by email, so the email goes there.
  // Callers never need to know any of this.
  const body = new URLSearchParams({ username: email, password });
  return apiFetch<Token>("/auth/login", { method: "POST", body });
}

export async function getCurrentUser(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/auth/me");
}
