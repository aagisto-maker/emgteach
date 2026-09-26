# emgteach 3.7.0 — the guided session goes on into the task

The version the article describes, and the one the November practicals run
on. It was rehearsed end to end with the simulated board and checked at the
bench with the BITalino before being tagged.

For a given set of fragments the analysis computes what 3.6.0 computed. What
changes is the set of fragments the editor proposes, and a contraction that no
load marker announced no longer borrows a load. Recordings made with 3.6.0
open and read as before.

## The guided session

- **It goes on into the task.** It used to stop once the reference had been
  measured. Now four panels guide the session: warm-up, calibration, the free
  manoeuvres and the grip. Each carries a row of boxes that maps its phase,
  in the colour the muscle has in the traces.
- **The free manoeuvres count themselves.** A contraction is counted when
  the muscle has been over a tenth of its own maximum for 0.30 s, and the
  phase moves on when the count is done and the muscle is back at rest.
  After 12 s with nothing new counted it moves on anyway. «Done — next»
  remains as a way out, no longer compulsory.
- **The grip is one hold of about eight seconds, squeezing a ball.** On the
  bench, a fist closed on nothing left the wrist extensors at 4 % of their
  reference and the grip gave no co-activation index. The load bars are
  drawn inside the grip's own panel, since that is where the guide tells the
  student to look.
- **The force-velocity study has the same map**: the lifts of the load in
  hand above, the whole experiment below.
- **The panel is opaque**, and resizes when its map is laid out, so the
  instruction is never covered.

## The fragment editor

- **Each proposed row holds the whole contraction**, from where its envelope
  leaves rest to where it returns to it, with a small margin either side.
  Rest is drawn on the plot as a dotted «rest» line.
  - In the agonist/antagonist practical the rows no longer have to be
    widened by hand.
  - In force-velocity they no longer run from before the cue to the end of
    the lift's window.
- **One row per lift the force-velocity wizard marked.** A lift the wizard
  did not ask for stays a dotted candidate. Each load marker gives its load
  to the one lift it announced (`force_velocity.marker_owners`), in the
  editor, the analysis and the tuned recording alike. The study starts a row
  with no load unticked.

## The practical

- **The pair practical says which pair it is on**: forearm, arm or another
  pair. The pair is written into the EDF header.
- **Electrodes.** One reference electrode goes on the olecranon, and both
  pairs are placed 5 cm from the epicondyle of their own side. The placement
  figure is the article's.
- **The station sheet** says the grip is made squeezing the ball.
- **The guides** say what the bench showed. Flexions and extensions give «not
  reported» or a low index (around 30 %), depending on whether the antagonist
  passes the 4.5 % floor, and the grip comes out clearly higher.

## Connecting to the board

- **The status says «connecting to the board…» until the first block
  arrives**, and «recording…» from then on.
- **After 20 s with nothing, the recording stops.** The status says the board
  did not answer, and a warning offers to try again. The warning no longer
  waits for Windows to release the Bluetooth port, which could freeze the
  window for most of a minute.
- **«Retry» while the old attempt still holds the port waits for it and then
  starts by itself.**
- **A recording stopped while the board is being reached stays stopped.**

## The Windows executable

From this version the release carries `emgteach-v3.7.0-windows-x64.exe`.
GitHub Actions builds it from this tag and self-tests it headless, and GitHub
attests where it was built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.7.0-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.7.0-windows-x64.exe --repo aagisto-maker/emgteach`.

The Zenodo record archives the source code of the tag, not the executable.

## Known limitations, for 3.8.0

- **An extra extension**: a seventh extension made before the phase has
  moved on is proposed as a row («ECR 7 of 6»). So is a small burst of the
  extensor at the change of phase. Drop them in the editor.
- **The onset markers after «REC start»** measure their resting level over
  the first flexion, so the first flexions may carry no live onset mark. The
  analysis is not affected.
- **The simulated board** can make an extra extension, and its grip reads
  about a third of the reference rather than the 50–60 % band.
- **A short pause of the screen** during a recording with automatic
  screenshots. The recording itself is complete.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change, with the measurements
behind it.
