import { useEffect, useRef, useState } from "react";
import type { OrbitalElements, Star } from "../types";
import { ellipsePath, positionAt } from "../kepler";

type Props = {
  star: Star;
  elements: OrbitalElements;
  secondsPerOrbit?: number;
};

export default function TopView({ star, elements, secondsPerOrbit = 12 }: Props) {
  const [tDays, setTDays] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    const period = elements.period ?? 365.25;
    const tick = (now: number) => {
      if (startRef.current === null) startRef.current = now;
      const elapsed = (now - startRef.current) / 1000;
      setTDays((elapsed / secondsPerOrbit) * period);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      startRef.current = null;
    };
  }, [elements.period, secondsPerOrbit]);

  const a = elements.a;
  const e = elements.e;
  const path = ellipsePath(a, e);
  const pos = positionAt(elements, star, tDays);
  const viewSize = a * 2.4;

  return (
    <svg
      viewBox={`${-viewSize / 2} ${-viewSize / 2} ${viewSize} ${viewSize}`}
      className="block h-full w-full"
      aria-label="top view of orbit"
    >
      <path
        d={path}
        fill="none"
        stroke="black"
        strokeWidth={a * 0.006}
        strokeDasharray={`${a * 0.025} ${a * 0.025}`}
      />
      <circle cx={0} cy={0} r={a * 0.06} fill="white" stroke="black" strokeWidth={a * 0.008} />
      <circle
        cx={pos.x}
        cy={pos.y}
        r={a * 0.035}
        fill="white"
        stroke="black"
        strokeWidth={a * 0.008}
      />
      <text
        x={-viewSize / 2 + a * 0.05}
        y={-viewSize / 2 + a * 0.12}
        fontSize={a * 0.08}
        fontFamily="ui-monospace, monospace"
        fill="black"
      >
        top view
      </text>
    </svg>
  );
}
