# IEEE S&P 2027, Cycle 2: anonymous submission package

**Paper:** Sealed Decoding: Encrypting PII Inside the LLM Generate Loop
**PDF to upload:** [`sealed_decoding_sp2027_anon.pdf`](sealed_decoding_sp2027_anon.pdf)
(10 pages: body pp. 1–9, references p. 9, Appendix A Ethics + Appendix B GenAI pp. 9–10)

CFP: https://www.sp2027.ieee-security.org/cfpapers.html
Cycle 2 HotCRP: **TBA** (Cycle 1 was https://cycle1.sp2027.ieee-security.org/; expect `cycle2.sp2027.ieee-security.org`)

## Deadlines (all AoE = UTC-12, i.e. 7:59:59 AM EST the next day in New York)

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
- [x] Body ≤ 13 pages; total ≤ 18 with references and appendices (current: ~8.5 body, 10 total)
- [x] Compiles clean with `latexmk -pdf`: 0 errors, 0 overfull boxes, 0 undefined refs/citations
- [x] All fonts embedded (`pdffonts` shows `emb yes` for every font)
- [x] PDF metadata: Author = "Anonymous" (no username in figure PDFs; matplotlib sets none)

## Double-blind checklist

- [x] Author block: "Anonymous Submission / Paper under double-blind review"; no names, affiliation, email, ORCID
- [x] No acknowledgments or funding section
- [x] GitHub link (`github.com/Jalendar10/...`) replaced by `[Anonymized repository]` (Reproducibility section)
- [x] "Released under Apache-2.0" reworded to future tense + anonymized mirror
- [x] No self-citations (the paper cites no prior work by the author). If one is added, cite in third person.
- [x] `pdftotext` grep for name, university, ORCID, `Jalendar10`, email: no hits
- [x] **Anonymized artifact mirror hosted** on Anonymous GitHub (private source `llm-stream-seal-artifact`; URL only in local `main.tex` / PDF / HotCRP — not committed here). Rebuild PDF after editing `main.tex`.
- [ ] Do not mention the arXiv preprint or the public repo in the S&P PDF or HotCRP fields. Posting to arXiv is allowed by the CFP; avoid widely advertising it during review.

## HotCRP registration (by Nov 10)

- [ ] Create account on the Cycle 2 HotCRP once announced
- [ ] Title, abstract (paste from `../../ABSTRACT.txt`, abstract paragraph only), author list *(visible to chairs only)*
- [ ] Topics: Privacy-enhancing technologies; ML – security and privacy of ML systems; Applied cryptography
- [ ] Conflicts of interest (advisors, co-workers at University of the Cumberlands, recent co-authors)
- [ ] **Ethics Considerations** field: paste from [`HOTCRP_FIELDS.md`](HOTCRP_FIELDS.md)
- [ ] **Generative AI usage considerations** field: paste from [`HOTCRP_FIELDS.md`](HOTCRP_FIELDS.md)
- [ ] Declare no simultaneous submission elsewhere (see `../QUEUE.md`)
- [ ] Upload PDF by Nov 17; re-download from HotCRP and check page count/fonts

## Files

| Path | Purpose |
|---|---|
| `main.tex` | Anonymized source (compsoc), adds Appendix A (Ethics) and B (GenAI) |
| `main.bbl`, `references.bib` | Bibliography (IEEEtran style) |
| `figures/*.pdf` | Vector figures (copied from `../../ieee/figures/`) |
| `generated/` | Table rows, macros, listings (copied from `../../ieee/generated/`) |
| `sealed_decoding_sp2027_anon.pdf` | Compiled submission PDF |
| `HOTCRP_FIELDS.md` | Text for the HotCRP Ethics and GenAI fields |

## Rebuild

```bash
cd paper/submissions/sp2027
latexmk -pdf main.tex && cp main.pdf sealed_decoding_sp2027_anon.pdf && latexmk -c && rm main.pdf
```

If the main paper in `paper/ieee/` changes, re-copy `figures/` and `generated/` and re-apply the anonymization diff (`diff ../../ieee/main.tex main.tex`).
