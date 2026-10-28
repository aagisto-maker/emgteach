# emgteach 3.10.1 — the guided sessions after the bench

A patch of 3.10.0. What its final bench left for a patch, and what the
benches with the executables of 3.10.1 found, in the three guided sessions of
the one-muscle practical and in the fragments the editor proposes there.

**3.7.0 remains the version the article describes.** No EDF format changes,
and recordings made with 3.10.0 and earlier open and read as before. What is
computed changes for the guided sessions, as below, and for the fragments the
editor proposes in the one-muscle practical — and with them the rows of a free
recording's contraction table in that practical, where two contractions less
than a second apart are now one. The other practicals compute as before.

## What changes

- **Graded contractions: each step is reached slowly.** At the bench every
  step began with a brief peak above the level asked, the subject jumping to
  the mark. Each step now says «Close your fist: rise slowly to the mark
  (1-2 s) and hold it there.», its band on the live bar rises from zero to
  the mark over 1.5 s, and its level is read from 1.5 s after the contraction
  begins instead of one second.
- **Fatigue: the −10 % is read on the line.** The summary line could say
  «MDF −10 % at 74 s», read on a 5 s running median, beside the verdict «Not
  detected (MDF fell less than 10 %)», read on the line. The time is now where
  the MDF's line falls to 90 % of its start, if it does within what was held:
  the mark of the view «MDF over time», the summary line, the report, the
  phones and the verdict come from the same measure.
- **Fatigue with a fixed load, on the forearm.** The session is now
  «Fatigue with a fixed load» (its files `…_fatiga_…`), and its texts name no
  posture, so the one session serves the forearm and the biceps. Exercise 1c
  of both guides and the manuals do it on the forearm flexor, with the
  electrodes of the gradation and the train: the forearm resting on the
  table, the hand over its edge, the weight hanging from the hand, gripped no
  harder than needed — one that cannot be held for more than 60-90 s
  (3-5 kg), so that fatigue comes within the session. The biceps, with the
  elbow at 90°, is a variant. The analysis does not change; on the bench's
  forearm the MDF fell from 118 to 87 Hz (−26 %, p < 0.001) and the fatigue
  was detected.
- **Quick contractions: the whole train, one contraction each.** The 1.5 s
  margin past the end mark says where a contraction of the train may begin:
  the train now ends where the last one begun inside it ends, even past the
  margin, never past the session's end (it was cut in two at the margin).
  And two peaks are two contractions only if the trace between them falls
  below 40 % of the lower one or they are 0.25 s apart: on the bench three
  contractions with two humps were counted twice, 20 for some 17, and the
  floor between the humps made the floor jump to half the peak.
- **The fragments of the one-muscle practical.**
  - **A fragment ends where the muscle is back at rest**: the envelope down
    to the baseline plus 5 % of the peak's height, and there for at least a
    second. The detector cut each active run at the valleys between its
    peaks, and a step of the gradation, with its brief peak at the start,
    came in two or three rows: twelve for five steps on the bench. In the
    editor's fine adjustment the gap reads «A fragment ends after a rest of
    (s)», and the valley slider is off. The pair keeps its cut at the valleys
    — its six contractions in a row rest less than a second — and kinematics
    its one row per lift.
  - **Every row starts 0.5 s before its contraction leaves that rest**, the
    same lead for all and never over the row before; the train's row and the
    held load's too. The load's row runs to where the weight is put down, not
    to the effort's end mark; the load is still read from 2 s after it begins
    to the effort's end.
  - **Fragments that touch are measured as one** in the guided sessions'
    measures: a step chosen in two touching rows was measured on the larger
    half alone.

## Behind the scenes

Two tests that waited for a fixed time failed once each on the Windows runner
and passed on a re-run: «Retry» after the board did not answer, and the late
subject on the simulated board. They now check what they are about whatever
the runner's load; nothing in the application changes with them.

## How it was tested

**By the automated suite**, 1714 tests, among them: the band of each step
rising over its ramp and the level read after the reach; the −10 % on the
line and its agreement with the verdict; a contraction begun inside the
train's margin counted whole, a subject going on past it cut between
contractions, and a contraction with two humps counted once; a step with a
peak at its start proposed as one fragment, a rest of less than a second not
cutting one, a light contraction beside a maximal one found, flickers of the
resting noise left out; each row starting half a second before its flank; the
load's row running to where the weight is put down while its reading stays
at the effort's end; and the fatigue session's texts naming no posture.

**At the bench**: with the real board, the executables of the branches
(27 October 2026). Manual run #143: the self-test, the board's diagnosis
(999 Hz); the gradation with its five rows proposed unedited, five steps of
19/34/45/52/75 % and its tuned recording; and the fatigue on the forearm,
its MDF from 118 to 87 Hz (−26 %, R² 0.39, p < 0.001), its −10 % at 24 s on
the line, «Detected», the view and the summary card agreeing. Manual run
#145: the gradation and the train reopened, with every row half a second
before its flank and a contraction with two humps counted once; and the
load's row, which still ended at the effort's end mark. With the real board,
the executable released: _(manual run, date and findings, added after the
bench)_.

## The Windows executable

The release carries `emgteach-v3.10.1-windows-x64.exe`. It is the executable
of the manual run of *Build Windows exe* on this tag's commit, the one tried
at the bench; GitHub Actions built it and self-tested it headless, and GitHub
attests where it was built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Chrome may block the download as dangerous**: open Downloads and choose
  Keep, or use another browser. The SHA-256 below tells you the file is the
  one released.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.10.1-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.10.1-windows-x64.exe --repo aagisto-maker/emgteach`.
- **VirusTotal**: _(link to the analysis, added when the draft is published)_.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
