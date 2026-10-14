/** The iceberg-and-penguin mark from the design header (also public/favicon.svg). */
export function LogoMark({ size = 38 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <polygon points="11,42.5 37,42.5 33,46.5 15,46.5" fill="#6FB8E3" opacity="0.45" />
      <polygon points="9,40 15,30 33,30 39,40" fill="#DDF1FB" />
      <polygon points="33,30 39,40 29,40" fill="#9ED6F1" />
      <polygon points="9,40 15,30 33,30 39,40" fill="none" stroke="#174E78" strokeWidth="1.4" strokeLinejoin="round" />
      <line x1="4" y1="41" x2="44" y2="41" stroke="#2F7FB9" strokeWidth="1.6" strokeLinecap="round" />
      <g transform="translate(24,30.5) scale(0.27)">
        <ellipse cx="-62" cy="-6" rx="9" ry="6" fill="#F2A33A" stroke="#12202B" strokeWidth="5" />
        <path d="M -58 -2 C -66 -30 -40 -60 2 -60 C 44 -60 68 -40 66 -18 C 64 0 48 2 0 2 C -36 2 -54 4 -58 -2 Z" fill="#2B3A47" stroke="#12202B" strokeWidth="6" strokeLinejoin="round" />
        <ellipse cx="34" cy="-28" rx="22" ry="17" fill="#FFFFFF" />
        <path d="M 24 -33 Q 30 -27 36 -33" fill="none" stroke="#12202B" strokeWidth="5" strokeLinecap="round" />
        <path d="M 38 -26 Q 43 -14 48 -26 Z" fill="#F2A33A" stroke="#12202B" strokeWidth="3.5" strokeLinejoin="round" />
      </g>
    </svg>
  );
}
