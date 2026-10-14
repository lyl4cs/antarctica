/**
 * The penguin illustrations from the design, as React components.
 *
 * HOW IT WORKS
 * The SVG markup is copied from docs/design/*.dc.html with attributes converted to
 * JSX (stroke-width -> strokeWidth). The lying-down penguin body is shared by every
 * scene (`PenguinBody`); each scene adds its own eyes, ice and water. Motion (bob,
 * ripple, zz, drift) is plain CSS keyframes in styles.css, which also switches it
 * off for people who ask their OS for reduced motion.
 *
 * `FloePenguin` takes a `mood`: "sleep" while the scan is queued, "awake" while it
 * runs, "happy" when the report is ready. All three eye sets are always in the DOM
 * and we fade between them with opacity, exactly like the design, so the change
 * animates instead of popping.
 */

import type { ReactNode } from "react";

export type Mood = "sleep" | "awake" | "happy";

/** Fish, body, belly and flipper: the parts every penguin pose shares. */
function PenguinBody({ children, fish = true }: { children?: ReactNode; fish?: boolean }) {
  return (
    <>
      <ellipse cx="-63" cy="-15" rx="9" ry="5.5" fill="#F2A33A" stroke="#12202B" strokeWidth="3" transform="rotate(-20 -63 -15)" />
      <ellipse cx="-62" cy="-4" rx="9" ry="5.5" fill="#F2A33A" stroke="#12202B" strokeWidth="3" />
      <path d="M -58 -2 C -66 -30 -40 -60 2 -60 C 44 -60 68 -40 66 -18 C 64 0 48 2 0 2 C -36 2 -54 4 -58 -2 Z" fill="#2B3A47" stroke="#12202B" strokeWidth="3.5" strokeLinejoin="round" />
      <path d="M -46 -2 C -48 -16 -28 -25 2 -25 C 34 -25 56 -18 57 -8 C 57 -1 44 -1 0 -1 C -24 -1 -42 0 -46 -2 Z" fill="#FFFFFF" />
      <ellipse cx="36" cy="-28" rx="20" ry="16" fill="#FFFFFF" />
      {children}
      {fish && <Fish />}
    </>
  );
}

function Fish() {
  return (
    <>
      <path d="M -32 -20 L -42 -29 L -40 -20 L -42 -11 Z" fill="#6FB8E3" stroke="#12202B" strokeWidth="2.6" strokeLinejoin="round" />
      <path d="M -32 -20 C -24 -32 2 -32 10 -20 C 2 -8 -24 -8 -32 -20 Z" fill="#6FB8E3" stroke="#12202B" strokeWidth="2.6" />
      <circle cx="2" cy="-22" r="1.8" fill="#12202B" />
      <path d="M -12 -27 Q -8 -20 -12 -13" fill="none" stroke="#12202B" strokeWidth="1.8" strokeLinecap="round" opacity="0.45" />
    </>
  );
}

function SleepyEyes() {
  return (
    <>
      <path d="M 26 -33 Q 30 -29 34 -33" fill="none" stroke="#12202B" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M 40 -33 Q 44 -29 48 -33" fill="none" stroke="#12202B" strokeWidth="2.6" strokeLinecap="round" />
    </>
  );
}

function Cheeks() {
  return (
    <>
      <ellipse cx="24" cy="-24" rx="4" ry="2.5" fill="#F6A9A0" opacity="0.85" />
      <ellipse cx="50" cy="-24" rx="4" ry="2.5" fill="#F6A9A0" opacity="0.85" />
      <path d="M 33.5 -27 Q 37 -19 40.5 -27 Z" fill="#F2A33A" stroke="#12202B" strokeWidth="2" strokeLinejoin="round" />
    </>
  );
}

/** The flipper hugging the fish (drawn after the fish so it sits on top). */
function HugFlipper() {
  return (
    <path d="M -10 -47 C 2 -41 6 -25 -2 -13 C -6 -8 -13 -10 -12 -17 C -10 -27 -16 -39 -10 -47 Z" fill="#2B3A47" stroke="#12202B" strokeWidth="3" strokeLinejoin="round" />
  );
}

function Zzz() {
  return (
    <g className="zz">
      <path d="M 60 -68 h 9 l -9 10 h 9" fill="none" stroke="#2F7FB9" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M 75 -86 h 6 l -6 7 h 6" fill="none" stroke="#2F7FB9" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </g>
  );
}

