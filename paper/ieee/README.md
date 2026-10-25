# IEEE version: Sealed Decoding

**Sealed Decoding: Encrypting PII Inside the LLM Generate Loop**
Jalendar Reddy Maligireddy, University of the Cumberlands, Williamsburg, KY, USA
(ORCID [0009-0002-5881-0084](https://orcid.org/0009-0002-5881-0084))

This is the canonical version of the paper: `IEEEtran` conference class, two columns,
US letter, 9 pages including references. Compiled PDF:
[`sealed_decoding_ieee.pdf`](sealed_decoding_ieee.pdf) (same file as
[`../sealed_decoding.pdf`](../sealed_decoding.pdf)).

## What is in the paper

Figures (all vector, black and white, made by `scripts/make_figures.py`):

| Fig. | File | Content |
|---|---|---|
| 1 | `figures/fig_pipeline.pdf` | Request path: injection scan, generate loop, `EncryptedGenerator`, registry check, client |
| 2 | `figures/fig_keyring.pdf` | Password → Argon2id KEK → wrapped DEK → AES-256-GCM seals; rotation rewraps the DEK |
| 3 | listing | A real SSN token from the healthcare run and its decoded header |
| 4 | `figures/fig_decision.pdf` | Per-chunk decision flow in `on_token` |
| 5 | `figures/fig_timeline.pdf` | When PII reaches the wire: raw vs. sealed stream, measured chunk times |
| 6 | listing | Verbatim terminal session: init, run, decrypt, wrong password |
| 7 | `figures/fig_latency.pdf` | Measured cost: crypto micro-benchmarks and raw vs. sealed generation |

Tables: placement of guards (I), attackers (II), tests by area 62/1 (III), crypto demo
9/9 (IV), Qwen3-0.6B 7/7 over three runs (V), user prompt → sealed output → decrypt →
wrong password (VI), cost of sealing (VII), chunk trace raw vs. sealed (VIII),
proposed evaluation, not yet run (IX).

Every number, token, and transcript comes from files in `artifacts/`. Nothing in the
paper is typed in by hand: `scripts/gen_tex.py` turns the artifacts into
`generated/*.tex` and `generated/*.txt`, which `main.tex` includes.

## Files

| Path | Purpose |
|---|---|
| `main.tex` | Paper source (`\documentclass[conference]{IEEEtran}`, `\pdfoutput=1`) |
| `references.bib`, `main.bbl` | Bibliography (`IEEEtran` style); `main.bbl` is kept so a build without BibTeX works |
| `figures/` | Vector PDFs used by `main.tex`, plus PNG previews |
| `generated/` | Table rows, macros, listings written by `scripts/gen_tex.py` |
| `artifacts/` | Raw outputs: `pytest_v.txt`, `math_demo.txt`, `qwen06b_run{1,2,3}.txt`, `measurements.json`, `timeline.json`, `examples/*.json` |
| `scripts/capture_examples.py` | Runs four synthetic prompts through the real CLI on Qwen3-0.6B, decrypts with right and wrong passwords |
| `scripts/measure.py` | Crypto micro-benchmarks, raw vs. sealed streaming (5 runs), chunk timeline, CLI cost |
| `scripts/make_figures.py` | Draws the figures (matplotlib) |
| `scripts/gen_tex.py` | Writes `generated/` from `artifacts/` |

## Compile

Needs TeX Live with `texlive-publishers` (for `IEEEtran.cls` / `IEEEtran.bst`),
`texlive-latex-extra`, `texlive-fonts-recommended`, and `latexmk`.

```bash
cd paper/ieee
latexmk -pdf main.tex
cp main.pdf sealed_decoding_ieee.pdf && cp main.pdf ../sealed_decoding.pdf
latexmk -c          # remove build files, keep main.bbl
```

To rebuild figures and generated tables from the stored artifacts (needs `matplotlib`):

```bash
cd paper/ieee
python scripts/make_figures.py && python scripts/gen_tex.py && latexmk -pdf main.tex
```

To re-measure from scratch (needs `torch`, `transformers`, and Qwen/Qwen3-0.6B in the
Hugging Face cache; times will differ on other hardware):

```bash
# from the repo root
cd python && python -m pytest -v > ../paper/ieee/artifacts/pytest_v.txt; cd ..
PYTHONPATH=python python paper/ieee/scripts/measure.py
PYTHONPATH=python python paper/ieee/scripts/capture_examples.py
```

## IEEE submission checklist

- [x] `IEEEtran` conference class, two columns, US letter, 10 pt
- [x] Title, author name, affiliation, email, ORCID in the IEEE author block
- [x] Abstract (no citations, no math) and `IEEEkeywords`
- [x] Figure captions below figures; TABLE captions above tables (IEEE small caps style)
- [x] Figures vector PDF, black and white, readable at column width
- [x] References in `IEEEtran` BibTeX style, numbered in order of citation
- [x] Last page columns balanced (`\balance`)
- [x] All fonts embedded (`pdffonts sealed_decoding_ieee.pdf` shows `emb yes` for every font)
- [x] No overfull boxes, undefined references, or LaTeX errors in `main.log`
- [x] `\pdfoutput=1` so arXiv and IEEE PDF eXpress build with pdfLaTeX
- [x] Proposed experiments labeled "Proposed" (Table IX); no benchmark numbers claimed
- [ ] Check the target venue's page limit and whether it wants a blind version (remove the author block and the GitHub link)
- [ ] Add the venue's copyright notice line once accepted (`\IEEEoverridecommandlockouts` + `\IEEEpubid`)
- [ ] Run the final PDF through IEEE PDF eXpress if the venue requires it

## Known limits stated in the paper

Detector covers EMAIL, PHONE, SSN, IP only (the patient name in Table VI stays plaintext).
The model's arithmetic in the account example is wrong (says 10 months; correct is 100);
sealing does not fix model errors. The paraphrased injection gets past the regex scan
and is stopped by response validation. Timings are from one 8-vCPU CPU host.
