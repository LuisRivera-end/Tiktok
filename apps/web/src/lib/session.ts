import type { User } from "@/lib/api";

const TOKEN = "veta.token";
const USER = "veta.user";

export function saveSession(token: string, user: User): void {
  localStorage.setItem(TOKEN, token);
  localStorage.setItem(USER, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN);
  localStorage.removeItem(USER);
}

export function readToken(): string | null {
  return localStorage.getItem(TOKEN);
}

export function readUser(): User | null {
  const raw = localStorage.getItem(USER);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}
