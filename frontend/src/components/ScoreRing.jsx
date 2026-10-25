// Circular score gauge (0–100%), colored by band. Defaults to phoneme clarity;
// sentence mode passes label="words" and its own caption.
export default function ScoreRing({ accuracy, nErrors, nPhonemes, label = "clarity", caption }) {
  const pct = Math.round(accuracy * 100);
  const r = 52;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  const color = pct >= 85 ? "#22c55e" : pct >= 60 ? "#f59e0b" : "#f43f5e";

  return (
    <div className="score-ring">
      <svg viewBox="0 0 130 130" width="130" height="130">
        <circle cx="65" cy="65" r={r} fill="none" stroke="rgba(148,163,184,0.2)" strokeWidth="12" />
        <circle
          cx="65"
          cy="65"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          transform="rotate(-90 65 65)"
        />
        <text x="65" y="60" textAnchor="middle" className="ring-pct" fill={color}>
          {pct}%
        </text>
        <text x="65" y="82" textAnchor="middle" className="ring-label">
          {label}
        </text>
      </svg>
      <p className="score-sub">
        {caption ?? `${nPhonemes - nErrors}/${nPhonemes} phonemes clear`}
      </p>
    </div>
  );
}
