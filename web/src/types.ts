export type Star = {
  name: string;
  mass: number;
};

export type OrbitalElements = {
  a: number;
  e: number;
  i: number;
  period?: number;
  M0?: number;
};

export type Trajectory = {
  planet: string;
  star: Star;
  elements: OrbitalElements;
};

export type ChatRole = "user" | "assistant";

export type ChatTurn = {
  role: ChatRole;
  content: string;
  trajectory?: Trajectory;
  tier?: 1 | 2 | 3;
  question?: string;
};

export type ChatResponse = {
  answer: string;
  tier: 1 | 2 | 3;
  similarity: number;
  fallback: boolean;
  sources: { question: string; similarity: number }[];
  tokens?: { input: number; output: number };
  cost_usd?: number;
  trajectory?: Trajectory;
};

export type LoginResponse = {
  token: string;
  expires_in: number;
};

export type StatsResponse = {
  daily_budget_usd: number;
  spent_usd: number;
  remaining_usd: number;
  llm_disabled: boolean;
  rate_limit: { requests_per_window: number; window_secs: number };
};

export type PlanetarySystem = {
  star: Star;
  planets: { name: string; elements: OrbitalElements }[];
};
