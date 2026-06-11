// Session persistence — chat turns and narration ledger stored together as
// one localStorage blob so they can only persist or reset as a unit.
import type { ChatTurn } from "./types";

export const STORAGE_KEY = "astrobot_session";

export interface SessionStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface Session {
  turns: ChatTurn[];
  narrated: string[];
}

const EMPTY: Session = { turns: [], narrated: [] };

export function saveSession(
  turns: ChatTurn[],
  narrated: string[],
  storage: SessionStorage = localStorage,
): void {
  storage.setItem(STORAGE_KEY, JSON.stringify({ turns, narrated }));
}

export function loadSession(storage: SessionStorage = localStorage): Session {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed?.turns) || !Array.isArray(parsed?.narrated)) {
      return EMPTY;
    }
    return { turns: parsed.turns as ChatTurn[], narrated: parsed.narrated as string[] };
  } catch {
    return EMPTY;
  }
}

export function clearSession(storage: SessionStorage = localStorage): void {
  storage.removeItem(STORAGE_KEY);
}
