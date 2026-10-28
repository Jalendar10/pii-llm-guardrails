# IEEE S&P 2027, Cycle 2: anonymous submission package

**Paper:** Sealed Decoding: Encrypting PII Inside the LLM Generate Loop
**PDF to upload:** [`sealed_decoding_sp2027_anon.pdf`](sealed_decoding_sp2027_anon.pdf)
(12 pages: body pp. 1–11 incl. measured Leakage Evaluation E1–E4, references pp. 11–12, Appendix A Ethics + Appendix B GenAI p. 12)

CFP: https://www.sp2027.ieee-security.org/cfpapers.html
Cycle 2 HotCRP: https://cycle2.sp2027.ieee-security.org/ (**open** as of Oct 28, 2026)

## Deadlines (all AoE = UTC-12, i.e. 6:59:59 AM EST the next day in New York; DST ends Nov 1)

| What | Date |
|---|---|
| Abstract registration (title, abstract, authors, conflicts, topics, **Ethics** and **GenAI** fields) | **Tue Nov 10, 2026** |
| Full paper upload | **Tue Nov 17, 2026** |
| Early-reject notification | Jan 18, 2027 |
| Reviews released / rebuttal due | Feb 11 / Feb 16, 2027 |
| Acceptance notification | Mar 5, 2027 |
| Camera-ready | Apr 8, 2027 |

Rejected papers must wait one year before resubmitting to S&P.

## Format checklist

- [x] `\documentclass[conference,compsoc]{IEEEtran}`, two columns, 10 pt, US letter (612×792 pt)
- [x] Body ≤ 13 pages; total ≤ 18 with references and appendices (current: 11 body, 12 total; rebuilt Oct 28, 2026 with TinyTeX, IEEEtran V1.8b)
- [x] Compiles clean with `latexmk -pdf`: 0 errors, 0 overfull boxes, 0 undefined refs/citations
- [x] All fonts embedded (`pdffonts` shows `emb yes` for every font)
- [x] PDF metadata: Author = "Anonymous" (no username in figure PDFs; matplotlib sets none)
- [x] Measured E1–E4 ported from the USENIX draft (Section 8, Tables 9–13); "proposed evaluation" table removed; every number checked against `eval/results/*.json` (see `SP2027_VALIDATION.md`)

## Double-blind checklist

- [x] Author block: "Anonymous Submission / Paper under double-blind review"; no names, affiliation, email, ORCID
- [x] No acknowledgments or funding section
- [x] GitHub link (`github.com/Jalendar10/...`) replaced by `[Anonymized repository]` (Reproducibility section)
- [x] "Released under Apache-2.0" reworded to future tense + anonymized mirror
- [x] No self-citations (the paper cites no prior work by the author). If one is added, cite in third person.
- [x] `pdftotext` grep for name, university, ORCID, `Jalendar10`, email: no hits
- [x] **Anonymized artifact mirror hosted** on Anonymous GitHub (private source `llm-stream-seal-artifact`; URL only in local `main.tex` / PDF / HotCRP — not committed here). Rebuild PDF after editing `main.tex`.
- [ ] **Mirror lacks `eval/` (E1–E4 scripts + JSON).** A staged, scrubbed update is outside this repo (`papers/tier1-security/sealed-decoding-sp2027/artifact_staged/`). Needs your approval to push to the private source repo **before Nov 17** (CFP: artifacts must not change after the paper deadline).
- [ ] Do not mention the arXiv preprint or the public repo in the S&P PDF or HotCRP fields. Posting to arXiv is allowed by the CFP; avoid widely advertising it during review.

## HotCRP registration (by Nov 10)

- [ ] Create account on the Cycle 2 HotCRP (you, not an agent); link ORCID 0009-0002-5881-0084 — ORCID email must match the HotCRP email, name must match
- [ ] Title, abstract (paste from [`HOTCRP_FIELDS.md`](HOTCRP_FIELDS.md) — the measured E1–E4 abstract; **title/abstract/authors are frozen after registration**), author list *(visible to chairs only)*
- [ ] Topics: Privacy-enhancing technologies; ML – security and privacy of ML systems; Applied cryptography
- [ ] Conflicts of interest (advisors, co-workers at University of the Cumberlands, recent co-authors)
- [ ] **Ethics Considerations** field: paste from [`HOTCRP_FIELDS.md`](HOTCRP_FIELDS.md)
- [ ] **Generative AI usage considerations** field: paste from [`HOTCRP_FIELDS.md`](HOTCRP_FIELDS.md)
- [ ] Declare no simultaneous submission elsewhere (see `../QUEUE.md`). USENIX Security '27 C2 and CCS '27 C1 are blocked while under S&P review, unless early-rejected on Jan 18, 2027
- [ ] Confirm the GenAI field's "Manuscript preparation" sentences are accurate for how AI tools were actually used (code/experiments included) before pasting
- [ ] Upload PDF by Nov 17; re-download from HotCRP and check page count/fonts

## Files

| Path | Purpose |
|---|---|
| `main.tex` | Anonymized source (compsoc), adds Appendix A (Ethics) and B (GenAI) |
| `main.bbl`, `references.bib` | Bibliography (IEEEtran style) |
| `figures/*.pdf` | Vector figures (copied from `../../ieee/figures/`) |
| `generated/` | Table rows, macros, listings (copied from `../../ieee/generated/`) |
| `sealed_decoding_sp2027_anon.pdf` | Compiled submission PDF |
| `HOTCRP_FIELDS.md` | Title, abstract, and text for the HotCRP Ethics and GenAI fields |
| `SP2027_VALIDATION.md` | PASS/FAIL validation against the S&P 2027 Cycle 2 CFP (Oct 28, 2026) |

## Rebuild

```bash
cd paper/submissions/sp2027
latexmk -pdf main.tex && cp main.pdf sealed_decoding_sp2027_anon.pdf && latexmk -c && rm main.pdf
```

If the main paper in `paper/ieee/` changes, re-copy `figures/` and `generated/` and re-apply the anonymization diff (`diff ../../ieee/main.tex main.tex`).
