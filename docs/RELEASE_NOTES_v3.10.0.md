# emgteach 3.10.0 — guided sessions in the one-muscle practical

Three sessions of the one-muscle practical that the application now runs by
itself: it times each phase, says on screen what to do, marks it in the file,
stops the recording at the end, and the analysis takes the session's own
spans.

**3.7.0 remains the version the article describes.** Nothing computed changes
for a free recording, and no EDF format changes: the sessions add their own
ASCII marks, which earlier versions read as ordinary annotations. Recordings
made with 3.9.1 and earlier open and read as before.

## What changes

- **Three guided sessions**, chosen beside «Calibrate MVC» in the one-muscle
  practical; «Free recording» stays the default. With a session chosen,
  «Start recording» runs it: the calibration first if the session needs one,
  the five-second countdown, then each phase announced on the panel over the
  plots and on the phones, with a row of boxes that fill as the contractions
  are done; the recording stops by itself at the end. Esc stops the session
  and the recording goes on.
  - **Graded contractions** (54 s after the calibration, which it needs):
    five isometric contractions of 4 s at 20, 40, 60 and 80 % of the bar and
    at the maximum, with 6 s of rest. In Analysis the steps are the rows of
    the contraction table, with what was asked and what was held, and a view
    «Steps».
  - **Fatigue: biceps with a fixed load** (103 s at most; no calibration):
    a measured rest, a countdown to pick up the weight, and the weight held
    with the elbow at 90° for 90 s. There is no bar during the effort, and
    **the space bar ends it early** when the student cannot go on. An effort
    that does not reach twice the rest is warned as a weak signal (a poor
    contact or a weight too light), and a rest above 0.03 mV as a loose
    electrode. The analysis
    reads the contraction from 2 s after it begins to its fall, follows the
    MDF and MNF in 1 s windows and fits a line through them. **Fatigue is
    the MDF falling significantly (p < 0.01) by at least 10 %**: on the
    bench the biceps' MDF fell 16-20 % in 90 s with an R² of only 0.3, while
    the RMS held or rose. It is shown in a view «MDF over time»: the
    windows, their 5 s means, the line, the −10 % time and the RMS in grey.
    It replaces the sustained maximum and the intermittent contractions
    tried on 24 and 25 October. The simulated board's subject tires while
    it holds, so the session can be rehearsed without hardware.
  - **Quick repeated contractions** (28 s): 10 s of contractions of the fist,
    closing and relaxing it as fast as possible. The contractions are counted
    with their rate, and the peaks and the floor between them followed on a
    50 ms moving RMS — not on the envelope, whose 5 Hz filter alone keeps the
    floor at a fifth to a third of the peak at four or five a second — with
    the floor the measure itself leaves at that rate given apart, in a view
    «Train».
  - Each has a section in the report and a summary for the phones, and the
    manuals and both practical guides take them (exercises 1b and 1c and the
    paragraph after 1c).
- **An optional tone at every phase change of every guided flow** — the
  calibration, the countdown to the recording, the pair's guided task, the
  force-velocity loads and the sessions —, with two falling notes at the end
  of a guided task. The «Tone» box shows in every practical, is remembered
  and is on by default; unticked, nothing sounds.
- **The words of the instructions.** Every text says «contraction» where it
  said «jerk» or «squeeze» («sacudida» or «apretar» in Spanish), and
  «intense» where it said «explosive», «hard» or «strong»: «Close your fist:
  a brief, intense contraction.»; the warm-up reads «Warm up first» in
  English and «Calentamiento previo» in Spanish; the held effort asks only
  to breathe normally. With a session chosen, the calibration asks
  for the session's own gesture, and with one muscle the warm-up asks for
  «two or three easy contractions», not «of each muscle». The pictures of the
  calibration and the station sheets with them.
- **What the bench with the board changed (26 October 2026).** The subject
  begins some tenths of a second after a cue and lets go up to a second after
  the end, so each step and train is now **the
  activity inside its marks run on 1.5 s past their end**, and a step's level
  the plateau of that contraction (measured between the marks, the steps took
  rest and lost their end, and the train lost its last two contractions). **The
  gradation measures its maximum as the highest mean over half a second**, as
  the level held is a mean: on the envelope's peak, a step held at the
  calibration's own intensity read 85-87 %, so the bar's 100 % could not be
  held. With fragments chosen round each contraction, a step or the train
  is measured over the part of it they keep (it was dropped when they left
  its cue out, and the «Steps» or «Train» view lost it). Measured alike, the bench's gradation read 22/36/59/81 % for the
  20/40/60/80 asked (it read 17/27/42/60). Its calibration, its live bar and
  its analysis use it; the other practicals keep the peak. A maximal step
  above the calibration is said, in the view and the report. The tuned
  recording keeps the session and its view, and the train of quick
  contractions gives no fatigue verdict.
- **The report the phones receive carries the panels ticked on screen.** It
  was given the position of each ticked box instead of the panel, so
  «2. Env. norm.» came out as the filtered and rectified signal, and so on —
  in the report the phones download, not in the one saved by hand.
- **The two splash screens and «About» read «Dr. Agis-Torres et al. UCM»**,
  without the dash.

## How it was tested

**By the automated suite**, 1689 tests, among them: each session's script,
its marks and its Spanish; the clock that crosses every phase even when a
tick is late; each session recorded with the simulated board, whose subject
does what each phase asks, and analysed by its spans; the levels held by the
steps; the held load's MDF line, its verdict on a synthetic spectrum that
slides down at a constant amplitude, the span from 2 s after the activity to
its fall, the early end with the space bar and the warning of a high rest;
the simulated subject's spectrum falling while it holds; the train's count,
rate, peaks and floor on synthetic trains, with the envelope leaving more
floor than the 50 ms RMS at four and five a second; the tone sounding at each
phase change with the box ticked and not at all without it; and the report
the phones receive carrying the panels ticked.

**At the bench**: with the simulated board, manual runs #119 to #130 of
*Build Windows exe* (24–25 October 2026): the four sessions, the boxes, the
tone, the calibration's gesture and the words of the instructions. With the
real board, a free recording of the biceps holding a fixed weight (26
October 2026) set the fatigue session's criterion. With the
real board, manual run #133 (26 October 2026): the self-test; the board's
diagnosis (999 Hz, no CRC errors, no frame lost); «About» saying 3.10.0; the
calibration, the gradation and the quick contractions, whose findings are the
first item above. _(The bench of the executable released is added after it.)_

## The Windows executable

The release carries `emgteach-v3.10.0-windows-x64.exe`. It is the executable
of the manual run of *Build Windows exe* on this tag's commit, the one tried
at the bench; GitHub Actions built it and self-tested it headless, and GitHub
attests where it was built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Chrome may block the download as dangerous**: open Downloads and choose
  Keep, or use another browser. The SHA-256 below tells you the file is the
  one released.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.10.0-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.10.0-windows-x64.exe --repo aagisto-maker/emgteach`.
- **VirusTotal**: _(link to the analysis, added when the draft is published)_.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
