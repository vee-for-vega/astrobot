import type { ChatResponse, ChatTurn, StatsResponse } from "./types";

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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string> | undefined) ?? {}),
  };
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
