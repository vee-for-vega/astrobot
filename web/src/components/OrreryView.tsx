import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import systemData from "../data/solar-system.json";
import { ellipsePath, positionAt, solveKepler } from "../kepler";
import type { OrbitalElements, Planet, PlanetarySystem, View } from "../types";

// ---------------------------------------------------------------------------
// Solar-system orrery for the landing page — Prometheus-style hologram.
//
// Single translucent cyan shade with a soft glow. Two levels share this view:
//   - "system": all 8 planets on COMPRESSED, evenly-spaced orbits, placed at
//     their REAL heliocentric longitude (Standish J2000 elements). Schematic
//     radius, real angle, real relative speeds.
//   - "planet": Sun + one planet with its real eccentric, inclined orbit.
//
// A simulation clock advances "days since J2000" at a user-controlled rate.
// LIVE syncs continuously to the real clock (planets where they are right now).
// A TILT toggle shows axial tilt + spin direction (Venus/Uranus retrograde).
// ---------------------------------------------------------------------------

const SYSTEM = systemData as PlanetarySystem;
const PLANETS = SYSTEM.planets;
const STAR = SYSTEM.star;

const DEG = Math.PI / 180;
const INCL_EXAG = 2.6; // side-view inclination exaggeration for visibility
const R_MIN = 26;
const R_MAX = 94;

const J2000_MS = Date.UTC(2000, 0, 1, 12, 0, 0);
const nowSimDays = () => (Date.now() - J2000_MS) / 86400000;
const START_SIM_DAYS = nowSimDays();

// Speed presets. LIVE = real clock; others advance N simulated days/real second.
type Speed = { label: string; dps?: number; live?: boolean };
const SPEEDS: Speed[] = [
  { label: "LIVE", live: true },
  { label: "1x", dps: 3 },
  { label: "10x", dps: 30 },
  { label: "50x", dps: 150 },
  { label: "200x", dps: 600 },
];

// Hologram palette.
const HOLO = "#7fe9ff";
const HOLO_BRIGHT = "#cdf6ff";
const HOLO_FILL = "rgba(127, 233, 255, 0.22)";
const HOLO_RING = "rgba(127, 233, 255, 0.22)";
const HOLO_LABEL = "#8fdcff";

const MAX_KM = Math.max(...PLANETS.map((p) => p.radiusKm));

function discR(km: number): number {
  return 2.2 + Math.sqrt(km / MAX_KM) * 5.8;
}

function scheduledR(index: number): number {
  return R_MIN + (R_MAX - R_MIN) * (index / (PLANETS.length - 1));
}

// Real heliocentric ecliptic longitude (radians) at tDays since J2000.
function heliocentricLongitude(el: OrbitalElements, tDays: number): number {
  const periDeg = el.peri ?? 0;
  const L0 = el.L0 ?? (el.M0 ?? 0) + periDeg;
  const period = el.period ?? 365.25;
  const n = 360 / period; // deg/day
  const Mdeg = L0 + n * tDays - periDeg;
  const M = (((Mdeg % 360) + 360) % 360) * DEG;
  const E = solveKepler(M, el.e);
  const nu = 2 * Math.atan2(
    Math.sqrt(1 + el.e) * Math.sin(E / 2),
    Math.sqrt(1 - el.e) * Math.cos(E / 2),
  );
  return nu + periDeg * DEG;
}

function Sun() {
  return (
    <>
      <circle cx={0} cy={0} r={13} fill={HOLO} opacity={0.12} filter="url(#holo-glow)" />
      <circle cx={0} cy={0} r={6} fill={HOLO} opacity={0.28} />
      <circle cx={0} cy={0} r={3.2} fill={HOLO_BRIGHT} filter="url(#holo-glow)" />
    </>
  );
}

function PlanetDisc({ x, y, r }: { x: number; y: number; r: number }) {
  return (
    <circle
      cx={x}
      cy={y}
      r={r}
      fill={HOLO_FILL}
      stroke={HOLO_BRIGHT}
      strokeWidth={0.5}
      filter="url(#holo-glow)"
    />
  );
}

// Spin-direction arrow above the planet (top view). Retrograde points opposite.
function SpinArrow({ x, y, r, retro }: { x: number; y: number; r: number; retro: boolean }) {
  const dir = retro ? -1 : 1;
  const L = r * 1.8 + 2;
  const ay = y - r - 1.6;
  return (
    <line
      x1={x - (dir * L) / 2}
      y1={ay}
      x2={x + (dir * L) / 2}
      y2={ay}
      stroke={retro ? "#ffd27f" : HOLO_BRIGHT}
      strokeWidth={0.6}
      markerEnd="url(#holo-arrow)"
    />
  );
}

