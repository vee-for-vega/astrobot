// LOCKED — acceptance criteria for session persistence, frozen 2026-06-10.
// Owner of these criteria: architect (human). Changes go through a new
// architect task, never by the implementing agent.
//
// Criteria (architect-approved):
//   1. Chat turns and narration ledger persist together as ONE localStorage
//      blob — they cannot be stored, loaded, or cleared independently.
//   2. A fresh or empty store returns empty state: {turns:[], narrated:[]}.
//   3. Corrupted or missing data returns empty state (never throws).
//   4. clearSession removes all persisted state; the next load returns empty.
//   5. The module exports a STORAGE_KEY constant so the blob location is
//      testable and not an implementation secret.

import { describe, expect, test } from "vitest";
import { saveSession, loadSession, clearSession, STORAGE_KEY } from "./session";
import type { ChatTurn } from "./types";

// Minimal in-memory storage — avoids jsdom/browser dependency in vitest's
// default node environment.
function makeFakeStorage() {
  const data: Record<string, string> = {};
  return {
    getItem: (k: string) => data[k] ?? null,
    setItem: (k: string, v: string) => { data[k] = v; },
    removeItem: (k: string) => { delete data[k]; },
    _data: data,
  };
}

const TURNS: ChatTurn[] = [
  { role: "user", content: "What is the Kuiper Belt?" },
  { role: "assistant", content: "A region beyond Neptune's orbit.", tier: 2 },
];
const NARRATED = ["system", "planet:Mars"];

describe("loadSession with empty store", () => {
  test("returns empty turns and narrated when storage has nothing", () => {
    const store = makeFakeStorage();
    const s = loadSession(store);
    expect(s.turns).toEqual([]);
    expect(s.narrated).toEqual([]);
  });
});

describe("saveSession + loadSession round-trip", () => {
  test("round-trips turns and narrated together", () => {
    const store = makeFakeStorage();
    saveSession(TURNS, NARRATED, store);
    const s = loadSession(store);
    expect(s.turns).toEqual(TURNS);
    expect(s.narrated).toEqual(NARRATED);
  });

  test("uses exactly one storage key (atomicity invariant)", () => {
    const store = makeFakeStorage();
    saveSession(TURNS, NARRATED, store);
    expect(Object.keys(store._data)).toHaveLength(1);
    expect(Object.keys(store._data)[0]).toBe(STORAGE_KEY);
  });

  test("empty turns and empty narrated round-trip", () => {
    const store = makeFakeStorage();
    saveSession([], [], store);
    const s = loadSession(store);
    expect(s.turns).toEqual([]);
    expect(s.narrated).toEqual([]);
  });

  test("overwrites previous state on second save", () => {
    const store = makeFakeStorage();
    saveSession(TURNS, NARRATED, store);
    saveSession([], ["system"], store);
    const s = loadSession(store);
    expect(s.turns).toEqual([]);
    expect(s.narrated).toEqual(["system"]);
  });
});

describe("clearSession", () => {
  test("clears both turns and narrated atomically", () => {
    const store = makeFakeStorage();
    saveSession(TURNS, NARRATED, store);
    clearSession(store);
    const s = loadSession(store);
    expect(s.turns).toEqual([]);
    expect(s.narrated).toEqual([]);
  });

  test("storage key is absent after clear", () => {
    const store = makeFakeStorage();
    saveSession(TURNS, NARRATED, store);
    clearSession(store);
    expect(store._data[STORAGE_KEY]).toBeUndefined();
  });
});

describe("resilience to bad data", () => {
  test("corrupted JSON returns empty state without throwing", () => {
    const store = makeFakeStorage();
    store.setItem(STORAGE_KEY, "not json {{{{");
    expect(() => loadSession(store)).not.toThrow();
    const s = loadSession(store);
    expect(s.turns).toEqual([]);
    expect(s.narrated).toEqual([]);
  });

  test("blob missing narrated field returns empty state", () => {
    const store = makeFakeStorage();
    store.setItem(STORAGE_KEY, JSON.stringify({ turns: TURNS }));
    const s = loadSession(store);
    expect(s.turns).toEqual([]);
    expect(s.narrated).toEqual([]);
  });

  test("blob missing turns field returns empty state", () => {
    const store = makeFakeStorage();
    store.setItem(STORAGE_KEY, JSON.stringify({ narrated: NARRATED }));
    const s = loadSession(store);
    expect(s.turns).toEqual([]);
    expect(s.narrated).toEqual([]);
  });
});
