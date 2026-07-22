import { useEffect, useState } from "react";

const STORAGE_KEY = "clario-theme";

function preferredTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/** Tracks the active theme, applies it to <html data-theme>, and persists it. */
export function useTheme() {
  const [theme, setTheme] = useState(preferredTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return [theme, setTheme];
}

export default function ThemeToggle({ theme, onChange }) {
  const isLight = theme === "light";
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => onChange(isLight ? "dark" : "light")}
      aria-label={isLight ? "Switch to dark mode" : "Switch to light mode"}
      title={isLight ? "Switch to dark mode" : "Switch to light mode"}
    >
      {isLight ? <MoonIcon /> : <SunIcon />}
    </button>
  );
}

function SunIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.8" />
      <g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M12 2.5v2.4M12 19.1v2.4M21.5 12h-2.4M4.9 12H2.5" />
        <path d="M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7M18.4 18.4l-1.7-1.7M7.3 7.3L5.6 5.6" />
      </g>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M20.5 14.7A8.6 8.6 0 1 1 9.3 3.5a7 7 0 0 0 11.2 11.2Z"
        fill="currentColor"
      />
    </svg>
  );
}
