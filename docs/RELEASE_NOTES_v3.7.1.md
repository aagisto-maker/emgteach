# emgteach 3.7.1 — a corrupted frame no longer ends the recording

A bug fix for the November practicals. With 3.7.0, one corrupted byte on the
Bluetooth link ended a student's whole recording.

**3.7.0 remains the version the article describes.** No interface, no EDF
format and no calculation changes: for a given set of fragments 3.7.1 computes
what 3.7.0 computes. Recordings made with 3.7.0 open and read as before.

## The BITalino link

- **A corrupted frame no longer ends the recording.** A single frame that
  failed its 4-bit CRC used to stop the acquisition as «connection lost». Now
  the reading skips forward one byte at a time until frames validate again,
  and gives the link up only after 256 bytes in a row with no valid frame.
- **A resynchronised frame is confirmed by the next one.** A window that
  straddles two frames passes a 4-bit CRC by chance one time in sixteen. The
  sample it would yield is garbage and can reach full scale, and the MVC
  calibration takes the maximum. So a frame found after discarding is
  accepted only when the frame after it also validates and carries the next
  sequence number.
- **A gap in the link is marked in the file.** The file's clock counts what
  arrived, so after a gap every later time is short by the frames that never
  came. Once per gap, the recording now writes:
  - an EDF+ annotation, «Link: {n} frame(s) lost» / «Enlace: {n} trama(s)
    perdida(s)»;
  - a line in its event log, «Warning — the link dropped {n} frame(s)
    ({total} so far).».

  The count comes from the frames' 4-bit sequence number, which wraps every
  16. A long gap is therefore under-counted by a multiple of 16.
- **The connection diagnostic** reports the bytes it discarded and the frames
  lost, instead of stating «No frame failed its CRC» whenever the reading did
  not stop.
- The fifth and sixth frame slots, which exist only with more than four
  inputs enabled, are scaled at 6 bits. The application never enables more
  than three, so no recording changes.

The resynchronisation comes from the sister project ecgteach. The
confirmation by the next frame is new here.

## How it was tested

**By the automated suite**, 1395 tests. Several of them build byte streams
with corrupted frames, lost frames, a misaligned window that passes the CRC
by chance, and a sequence number that wraps.

**With the BITalino in normal use**, at the bench on 27 September:
- the connection diagnostic;
- a full agonist/antagonist session;
- a one-muscle recording.

None showed a link warning or a lost-frame mark, and each file lasted what
the event log's clock says it lasted.

**A real Bluetooth failure could not be provoked.** Walking away with the
board to more than 4 m did not interrupt or weaken the signal. So the
resynchronisation and the lost-frame mark have not yet been seen working on
a real failing link. What the bench shows is that they change nothing when
the link is sound.

## Saving the tuned recording

Saving the tuned recording of a recording with nothing to tune now gives a
warning, «Save tuned recording», with the reason, instead of «Unexpected
error». A one-muscle recording is such a case: it has no «REC start», no
calibration and no load marks. The same holds for a destination that would
overwrite the source.

Both refusals called a method the Analysis tab never had, so the refusal
itself crashed. It was found at the 3.7.1 bench check and dates from when the
tuned recording was introduced.

## Known limitation, for 3.8.0

**The fragment editor drops very brief contractions.** A contraction that
stays less than 0.5 s above the activity threshold gets no row. In the
one-muscle practical there is no expected count to warn about it. At the
bench, three brisk contractions of twelve were left out.

Such contractions may come out as a dotted candidate or not be marked at
all. They are added by hand: click the dotted one, or use «Add fragment».
The practical guides now say so. The fix goes to the list for 3.8.0.

## The Windows executable

The release carries `emgteach-v3.7.1-windows-x64.exe`. GitHub Actions builds
it from this tag and self-tests it headless, and GitHub attests where it was
built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.7.1-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.7.1-windows-x64.exe --repo aagisto-maker/emgteach`.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
