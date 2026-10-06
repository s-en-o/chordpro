import { useEffect, useState } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "chordpro-theme";

/**
 * Read the saved theme, falling back to the OS preference. The storage read is
 * guarded so a blocked localStorage (private mode, etc.) still works.
 */
function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") {
      return saved;
    }
  } catch {
    // Ignore storage access errors; fall through to the OS preference.
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/**
 * Apply a theme to <html>. When ``persist`` is true the choice is saved, so
 * the OS default is only remembered once the user actually picks a theme.
 */
function applyTheme(theme: Theme, persist: boolean): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  if (persist) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Ignore storage write errors; the class is still applied.
    }
  }
}

/**
 * A small light/dark toggle. The initial theme follows the OS setting; the
 * choice is remembered only once the user picks one.
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  // Sync <html> with the current theme; persist only on an explicit change
  // (not on the very first render, which just reflects the OS default).
  useEffect(() => {
    applyTheme(theme, false);
  }, [theme]);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next, true);
    setTheme(next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
      aria-label="Toggle dark mode"
      aria-pressed={theme === "dark"}
    >
      {theme === "dark" ? "☀︎ Light" : "☾ Dark"}
    </button>
  );
}
