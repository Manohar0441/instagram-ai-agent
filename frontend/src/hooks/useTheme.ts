import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "instalysis.theme";

function readStored(): Theme {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

/**
 * Light/dark/system theme, persisted across sessions.
 *
 * "system" removes the data-theme attribute entirely rather than resolving
 * to a concrete value, so the CSS `prefers-color-scheme` query stays in
 * charge and the theme keeps following the OS if it changes mid-session.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readStored);

  useEffect(() => {
    const root = document.documentElement;

    if (theme === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", theme);
    }

    try {
      if (theme === "system") {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, theme);
      }
    } catch {
      // Non-fatal: the theme just won't survive a reload.
    }
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      if (current === "system") {
        // First explicit choice: flip away from whatever the OS is doing.
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        return prefersDark ? "light" : "dark";
      }
      return current === "dark" ? "light" : "dark";
    });
  }, []);

  const isDark =
    theme === "dark" ||
    (theme === "system" &&
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);

  return { theme, isDark, setTheme, toggle };
}
