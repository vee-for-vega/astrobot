import type { OrbitalElements, Star } from "./types";

const DEG = Math.PI / 180;

export function solveKepler(M: number, e: number): number {
  let E = e < 0.8 ? M : Math.PI;
  for (let i = 0; i < 30; i++) {
    const dE = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    E -= dE;
    if (Math.abs(dE) < 1e-10) break;
  }
  return E;
}

export function derivePeriodDays(a: number, starMass: number): number {
  return 365.25 * Math.sqrt((a * a * a) / starMass);
}

export function positionAt(
  elements: OrbitalElements,
  star: Star,
  tDays: number,
): { x: number; y: number } {
  const period = elements.period ?? derivePeriodDays(elements.a, star.mass);
  const M0 = (elements.M0 ?? 0) * DEG;
  const M = M0 + (2 * Math.PI * tDays) / period;
  const e = elements.e;
  const E = solveKepler(((M % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI), e);
  const a = elements.a;
  const x = a * (Math.cos(E) - e);
  const y = a * Math.sqrt(1 - e * e) * Math.sin(E);
  return { x, y };
}

export function ellipsePath(a: number, e: number, samples = 256): string {
  const b = a * Math.sqrt(1 - e * e);
  const cx = -a * e;
  let d = "";
  for (let i = 0; i <= samples; i++) {
    const t = (i / samples) * 2 * Math.PI;
    const x = cx + a * Math.cos(t);
    const y = b * Math.sin(t);
    d += (i === 0 ? "M" : "L") + x.toFixed(4) + "," + y.toFixed(4);
  }
  return d + "Z";
}
