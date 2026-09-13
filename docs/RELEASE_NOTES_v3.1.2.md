# emgteach 3.1.2 — the calibration is a brief, explosive maximal jerk

A patch on what the calibration asks the subject to do, and on the text that
describes it. Nothing that is computed changes: no calculation, threshold or
default value is touched.

## Changed

- **The calibration asks for a brief, explosive maximal jerk, not a sustained
  push against something fixed.** A surface electrode on the forearm sees the
  compartment beneath it, finger flexors or extensors included, and a
  reference is only a yardstick if it recruits the same muscle mass as the
  task. The agonist/antagonist task includes a grip: clenching the fist brings
  in the finger flexors, whereas a push of the wrist leaves them out and,
  because the forearm has to be braced, switches on the antagonist as well.
- In the agonist/antagonist practical the wizard names each channel's gesture
  during the countdown: wrist flexion with the fist clenched with all one's
  strength for the flexor, wrist extension with the hand open and the fingers
  stretched out as far as they go for the extensor. The single-muscle and
  kinematics practicals, whose muscle may be the biceps, give the general
  rule.
- The same wording replaces «against something that cannot move» in the
  not-a-maximum warnings of the wizard, the analysis summary and the PDF
  report, in the MVC tab's introduction, in the calibration and
  force-velocity help, in the guided tour's calibration picture and the
  station sheet, and in the manuals, practical guides, cheat sheets, rubric
  and electrode-placement guide.
- **Releases carry the source only.** No pre-built Windows executable is
  attached to them: an unsigned one-file PyInstaller build is often flagged by
  antivirus software when it is downloaded. `packaging/emgteach.spec` still
  builds it, locally or on demand in CI.

## Fixed

- **The documentation describes the MVC reference as the code computes it.**
  Each calibration repetition is worth the highest 0.2 s running mean of its
  envelope, taken as it is — no resting level is subtracted — and the
  reference is the best of the repetitions. The user manual said the window's
  resting level was subtracted, and several docstrings still gave the 95th
  percentile of the envelope or a half-second window.

## Unchanged, on purpose

The force-velocity rehearsal, which plays the procedure over a synthetic
recording with no hardware, still narrates and synthesises a held maximum.
Task instructions — flexions against the table, holds at a share of the bar,
the grip in the air — are tasks, not the calibration, and keep their wording.

## Meta

- Bumped to 3.1.2 (`pyproject.toml`, `__init__`, `.zenodo.json`,
  `CITATION.cff`).
- New `tests/test_maniobra_calibracion.py`. **1078 automated tests.**
- The version-specific Zenodo DOI is to be minted at release.