// Spin axis through the planet (side view), tilted by obliquity from vertical.
// Retrograde axes (tilt > 90) end up pointing downward and are dashed.
function AxisLine({ x, y, r, tiltDeg }: { x: number; y: number; r: number; tiltDeg: number }) {
  const ang = tiltDeg * DEG; // measured from "up" (orbital-plane normal)
  const L = r * 2.4 + 2;
  const ux = Math.sin(ang);
  const uy = -Math.cos(ang);
  const retro = tiltDeg > 90;
  return (
    <>
      <line
        x1={x - L * ux}
        y1={y - L * uy}
        x2={x + L * ux}
        y2={y + L * uy}
        stroke={retro ? "#ffd27f" : HOLO_BRIGHT}
        strokeWidth={0.5}
        strokeDasharray={retro ? "1 1" : undefined}
        opacity={0.9}
      />
      {/* north-pole marker */}
      <circle cx={x + L * ux} cy={y + L * uy} r={0.9} fill={retro ? "#ffd27f" : HOLO_BRIGHT} />
    </>
  );
}

function Panel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="relative flex-1 overflow-hidden rounded-lg border border-[#16384a] bg-[#03070d]">
      <div
        className="absolute left-3 top-2 z-10 font-mono text-[10px] text-[#5fb6cc]"
        style={{ letterSpacing: "2px" }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}

const SVG_PROPS = {
  viewBox: "-100 -100 200 200",
  preserveAspectRatio: "xMidYMid meet",
  className: "block h-full w-full",
} as const;

// ---- system level ----

