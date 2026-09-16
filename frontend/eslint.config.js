// Flat config (ESLint 9+). `npm run lint` referenced this file since the
// project's inception but it never existed — `eslint .` was silently a
// no-op config error. Closing that gap here (Phase 13 pre-flight item).
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default tseslint.config(
  { ignores: ["dist", "android", "node_modules", "coverage"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: { window: "readonly", document: "readonly" },
    },
    settings: { react: { version: "detect" } },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // JSX runtime is automatic (tsconfig "jsx": "react-jsx") — no need to
      // import React in every file.
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      // Zero-hardcoding requirement (master doc section 22): catch the most
      // common accidental violation — a literal API base URL instead of the
      // configured one — without hand-auditing every PR for it.
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/^https?:\\/\\/(localhost|127\\.0\\.0\\.1)/]",
          message:
            "Do not hardcode a backend URL — use the configured VITE_API_BASE_URL (see src/services/apiClient.ts).",
        },
      ],
    },
  }
);
