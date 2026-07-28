# Clario thesis — LaTeX source

Full dissertation source for *Phoneme-Level Pronunciation Error Detection in
Dysarthric Speech Using a Control-Baseline Labelling Strategy and a CNN–BiLSTM
Classifier*.

## Before you build

Open [settings/thesis-info.tex](settings/thesis-info.tex) and replace every
value marked `TODO` (name, index number, supervisor, degree, department,
faculty, university). Nothing else in the document hard-codes those details —
they are all read from that one file.

## Build

Engine is **pdfLaTeX** (IPA symbols are typeset with the `tipa` package, so
XeLaTeX/LuaLaTeX are *not* required and are not configured).

```bash
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

or, if you have it:

```bash
latexmk -pdf main.tex
```

Overleaf: upload the whole `thesis/` folder, set the compiler to **pdfLaTeX**
and the main document to `main.tex`.

## Build status (verified)

Built clean with MiKTeX 25.12 / pdfTeX 4.23 on Windows:

```
errors       : NONE
undefined    : NONE  (all refs and all 37 citations resolve)
rerun needed : no
overfull hbox: 8   (largest 3.5pt — cosmetic)
Type 3 fonts : 0   (everything embedded as Type 1)
pages        : 112
figures      : 13
tables       : 22
```

## Package requirements

All from a standard TeX Live / MiKTeX installation:
`geometry`, `setspace`, `fancyhdr`, `titlesec`, `tipa`, `booktabs`, `tabularx`,
`caption`, `float`, `enumitem`, `listings`, `tikz`, `pgfplots`, `url`,
`hyperref`, `amsmath`, `graphicx`, `xcolor`, `lmodern`.

`IEEEtran.bst` is needed for the bibliography style (ships with the `IEEEtran`
package).

### If IPA glyphs come out as bitmaps (MiKTeX only)

MiKTeX's `tipa` package installs its font map to the legacy path
`<miktex>/dvips/tipa/tipa.map`, which is **not** on the map search path, so
`updmap` silently skips it and pdfTeX falls back to Type 3 bitmap fonts for
every IPA character. Fix once, per machine:

```powershell
$mk = "$env:LOCALAPPDATA\Programs\MiKTeX"
New-Item -ItemType Directory -Force "$mk\fonts\map\dvips\tipa" | Out-Null
Copy-Item "$mk\dvips\tipa\tipa.map" "$mk\fonts\map\dvips\tipa\tipa.map" -Force
initexmf --update-fndb
initexmf --mkmaps
```

Verify with `kpsewhich tipa.map` (should print a path) and `pdffonts main.pdf`
(should show no `Type 3`). TeX Live is unaffected.

### Known cosmetic limitation

TIPA's T3 encoding carries no ToUnicode map, so copying an IPA character out of
the PDF yields the wrong codepoint (`/ɾ/` copies as `/R/`). This affects
copy-paste and full-text search of IPA symbols only — the glyphs themselves
render and print correctly as embedded Type 1 outlines. This is inherent to
`tipa` under pdfLaTeX; avoiding it would mean switching to XeLaTeX with a
Unicode IPA font such as Doulos SIL.

## Figures

There are **no external image files**. Every figure is drawn in TikZ/pgfplots
directly in the chapter source, so the document is fully self-contained and
nothing can go missing. Plot data (training curves, architecture comparison,
per-phoneme error rates, confusion matrix) is inlined as literal coordinates.

## Layout

```
thesis/
├── main.tex                    # your skeleton + two \phantomsection lines
│                               # (without them the REFERENCES / APPENDICES
│                               #  TOC links jump to the wrong page)
├── references.bib              # 34 entries, IEEEtran style
├── settings/
│   ├── preamble.tex            # packages, page style, IPA mappings, TikZ styles
│   └── thesis-info.tex         # >>> FILL IN THE TODOs HERE <<<
├── frontmatter/                # cover, title, declaration, abstract, dedication,
│                               # acknowledgement, abbreviations
├── chapters/
│   ├── chapter1-introduction.tex
│   ├── chapter2-literature-review.tex
│   ├── chapter3-methodology.tex          # Method 1 vs Method 2 labelling
│   ├── chapter4-analysis-design.tex
│   ├── chapter5-implementation-testing.tex
│   ├── chapter6-results-evaluation.tex   # all measured results
│   └── chapter7-conclusion.tex
└── appendices/
    └── appendix-a.tex          # config reference, code listings, full tables
```

## Where the numbers come from

| Figure / table | Source |
|---|---|
| Dataset statistics, deviation range, cutoff, mel mean/std | `notebooks/phoneme-error-detection.ipynb` cell 5 output |
| Layer table, parameter counts | notebook cell 6 `model.summary()` |
| Training curves (12 epochs) | notebook cell 6 fit log |
| Classification report, accuracy 71.99% | notebook cell 7 output |
| Confusion matrix cells | derived from the cell-7 report (accuracy + per-class recall + support); the four values are the unique solution |
| Per-phoneme error rates | notebook cell 7 `per_phoneme_error_rates` output |
| Architecture comparison (5 models) | your separate comparison experiment |
| Qualitative "shift" example | notebook cell 9 output |
| Config parameters, API schema, pipeline code | `backend/app/*.py` |

## Two things to check before submitting

1. **Section 6.5.4 "Note on evaluation protocol"** states that the
   five-architecture comparison was evaluated on a *class-balanced* set, which
   is the only reading consistent with its 71.61% error precision alongside the
   0.32 error precision measured on the natural 15/85 held-out split. If your
   comparison actually used a different protocol, correct that subsection —
   everything else follows from it.
2. **Limitation L2** (Section 6.13) records that the held-out split was also
   passed to Keras as `validation_data`, so early stopping saw the test set.
   That is what the notebook does; it is stated openly rather than hidden. Keep
   it unless you re-run with a three-way split.
