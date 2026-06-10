// LOCKED — acceptance criteria for narration dedupe, frozen 2026-06-10.
// Owner of these criteria: architect (human). Changes go through a new
// architect task, never by the implementing agent.
//
// Criteria (architect-approved):
//   1. First entry into a view narrates it via the API (tour-guide mode).
//   2. Re-entering an already-narrated view costs ZERO API calls — the bot
//      prints a short local "re-entering" line instead.
//   3. Each planet is tracked separately; the galaxy landing never narrates.
//   4. Re-firing the same view (not a transition) says nothing at all.
//   5. A view whose narration was skipped (e.g. mid-typewriter transition)
//      is NOT marked narrated — it gets the full tour on the next entry.
//      (The component owns recording; the planner must keep re-proposing
//      "narrate" until the key actually lands in the ledger.)

import { describe, expect, test } from "vitest";
import { planNarration, viewKey } from "./narration";
import type { View } from "./types";

const GALAXY: View = { level: "galaxy" };
const SYSTEM: View = { level: "system" };
const MARS: View = { level: "planet", planet: "Mars" };
const VENUS: View = { level: "planet", planet: "Venus" };

describe("viewKey", () => {
  test("keys distinguish levels and individual planets", () => {
    expect(viewKey(GALAXY)).toBe("galaxy");
    expect(viewKey(SYSTEM)).toBe("system");
    expect(viewKey(MARS)).toBe("planet:Mars");
    expect(viewKey(VENUS)).toBe("planet:Venus");
  });
});

describe("first visits narrate via the API", () => {
  test("entering the system for the first time narrates the solar system", () => {
    const plan = planNarration(SYSTEM, new Set(), "galaxy");
    expect(plan.kind).toBe("narrate");
    if (plan.kind !== "narrate") return;
    expect(plan.key).toBe("system");
    expect(plan.question.toLowerCase()).toContain("solar system");
  });

  test("entering a planet for the first time narrates that planet's orbit", () => {
    const plan = planNarration(MARS, new Set(["system"]), "system");
    expect(plan.kind).toBe("narrate");
    if (plan.kind !== "narrate") return;
    expect(plan.key).toBe("planet:Mars");
    expect(plan.question).toContain("Mars");
  });
});

describe("revisits are local and free", () => {
  test("returning to the system after a planet trip does NOT re-narrate", () => {
    const narrated = new Set(["system", "planet:Mars"]);
    const plan = planNarration(SYSTEM, narrated, "planet:Mars");
    expect(plan.kind).toBe("revisit");
    if (plan.kind !== "revisit") return;
    expect(plan.line.toLowerCase()).toContain("re-entering");
    // A revisit plan carries no API question — zero tokens by construction.
    expect("question" in plan).toBe(false);
  });

  test("returning to an already-toured planet gets a local line only", () => {
    const narrated = new Set(["system", "planet:Mars"]);
    const plan = planNarration(MARS, narrated, "system");
    expect(plan.kind).toBe("revisit");
    if (plan.kind !== "revisit") return;
    expect(plan.line).toContain("Mars");
  });

  test("each planet narrates once independently", () => {
    const narrated = new Set(["system", "planet:Mars"]);
    const venus = planNarration(VENUS, narrated, "system");
    expect(venus.kind).toBe("narrate"); // Venus not toured yet
    const mars = planNarration(MARS, narrated, "system");
    expect(mars.kind).toBe("revisit"); // Mars already toured
  });
});

describe("silent cases", () => {
  test("the galaxy landing never narrates, visited or not", () => {
    expect(planNarration(GALAXY, new Set(), "system").kind).toBe("none");
    expect(planNarration(GALAXY, new Set(["galaxy"]), "planet:Mars").kind).toBe("none");
  });

  test("re-firing the same view is not a transition and says nothing", () => {
    const narrated = new Set(["system", "planet:Mars"]);
    expect(planNarration(MARS, narrated, "planet:Mars").kind).toBe("none");
    expect(planNarration(SYSTEM, new Set(), "system").kind).toBe("none");
  });
});

describe("skipped narration is not lost", () => {
  test("a key absent from the ledger keeps proposing narrate on every entry", () => {
    // Simulates: user flipped views mid-typewriter, component skipped the
    // narration and did NOT record the key. Next entry must tour in full.
    const narrated = new Set(["planet:Mars"]); // system never actually narrated
    const again = planNarration(SYSTEM, narrated, "planet:Mars");
    expect(again.kind).toBe("narrate");
  });
});
