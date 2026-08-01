/** Read the `exp` claim without pulling in a JWT library.
 *
 * This is not verification — the signature is the server's business. It
 * exists only so the UI can warn before a token lapses instead of letting
 * the user discover it through a failed request.
 */
export function getExpiry(token: string): number | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;

    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(atob(normalized));

    return typeof claims.exp === "number" ? claims.exp : null;
  } catch {
    return null;
  }
}

/** Milliseconds until the token expires; 0 if already expired or unreadable. */
export function millisUntilExpiry(token: string): number {
  const exp = getExpiry(token);
  if (exp === null) return 0;
  return Math.max(0, exp * 1000 - Date.now());
}
