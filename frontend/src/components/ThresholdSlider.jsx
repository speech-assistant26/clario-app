export const MIN_THRESHOLD = 0.3;
export const MAX_THRESHOLD = 0.7;
export const DEFAULT_THRESHOLD = 0.5;

function label(value) {
  if (value <= 0.4) return "Screening — flags more sounds";
  if (value <= 0.55) return "Balanced";
  return "Precise — stricter cutoff";
}

// Lets the user tune the per-phoneme error-probability cutoff sent with each
// analysis request (see backend CLARIO_ERROR_THRESHOLD / the per-request
// `error_threshold` form field it maps to).
export default function ThresholdSlider({ value, onChange }) {
  return (
    <div className="threshold-field">
      <div className="threshold-head">
        <label className="field-label" htmlFor="threshold" style={{ margin: 0 }}>
          Sensitivity
        </label>
        <span className="threshold-value">{value.toFixed(2)}</span>
      </div>
      <input
        id="threshold"
        type="range"
        min={MIN_THRESHOLD}
        max={MAX_THRESHOLD}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="threshold-range"
      />
      <p className="threshold-label">{label(value)}</p>
    </div>
  );
}
