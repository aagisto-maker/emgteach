# emgteach 3.8.0 — what ecgteach and eegteach found, brought to emgteach

A short release before the November practicals. The bench of the sister
applications, ecgteach 0.4.0 and eegteach 0.3.0 (5–6 October 2026), turned up
faults in code emgteach shares with them; this version carries the fixes over
and nothing else.

**3.7.0 remains the version the article describes.** No analysis, no EDF
format and no calculation changes. Recordings made with 3.7.x open and read as
before.

## A fault of the published 3.7.2

- **A phone that joins the broadcast late now gets the report.** The button
  to download the PDF reached only the phones connected at the moment the
  report was saved; a phone that opened the page afterwards, or reconnected
  after its screen went off, never had it. Each phone that connects now gets
  it. A new recording, a new configuration or stopping the broadcast forget
  it, so no phone gets an earlier recording's report.

## The recording

- **The event log survives a crash.** `<name>.eventos.txt` is written line by
  line as the recording runs, each line pushed to disk, as `.marcas.txt`
  already was. Before, it was written at the end, and a process killed in
  mid-recording left no log.
- **The default name carries the seconds**
  (`P07_2026-10-06_10-15-42.edf`): two recordings in the same minute were
  offered the same name. A recording that reuses a name replaces the earlier
  `.eventos.txt`, as it did `.marcas.txt`.
- **A file that disappears is said at once.** With the recording's folder
  gone — a memory stick taken out — the recording went on without a word. It
  now stops within a second, the log says why, and a box says «The recording
  cannot be saved» («No se puede guardar el registro») without blocking the
  window.
- **The save dialog does not open in a folder that is gone.** It opens in
  Documents, and the log names the folder that was missing.
- **After a recording with the BITalino, the status says «Estado: apague y
  encienda la placa»**, with the whole sentence in its tooltip, until the
  next recording or connection. At the bench every new recording needed the
  board switched off and on. Not with the simulated board or the Arduino.

## How it was tested

**By the automated suite**, 1433 tests, among them: a real WebSocket follower
that joins after the report; a process recording the simulated board that is
killed, with its event log checked afterwards; the recording's folder deleted
with the real writer running; and the status after a recording with a board
that answers and with the simulated one.

**At the bench**: see the 3.8.0 bench list.

## The Windows executable

The release carries `emgteach-v3.8.0-windows-x64.exe`. GitHub Actions builds
it from this tag and self-tests it headless, and GitHub attests where it was
built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.8.0-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.8.0-windows-x64.exe --repo aagisto-maker/emgteach`.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
