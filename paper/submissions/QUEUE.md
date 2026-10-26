# Venue queue: Sealed Decoding

**Rule: do NOT dual-submit.** S&P 2027 forbids simultaneous submission to any other
venue with proceedings or to a journal (automatic rejection), and IEEE TDSC, IEEE TIFS,
and PoPETs have the same rule. Submit to the next venue only after the S&P decision is
final (rejection, or withdrawal in writing via HotCRP). An arXiv preprint is not a
submission and may stay up throughout.

## Current

| # | Venue | Package | Deadline | Status |
|---|---|---|---|---|
| 0 | arXiv (cs.CR, cross-list cs.CL) | `arxiv/` | any time | **blocked:** pending endorsement for cs.CR (endorsement code HXYQ3N; email to jmaligireddy48581@ucumberlands.edu) |
| 1 | IEEE S&P 2027, Cycle 2 | `sp2027/` | abstract Nov 10, 2026; paper Nov 17, 2026 (AoE) | package ready; anonymized artifact mirror prepared (see `sp2027/ANON_MIRROR.md`), not yet hosted; Cycle 2 HotCRP still TBA |

S&P Cycle 2 timeline: early reject Jan 18, 2027; final decision Mar 5, 2027.

**Next action:** submit to S&P Cycle 2 (register abstract, then upload PDF) as soon as the
Cycle 2 HotCRP opens. Host the anonymized artifact first (`sp2027/ANON_MIRROR.md`).

_Status updated Oct 25, 2026._

## Next, only after the S&P decision

| # | Venue | Submit at | Deadline / notes |
|---|---|---|---|
| 2 | IEEE TDSC, Special Issue (Transactions on Dependable and Secure Computing) | https://ieee.atyponrex.com/journal/tdsc-cs (Atypon ReX; legacy: https://mc.manuscriptcentral.com/tdsc-cs) | SI deadline **Jan 15, 2027**. This falls *before* the S&P early-reject date (Jan 18, 2027), so the SI is only usable if the S&P submission is formally withdrawn first. Otherwise use the regular TDSC track after the Mar 5, 2027 decision. |
| 3 | IEEE TIFS (Transactions on Information Forensics and Security) | https://mc.manuscriptcentral.com/tifs-ieee | Rolling. Journal format (`IEEEtran` journal, single-blind). Expand evaluation (Table IX items) first. |
| 4 | PoPETs (Proceedings on Privacy Enhancing Technologies) | https://submit.petsymposium.org | Four quarterly deadlines; check the current year's CFP. Double-blind, own template (not IEEEtran). |

## Notes for re-targeting

- S&P reviews are confidential; address them in the revision but do not quote them.
- Journals (TDSC, TIFS) expect substantially more evaluation: run the proposed leak-rate,
  detector-recall, utility, and adaptive-attack experiments (paper Table IX) and Qwen3-8B.
- Track each submission here with date, venue, ID, and outcome before starting the next.
