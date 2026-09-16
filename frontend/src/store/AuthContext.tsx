import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiClient } from "../services/apiClient";
import { setAuthTokens, clearAuthTokens, getAuthTokens } from "../services/tokenStorage";
import type { TokenPair, User } from "../types";

interface AuthContextValue {
  user: User | null;
  status: "loading" | "authenticated" | "unauthenticated";
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshCurrentUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  async function refreshCurrentUser() {
    try {
      const current = await apiClient.get<User>("/api/v1/users/me");
      setUser(current);
      setStatus("authenticated");
    } catch {
      setUser(null);
      setStatus("unauthenticated");
    }
  }

  useEffect(() => {
    void (async () => {
      if (await getAuthTokens()) {
        void refreshCurrentUser();
      } else {
        setStatus("unauthenticated");
      }
    })();
  }, []);

  async function login(email: string, password: string) {
    const tokens = await apiClient.post<TokenPair>(
      "/api/v1/auth/login",
      { email, password },
      { auth: false }
    );
    await setAuthTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
    await refreshCurrentUser();
  }

  async function register(email: string, password: string) {
    await apiClient.post("/api/v1/auth/register", { email, password }, { auth: false });
    await login(email, password);
  }

  async function logout() {
    await clearAuthTokens();
    setUser(null);
    setStatus("unauthenticated");
  }

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout, refreshCurrentUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
