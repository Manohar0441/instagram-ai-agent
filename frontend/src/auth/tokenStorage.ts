/* Where the bearer token lives.
 *
 * localStorage, not sessionStorage: the token expires after 30 minutes and
 * there is no refresh flow, so losing the session on every tab close would
 * mean re-authenticating constantly. httpOnly cookies aren't an option
 * either — the backend issues a bearer token, not a Set-Cookie.
 *
 * The trade-off is XSS: any injected script can read this. The mitigation
 * is that nothing in this app ever renders untrusted content as HTML —
 * AI chat replies and Instagram captions are rendered as text nodes.
 */

const TOKEN_KEY = "instalysis.access_token";

export const tokenStorage = {
  get(): string | null {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      // Private-browsing modes can throw on access rather than returning null.
      return null;
    }
  },

  set(token: string): void {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // Non-fatal: the session simply won't survive a reload.
    }
  },

  clear(): void {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch {
      // Nothing useful to do.
    }
  },
};
