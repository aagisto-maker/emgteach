# emgteach 3.5.0 — the kit for the laboratory: a board in software, a diagnostic for the station, and a recording that is not lost

A minor version. It adds what a practical needs around the measurement —
a simulated board to prepare and teach without hardware, a diagnostic that
answers why a station does not connect, an event log beside every recording
and a way to read back a recording whose process died — and it repairs the
two documents the student takes away, the report and the CSV, which were
losing columns off the page and the operator's user name into the file.

## What does not change, and what does

The definitions are those of 3.4.0: the MVC reference (the envelope's peak
across the calibration repetitions kept), % MVC, the co-activation index and
its 4.5 % floor, the contraction table, the task maximum over the recording
phase and the fatigue analysis. A recording reanalysed with 3.5.0 gives the
same figures — with three exceptions, all of them faults being repaired:

- **The onset detector takes its resting level at the start of the recording
  phase**, not from the first second of the stream. In a guided session that
  second is the beginning of the warm-up — contractions, not rest — so the
  threshold came out inflated and weak contractions were missed. A guided
  session reanalysed with 3.5.0 can mark contractions the previous version
  did not.
- **The live P10/P50/P90 count from the recording phase**, not from the end
  of the calibration: the countdown's seconds of rest went into the task's
  distribution and lowered the three levels. The offline Jonsson analysis is
  unchanged.
- **An MVC reference below 1e-4 mV read back wrong** (`5e-05` was read as
  `5`), so a file written with one is now normalised against the reference it
  was meant to carry.

## Added

- **A BITalino in software.** Writing `simulada` (or `simulated`) as the
  address connects a board the application simulates, with no Bluetooth: it
  speaks the board's protocol byte for byte — the version reply, the rate and
  start commands, frames with their sequence number and CRC — so the frame
  decoder, the acquisition, the calibration, the recording and the classroom
  broadcast run as with the board. The signal is synthetic (a 12-second cycle
  of rest, flexion, extension and grip, with an accelerometer that follows the
  first muscle) and the device calls itself «BITalino (simulated)». A
  practical can be prepared, rehearsed and taught where the board is not at
  hand.
- **The station's address in a text file.** A `bitalino.txt` beside the
  application sets the address for that computer: the acquisition tab starts
  with it, says so in the log, and «Default» returns to it. Typed into the
  field, the address had to be typed again wherever the settings did not
  survive — another account, a reimaged PC, the application copied on a
  stick; the file travels with the application.
- **A connection diagnostic.** `diagnostico_bitalino.exe`, run beside the
  application, answers in order: which address it tries and where that came
  from; whether Windows sees a working Bluetooth adapter; whether a board is
  paired and on which COM port; whether it answers the handshake and how
  fast; and ten seconds of acquisition — frames, rate, CRC failures and
  whether each channel carries a signal. It connects as the acquisition tab
  does, so a station that passes here connects in the application. Its answers
  are saved to a text file beside it.
- **The event log of each recording is saved beside it**, as
  `<name>.eventos.txt`. The log on screen died with the application, and it is
  what tells what happened when something went wrong without raising.
- **A recording that was not closed can be recovered.** An EDF+ file is
  written record by record, but its record count and its annotations are only
  written when it closes: a process that died in mid-recording left a file
  with all its signal that no reader accepted and without a mark of the
  session. Every mark is now mirrored, as it is made, to `<name>.marcas.txt`,
  and `python -m emgteach.recovery <file>.edf` writes
  `<file>_recuperado.edf` with the signal on disk and the marks of that
  side-car. The original is never modified.

## Changed

- **One decimal mark, and it is the point,** in both languages. Three were on
  screen at once: the numbers formatted by hand wrote `1.5`, the handful that
  went through the interface's own helper wrote `1,5` in Spanish, and every
  spin box followed the operating system — on a Spanish Windows it showed
  `1,5` and refused the `1.5` printed beside it. The fields now write the
  point and take a comma typed in, because a Spanish keypad sends one. The
  CSV export is the deliberate exception: its dialect is the spreadsheet's.
