// Narration planner for view transitions. Pure logic, no React, no IO —
// the locked tests in narration.test.ts pin its behavior.
//
// The ledger (a Set of view keys narrated this session) is what stops the
// bot from re-touring a view the user has already visited: first entry
// narrates via the API, revisits get a short local line at zero token cost.
import type { View } from "./types";

export type NarrationPlan =
  | { kind: "narrate"; key: string; question: string; prefix: string }
  | { kind: "revisit"; key: string; line: string }
  | { kind: "none" };

export function viewKey(view: View): string {
  return view.level === "planet" ? `planet:${view.planet}` : view.level;
}

export function planNarration(
  view: View,
  narrated: ReadonlySet<string>,
  lastKey: string | null,
): NarrationPlan {
  const key = viewKey(view);
  // Same view re-fired (e.g. re-clicking the planet you are already on):
  // not a transition, say nothing.
  if (key === lastKey) return { kind: "none" };
  // The galaxy is the landing view — it never narrates.
  if (view.level === "galaxy") return { kind: "none" };

  if (narrated.has(key)) {
    const line =
      view.level === "system"
        ? "Re-entering the solar system view."
        : `Re-entering ${view.planet}.`;
    return { kind: "revisit", key, line };
  }

  if (view.level === "system") {
    return {
      kind: "narrate",
      key,
      question: "Give me a brief overview of our solar system.",
      prefix: "Entering the solar system view. ",
    };
  }
  return {
    kind: "narrate",
    key,
    question: `Describe the orbit of ${view.planet}.`,
    prefix: `Entering ${view.planet}. `,
  };
}
