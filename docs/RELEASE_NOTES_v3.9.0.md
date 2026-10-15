# emgteach 3.9.0 — marking by hand while recording, back

A short release for experiments that need their own events marked. Marking by
hand was removed in 3.0.0 (5 September 2026): nobody used it, and it took
height in the tab where height matters most. It is back, optional, as ecgteach
and eegteach have it.

**3.7.0 remains the version the article describes.** No analysis, no EDF
format and no calculation changes. Recordings made with 3.8.0 and earlier open
and read as before.

## Marking by hand

- **A label and a button, beside the list of the last marks.** Choose
  «Contraction start», «Contraction end», «Fatigue», «Rest» or «Other»
  («Inicio contracción», «Fin contracción», «Fatiga», «Reposo», «Otro») and
  press «Mark (M)» («Marcar (M)»), or the M key, and a mark is put at that
  moment. Only while recording: from the first block of signal until the
  recording ends. The box is no taller: the controls take the row of the
  list.
- **The mark goes where every mark goes**: an EDF+ annotation, a line in
  `<name>.eventos.txt` and, while the recording runs, a line in the
  `.marcas.txt` mirror, which is there for a recording that does not close
  and is removed when it closes normally. It is written in the language of
  the interface.
- **The analysis draws manual marks apart**, as a solid teal line with their
  label, and recognises them in either language.
- **The M and the text fields.** With the cursor in a text field the M is
  typed and does not mark. Enter or Esc in the field, or a click anywhere
  else in the tab, the live plot included, hands the focus back and the M
  marks again.
- **The live plots take no focus of their own.** A click anywhere in the
  tab that is not a text field — the plot, its frame, a label — gives the M
  back, and an M that reaches the plot while recording marks. Zoom, drag and
  the wheel are unchanged; pyqtgraph's keyboard zoom (-, +, Backspace), never
  offered, is gone.
- **The list of the last marks keeps its two lines**: a long one ends in «…»
  instead of bringing up a scroll bar that took the second line.
- There is no Delete button, no free-text dialog behind «Other» and no step
  in the guided tour. The manuals say the marking is optional and what it is
  for.

## Behind the scenes

- **The release publishes the executable that was tried.** A version tag no
  longer builds the executable again: it takes the one from the manual run
  that was tried at the bench, on the same commit, checks where it was built
  and that it says the tag's version, and drafts the release with it.
- **The fragment editor's proposal is computed without Qt**
  (`emgteach.fragments`). Nothing it proposes changes.
- **Type checking is enforced** in the continuous integration, as in ecgteach
  and eegteach.

## Known issue

- **The live view stops following the signal after a wheel zoom**; the «A»
  autoscale button in the plot's corner brings it back. It happened in 3.8.0
  too, and is left for a later version.

## How it was tested

**By the automated suite**, 1478 tests, among them: the mark reaching the
EDF+, the mirror and the event log; the M not marking while the cursor is in
a text field, and marking again after Enter, Esc or a click in the plots'
frame (each of these three checked to fail without its fix) or in the live
plot; an M that reaches the live plot marking; the wheel zoom still working; the analysis drawing manual
marks in teal; and what the fragment editor proposes, fixed to the hundredth
in five cases.

**At the bench**: with the simulated board, run #111 of *Build Windows exe*
(15 October 2026): the M after Enter, Esc and a click, in the plot and out of
it; «Mark (M)» whole at 100 % and 125 % scaling; manual marks teal in the
analysis; two lines in the list. With the real board, the executable
released (manual run #112, 15 October 2026): the self-test; the simulated
diagnosis (1000 Hz, no CRC errors, no frame lost); «About» saying 3.9.0; the
notice on stopping read whole; and five marks, by the M and by the button, in
the event log at the right times.

## The Windows executable

The release carries `emgteach-v3.9.0-windows-x64.exe`. It is the executable
of the manual run of *Build Windows exe* on this tag's commit, the one tried
at the bench; GitHub Actions built it and self-tested it headless, and GitHub
attests where it was built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Chrome may block the download as dangerous**: open Downloads and choose
  Keep, or use another browser. The SHA-256 below tells you the file is the
  one released.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.9.0-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.9.0-windows-x64.exe --repo aagisto-maker/emgteach`.
- **VirusTotal**: _(link to the analysis, added when the draft is published)_.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
