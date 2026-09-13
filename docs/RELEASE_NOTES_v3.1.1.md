# emgteach 3.1.1 — the co-activation of a named window is read on the uncut recording

A patch on one measurement. Choosing fragments in the analysis tab
concatenated them into one signal, and the co-activation table was read off
that signal. The index subtracts from each muscle its resting level — the 10th
percentile of the analysed signal — and a signal made only of contractions has
no rest left in it: its 10th percentile is the quietest the muscle got *while
working*. For the antagonist that is its own share of the other muscle's
manoeuvre, and subtracting it punishes the small signal most, which is the
signal the agonist/antagonist practical is about.

## Fixed

- **A named fragment is a window read where it lies, with the resting level
  of the whole recording phase.** The envelopes of both muscles are computed
  once over the recording phase uncut; each named fragment is a mask over
  them; the resting level is the 10th percentile of that whole phase, the
  definition the table already used when no fragments are chosen, so both
  routes now subtract the same zero. Consecutive fragments of one name are
  still
  one window, an unnamed fragment still opens none, and a window's seconds
  are now those of the recording phase — as in an analysis without fragments
  — rather than of the concatenated signal.
- On the report's example recording, the row the fragment editor proposes
  for the grip read 58 % with the extensor at 6.3 % MVC; it reads 75 % and
  10.9 %.
- `tools/figura6.py` reads its `--ventana` windows through the same
  function, so the figure and the application cannot disagree. The tool
  used to take each window's resting level from the window itself; through
  the shared function its means move by up to 0.3 % MVC and its indices by
  up to 0.7 points.

## Unchanged, on purpose

The spectrum, the per-segment RMS and MDF, the fatigue fit and the
contraction table still run on the concatenated fragments. The fatigue fit
needs one-second segments over the contractions in order, and a series of
brief efforts has no segment that fits inside a single fragment; on both
example recordings the verdict is the same either way. A derived («tuned»)
recording is a concatenation on disk and is read as such. Nothing in the
interface moves.

## Meta

- Bumped to 3.1.1 (`pyproject.toml`, `__init__`, `.zenodo.json`,
  `CITATION.cff`).
- New `coactivation_by_fragments` in `emgteach.coactivation`;
  `tests/test_coactivation_sin_recortar.py`, with the acceptance test on the
  example recording. **1074 automated tests.**
- The version-specific Zenodo DOI is to be minted at release.
