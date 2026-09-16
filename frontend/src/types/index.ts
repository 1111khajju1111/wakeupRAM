export interface Profile {
  display_name: string | null;
  preferred_language: "en" | "te";
  theme_preference: "light" | "dark" | "system";
  timezone: string;
  onboarding_completed: boolean;
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  profile: Profile | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
