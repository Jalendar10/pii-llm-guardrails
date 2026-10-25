# LaTeX source: Sealed Decoding

**Sealed Decoding: Encrypting PII Inside the LLM Generate Loop**
Jalendar Reddy Maligireddy, University of the Cumberlands (ORCID 0009-0002-5881-0084)

> **Superseded.** The canonical, IEEE-formatted version (IEEEtran conference, 9 pages, 5 figures,
> user I/O examples and measured costs) is in [`../ieee/`](../ieee/) and is what
> [`../sealed_decoding.pdf`](../sealed_decoding.pdf) now contains. This folder keeps the earlier
> single-column `article` version (11 pages) for reference; its PDF is [`sealed_decoding.pdf`](sealed_decoding.pdf).
The Markdown version of the same paper is [`../PAPER.md`](../PAPER.md).

## Files

| File | Purpose |
|---|---|
| `main.tex` | Full paper, single file (`article`, 11pt, 1in margins, Times) |
| `references.bib` | BibTeX for every citation in `main.tex` (10 entries) |
| `main.bbl` | Pre-built bibliography, so arXiv does not need to run BibTeX |
| `figures/pipeline.pdf` | Figure 1, vector PDF converted from `../figures/pipeline.svg` |
| `figures/pipeline.png` | Raster fallback of Figure 1 (not used by `main.tex`) |
| `sealed_decoding.pdf` | Compiled output |

## Compile

Needs a standard TeX Live install (`texlive-latex-base`, `texlive-latex-recommended`,
`texlive-latex-extra`, `texlive-fonts-recommended`, `latexmk`). No network access or
custom class files are needed.

```bash
cd paper/latex
latexmk -pdf main.tex
# or, by hand:
pdflatex main && bibtex main && pdflatex main && pdflatex main
cp main.pdf sealed_decoding.pdf   # do not overwrite ../sealed_decoding.pdf (that is the IEEE build)
```

`latexmk -C` removes build files.

To regenerate the figure from the SVG: `rsvg-convert -f pdf -o figures/pipeline.pdf ../figures/pipeline.svg`.

## arXiv upload

- Primary category: **cs.CR** (Cryptography and Security). Cross-list: **cs.CL** (Computation and Language).
- `main.tex` starts with `\pdfoutput=1`, so arXiv builds with pdfLaTeX.
- Build the upload bundle:

  ```bash
  cd paper/latex
  latexmk -pdf main.tex   # refreshes main.bbl
  tar czf arxiv.tar.gz main.tex main.bbl references.bib figures/pipeline.pdf
  ```

- Upload `arxiv.tar.gz`. arXiv uses `main.bbl` directly; `references.bib` is included for reference.
- License suggestion: CC BY 4.0 for the paper (code is Apache-2.0).
- Do not include `sealed_decoding.pdf` in the arXiv bundle; arXiv compiles its own.
