import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import te from "./te.json";

// The initial language here is a safe fallback only. The real preferred
// language always comes from the user's stored profile (profile.preferred_language)
// and is applied via i18n.changeLanguage() once the profile loads — see
// src/app/App.tsx.
void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    te: { translation: te },
  },
  fallbackLng: "en",
  lng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
