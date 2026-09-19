# emgteach 3.6.0 — the simulated board obeys the calibration

A minor version, and one thing carries it: a session rehearsed without the
board now teaches what the practical teaches. Nothing computed changes, and no
recording made with the board reads any differently: the analysis, the
reference, the co-activation index and the reports of 3.5.0 are untouched.

## The fault

The simulated board's subject repeats a fixed twelve-second cycle that starts
when the board is connected — a flexion of the first muscle, an extension of
the second, a grip with both — and it never reaches full activation: 0.50, 0.50
and 0.40 of each muscle's maximum. It read nothing from the application, so the
calibration span fell wherever that cycle happened to be. At rest half the
time, or on an edge, which passes without the «calibration too weak» warning
and leaves a reference half way up. The task then read **above 100 % of the
maximal voluntary contraction**, and a practical rehearsed without hardware
showed the opposite of what it is about.

## The fix

The calibration wizard already knows when it is asking for a maximum, because
it opens a `CAL` span and closes it. It now says so to the device as well.

- **`AcquisitionDevice.instruct(channel_index, level)`** — what is being asked
  of a muscle, 1.0 being its maximum, or `None` to stop asking. It does nothing
  by default: a board has no say in what the person attached to it does. It is
  deliberately not abstract, so no backend has to write an empty method to say
  that it cannot act on it.
- **The BITalino forwards it to the simulated port**, and only when the address
  selects the simulated board.
- **While an effort is asked of one muscle the synthetic subject gives it in
  full and rests the other** — the gesture the instruction asks for. Nothing
  touches the clock, so the cycle goes on from where it was when the asking
  stops.

## What a rehearsal gives now

Measured on the application's own envelope:

| | first muscle | second muscle |
|---|---|---|
| reference, as a share of that muscle's maximum | 0.67 | 0.69 |
| maximum of the task, in % MVC | 53 % | 54 % |

The reference is not the muscle's standard deviation because the envelope of a
Gaussian signal averages less than one. What matters is that the task reads
about the half the cycle asks for, with room to spare, instead of more than the
maximum.

And the co-activation index of the simulated grip is **81 %**, against 20 % for
the flexion and 33 % for the extension: the shape of this laboratory's own
figures for the practical, which is what a rehearsal should show.

## Also in this version

- **Two tests waited by the clock** for something another thread had to do, and
  failed on loaded continuous-integration runners with an index out of range
  that read like a broken worker. Each now waits for the event it depends on,
  and the helper that waits for a signal says so when the signal does not come
  instead of returning quietly.
- **The Zenodo description no longer lists an ECG profile among the features.**
  It is not selectable — `get_profile` has no caller outside its own module in
  any released version — and naming signal families the application does not
  offer invites the question of whether they are there. The profile stays in
  the library, where it is.

## Upgrading

Nothing to do. The settings, the EDF files and the reports of 3.5.0 are read as
before, and a station with a `bitalino.txt` keeps it.
