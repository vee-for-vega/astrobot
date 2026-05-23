import type { OrbitalElements, Star } from "../types";
import { derivePeriodDays } from "../kepler";

type Props = {
  planet: string;
  star: Star;
  elements: OrbitalElements;
};

export default function PlanetInfo({ planet, star, elements }: Props) {
  const period = elements.period ?? derivePeriodDays(elements.a, star.mass);
  const perihelion = elements.a * (1 - elements.e);
  const aphelion = elements.a * (1 + elements.e);
  const periodLabel =
    period < 365 ? `${period.toFixed(1)} d` : `${(period / 365.25).toFixed(2)} yr`;

  const rows: [string, string][] = [
    ["planet", planet],
    ["star", star.name],
    ["a", `${elements.a.toFixed(3)} AU`],
    ["e", elements.e.toFixed(4)],
    ["i", `${elements.i.toFixed(2)}°`],
    ["period", periodLabel],
    ["perihelion", `${perihelion.toFixed(3)} AU`],
    ["aphelion", `${aphelion.toFixed(3)} AU`],
  ];

  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-xs text-neutral-700 sm:grid-cols-4">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between border-b border-neutral-200 py-1">
          <dt className="text-neutral-500">{k}</dt>
          <dd className="text-neutral-900">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
