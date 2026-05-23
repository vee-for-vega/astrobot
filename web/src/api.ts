import type { ChatResponse, ChatTurn, LoginResponse, StatsResponse } from "./types";

const TOKEN_KEY = "astrobot_token";
const EXPIRES_KEY = "astrobot_expires_at";

export type ApiError = {
  status: number;
  detail?: string;
  retryAfter?: number;
};

export class HttpError extends Error implements ApiError {
  status: number;
  detail?: string;
  retryAfter?: number;
  constructor(status: number, detail?: string, retryAfter?: number) {
    super(detail ?? `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
    this.retryAfter = retryAfter;
  }
}

export function loadToken(): string | null {
  const t = localStorage.getItem(TOKEN_KEY);
  const exp = parseInt(localStorage.getItem(EXPIRES_KEY) ?? "0", 10);
  if (!t || Date.now() > exp - 30_000) return null;
  return t;
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRES_KEY);
}

function storeToken(token: string, expiresInSecs: number): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EXPIRES_KEY, String(Date.now() + expiresInSecs * 1000));
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = loadToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string> | undefined) ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    const retryAfter = res.headers.get("Retry-After");
    let detail: string | undefined;
    try {
      const body = (await res.json()) as { detail?: string };
      detail = body.detail;
    } catch {
      // body not JSON
    }
    throw new HttpError(res.status, detail, retryAfter ? parseInt(retryAfter, 10) : undefined);
  }
  return (await res.json()) as T;
}

export async function login(password: string): Promise<void> {
  const body = await request<LoginResponse>("/api/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
  storeToken(body.token, body.expires_in);
}

export async function chat(question: string, history: ChatTurn[]): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      question,
      history: history.map((t) => ({ role: t.role, content: t.content })),
    }),
  });
}

export async function stats(): Promise<StatsResponse> {
  return request<StatsResponse>("/api/stats");
}

export function isAuthenticated(): boolean {
  return loadToken() !== null;
}