- **The guided session states the rule before the example.** The pair
  practical is agonist/antagonist — the calculations know no anatomy, and the
  teacher names the muscles — but the wizard told the subject to clench the
  fist whichever two muscles the electrodes were on. Every calibration
  instruction now says «one brief, explosive maximal jerk of the movement
  this muscle makes» first and names the forearm behind it, as the example of
  the practical guide.
- **The default limits say where they were measured.** The co-activation
  floor, the channel-separation criterion and the ranges of the calibration
  checks come from the forearm pair (FCR and ECR) of the practical guide, not
  from the method, and the code, the help and both manuals say so. The
  practical guide documents a second pair — biceps and triceps — with its own
  reference gesture and the three warnings to check on a test recording.
- **The reports say more about what they describe:** both muscles' metrics
  side by side, both channel names, and, in the MVC report, the channel, the
  analysed fragments, the window the graphs show, the filters and the device.
- **The CSV export speaks the spreadsheet's language:** a semicolon and a
  decimal comma in Spanish (with a comma and a point, Excel in Spanish opened
  everything in one column), the file's name instead of its full path, the
  version, the MVC reference with its provenance, both muscles, and the
  contractions and co-activation windows as blocks after the per-segment
  table.
- **Every recording calibrates itself.** The references measured for a
  previous recording of the same session are no longer written into the next
  file's header: they were written and, in the same breath, cleared from the
  screen, so the file said «MVC ref» for a calibration it did not contain.
- **Automatic screenshots stop at 60 per recording.** With no limit, a
  recording left running wrote one every three seconds for as long as it ran.
- **`import emgteach` imports nothing until it is asked for,** which is what
  lets the connection diagnostic be built without scipy: 23 MB instead of 61.
  Both executables are built with the pinned versions of
  `packaging/requirements-exe.txt` and self-tested in the workflow.
- **The live Jonsson levels are read from a histogram** instead of ten
  minutes of samples, so they cost the same at any recording length. The
  readout, which shows whole percents, does not change.

## Removed

- **The two CSV downloads of the phone page.** A CSV on a phone is a file a
  student does not open, and if they do they do not know what to look at. The
  report is the only download the page offers.
- **The accelerometer's channel diagnostic**, whose button had been
  unreachable since the accelerometer's input became part of the practical,
  and the catalogue entries no code asked for any more.

## Fixed

- **The report's tables fit the page.** Every table was built with two column
  widths and reportlab repeats the last one, so the table of contractions —
  seven columns, 55 cm on a 17 cm frame — lost Muscle, RMS, Peak and MDF off
  the right edge. A table split across pages now repeats its header, and the
  examples published in `docs/` are regenerated.
- **A recording that cannot be written stops and says so.** An error writing a
  block (a full disk, a folder that went away) was noted in the log while the
  recording went on, the screen said «Signal OK», and the file was announced
  as saved.
- **Stopping and starting again at once no longer freezes the screen on the
  previous file**, and the status line derives from the Connect button, so it
  tells the truth after a disconnection in mid-recording.
- **The Spanish interface says «usted» all the way through**, «la CVM» in the
  feminine, and **«la placa BITalino»** — a card, and the agreement follows
  the word — in the interface, the manuals, the practical guide, the station's
  address file and the connection diagnostic.
- **The device, the protocol and the provenance reach both reports**, instead
  of «Device: not stored in the EDF» on every file; and the identifier on a
  report is the file's, or none, instead of the acquisition tab's current one
   — another student's as often as not.
- **Tuning a file without `REC start` no longer ignores the fragments in
  silence**, the phones show the warm-up and preparation countdowns, and the
  simulated board's name reaches the EDF header whole.

## Upgrading

Nothing to do: the settings, the EDF files and the reports of 3.4.0 are read
as before. A station that already has a `bitalino.txt` keeps it.
