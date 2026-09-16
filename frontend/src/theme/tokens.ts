/**
 * Centralized design tokens.
 *
 * The brief specifies an original minimalist technical interface inspired by
 * monochrome phone aesthetics: black/white dominant, thin borders, large
 * numerical typography, dot-grid/glyph motifs, restrained motion. Every
 * screen must consume these tokens rather than hardcoding raw values, so a
 * future palette/theme change happens in exactly one place.
 */

export const colorTokens = {
  light: {
    background: "#FAFAF9",
    surface: "#FFFFFF",
    ink: "#0A0A0A",
    inkMuted: "#5C5C5C",
    border: "#DCDCDA",
    accent: "#0A0A0A", // monochrome-first: accent is ink itself, not a color pop
    danger: "#B3261E",
    success: "#1E6B4F",
  },
  dark: {
    background: "#0A0A0A",
    surface: "#141414",
    ink: "#F5F5F4",
    inkMuted: "#9A9A98",
    border: "#2A2A2A",
    accent: "#F5F5F4",
    danger: "#E5625A",
    success: "#4CAF88",
  },
} as const;

export const typeTokens = {
  // Technical/monospace for numerals, timers, data — display for large moments.
  fontDisplay: '"Neue Montreal", "Inter", system-ui, sans-serif',
  fontMono: '"JetBrains Mono", "IBM Plex Mono", monospace',
  scale: {
    xs: "0.75rem",
    sm: "0.875rem",
    base: "1rem",
    lg: "1.25rem",
    xl: "1.75rem",
    "2xl": "2.5rem",
    display: "4rem", // large numerical typography (home screen clock, countdowns)
  },
} as const;

export const spaceTokens = {
  xs: "4px",
  sm: "8px",
  md: "16px",
  lg: "24px",
  xl: "40px",
  "2xl": "64px",
} as const;

export const radiusTokens = {
  none: "0px",
  sm: "2px", // thin, technical — not the rounded SaaS-card look
  md: "6px",
};

export const borderTokens = {
  hairline: "1px solid",
};

export const motionTokens = {
  // Restrained: one deliberate transition duration, used sparingly.
  duration: "160ms",
  easing: "cubic-bezier(0.4, 0, 0.2, 1)",
};

export type ThemeMode = "light" | "dark" | "system";
