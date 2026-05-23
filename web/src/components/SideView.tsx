import { useEffect, useRef, useState } from "react";
import type { OrbitalElements, Star } from "../types";
import { positionAt } from "../kepler";

type Props = {
  star: Star;
  elements: OrbitalElements;
  secondsPerOrbit?: number;
};

export default function SideView({ star, elements, secondsPerOrbit = 12 }: Props) {
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
  const i = (elements.i * Math.PI) / 180;
  const viewSize = a * 2.4;
  const halfLen = a * (1 + elements.e);
  const x1 = -halfLen * Math.cos(i);
  const y1 = -halfLen * Math.sin(i);
  const x2 = halfLen * Math.cos(i);
  const y2 = halfLen * Math.sin(i);

  const pos = positionAt(elements, star, tDays);
  const px = pos.x * Math.cos(i);
  const py = pos.x * Math.sin(i);

  return (
    <svg
      viewBox={`${-viewSize / 2} ${-viewSize / 2} ${viewSize} ${viewSize}`}
      className="block h-full w-full"
      aria-label="side view of orbit"
    >
      <line
        x1={-viewSize / 2}
        y1={0}
        x2={viewSize / 2}
        y2={0}
        stroke="black"
        strokeWidth={a * 0.003}
        strokeDasharray={`${a * 0.04} ${a * 0.04}`}
        opacity={0.3}
      />
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke="black"
        strokeWidth={a * 0.006}
        strokeDasharray={`${a * 0.025} ${a * 0.025}`}
      />
      <circle cx={0} cy={0} r={a * 0.06} fill="white" stroke="black" strokeWidth={a * 0.008} />
      <circle
        cx={px}
        cy={py}
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
        side view · {elements.i.toFixed(2)}°
      </text>
    </svg>
  );
}
