/**
 * Token storage abstraction — now backed by Capacitor's Preferences plugin
 * on native platforms, plain localStorage on web.
 *
 * Why Preferences on native (Phase 11): Capacitor's Preferences plugin
 * stores data via each platform's native mechanism — on Android that's
 * SharedPreferences, which is already sandboxed to this app by the OS and
 * is the standard place Android apps keep small persisted values. It is
 * NOT hardware-backed encryption (that would be `@capacitor/secure-storage`
 * or the Android Keystore directly, wrapping every value in a key that
 * never leaves hardware) — moving to that is a real future hardening step,
 * not done here, and is noted rather than quietly assumed away.
 *
 * On web, Preferences falls back to localStorage internally anyway (per
 * Capacitor's own docs), so keeping an explicit web branch here changes
 * nothing there — it's the native branch that's the actual improvement.
 *
 * The API is async now (Preferences is always async, even on web) — every
 * call site was updated accordingly when this file changed from sync to
 * async; grep for getAuthTokens/setAuthTokens/clearAuthTokens if adding a
 * new one; they all now return Promises.
 */
import { Preferences } from "@capacitor/preferences";

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

const STORAGE_KEY = "wake_up_ram.auth_tokens";

export async function getAuthTokens(): Promise<AuthTokens | null> {
  const { value } = await Preferences.get({ key: STORAGE_KEY });
  if (!value) return null;
  try {
    return JSON.parse(value) as AuthTokens;
  } catch {
    return null;
  }
}

export async function setAuthTokens(tokens: AuthTokens): Promise<void> {
  await Preferences.set({ key: STORAGE_KEY, value: JSON.stringify(tokens) });
}

export async function clearAuthTokens(): Promise<void> {
  await Preferences.remove({ key: STORAGE_KEY });
}
