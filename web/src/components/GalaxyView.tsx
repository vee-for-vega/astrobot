import { useEffect, useMemo, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Realistic Milky Way top-down map.
//
// Spiral arm geometry: log-spiral parameters from Reid et al. 2019,
//   "Trigonometric Parallaxes of High Mass Star Forming Regions: Our View
//    of the Milky Way" (ApJ 885:131). Modern picture is 2 major arms
//   (Scutum-Centaurus, Perseus) + 2 minor arms (Sagittarius-Carina, Norma)
//   + the Local Arm spur where the Sun lives. Sun distance to Sgr A*
//   R₀ = 8.18 kpc (GRAVITY Collaboration 2019).
// Disk surface density: exponential with scale length h ≈ 3.5 kpc.
// Bar: ~5 kpc long, oriented ~25° from the Sun–Galactic Center line.
// Galactic disk radius ≈ 50 kpc.
// ---------------------------------------------------------------------------

type Dot = { x: number; y: number; r: number; opacity: number; color: string };

function makeRand(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function gauss(rand: () => number): number {
  const u = Math.max(rand(), 1e-9);
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

// SVG units per kiloparsec. Disk extends to ~50 kpc → ~750 SVG units. With viewBox half-width
// of 500, the disk extends well past the viewBox edges; the bright bulge + arms dominate the screen.
const KPC = 15;
const DISK_KPC = 50;
const DISK_R = DISK_KPC * KPC;

// Reid+ 2019 Table 2 (simplified). Pitch ψ in degrees, ref radius in kpc,
// ref azimuth in degrees (galactocentric, measured anticlockwise from Sun→GC).
type ArmModel = {
  name: string;
  rRefKpc: number;
  phiRefDeg: number;
  pitchDeg: number;
  widthKpc: number;
  density: number; // relative star count (major vs minor)
  rInnerKpc: number;
  rOuterKpc: number;
  color: string;
};

const ARMS: ArmModel[] = [
  {
    name: "SCUTUM-CENTAURUS",
    rRefKpc: 5.0,
    phiRefDeg: 23,
    pitchDeg: 12.1,
    widthKpc: 0.40,
    density: 1.0,
    rInnerKpc: 3,
    rOuterKpc: 18,
    color: "#cfdcff",
  },
  {
    name: "PERSEUS",
    rRefKpc: 8.87,
    phiRefDeg: 40,
    pitchDeg: 10.3,
    widthKpc: 0.45,
    density: 0.95,
    rInnerKpc: 5,
    rOuterKpc: 22,
    color: "#cfdcff",
  },
  {
    name: "SAGITTARIUS-CARINA",
    rRefKpc: 6.04,
    phiRefDeg: 24,
    pitchDeg: 17.1,
    widthKpc: 0.35,
    density: 0.6,
    rInnerKpc: 3.5,
    rOuterKpc: 14,
    color: "#dfe6ff",
  },
  {
    name: "NORMA",
    rRefKpc: 4.46,
    phiRefDeg: 18,
    pitchDeg: 19.5,
    widthKpc: 0.30,
    density: 0.5,
    rInnerKpc: 3,
    rOuterKpc: 10,
    color: "#dfe6ff",
  },
  {
    name: "LOCAL ARM",
    rRefKpc: 8.26,
    phiRefDeg: 9,
    pitchDeg: 11.4,
    widthKpc: 0.30,
    density: 0.45,
    rInnerKpc: 6,
    rOuterKpc: 12,
    color: "#e8eeff",
  },
];

// Sun's measured position relative to Sgr A* (GRAVITY 2019).
const SUN_R_KPC = 8.18;
// Place Sun on the Local Arm (φ = phiRef of Local Arm at R = rRef ≈ SUN_R).
// We pick a static "view rotation" so the Sun sits in a visually pleasant spot
// on first render; the whole disk rotates from there.
const VIEW_ROT_DEG = 231; // brings Sun's natural position to upper-left of center

// Log-spiral position for arm: R(φ) = R_ref * exp(-(φ - φ_ref) * tan(ψ))
// Inverse: φ(R) = φ_ref - ln(R/R_ref) / tan(ψ)
function armPhiAtR(arm: ArmModel, rKpc: number): number {
  const pitch = (arm.pitchDeg * Math.PI) / 180;
  const phiRef = (arm.phiRefDeg * Math.PI) / 180;
  return phiRef - Math.log(rKpc / arm.rRefKpc) / Math.tan(pitch);
}

// Low-frequency wiggle on the arm centerline (in kpc) so arms aren't perfect log spirals.
// Real spiral arms deviate from any clean mathematical curve — sum of sines gives a smooth,
// deterministic perturbation per arm.
function armWiggle(t: number, armSeed: number): number {
  return (
    0.32 * Math.sin(t * 7 + armSeed * 0.9) +
    0.18 * Math.sin(t * 19 + armSeed * 2.3) +
    0.09 * Math.sin(t * 41 + armSeed * 4.1)
  );
}

function pickStarColor(rand: () => number, inCluster: boolean): string {
  const r = rand();
  if (inCluster) {
    // Bright young O/B-association colors — bluer / whiter
    if (r < 0.35) return "#ffffff";
    if (r < 0.7) return "#c8d6ff";
    if (r < 0.92) return "#a0b8ff";
    return "#8aa6ff";
  }
  // Inter-cluster field — more variety
  if (r < 0.5) return "#ffffff";
  if (r < 0.78) return "#dde6ff";
  if (r < 0.93) return "#fff0d0";
  return "#cfdcff";
}

type HII = { x: number; y: number; r: number; opacity: number };

// Real spiral arms aren't smooth tubes of stars — they're chains of star-forming
// complexes (giant molecular clouds → OB associations → HII regions) strung along
// a density wave. This generator samples cluster centers along each arm and packs
// stars into elongated knots, plus a thin diffuse population between clusters.
function generateArmContent(
  rand: () => number,
  arm: ArmModel,
  armIndex: number,
): { stars: Dot[]; hii: HII[] } {
  const stars: Dot[] = [];
  const hii: HII[] = [];
  const armSeed = (armIndex + 1) * 3.7;
  const pitch = (arm.pitchDeg * Math.PI) / 180;

  // 1. Cluster centers (knots of star formation)
  const numClusters = Math.round(7 + arm.density * 7);
  for (let c = 0; c < numClusters; c++) {
    // Evenly spaced along arm length with jitter
    const t = (c + 0.5 + (rand() - 0.5) * 0.7) / numClusters;
    if (t < 0.02 || t > 0.98) continue;
    const rKpcBase = arm.rInnerKpc + (arm.rOuterKpc - arm.rInnerKpc) * t;
    const rKpc = Math.max(2, rKpcBase + armWiggle(t, armSeed));
    const phi = armPhiAtR(arm, rKpc);
    const r = rKpc * KPC;
    const cx = r * Math.cos(phi);
    const cy = r * Math.sin(phi);

    const tangent = phi + Math.PI / 2 - pitch;
    const tcos = Math.cos(tangent);
    const tsin = Math.sin(tangent);
    const pcos = -Math.sin(tangent);
    const psin = Math.cos(tangent);

    // Cluster shape: elongated along the arm tangent, thin across
    const clusterMajor = (0.45 + rand() * 0.75) * KPC;
    const clusterMinor = (0.18 + rand() * 0.32) * KPC;
    const numStars = 16 + Math.floor(rand() * 32 * arm.density);

    for (let i = 0; i < numStars; i++) {
      const a = gauss(rand) * clusterMajor * 0.6;
      const b = gauss(rand) * clusterMinor;
      stars.push({
        x: cx + a * tcos + b * pcos,
        y: cy + a * tsin + b * psin,
        r: 0.32 + rand() * 0.95,
        opacity: 0.55 + rand() * 0.45,
        color: pickStarColor(rand, true),
      });
    }

    // ~35% of cluster sites get an HII emission-nebula halo (real Hα-emitting complexes)
    if (rand() < 0.35) {
      hii.push({
        x: cx + (rand() - 0.5) * clusterMajor * 0.4,
        y: cy + (rand() - 0.5) * clusterMajor * 0.4,
        r: (0.55 + rand() * 0.85) * KPC,
        opacity: 0.16 + rand() * 0.16,
      });
    }
  }

  // 2. Inter-cluster diffuse population — thin scattering between knots
  const numField = Math.round(70 * arm.density);
  for (let i = 0; i < numField; i++) {
    const t = rand();
    const rKpcBase = arm.rInnerKpc + (arm.rOuterKpc - arm.rInnerKpc) * Math.pow(t, 0.6);
    const rKpc = Math.max(2, rKpcBase + armWiggle(t, armSeed));
    const phi = armPhiAtR(arm, rKpc);
    const r = rKpc * KPC;
    const widthScatter = gauss(rand) * arm.widthKpc * KPC * 3.0;
    const tangent = phi + Math.PI / 2 - pitch;
    stars.push({
      x: r * Math.cos(phi) - Math.sin(tangent) * widthScatter,
      y: r * Math.sin(phi) + Math.cos(tangent) * widthScatter,
      r: 0.22 + rand() * 0.65,
      opacity: 0.3 + rand() * 0.5,
      color: pickStarColor(rand, false),
    });
  }

  return { stars, hii };
}

// Dust lane: a dark band along the inner (leading) edge of each spiral arm.
// In real galaxies, gas and dust are compressed on the leading edge of the
// density wave before triggering star formation — visible as dark dust lanes
// running parallel to and slightly inside each bright arm.
function dustLanePath(arm: ArmModel, armIndex: number, offsetKpc: number, samples: number): string {
  let d = "";
  const armSeed = (armIndex + 1) * 3.7;
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const rKpcBase = arm.rInnerKpc + (arm.rOuterKpc - arm.rInnerKpc) * t;
    const rKpc = Math.max(2, rKpcBase + armWiggle(t, armSeed));
    const phi = armPhiAtR(arm, rKpc);
    const rOffset = (rKpc - offsetKpc) * KPC;
    const x = rOffset * Math.cos(phi);
    const y = rOffset * Math.sin(phi);
    d += (i === 0 ? "M" : " L") + x.toFixed(1) + " " + y.toFixed(1);
  }
  return d;
}

// Inter-arm diffuse disk. Surface density Σ(R) ∝ exp(-R/h). For sampling,
// the radial PDF includes the Jacobian R, giving Gamma(shape=2, scale=h).
// Sample as the sum of two exponentials.
function sampleDiffuseDisk(rand: () => number, count: number, hKpc: number, rMaxKpc: number): Dot[] {
  const dots: Dot[] = [];
  let i = 0;
  while (i < count) {
    const rKpc = -hKpc * (Math.log(Math.max(rand(), 1e-9)) + Math.log(Math.max(rand(), 1e-9)));
    if (rKpc > rMaxKpc || rKpc < 0.5) continue;
    const theta = rand() * 2 * Math.PI;
    const r = rKpc * KPC;
    dots.push({
      x: r * Math.cos(theta),
      y: r * Math.sin(theta),
      r: 0.22 + rand() * 0.55,
      opacity: 0.18 + rand() * 0.4,
      color: rand() < 0.7 ? "#d6deff" : "#ffefd0",
    });
    i++;
  }
  return dots;
}

// Bar: elongated stellar bar, ~5 kpc semi-major, ~25° to Sun-GC line.
// Inner bulge: nearly spherical population of old (yellow) stars.
function generateBarBulge(rand: () => number, barCount: number, coreCount: number): Dot[] {
  const dots: Dot[] = [];
  const barAngle = (25 * Math.PI) / 180;
  const c = Math.cos(barAngle);
  const s = Math.sin(barAngle);
  const aBar = 2.5 * KPC; // semi-major in units
  const bBar = 0.9 * KPC; // semi-minor
  let placed = 0;
  while (placed < barCount) {
    const x0 = gauss(rand) * aBar;
    const y0 = gauss(rand) * bBar;
    if (Math.abs(x0) > 2.6 * aBar || Math.abs(y0) > 2.6 * bBar) continue;
    dots.push({
      x: x0 * c - y0 * s,
      y: x0 * s + y0 * c,
      r: 0.32 + rand() * 0.85,
      opacity: 0.55 + rand() * 0.45,
      color: ["#fff5cc", "#ffe6a4", "#ffd485", "#ffc36b"][Math.floor(rand() * 4)],
    });
    placed++;
  }
  // tight inner bulge (older Pop II, redder/yellower)
  placed = 0;
  while (placed < coreCount) {
    const r = Math.abs(gauss(rand)) * 0.95 * KPC;
    const theta = rand() * 2 * Math.PI;
    dots.push({
      x: r * Math.cos(theta),
      y: r * Math.sin(theta),
      r: 0.3 + rand() * 0.75,
      opacity: 0.65 + rand() * 0.35,
      color: rand() < 0.5 ? "#fff6cc" : "#ffe098",
    });
    placed++;
  }
  return dots;
}

export default function GalaxyView() {
  // Track the actual pixel scale of the SVG so the kpc bar resizes with the window.
  // viewBox is 1000×1000 with slice → scale = max(rendered width, rendered height) / 1000.
  const svgRef = useRef<SVGSVGElement>(null);
  const [sliceScale, setSliceScale] = useState(1);
  useEffect(() => {
    const node = svgRef.current;
    if (!node) return;
    const update = () => {
      const rect = node.getBoundingClientRect();
      if (rect.width && rect.height) {
        setSliceScale(Math.max(rect.width, rect.height) / 1000);
      }
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const { armDots, hiiRegions, disk, bulge, armLabels, sun } = useMemo(() => {
    const rand = makeRand(20260527);
    const armDots: Dot[] = [];
    const hiiRegions: HII[] = [];
    ARMS.forEach((arm, i) => {
      const { stars, hii } = generateArmContent(rand, arm, i);
      armDots.push(...stars);
      hiiRegions.push(...hii);
    });
    const disk = sampleDiffuseDisk(rand, 900, 3.5, 22);
    const bulge = generateBarBulge(rand, 700, 350);

    // Per-arm label anchored at a representative radius along the arm
    const armLabels = ARMS.map((arm) => {
      const rKpc = (arm.rInnerKpc + arm.rOuterKpc) / 2;
      const phi = armPhiAtR(arm, rKpc);
      const r = rKpc * KPC;
      return { name: arm.name, x: r * Math.cos(phi), y: r * Math.sin(phi), arm };
    });

    // Sun sits exactly on the Local Arm at the measured R₀ = 8.18 kpc
    const localArm = ARMS.find((a) => a.name === "LOCAL ARM")!;
    const sunPhi = armPhiAtR(localArm, SUN_R_KPC);
    const sunR = SUN_R_KPC * KPC;
    const sun = { x: sunR * Math.cos(sunPhi), y: sunR * Math.sin(sunPhi) };

    return { armDots, hiiRegions, disk, bulge, armLabels, sun };
  }, []);

  return (
    <div className="relative h-full w-full bg-[#06010f]">
      {/* Reserve the right portion of the viewport for the chat console (360px panel + 24px right inset + 24px gap) */}
      <div className="absolute inset-y-0 left-0" style={{ right: 408 }}>
        <svg
          ref={svgRef}
          viewBox="-500 -500 1000 1000"
          preserveAspectRatio="xMidYMid slice"
          className="block h-full w-full"
          aria-label="Milky Way galactic map — top-down view, Reid et al. 2019 spiral model"
        >
        <defs>
          <radialGradient id="space-bg" cx="50%" cy="50%" r="65%">
            <stop offset="0%" stopColor="#1a0936" />
            <stop offset="55%" stopColor="#0a0320" />
            <stop offset="100%" stopColor="#04010c" />
          </radialGradient>

          <radialGradient id="disk-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff0c0" stopOpacity="0.20" />
            <stop offset="25%" stopColor="#b89cff" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#5a3a9a" stopOpacity="0" />
          </radialGradient>

          {/* Galactic halo — diffuse spherical glow extending well past the disk edge */}
          <radialGradient id="halo-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#7d6cb8" stopOpacity="0" />
            <stop offset="55%" stopColor="#4a3a82" stopOpacity="0.09" />
            <stop offset="80%" stopColor="#251444" stopOpacity="0.05" />
            <stop offset="100%" stopColor="#0a0420" stopOpacity="0" />
          </radialGradient>

          {/* Soft blur for dust lanes so they blend rather than read as hard strokes */}
          <filter id="dust-blur" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="1.4" />
          </filter>

          {/* HII region emission nebula — pink/red Hα-like glow at star-forming knots */}
          <radialGradient id="hii-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffb6c8" stopOpacity="0.55" />
            <stop offset="40%" stopColor="#ff6080" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#c83050" stopOpacity="0" />
          </radialGradient>

          <filter id="hii-blur" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="2.2" />
          </filter>

          <radialGradient id="core-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff5d0" stopOpacity="0.9" />
            <stop offset="35%" stopColor="#ffd070" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#c87020" stopOpacity="0" />
          </radialGradient>

          <radialGradient id="sun-corona" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff2c0" stopOpacity="0.9" />
            <stop offset="60%" stopColor="#ffb040" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#ff7010" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sun-disc" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fffaf0" />
            <stop offset="70%" stopColor="#ffe28a" />
            <stop offset="100%" stopColor="#f8b34a" />
          </radialGradient>
        </defs>

        <rect x="-500" y="-500" width="1000" height="1000" fill="url(#space-bg)" />

        {/* Galactic halo — old Pop II stars + globular clusters, extends well beyond the disk */}
        <circle cx={0} cy={0} r={DISK_R * 1.08} fill="url(#halo-glow)" />

        {/* diffuse disk light glow under the stars */}
        <circle cx={0} cy={0} r={DISK_R} fill="url(#disk-glow)" />

        {/* Everything inside the galaxy rotates as one pattern (density-wave model). */}
        <g transform={`rotate(${VIEW_ROT_DEG})`}>
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`${VIEW_ROT_DEG}`}
            to={`${VIEW_ROT_DEG + 360}`}
            dur="900s"
            repeatCount="indefinite"
          />

          {/* diffuse exponential-disk fill */}
          {disk.map((s, i) => (
            <circle key={`d${i}`} cx={s.x} cy={s.y} r={s.r} fill={s.color} opacity={s.opacity} />
          ))}

          {/* dust lanes — patchy dashes on the inner edge of each arm, blurred for natural blend */}
          <g filter="url(#dust-blur)">
            {ARMS.map((arm, i) => {
              const w = arm.widthKpc * KPC;
              return (
                <path
                  key={`dust-${arm.name}`}
                  d={dustLanePath(arm, i, 0.35, 120)}
                  fill="none"
                  stroke="#100624"
                  strokeOpacity={0.16 + arm.density * 0.2}
                  strokeWidth={w * 1.3}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray={`${w * 9} ${w * 3.5} ${w * 5} ${w * 6} ${w * 11} ${w * 4}`}
                />
              );
            })}
          </g>

          {/* HII regions — soft pink emission nebulae at star-forming knots */}
          <g filter="url(#hii-blur)">
            {hiiRegions.map((h, i) => (
              <circle key={`h${i}`} cx={h.x} cy={h.y} r={h.r} fill="url(#hii-glow)" opacity={h.opacity} />
            ))}
          </g>

          {/* spiral arm stars — clumped into star-forming knots + diffuse field */}
          {armDots.map((s, i) => (
            <circle key={`a${i}`} cx={s.x} cy={s.y} r={s.r} fill={s.color} opacity={s.opacity} />
          ))}

          {/* bar bulge glow + bar/core stars */}
          <ellipse cx={0} cy={0} rx={2.6 * KPC} ry={0.95 * KPC} fill="url(#core-glow)" transform="rotate(25)" />
          {bulge.map((s, i) => (
            <circle key={`b${i}`} cx={s.x} cy={s.y} r={s.r} fill={s.color} opacity={s.opacity} />
          ))}

          {/* Sgr A* — central supermassive black hole */}
          <g>
            <circle cx={0} cy={0} r={1.6} fill="#ffffff" />
            <circle cx={0} cy={0} r={3} fill="none" stroke="#ffffff" strokeOpacity={0.5} strokeWidth={0.3} />
            <text
              x={6}
              y={-5}
              fill="#ffffff"
              fillOpacity={0.75}
              fontSize={7.5}
              fontFamily="ui-monospace, monospace"
              letterSpacing="1.5"
            >
              Sgr A*
            </text>
          </g>

          {/* Per-arm labels */}
          {armLabels.map((lbl) => (
            <text
              key={lbl.name}
              x={lbl.x}
              y={lbl.y}
              fill="#b8c4f0"
              fillOpacity={0.55}
              fontSize={7.5}
              fontFamily="ui-monospace, monospace"
              letterSpacing="2"
              textAnchor="middle"
            >
              {lbl.name}
            </text>
          ))}

          {/* Sun marker — orbits with the disk, pulses to draw the eye */}
          <circle cx={sun.x} cy={sun.y} r={6} fill="url(#sun-corona)">
            <animate attributeName="r" values="5;9;5" dur="4.5s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.6;1;0.6" dur="4.5s" repeatCount="indefinite" />
          </circle>
          <circle cx={sun.x} cy={sun.y} r={1.4} fill="url(#sun-disc)" />
          <text
            x={sun.x + 8}
            y={sun.y + 3}
            fill="#ffeaa8"
            fillOpacity={0.9}
            fontSize={8.5}
            fontFamily="ui-monospace, monospace"
            letterSpacing="2"
          >
            SOL
          </text>
        </g>

        </svg>

        {/* Scale bar overlay — HTML so it never gets clipped by the SVG slice aspect ratio.
            Bar pixel length tracks the actual rendered scale via ResizeObserver. */}
        <div
          className="pointer-events-none absolute bottom-5 left-5 font-mono text-[10px]"
          style={{ color: "rgba(207, 214, 255, 0.7)", letterSpacing: "1.5px" }}
        >
          <div className="flex items-end" style={{ width: 5 * KPC * sliceScale }}>
            <div style={{ width: 1, height: 7, background: "currentColor" }} />
            <div className="flex-1 self-end" style={{ height: 1, background: "currentColor" }} />
            <div style={{ width: 1, height: 7, background: "currentColor" }} />
          </div>
          <div className="mt-1 text-center" style={{ width: 5 * KPC * sliceScale }}>
            5 kpc · 16,300 ly
          </div>
        </div>

        {/* Source credit overlay */}
        <div
          className="pointer-events-none absolute bottom-5 right-5 text-right font-mono text-[9px]"
          style={{ color: "rgba(124, 135, 184, 0.6)", letterSpacing: "1px" }}
        >
          Spiral model: Reid+ 2019 · R₀ = 8.18 kpc (GRAVITY 2019)
        </div>
      </div>
    </div>
  );
}
