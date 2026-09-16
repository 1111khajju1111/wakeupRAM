import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { colorTokens, type ThemeMode } from "./tokens";

interface ThemeContextValue {
  mode: ThemeMode;
  resolvedMode: "light" | "dark";
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function resolveSystemPreference(): "light" | "dark" {
  if (typeof window === "undefined" || !window.matchMedia) return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

interface ThemeProviderProps {
  children: ReactNode;
  /** Comes from the user's stored profile.theme_preference — never hardcoded. */
  initialMode?: ThemeMode;
}

export function ThemeProvider({ children, initialMode = "system" }: ThemeProviderProps) {
  const [mode, setMode] = useState<ThemeMode>(initialMode);
  const [systemPref, setSystemPref] = useState<"light" | "dark">(resolveSystemPreference());

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = (event: MediaQueryListEvent) => setSystemPref(event.matches ? "dark" : "light");
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, []);

  const resolvedMode = mode === "system" ? systemPref : mode;

  useEffect(() => {
    const palette = colorTokens[resolvedMode];
    const root = document.documentElement;
    Object.entries(palette).forEach(([key, value]) => {
      root.style.setProperty(`--color-${key}`, value);
    });
    root.dataset.theme = resolvedMode;
  }, [resolvedMode]);

  const value = useMemo(() => ({ mode, resolvedMode, setMode }), [mode, resolvedMode]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
}
