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
  // Standish J2000 elements for placing planets in a common frame (real
  // positions). L0 = mean longitude at J2000 (deg); peri = longitude of
  // perihelion (deg). Optional: only the orrery uses them.
  L0?: number;
  peri?: number;
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

export type Planet = {
  name: string;
  elements: OrbitalElements;
  radiusKm: number;
  // Axial tilt / obliquity in degrees. > 90 means retrograde rotation
  // (Venus ~177, Uranus ~98 — rotates on its side).
  tiltDeg: number;
};

export type PlanetarySystem = {
  star: Star;
  planets: Planet[];
};

// Landing-page navigation state: galaxy map -> solar-system orrery -> single planet.
export type View =
  | { level: "galaxy" }
  | { level: "system" }
  | { level: "planet"; planet: string };
