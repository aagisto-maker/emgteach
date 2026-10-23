# emgteach 3.9.1 — the live view keeps following the signal

A patch of 3.9.0. Two things a user sees change, and one word in Spanish.

**3.7.0 remains the version the article describes.** No analysis, no EDF
format and no calculation changes. Recordings made with 3.9.0 and earlier open
and read as before.

## What changes

- **The live view keeps following the signal after a wheel zoom.** Until
  now, zooming a live plot with the mouse wheel left it on the window it was
  zoomed to, and the signal ran on out of sight to the right until the «A»
  button in the plot's corner was pressed; it did so in 3.8.0 and before.
  The wheel now sets how many seconds are shown, and the view goes on with
  the signal, as an oscilloscope's does; «A» gives the whole window back.
  The raw signal, the envelope and the accelerometer alike. Dragging the
  live view back while recording no longer holds it there: the review that
  opens when the recording ends is where the whole recording is looked at.
- **Closing the window while «Retry» waits for the port starts no
  recording.** After the board did not answer, «Retry» waits for Windows to
  let go of the Bluetooth port, which can take most of a minute. Closing the
  window during that wait could, if the port was let go in the following
  seconds, start a recording after the window had gone, with a «Save as»
  dialog nobody asked for. It no longer does.
- **In Spanish the unit reads «% CVM»**, not «% MVC», in the load bar of the
  acquisition tab, the data panel of the normalisation tab and the report's
  metrics table. In English it still reads «% MVC».

## Behind the scenes

Four tests that waited for a fixed time, or that could leave a thread or a
dialog behind, now wait for what they check and clean up after themselves;
nothing in the application changes with them.

## How it was tested

**By the automated suite**, 1492 tests, among them: the zoomed live view
following the last sample with the width the wheel chose, and «A» giving the
whole window back; the window closed while «Retry» waits for the port, with
the port let go during the wait or after it; and «% CVM» in Spanish and
«% MVC» in English in the bar, the panel and the report.

**At the bench**: with the simulated board, manual run #114 of *Build Windows
exe* (22 October 2026): the live view after a wheel zoom. With the real
board: _(added after the bench check)_.

## The Windows executable

The release carries `emgteach-v3.9.1-windows-x64.exe`. It is the executable
of the manual run of *Build Windows exe* on this tag's commit, the one tried
at the bench; GitHub Actions built it and self-tested it headless, and GitHub
attests where it was built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Chrome may block the download as dangerous**: open Downloads and choose
  Keep, or use another browser. The SHA-256 below tells you the file is the
  one released.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.9.1-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.9.1-windows-x64.exe --repo aagisto-maker/emgteach`.
- **VirusTotal**: _(link to the analysis, added when the draft is published)_.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
