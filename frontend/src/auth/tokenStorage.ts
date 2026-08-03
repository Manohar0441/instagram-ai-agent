/* Where the access + refresh tokens live.
 *
 * localStorage, not sessionStorage: losing the session on every tab close
 * would defeat the point of a long-lived refresh token. httpOnly cookies
 * aren't an option either — the backend issues bearer tokens, not a
 * Set-Cookie.
 *
 * The trade-off is XSS: any injected script can read these, including the
 * long-lived refresh token now. The mitigation is unchanged — nothing in
 * this app ever renders untrusted content as HTML: AI chat replies and
 * Instagram captions are rendered as text nodes.
 */

const TOKEN_KEY = "instalysis.access_token";
const REFRESH_TOKEN_KEY = "instalysis.refresh_token";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    // Private-browsing modes can throw on access rather than returning null.
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Non-fatal: the session simply won't survive a reload.
  }
}

function remove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Nothing useful to do.
  }
}

export const tokenStorage = {
  get(): string | null {
    return read(TOKEN_KEY);
  },

  set(token: string): void {
    write(TOKEN_KEY, token);
  },

  getRefresh(): string | null {
    return read(REFRESH_TOKEN_KEY);
  },

  setRefresh(token: string): void {
    write(REFRESH_TOKEN_KEY, token);
  },

  /** Sign-out always clears both — a lingering refresh token would silently
   * sign the next request back in. */
  clear(): void {
    remove(TOKEN_KEY);
    remove(REFRESH_TOKEN_KEY);
  },
};