/** Home hero: iceberg, waterline, sleeping penguin on top. Decorative content only. */
export function HeroIceberg() {
  return (
    <svg
      viewBox="0 0 520 460"
      role="img"
      aria-label="An iceberg with a sleeping penguin hugging a fish on top. Above the waterline is the score; below it, the findings slowing the page down."
    >
      <rect x="0" y="170" width="520" height="290" fill="#D3EAF7" />
      <rect x="0" y="330" width="520" height="130" fill="#C4E2F3" />
      <polygon points="120,176 420,176 470,250 440,340 360,410 230,420 140,370 90,280" fill="#8CC9EA" />
      <polygon points="120,176 260,176 230,300 90,280" fill="#A6D6F0" />
      <polygon points="260,176 420,176 470,250 330,300" fill="#7FC0E6" />
      <polygon points="90,280 230,300 230,420 140,370" fill="#72B6DF" />
      <polygon points="230,300 330,300 360,410 230,420" fill="#5EA9D9" />
      <polygon points="330,300 470,250 440,340 360,410" fill="#4F9BD0" />
      <polygon points="150,170 195,105 222,94 238,58 314,58 332,92 354,100 392,170" fill="#D9F0FB" />
      <polygon points="150,170 195,105 222,94 238,170" fill="#F6FCFE" />
      <polygon points="314,58 332,92 354,100 392,170 284,170 298,58" fill="#A9DCF3" />
      <polygon points="332,92 354,100 392,170 344,170" fill="#8FD0EE" />
      <polygon points="234,62 240,55 312,55 318,62 308,67 292,63 276,68 260,63 246,66" fill="#FFFFFF" />
      <line x1="0" y1="170" x2="520" y2="170" stroke="#FFFFFF" strokeWidth="3" />
      <line x1="96" y1="184" x2="128" y2="184" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" opacity="0.8" />
      <line x1="410" y1="190" x2="452" y2="190" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" opacity="0.8" />
      <g transform="translate(276,58) scale(0.5)">
        <ellipse cx="0" cy="3" rx="68" ry="7" fill="#12202B" opacity="0.10" />
        <PenguinBody>
          <SleepyEyes />
          <Cheeks />
        </PenguinBody>
        <HugFlipper />
        <Zzz />
      </g>
    </svg>
  );
}

/** Scan page scene: penguin on a bobbing ice floe; eyes follow the scan state. */
export function FloePenguin({ mood }: { mood: Mood }) {
  const show = (m: Mood) => (mood === m ? 1 : 0);
  return (
    <svg
      viewBox="0 0 760 230"
      role="img"
      aria-label="A penguin with its fish on an ice floe. It naps while the scan is queued, wakes up while it runs, and smiles when the report is ready."
    >
      <rect x="0" y="150" width="760" height="80" fill="#D3EAF7" />
      <line x1="0" y1="150" x2="760" y2="150" stroke="#FFFFFF" strokeWidth="3" />
      <line className="ripple" x1="200" y1="168" x2="250" y2="168" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
      <line className="ripple2" x1="505" y1="176" x2="560" y2="176" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
      <line className="ripple2" x1="120" y1="196" x2="150" y2="196" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
      <line className="ripple" x1="610" y1="204" x2="640" y2="204" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
      <g className="bob">
        <polygon points="282,150 300,132 478,128 494,150 470,170 300,168" fill="#A9DCF3" />
        <polygon points="300,132 478,128 494,150 282,150" fill="#EAF7FD" />
        <polygon points="282,150 494,150 470,170 300,168" fill="#7FC0E6" />
        <g transform="translate(390,134) scale(0.95)">
          <PenguinBody>
            <g className="eyes" opacity={show("sleep")} data-eyes="sleep">
              <SleepyEyes />
            </g>
            <g className="eyes" opacity={show("awake")} data-eyes="awake">
              <circle cx="30" cy="-33" r="3.6" fill="#12202B" />
              <circle cx="44" cy="-33" r="3.6" fill="#12202B" />
              <circle cx="31.2" cy="-34.4" r="1.2" fill="#FFFFFF" />
              <circle cx="45.2" cy="-34.4" r="1.2" fill="#FFFFFF" />
            </g>
            <g className="eyes" opacity={show("happy")} data-eyes="happy">
              <path d="M 26 -31 Q 30 -37 34 -31" fill="none" stroke="#12202B" strokeWidth="2.6" strokeLinecap="round" />
              <path d="M 40 -31 Q 44 -37 48 -31" fill="none" stroke="#12202B" strokeWidth="2.6" strokeLinecap="round" />
            </g>
            <Cheeks />
          </PenguinBody>
          <HugFlipper />
          <g className="eyes" opacity={show("sleep")}>
            <Zzz />
          </g>
        </g>
      </g>
    </svg>
  );
}

