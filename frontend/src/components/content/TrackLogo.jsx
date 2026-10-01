/** Compact language marks for track cards — calm monograms, not stock icons. */

const SIZE = { sm: 28, md: 40, lg: 48 };

export default function TrackLogo({ slug, color = "var(--accent)", size = "md", title }) {
  const px = SIZE[size] || SIZE.md;
  const label = title || slug;
  const common = {
    width: px,
    height: px,
    viewBox: "0 0 40 40",
    role: "img",
    "aria-label": label,
    className: "track-logo",
  };

  if (slug === "bash") {
    return (
      <svg {...common}>
        <rect width="40" height="40" rx="10" fill={color} fillOpacity="0.18" />
        <path
          d="M8 12h24v16H8z"
          fill="none"
          stroke={color}
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <path d="M12 18l4 2-4 2" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
        <path d="M18 24h8" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (slug === "python") {
    return (
      <svg {...common}>
        <rect width="40" height="40" rx="10" fill={color} fillOpacity="0.18" />
        <path
          d="M20 8c-4.5 0-6 2-6 5.5V16h7v1.5H12.5C9 17.5 7 20 7 24s2 6.5 5.5 6.5H16V26h-2.2c-1.6 0-2.8-1-2.8-2.5S12.2 21 13.8 21H21c2.4 0 4-1.4 4-3.8V13.5C25 10 23 8 20 8zm-2.2 2.4c.8 0 1.4.6 1.4 1.4s-.6 1.4-1.4 1.4-1.4-.6-1.4-1.4.6-1.4 1.4-1.4z"
          fill={color}
        />
        <path
          d="M20 32c4.5 0 6-2 6-5.5V24h-7v-1.5h8.5C31 22.5 33 20 33 16s-2-6.5-5.5-6.5H24V14h2.2c1.6 0 2.8 1 2.8 2.5S27.8 19 26.2 19H19c-2.4 0-4 1.4-4 3.8v3.7C15 30 17 32 20 32zm2.2-2.4c-.8 0-1.4-.6-1.4-1.4s.6-1.4 1.4-1.4 1.4.6 1.4 1.4-.6 1.4-1.4 1.4z"
          fill={color}
          fillOpacity="0.75"
        />
      </svg>
    );
  }
  if (slug === "go") {
    return (
      <svg {...common}>
        <rect width="40" height="40" rx="10" fill={color} fillOpacity="0.18" />
        <text
          x="20"
          y="26"
          textAnchor="middle"
          fontFamily="JetBrains Mono, ui-monospace, monospace"
          fontSize="16"
          fontWeight="600"
          fill={color}
        >
          Go
        </text>
      </svg>
    );
  }
  if (slug === "javascript") {
    return (
      <svg {...common}>
        <rect width="40" height="40" rx="10" fill={color} fillOpacity="0.18" />
        <text
          x="20"
          y="27"
          textAnchor="middle"
          fontFamily="JetBrains Mono, ui-monospace, monospace"
          fontSize="15"
          fontWeight="700"
          fill={color}
        >
          JS
        </text>
      </svg>
    );
  }
  if (slug === "sql") {
    return (
      <svg {...common}>
        <rect width="40" height="40" rx="10" fill={color} fillOpacity="0.18" />
        <path
          d="M10 13h20v4H10zm0 7h20v4H10zm0 7h12v4H10z"
          fill="none"
          stroke={color}
          strokeWidth="1.7"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <rect width="40" height="40" rx="10" fill={color} fillOpacity="0.18" />
      <circle cx="20" cy="20" r="7" fill="none" stroke={color} strokeWidth="1.8" />
    </svg>
  );
}
