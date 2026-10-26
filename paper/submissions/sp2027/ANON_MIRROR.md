# Anonymized artifact mirror (IEEE S&P 2027, double-blind)

Status (Oct 25, 2026): **hosted on Anonymous GitHub.** Private source:
`https://github.com/Jalendar10/llm-stream-seal-artifact`. The anonymous reviewer URL
is kept only in the local submission PDF / HotCRP fields (not recorded in this public
file). Available until Apr 25, 2027 (Remove when expired).

## What was built

| Item | Location (local, not committed) |
|---|---|
| Scrubbed tree, fresh git repo (one commit by `Anonymous Author <anonymous@example.com>`, UTC date, no history from this repo) | `/workspace/pii-llm-guardrails-anon/` |
| Zip of that tree (`git archive`, top folder `Anonymized-Repo/`, no `.git`) | `paper/submissions/sp2027/artifact_anon.zip` (kept out of git via `.git/info/exclude`) |

Contents: `python/` (package, tests, demos, requirements), `configs/`, `docs/`, `models/`,
`paper/ieee/{artifacts,scripts,figures,generated}`, the anonymized `sp2027/main.tex` (as
`paper/ieee/main.tex`) with `main.bbl` and `references.bib`, the anonymized PDF
(`paper/sealed_decoding_anon.pdf`), scrubbed `paper/PAPER.md`, `paper/MODEL_CARD.md`,
`paper/ABSTRACT.txt`, a rewritten `README.md`, `ARTIFACT.md` (claims → commands →
expected output), and `LICENSE` (Apache-2.0, unchanged).

Left out: `paper/latex/`, `paper/submissions/` (arXiv package with author block),
`paper/BLOG_OUTLINE.md`, the non-anonymous `paper/ieee/main.tex` and compiled PDFs, and
all git history.

Scrubbing: author name, affiliation, ORCID, personal email (test fixtures now use
`jdoe@example.com`; the hold-back comment in `generate.py` too), the account name in
GitHub URLs (→ `https://anonymous.4open.science/r/Anonymized-Repo`), the repo name and
home paths in pytest logs and artifacts (→ `<repo>`, `/tmp/<tmpdir>`), and the
"preprint"/arXiv status line.

Checks run on the mirror: `pytest -q` 62 passed, 1 skipped; `math_encrypt_rotate_demo.py`
9/9 PASS; `latexmk -pdf main.tex` builds 10 pages with PDF Author = "Anonymous"; a
case-insensitive grep of all text files and `strings` of all PDF/PNG/SVG files for the
author's name, university, ORCID, the account name, the repo name, `gmail`,
`/workspace`, and `/home/` found nothing.

Known residual risk: the package name `piiguard`, the paper title, and distinctive code
can still be searched on GitHub and lead to the public repo. Per the S&P and Anonymous
GitHub guidance, searching for the authors is the reviewer's own deliberate act, but do
not advertise the public repo or the arXiv preprint during review.

## Hosting on Anonymous GitHub (https://anonymous.4open.science/)

Anonymous GitHub proxies an existing GitHub repository; it does not take zip uploads.

1. ~~Create a new **private** GitHub repository~~ — done:
   `Jalendar10/llm-stream-seal-artifact` (private). Do not use the public
   `pii-llm-guardrails` repository or its history.
2. ~~Push the scrubbed tree~~ — done (`Anonymous Author <anonymous@example.com>`,
   single commit on `main`). Do not amend that commit with your own identity.
3. Open https://anonymous.4open.science/, sign in with GitHub, choose **Anonymize**, and
   pick `llm-stream-seal-artifact` / branch `main`.
4. Terms to replace (one per line): your full name and each part of it, your GitHub
   account name, your university's name, your ORCID, your email addresses, and the public
   repository name. Anonymous GitHub replaces each with `XXXX` in file contents, file
   names, and URLs. Nothing in the tree should match; this is a second net.
5. If the form offers an expiration date, set one after the final decision (for example
   Mar 31, 2027). Turn off any option that links back to the original repository. Save. Copy the
   `https://anonymous.4open.science/r/<id>/` link.
6. Open the anonymous link in a private browser window and check `README.md`,
   `ARTIFACT.md`, and a test file for any leak.
7. Put the link in place of `[Anonymized repository]` in `sp2027/main.tex` (Reproducibility
   section), rebuild the PDF, and paste it into the HotCRP artifact field if there is one.
   Do **not** record the anonymous link in this public repository: it would connect the
   anonymous artifact to this account.

Alternative: GitFront (https://gitfront.io) also mirrors a GitHub repository by link and
needs an account. If neither is wanted, upload `artifact_anon.zip` as supplementary
material in HotCRP, if the Cycle 2 form allows it.

## Rebuild the mirror

If code or artifacts change before submission, rebuild the scrubbed tree, re-run the
checks above, make a new single anonymous commit, and regenerate the zip:

```bash
cd /workspace/pii-llm-guardrails-anon
git archive --format=zip --prefix=Anonymized-Repo/ \
  -o /workspace/pii-llm-guardrails/paper/submissions/sp2027/artifact_anon.zip HEAD
```
