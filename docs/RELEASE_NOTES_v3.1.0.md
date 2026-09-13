# emgteach 3.1.0 — the practical in the classroom

A minor release about handling. What the application measures is unchanged;
what changes is how it is used at a laboratory bench by a student who has not
seen it before: the fragment editor becomes a procedure that says which step
it is on, a second launch no longer opens a second copy, saving never fails on
a missing folder, and the guided tour and a printed sheet show where the
electrodes go and what the calibration asks for.

## The fragment editor, step by step

- **Three steps, named over the plot**: the sensitivity, each contraction in
  turn, and «Use these fragments». A yellow line says what the current step
  asks for and how many rows have been reviewed, and a «?» on the editor
  repeats the procedure.
- **A counter against the protocol**: «FCR: 5 / 6» beside the sensitivity —
  six flexions, six extensions and one grip in the agonist/antagonist
  practical, editable when a series is repeated. A missing contraction shows
  in amber before it can become a wrong co-activation index.
- **Candidates under the threshold**, drawn dotted: a click makes one a row,
  so every mark sits on activity the threshold located and none is placed by
  hand.
- **Each row edited where it stands**: ◀ ▶ or a click on the plot selects it;
  «Keep it», «Drop it» and «Split it» act on it, one button per muscle
  corrects who led it, and a mark can be dragged onto nearby activity.
  Splitting is offered only where the envelopes show two peaks with a valley
  between them.
- **The sensitivity is set per practical and is part of the result**: k = 4.4
  in the agonist/antagonist practical and 3.0 in the others, written into the
  report's «Configuration used» table and into the CSV header.

## At the bench

- **One running copy.** A second launch hands the focus to the window already
  open and exits, instead of competing for the same Bluetooth port and the
  same recording; the packaged application shows a splash image from the
  first second.
- **Saving into a folder that no longer exists** creates it, and recordings go
  to Documents until another folder is chosen.
- **The guided tour shows the electrodes and the calibration** as pictures in
  the agonist/antagonist practical, in the application's colour key — first
  muscle blue, second red — in English and Spanish.
- **A sheet for each laboratory station**: the agonist/antagonist practical on
  one landscape A4, to print and laminate, in `docs/hoja-puesto/`.
- **Screenshots without leaving the recording**: F12 from any tab, and an
  «Auto» mode that saves one picture every three seconds while a recording
  runs, each named after the recording it belongs to.
- **The phones get the PDF report first**, and the broadcast says when no
  phone can reach it: no network interface, or nobody connected after ninety
  seconds.

## Fixed

The live envelope no longer leaves its axes; the editor's pressed buttons are
readable on Windows; rows that touch are kept apart, so the editor can no
longer show a contraction more than was analysed; the calibration's help text
is written from the constants the wizard runs, and the guides no longer
describe efforts held for four seconds; «Save tuned EDF…» is offered in every
practical once fragments have been chosen.

## Meta

- Bumped to 3.1.0 (`pyproject.toml`, `__init__`, `.zenodo.json`,
  `CITATION.cff`).
- The rows proposed for an agonist/antagonist recording, and the
  co-activation windows read off them, can differ from those 3.0.0 proposed
  for the same file, because the detection sensitivity above changed.
- Runs on Windows/macOS/Linux with Python 3.10–3.12; **1064 automated
  tests**; GPL-3.0-or-later.
- The version-specific Zenodo DOI is to be minted at release.
