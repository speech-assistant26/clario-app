import { useEffect, useState } from "react";
import WaveformChart from "./WaveformChart.jsx";
import PhonemeList from "./PhonemeList.jsx";
import ScoreRing from "./ScoreRing.jsx";
import WordList from "./WordList.jsx";

// Full result for one attempt — used for a fresh analysis and for an attempt
// re-opened from history (same response shape).
export default function ResultView({ result, audioUrl, children }) {
  const sentence = result.mode === "sentence";
  const [selected, setSelected] = useState(null);

  useEffect(() => setSelected(null), [result]);

  const shownPhonemes =
    sentence && selected != null
      ? result.phonemes.filter((p) => p.word_index === selected)
      : result.phonemes;
  const selectedWord = sentence && selected != null ? result.words[selected] : null;

  return (
    <section className="card result-card">
      {result.word_warning && <p className="warning">{result.word_warning}</p>}
      <div className="result-head">
        {sentence ? (
          <div className="rings">
            <ScoreRing
              accuracy={result.word_accuracy ?? 0}
              label="words"
              caption={`${result.n_words_correct}/${result.n_words} words correct`}
            />
            {/* All phonemes, or just the focused word's. */}
            <ScoreRing
              accuracy={selectedWord ? selectedWord.accuracy ?? 0 : result.accuracy}
              nErrors={selectedWord ? selectedWord.n_errors : result.n_errors}
              nPhonemes={selectedWord ? selectedWord.n_phonemes : result.n_phonemes}
              label={selectedWord ? "word" : "phonemes"}
              caption={
                selectedWord
                  ? `“${selectedWord.word}”: ${selectedWord.n_phonemes - selectedWord.n_errors}/${selectedWord.n_phonemes} clear`
                  : undefined
              }
            />
          </div>
        ) : (
          <ScoreRing
            accuracy={result.accuracy}
            nErrors={result.n_errors}
            nPhonemes={result.n_phonemes}
          />
        )}
        <div className="result-meta">
          <h2 className={sentence ? "sentence-title" : ""}>“{result.target_word}”</h2>
          <p className="muted">
            {result.n_phonemes} phonemes · {result.n_errors} flagged · {result.duration_sec}s ·
            threshold {result.error_threshold}
          </p>
          {audioUrl && <audio className="player" controls src={audioUrl} />}
          {children}
        </div>
      </div>

      <WaveformChart
        waveform={result.waveform}
        rate={result.waveform_rate}
        phonemes={result.phonemes}
        duration={result.duration_sec}
        words={sentence ? result.words : null}
        selectedWord={selected}
      />

      {sentence && (
        <>
          <h3 className="section-title">Words</h3>
          <WordList words={result.words} selected={selected} onSelect={setSelected} />
        </>
      )}

      <h3 className="section-title">
        Phoneme breakdown
        {sentence && (selectedWord ? ` — “${selectedWord.word}”` : " — tap a word to focus")}
      </h3>
      <PhonemeList phonemes={shownPhonemes} />
    </section>
  );
}