/** Failed scan scene: the floe cracks, the fish drifts off, the penguin says "Oh no!". */
export function CrackedFloe() {
  return (
    <svg
      viewBox="0 0 760 230"
      role="img"
      aria-label="An ice floe cracked in two. The penguin on one half throws a flipper up and says Oh no! as its fish drifts away on the other half."
    >
      <rect x="0" y="150" width="760" height="80" fill="#D9E8F0" />
      <line x1="0" y1="150" x2="760" y2="150" stroke="#FFFFFF" strokeWidth="3" />
      <line x1="180" y1="176" x2="226" y2="176" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" opacity="0.7" />
      <line x1="560" y1="192" x2="604" y2="192" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" opacity="0.7" />
      <g className="dl">
        <polygon points="250,150 266,133 368,130 356,142 372,150 360,170 268,168" fill="#B6DDF0" />
        <polygon points="266,133 368,130 356,142 372,150 250,150" fill="#EEF7FC" />
        <polygon points="250,150 372,150 360,170 268,168" fill="#8FC5E3" />
        <g transform="translate(312,137) scale(0.85)">
          <PenguinBody fish={false}>
            <circle cx="29" cy="-33" r="5.2" fill="#FFFFFF" stroke="#12202B" strokeWidth="2.2" />
            <circle cx="44" cy="-33" r="5.2" fill="#FFFFFF" stroke="#12202B" strokeWidth="2.2" />
            <circle cx="31" cy="-33" r="2.2" fill="#12202B" />
            <circle cx="46" cy="-33" r="2.2" fill="#12202B" />
            <ellipse cx="23" cy="-23" rx="4" ry="2.5" fill="#F6A9A0" opacity="0.85" />
            <ellipse cx="51" cy="-23" rx="4" ry="2.5" fill="#F6A9A0" opacity="0.85" />
            <ellipse cx="37" cy="-20.5" rx="3.6" ry="4.6" fill="#12202B" />
            <path d="M 32.5 -27 Q 37 -31 41.5 -27 L 37 -23.5 Z" fill="#F2A33A" stroke="#12202B" strokeWidth="2" strokeLinejoin="round" />
          </PenguinBody>
          <path d="M -16 -52 C -20 -70 -10 -88 -2 -88 C 4 -86 4 -70 4 -54 Z" fill="#2B3A47" stroke="#12202B" strokeWidth="3" strokeLinejoin="round" />
          <path d="M -20 -84 l -7 -5" fill="none" stroke="#12202B" strokeWidth="2.6" strokeLinecap="round" />
          <path d="M -23 -73 l -9 0" fill="none" stroke="#12202B" strokeWidth="2.6" strokeLinecap="round" />
          <path d="M 70 -62 C 65.5 -54 65.5 -49 70 -49 C 74.5 -49 74.5 -54 70 -62 Z" fill="#8FD0EE" stroke="#12202B" strokeWidth="2" strokeLinejoin="round" />
        </g>
        <path d="M 350 34 h 96 a 14 14 0 0 1 14 14 v 14 a 14 14 0 0 1 -14 14 h -70 l -14 14 l 2 -14 h -14 a 14 14 0 0 1 -14 -14 v -14 a 14 14 0 0 1 14 -14 Z" fill="#FFFFFF" stroke="#12202B" strokeWidth="2.5" strokeLinejoin="round" />
        <text x="398" y="63" textAnchor="middle" style={{ fontFamily: "'Bricolage Grotesque', system-ui, sans-serif", fontSize: 23, fontWeight: 800, letterSpacing: "-0.02em", fill: "#12202B" }}>
          Oh no!
        </text>
      </g>
      <g className="dr">
        <polygon points="398,150 410,141 400,131 494,128 510,150 488,170 404,168" fill="#B6DDF0" />
        <polygon points="400,131 494,128 510,150 398,150 410,141" fill="#EEF7FC" />
        <polygon points="398,150 510,150 488,170 404,168" fill="#8FC5E3" />
        <g transform="translate(462,138) rotate(-8)">
          <Fish />
        </g>
      </g>
    </svg>
  );
}