function SystemTop({
  simDays,
  showTilt,
  onSelectPlanet,
}: {
  simDays: number;
  showTilt: boolean;
  onSelectPlanet: (n: string) => void;
}) {
  return (
    <svg {...SVG_PROPS} aria-label="solar system top view">
      <Sun />
      {PLANETS.map((p, idx) => {
        const r = scheduledR(idx);
        const lam = heliocentricLongitude(p.elements, simDays);
        const x = r * Math.cos(lam);
        const y = r * Math.sin(lam);
        const dr = discR(p.radiusKm);
        return (
          <g key={p.name} style={{ cursor: "pointer" }} onClick={() => onSelectPlanet(p.name)}>
            <circle
              cx={0}
              cy={0}
              r={r}
              fill="none"
              stroke={HOLO_RING}
              strokeWidth={0.5}
              strokeDasharray="1.5 2"
            />
            <circle cx={x} cy={y} r={dr + 5} fill="transparent" />
            <PlanetDisc x={x} y={y} r={dr} />
            {showTilt && <SpinArrow x={x} y={y} r={dr} retro={p.tiltDeg > 90} />}
            <text
              x={x}
              y={y - dr - (showTilt ? 5 : 2)}
              fontSize={4.5}
              fill={HOLO_LABEL}
              textAnchor="middle"
              fontFamily="ui-monospace, monospace"
            >
              {p.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function SystemSide({ simDays, showTilt }: { simDays: number; showTilt: boolean }) {
  return (
    <svg {...SVG_PROPS} aria-label="solar system side view">
      <line
        x1={-96}
        y1={0}
        x2={96}
        y2={0}
        stroke="rgba(127,233,255,0.14)"
        strokeWidth={0.4}
        strokeDasharray="2 3"
      />
      <Sun />
      {PLANETS.map((p, idx) => {
        const r = scheduledR(idx);
        const incl = p.elements.i * DEG * INCL_EXAG;
        const lam = heliocentricLongitude(p.elements, simDays);
        const slide = Math.cos(lam);
        const c = Math.cos(incl);
        const s = Math.sin(incl);
        const dr = discR(p.radiusKm);
        const px = r * slide * c;
        const py = r * slide * s;
        return (
          <g key={p.name}>
            <line
              x1={-r * c}
              y1={-r * s}
              x2={r * c}
              y2={r * s}
              stroke={HOLO_RING}
              strokeWidth={0.5}
              strokeDasharray="1.5 2"
            />
            <PlanetDisc x={px} y={py} r={dr} />
            {showTilt && <AxisLine x={px} y={py} r={dr} tiltDeg={p.tiltDeg} />}
          </g>
        );
      })}
    </svg>
  );
}

// ---- single-planet level (real eccentric / inclined orbit) ----

function PlanetTop({ planet, simDays, showTilt }: { planet: Planet; simDays: number; showTilt: boolean }) {
  const { a, e } = planet.elements;
  const fit = 88 / (a * (1 + e));
  const pos = positionAt(planet.elements, STAR, simDays);
  const dr = discR(planet.radiusKm);
  return (
    <svg {...SVG_PROPS} aria-label={`${planet.name} top view`}>
      <g transform={`scale(${fit})`}>
        <path
          d={ellipsePath(a, e)}
          fill="none"
          stroke={HOLO}
          strokeOpacity={0.5}
          strokeWidth={1}
          strokeDasharray="3 3"
          vectorEffect="non-scaling-stroke"
        />
      </g>
      <Sun />
      <PlanetDisc x={pos.x * fit} y={pos.y * fit} r={dr} />
      {showTilt && <SpinArrow x={pos.x * fit} y={pos.y * fit} r={dr} retro={planet.tiltDeg > 90} />}
      <text x={-94} y={-86} fontSize={6} fill={HOLO_LABEL} fontFamily="ui-monospace, monospace">
        {`a=${a.toFixed(2)} AU · e=${e.toFixed(3)}`}
      </text>
    </svg>
  );
}

function PlanetSide({ planet, simDays, showTilt }: { planet: Planet; simDays: number; showTilt: boolean }) {
  const { a, e, i } = planet.elements;
  const incl = i * DEG * INCL_EXAG;
  const fit = 88 / (a * (1 + e));
  const pos = positionAt(planet.elements, STAR, simDays);
  const c = Math.cos(incl);
  const s = Math.sin(incl);
  const half = a * (1 + e) * fit;
  const dr = discR(planet.radiusKm);
  const px = pos.x * fit * c;
  const py = pos.x * fit * s;
  const retro = planet.tiltDeg > 90;
  return (
    <svg {...SVG_PROPS} aria-label={`${planet.name} side view`}>
      <line
        x1={-96}
        y1={0}
        x2={96}
        y2={0}
        stroke="rgba(127,233,255,0.14)"
        strokeWidth={0.4}
        strokeDasharray="2 3"
      />
      <line
        x1={-half * c}
        y1={-half * s}
        x2={half * c}
        y2={half * s}
        stroke={HOLO}
        strokeOpacity={0.5}
        strokeWidth={0.8}
        strokeDasharray="3 3"
      />
      <Sun />
      <PlanetDisc x={px} y={py} r={dr} />
      {showTilt && <AxisLine x={px} y={py} r={dr} tiltDeg={planet.tiltDeg} />}
      <text x={-94} y={-86} fontSize={6} fill={HOLO_LABEL} fontFamily="ui-monospace, monospace">
        {`i=${i.toFixed(2)}° · tilt ${planet.tiltDeg.toFixed(0)}°${retro ? " (retrograde spin)" : ""}`}
      </text>
    </svg>
  );
}

// ---- container ----

type Props = {
  view: Extract<View, { level: "system" } | { level: "planet" }>;
  onSelectPlanet: (name: string) => void;
  onBack: () => void;
};

export default function OrreryView({ view, onSelectPlanet, onBack }: Props) {
  const [simDays, setSimDays] = useState(START_SIM_DAYS);
  const [playing, setPlaying] = useState(true);
  const [speedIdx, setSpeedIdx] = useState(0); // default: LIVE
  const [showTilt, setShowTilt] = useState(false);

  const modeRef = useRef<Speed>(SPEEDS[0]);
  modeRef.current = playing ? SPEEDS[speedIdx] : { label: "PAUSE", dps: 0 };

  useEffect(() => {
    let raf = 0;
    let last: number | null = null;
    const tick = (now: number) => {
      const m = modeRef.current;
      if (m.live) {
        setSimDays(nowSimDays());
      } else if (last !== null && m.dps) {
        const dt = (now - last) / 1000;
        setSimDays((d) => d + m.dps! * dt);
      }
      last = now;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't hijack keys while the user is typing in the chat box.
      const el = e.target as HTMLElement | null;
      if (
        el &&
        (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)
      ) {
        return;
      }
      if (e.key === "Escape") onBack();
      if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onBack]);

  const selected =
    view.level === "planet" ? PLANETS.find((p) => p.name === view.planet) ?? null : null;

  const elapsedYears = (simDays - START_SIM_DAYS) / 365.25;
  const isLive = playing && SPEEDS[speedIdx].live;

  return (
    <div className="relative h-full w-full bg-[#03060c] text-[#bfe9f5]">
      {/* Shared hologram defs (glow + arrowhead), referenced by all panel svgs. */}
      <svg width="0" height="0" className="absolute" aria-hidden="true">
        <defs>
          <filter id="holo-glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="1.1" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker
            id="holo-arrow"
            markerWidth="5"
            markerHeight="5"
            refX="2.5"
            refY="2.5"
            orient="auto"
          >
            <path d="M0,0 L5,2.5 L0,5 z" fill="#cdf6ff" />
          </marker>
        </defs>
      </svg>

      <div className="absolute inset-y-0 left-0" style={{ right: 408 }}>
        {/* header: back + breadcrumb */}
        <div
          className="absolute left-5 top-5 z-10 flex items-center gap-3 font-mono text-[11px]"
          style={{ letterSpacing: "1.5px" }}
        >
          <button
            onClick={onBack}
            className="rounded border border-[#1f4f63] px-2 py-1 text-[#8fdcff] transition hover:border-[#46a6c4] hover:text-white"
          >
            {"< BACK"}
          </button>
          <span className="text-[#5fb6cc]">
            GALAXY / SOLAR SYSTEM
            {selected ? ` / ${selected.name.toUpperCase()}` : ""}
          </span>
        </div>

        <div className="flex h-full w-full flex-col gap-2 p-4 pt-16 md:flex-row">
          <Panel label="TOP VIEW">
            {view.level === "system" ? (
              <SystemTop simDays={simDays} showTilt={showTilt} onSelectPlanet={onSelectPlanet} />
            ) : (
              selected && <PlanetTop planet={selected} simDays={simDays} showTilt={showTilt} />
            )}
          </Panel>
          <Panel label="SIDE VIEW">
            {view.level === "system" ? (
              <SystemSide simDays={simDays} showTilt={showTilt} />
            ) : (
              selected && <PlanetSide planet={selected} simDays={simDays} showTilt={showTilt} />
            )}
          </Panel>
        </div>

        {/* legend: pause/play + speed presets (incl. LIVE) + TILT + elapsed years */}
        <div
          className="pointer-events-auto absolute bottom-4 left-4 flex items-center gap-2 rounded-md border border-[#16384a] bg-[#03070d]/85 px-3 py-2 font-mono text-[10px] text-[#8fdcff]"
          style={{ letterSpacing: "1px" }}
        >
          <button
            onClick={() => setPlaying((p) => !p)}
            className="rounded border border-[#1f4f63] px-2 py-1 transition hover:border-[#46a6c4] hover:text-white"
            style={{ minWidth: 52 }}
          >
            {playing ? "PAUSE" : "PLAY"}
          </button>
          <span className="text-[#3f7e92]">SPEED</span>
          {SPEEDS.map((sp, idx) => (
            <button
              key={sp.label}
              onClick={() => {
                setSpeedIdx(idx);
                setPlaying(true);
              }}
              className={
                "rounded border px-1.5 py-1 transition " +
                (idx === speedIdx && playing
                  ? "border-[#7fe9ff] text-white"
                  : "border-[#1f4f63] hover:border-[#46a6c4]")
              }
            >
              {sp.label}
            </button>
          ))}
          <button
            onClick={() => setShowTilt((v) => !v)}
            className={
              "ml-1 rounded border px-2 py-1 transition " +
              (showTilt ? "border-[#7fe9ff] text-white" : "border-[#1f4f63] hover:border-[#46a6c4]")
            }
          >
            TILT
          </button>
          <span className="ml-1 border-l border-[#16384a] pl-2 text-[#bfe9f5]">
            {isLive ? "LIVE · now" : `+${elapsedYears.toFixed(1)} Earth yr`}
          </span>
        </div>

        <div
          className="pointer-events-none absolute bottom-4 right-4 font-mono text-[10px] text-[#3f7e92]"
          style={{ letterSpacing: "1px" }}
        >
          {view.level === "system"
            ? "Click a planet · LIVE = real positions now · Space to pause · Esc to exit"
            : "Esc or BACK to return to the system view"}
        </div>
      </div>
    </div>
  );
}
