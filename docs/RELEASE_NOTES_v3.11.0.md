# emgteach 3.11.0 — the review shows what is measured

After a recording, the acquisition tab's review shows where each contraction
is and, in the one-muscle practical, the stretch each number was measured
on. The fragments that practical proposes follow each contraction to rest; a
weak contraction among strong ones is measured; a recording never ends
without its review in silence; and the classroom link carries the address
the phones can reach.

**3.7.0 remains the version the article describes.** No EDF format changes,
and recordings made with 3.10.1 and earlier open and read as before. What is
computed changes in the one-muscle practical: the fragments the editor
proposes there, and with them the rows of the contraction table and the
numbers over the analysed span, as below. Each step's level, RMS and MDF in a
gradation, the fixed load and the quick contractions compute as before; so do
the pair and kinematics.

## What changes

- **The review shows each contraction.** At the end of a recording the
  review shades the session's phases, which are what the application asked;
  under the traces a **teal bar** now marks each contraction the fragment
  editor will propose, from where it starts to where the muscle is back at
  rest, the letting go after the tone included. It is worked out with the
  editor's own rule, free recordings too: what is seen in the review is what
  the editor will propose when it opens.
- **And the stretch each number was measured on.** In the one-muscle
  practical, once the first analysis ends, a taller **light green stretch
  with a dark edge** appears inside each bar: in a gradation, each step's
  plateau, from 1.5 s after it begins, where its % MVC, RMS and MDF come
  from; with a fixed load, the held load its fatigue was read on; in a free
  recording, each row of the contraction table. The quick contractions have
  none, since the train is measured whole. A line under the plots says what
  each colour is. It is read from the analysis's own result, never worked out
  again, and follows the fragments chosen afterwards. Not yet in the pair or
  kinematics.
- **A fragment follows its contraction's fall to rest.** In the one-muscle
  practical a row ended where the envelope fell below the baseline plus 5 %
  of its peak, which on a strong step is many times the rest. The 5 % still
  separates one contraction from the next, but a row now follows the fall
  that carries on from it to the dotted «rest» line, or to the bottom of the
  fall if the envelope rises again first. Nothing that rises after the fall
  is joined: a hump or a second twitch stays dotted, a click away. And a row
  runs from the first to the last contraction in it — a peak at least 25 %
  of the tallest one's height — so a series of brisk contractions with less
  than a second of rest between them is one row, whole, where it kept only
  its first contraction.
- **A gradation is proposed one row per step**, each the detected row that
  overlaps its step the most; what the muscle does outside the steps is left
  dotted, and the editor expects five. On the bench's gradation: five rows
  instead of six, each ending 0.04-0.21 s later, at the end of its fall; the
  analysed span 22.4 → 22.1 s, its RMS 0.146 → 0.147 mV, its MDF 87.2 →
  86.8 Hz, five contractions in the table instead of six; each step's level,
  RMS and MDF unchanged. On the bench's free recording, 18 s of brisk
  contractions: two rows, each its whole series — 2.0 → 13.8 s analysed, RMS
  0.096 → 0.073 mV, MDF 71.7 → 86.0 Hz.
- **A weak contraction among strong ones is measured.** The contraction table
  dropped a window whose peak above rest was under 10 % of the span's
  strongest, as noise; a weak contraction between two strong ones, some forty
  noise deviations over rest, had a bar in the review and no row. A window is
  now noise only if it is under that 10 % and also barely clears the
  detector's line; and a fragment accepted in the editor is always a row,
  however weak.
- **A recording never ends without its review in silence.** A recording that
  left no file (stopped before the board's first sample, a write failure),
  one that ended after another had started, a file with no EMG channel and an
  error inside the review all ended with no review and nothing said. Each now
  ends in the review or in a line of the event log, «No review of <file>:
  <reason>.»; an error nobody expected is also written to
  `emgteach-errores.log` and leaves the plots as they were.
- **The classroom link carries the address the phones can reach.** On some
  computers the phones could not load the page: the link carried the first
  address the system listed, which could be a
  virtual adapter's (WSL, Hyper-V, VirtualBox, VMware, a VPN) or the cable's
  with the phones on the Wi‑Fi. The address is now chosen among the
  computer's: the one fixed in this station's `difusion.txt` with
  `ip = …`; the interface fixed there with `interfaz = …`, which holds when
  DHCP changes the address; the Windows mobile hotspot; the one the default
  route goes out through, unless it is a virtual adapter's; the first that is
  not virtual. When classroom mode is switched on, the event log lists every
  address with its interface and says which was chosen and why. The ports
  are the same as before, 8080 for the page and 8443 for the live data,
  changed in the same file. On a computer whose firewall is managed by its
  organisation the broadcast may not reach the phones: emgteach's incoming
  connections have to be allowed.

## Behind the scenes

The acquisition tab, some 6200 lines, is being split into pieces of their
own, as its plan sets out (`docs/PLAN-partir-AcquisitionTab.md`): the
device's full scale (step 0), the classroom broadcast (1), the device and its
link (2), the live plots and the review (3) and what every guided flow asks of
the world around it (4). The tab is now some 4500 lines; the screen is the
same to the pixel, in the three practicals, at rest, connected, recording and
reviewing.

Several tests that checked a guided session against the wall clock failed
now and then on the Windows runner; they now check it against the clock the
session decides by. No test leaves a window open, and every run of the suite
measures the interface thread's disk syncs and stalls.

## How it was tested

**By the automated suite**, 1860 tests, among them: the row of each step
ending at the end of its fall and the hump after it left dotted; a series of
brisk contractions proposed as one row, whole; a gradation proposed one row
per step; the review's bars being the rows the editor proposes, free
recordings too; the measured stretches read from the analysis's result, in
the file's time, with a test holding four synthetic sessions to the numbers
the code before gave; a weak contraction at 8 % of the strongest being a row
with its stretch, the resting noise still none, and a weak fragment accepted
in the editor a row; each way a recording can end without a review saying
why; and the classroom address chosen right with a virtual adapter listed
first, the cable and the Wi‑Fi with the route on either, the hotspot, a VPN,
only virtual adapters, no network, and each line of `difusion.txt`.

**At the bench**: with the real board, the executable of the branch (manual
run #150, 6 November 2026): the gradation on the forearm, whose rows and
numbers are the ones above, and the free recording of brisk contractions.
With the real board, in the laboratory (manual run #152 on `3ce37ac`, 10
November 2026): the gradation's review, with its five bars and five
stretches, and its five rows in the editor; and the free recording, with a
weak contraction between two strong ones measured and a recording stopped
before any sample saying why it has no review; and the choice of the
classroom address, checked with success. _(The bench with the executable
released, added after it.)_

## The Windows executable

The release carries `emgteach-v3.11.0-windows-x64.exe`. It is the executable
of the manual run of *Build Windows exe* on this tag's commit, the one tried
before the tag; GitHub Actions built it and self-tested it headless, and
GitHub attests where it was built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Chrome may block the download as dangerous**: open Downloads and choose
  Keep, or use another browser. The SHA-256 below tells you the file is the
  one released.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.11.0-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.11.0-windows-x64.exe --repo aagisto-maker/emgteach`.
- **VirusTotal**: _(link to the analysis, added when the draft is published)_.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
