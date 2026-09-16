import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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

vi.mock("../services/apiClient", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from "../services/apiClient";
import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { user, status, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="email">{user?.email ?? "none"}</span>
      <button onClick={() => login("ram@example.com", "password123")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    store.clear();
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.post).mockReset();
  });

  it("starts unauthenticated when no tokens are stored", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));
    expect(screen.getByTestId("email")).toHaveTextContent("none");
  });

  it("logs in, stores tokens, and loads the current user", async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      access_token: "access-1",
      refresh_token: "refresh-1",
    });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ id: "u1", email: "ram@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));

    await act(async () => {
      await userEvent.click(screen.getByText("login"));
    });

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("email")).toHaveTextContent("ram@example.com");
    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      { email: "ram@example.com", password: "password123" },
      { auth: false }
    );
  });

  it("logout clears the user and returns to unauthenticated", async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      access_token: "access-1",
      refresh_token: "refresh-1",
    });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ id: "u1", email: "ram@example.com" });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));
    await act(async () => {
      await userEvent.click(screen.getByText("login"));
    });
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    await act(async () => {
      await userEvent.click(screen.getByText("logout"));
    });

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));
    expect(screen.getByTestId("email")).toHaveTextContent("none");
  });
});
