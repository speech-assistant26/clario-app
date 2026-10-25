// Sentence-mode word tiles: one per target word, green when correct, red when
// not, grey when it couldn't be scored. Tapping a tile selects that word so
// its phoneme breakdown (and waveform span) can be shown.
export default function WordList({ words, selected, onSelect }) {
  return (
    <div className="word-list">
      {words.map((w) => {
        const state = w.correct == null ? "na" : w.correct ? "ok" : "err";
        const pct = w.accuracy == null ? "–" : `${Math.round(w.accuracy * 100)}%`;
        return (
          <button
            key={w.index}
            type="button"
            className={`word-tile ${state} ${selected === w.index ? "selected" : ""}`}
            onClick={() => onSelect(selected === w.index ? null : w.index)}
            title={
              w.heard === false
                ? "Speech recognition didn't pick this word up — it may have been skipped, so it isn't counted as correct."
                : undefined
            }
          >
            <span className="word-text">{w.word}</span>
            <span className="word-score">
              {pct}
              {w.heard === false && <span className="word-flag"> · not heard</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
