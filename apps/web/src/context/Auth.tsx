import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { api, type AuthResponse, type User } from "@/lib/api";
import { clearSession, readToken, readUser, saveSession } from "@/lib/session";
import type { Gender } from "@/lib/gender";

type AuthContextValue = {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: { email: string; password: string; display_name: string; role: string; gender?: Gender }) => Promise<void>;
  updateGender: (gender: Gender) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readToken());
  const [user, setUser] = useState<User | null>(() => readUser());

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      async updateGender(gender) {
        const updated = await api<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ gender }) }, token ?? undefined);
        saveSession(token!, updated);
        setUser(updated);
      },
      async login(email, password) {
        const res = await api<AuthResponse>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        saveSession(res.access_token, res.user);
        setToken(res.access_token);
        setUser(res.user);
      },
      async register(payload) {
        const res = await api<AuthResponse>("/auth/register", {
          method: "POST",
          body: JSON.stringify({ ...payload, age: 21 }),
        });
        saveSession(res.access_token, res.user);
        setToken(res.access_token);
        setUser(res.user);
      },
      logout() {
        clearSession();
        setToken(null);
        setUser(null);
      },
    }),
    [token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider ausente");
  return ctx;
}
