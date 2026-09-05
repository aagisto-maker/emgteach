# emgteach 3.0.0 — the practical is the configuration

A major release that changes how a session is set up. The application is no
longer assembled out of settings: you choose the practical, and the practical
decides what is recorded and what each tab offers. Around that, the session
becomes a **single file with its phases marked inside it**, so the maximum
every percentage is measured against travels with the signal.

Exercised against the hardware on 1, 3 and 5 September 2026. The figures
quoted below are measured on those recordings, not estimated.

## The breaking change

- **Three practicals instead of a panel of controls**: one muscle (1 channel),
  agonist/antagonist (2 channels) and muscle kinematics (1 channel + the
  accelerometer). The practical fixes the channel count and the accelerometer,
  and each tab offers only the measurements that suit it. The channel-count
  selector, the accelerometer tick box and the free-analysis mode are **gone
  from the interface**: they could only ever contradict the chosen practical.
  A coloured band names the level — basic, intermediate, advanced — and the
  fine controls belong to the kinematics practical, which is advanced by its
  own nature.

## Added

- **The session is one file, with its phases marked inside it.** Warm-up,
  calibration repetitions, preparation and recording are written as EDF+
  annotations, and the MVC reference travels in the file as well. Both tabs
  recompute the reference from the same spans, so the same recording opened
  anywhere tells the same story. A derived **tuned recording** writes the
  decisions taken on screen — which repetitions count, which fragments are the
  task — into a new file that reopens with those same numbers, leaving the
  original untouched.
- **A teaching layer.** A guided tour over the interface itself, following the
  practical; a «?» on every box, with the physiology behind the control; empty
  panels that say what to do next; and a floating panel that names the next
  step over the control it points at.
- **One analysis row per contraction**, with when it began, how long it
  lasted, which muscle led it, its RMS, its peak as a share of the maximum,
  its median frequency and — where the accelerometer sits on the moving
  segment — its **electromechanical delay**. Median 42 ms on the bench, in the
  30–100 ms range the literature gives.
- **Agonist/antagonist co-activation** by the Falconer-Winter index, computed
  per marked phase and in % MVC of each muscle's own reference, with three
  safeguards against the index that a pair of resting muscles would otherwise
  return. On the forearm protocol: 16 % for the flexion, 12 % for the
  extension and 95 % for the grip.
- **The kinematics practical as the sequence it is**: the plan (loads, lifts
  per load, seconds to prepare and to lift), an optional rehearsal that runs
  the whole procedure with no hardware, and a record button that runs the
  session by itself — the calibration of the maximum, then one cued quick lift
  per repetition of each load, each marked in the file with its load. The
  force-velocity study then reads the contraction table's own rows.
- **A crash log**: uncaught exceptions are written to `emgteach-errores.log`
  in the user's home directory and announced without blocking the application.

## Changed

- **The reference is the maximum the task cannot beat.** Measured over the
  strongest 0.2 s, and the calibration asks for three brief maximal efforts
  against something that cannot move. A maximum performed in mid-air is
  submaximal by construction, which is the force-velocity relationship this
  application teaches in another practical.
- **Auto-normalisation is no longer offered** unless the fine controls are on,
  and where it is used the result is marked as such on screen and in the PDF.
- The Spanish interface settles on *usted*, and Qt's own dialogue buttons are
  translated.
- The BITalino front-end gain is divided out in the conversion to millivolts:
  full excursion is ±1.635 mV, not ±1.65 mV. Anything expressed as a ratio is
  unaffected.

## Fixed

Among many others: EDF+ annotations were being dropped in bursts (four
annotation signals are reserved now); an annotation was cut by characters
where the format counts **bytes**, which left a partial character and made a
derived file unreadable; a Qt warning reached the operator as a crash dialogue
because the windowed build has no stderr; and no sentence written at run time
can push the window off the screen any more.

## Meta

- Bumped to 3.0.0 (`pyproject.toml`, `__init__`, `.zenodo.json`,
  `CITATION.cff`).
- Runs on Windows/macOS/Linux with Python 3.10–3.12; **940 automated tests**;
  GPL-3.0-or-later.
- Documentation rewritten around the three practicals, in English and
  Spanish: manual, lab practicals, cheat sheet, electrode placement and
  evaluation rubric.
- The version-specific Zenodo DOI is to be minted at release.
