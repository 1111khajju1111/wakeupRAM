import { describe, expect, it, vi, beforeEach } from "vitest";

// Capacitor's Preferences plugin has no browser-DOM implementation to run
// against in jsdom, so it's mocked with a simple in-memory Map standing in
// for native storage. This tests tokenStorage's own contract (round-trip,
// null-on-missing, and — importantly — that clearing it actually removes
// the value rather than leaving stale tokens behind).
const store = new Map<string, string>();

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn(async ({ key }: { key: string }) => ({ value: store.get(key) ?? null })),
    set: vi.fn(async ({ key, value }: { key: string; value: string }) => {
      store.set(key, value);
    }),
    remove: vi.fn(async ({ key }: { key: string }) => {
      store.delete(key);
    }),
  },
}));

import { getAuthTokens, setAuthTokens, clearAuthTokens } from "./tokenStorage";

describe("tokenStorage", () => {
  beforeEach(() => {
    store.clear();
  });

  it("returns null when nothing has been stored yet", async () => {
    await expect(getAuthTokens()).resolves.toBeNull();
  });

  it("round-trips a stored token pair", async () => {
    await setAuthTokens({ accessToken: "access-123", refreshToken: "refresh-456" });
    await expect(getAuthTokens()).resolves.toEqual({
      accessToken: "access-123",
      refreshToken: "refresh-456",
    });
  });

  it("clears tokens so a logged-out session never reuses a stale token", async () => {
    await setAuthTokens({ accessToken: "access-123", refreshToken: "refresh-456" });
    await clearAuthTokens();
    await expect(getAuthTokens()).resolves.toBeNull();
  });

  it("treats corrupted stored JSON as absent rather than throwing", async () => {
    store.set("wake_up_ram.auth_tokens", "{not-valid-json");
    await expect(getAuthTokens()).resolves.toBeNull();
  });
});
