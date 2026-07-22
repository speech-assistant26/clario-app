// Clario's brand mark: a small waveform badge, used in the header, favicon,
// and PWA manifest (see index.html / public/manifest.webmanifest for the
// data-URI copies of this same shape).
export default function Logo({ size = 32 }) {
  return (
    <svg
      className="logo-mark"
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Clario logo"
    >
      <defs>
        <linearGradient id="clarioLogoGrad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366f1" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#clarioLogoGrad)" />
      <rect x="9" y="17" width="4" height="6" rx="2" fill="white" opacity="0.85" />
      <rect x="15" y="12" width="4" height="16" rx="2" fill="white" />
      <rect x="21" y="8" width="4" height="24" rx="2" fill="white" />
      <rect x="27" y="14" width="4" height="12" rx="2" fill="white" opacity="0.85" />
    </svg>
  );
}
