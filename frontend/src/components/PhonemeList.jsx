// Per-phoneme breakdown: one row per aligned phoneme with its error probability
// rendered as a small meter. Errors are red, correct sounds green.
export default function PhonemeList({ phonemes }) {
  return (
    <div className="phoneme-list">
      {phonemes.map((p, i) => {
        const pct = Math.round(p.error_prob * 100);
        const isErr = p.verdict === "ERROR";
        return (
          <div key={i} className={`phoneme-row ${isErr ? "err" : "ok"}`}>
            <span className="phoneme-sym">{p.phoneme}</span>
            <div className="phoneme-bar-wrap">
              <div className="phoneme-bar" style={{ width: `${pct}%` }} />
            </div>
            <span className="phoneme-prob">{pct}%</span>
            <span className={`phoneme-badge ${isErr ? "err" : "ok"}`}>
              {isErr ? "error" : "clear"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
