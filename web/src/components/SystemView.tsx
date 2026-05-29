import { useMemo } from "react";

type StarDot = { x: number; y: number; r: number; opacity: number };

// deterministic LCG so the starfield doesn't reshuffle every render
function generateStars(count: number, seed: number): StarDot[] {
  let s = seed;
  const rand = () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
  return Array.from({ length: count }, () => ({
    x: rand() * 1000 - 500,
    y: rand() * 1000 - 500,
    r: 0.25 + rand() * 0.9,
    opacity: 0.25 + rand() * 0.65,
  }));
}

export default function SystemView() {
  const stars = useMemo(() => generateStars(80, 1337), []);

  return (
    <div className="h-full w-full bg-[#06010f]">
      <svg
        viewBox="-500 -500 1000 1000"
        preserveAspectRatio="xMidYMid slice"
        className="block h-full w-full"
        aria-label="solar system top view"
      >
        <defs>
          <radialGradient id="space-bg" cx="50%" cy="50%" r="65%">
            <stop offset="0%" stopColor="#1a0936" />
            <stop offset="55%" stopColor="#0a0320" />
            <stop offset="100%" stopColor="#04010c" />
          </radialGradient>

          {/* outer corona — wide, very faint warm halo */}
          <radialGradient id="corona-outer" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffd070" stopOpacity="0.35" />
            <stop offset="35%" stopColor="#ff9030" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#ff6600" stopOpacity="0" />
          </radialGradient>

          {/* inner corona — tighter glow at the limb */}
          <radialGradient id="corona-inner" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff2c0" stopOpacity="0.7" />
            <stop offset="60%" stopColor="#ffb040" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#ff7010" stopOpacity="0" />
          </radialGradient>

          {/* photosphere — nearly-white core fading to warm yellow at the limb (limb darkening) */}
          <radialGradient id="photosphere" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fffaf0" />
            <stop offset="55%" stopColor="#ffe28a" />
            <stop offset="90%" stopColor="#f8b34a" />
            <stop offset="100%" stopColor="#e2862a" />
          </radialGradient>
        </defs>

        <rect x="-500" y="-500" width="1000" height="1000" fill="url(#space-bg)" />

        {stars.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#ffffff" opacity={s.opacity} />
        ))}

        {/* Sun */}
        <circle cx={0} cy={0} r={160} fill="url(#corona-outer)" />
        <circle cx={0} cy={0} r={70} fill="url(#corona-inner)" />
        <circle cx={0} cy={0} r={38} fill="url(#photosphere)" />
      </svg>
    </div>
  );
}
