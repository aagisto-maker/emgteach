# emgteach 2.0.0 — kinematics with the BITalino accelerometer

A major release adding a **kinematic dimension** to emgteach through the
BITalino accelerometer, validated on hardware (real velocities; correctly
descending load-velocity and Hill force-velocity curves).

## Added

- **Selectable accelerometer channel + a live channel diagnostic.** The
  accelerometer is no longer hard-wired to A4: an *ACC ch:* selector and a
  *Find ACC channel…* tool read all six analogue inputs live and identify the
  one that responds when the sensor is tilted (on this board the on-board
  accelerometer is on A1). The device always exposes the accelerometer as the
  trailing column whatever input it is on, and the EMG channels automatically
  skip it.
- **Guided force-velocity acquisition.** A *Guided F-V…* wizard runs an MVC
  maximum (no load) and then, for each load and repetition, a discrete
  quick-lift cue (`Lift <kg>!` → `Relax!`, no hold — force-velocity needs
  shortening velocity, not an isometric hold). It starts the recording itself
  and auto-marks every contraction with its load.
- **Force-velocity study.** Builds its repetition windows straight from those
  markers, pre-fills the loads, lets you exclude an invalid repetition and
  averages repetitions of the same load, warns when the accelerometer barely
  moved, and draws the load-velocity, Hill force-velocity, power and
  recruitment curves.
- **Movement-vs-EMG analysis panel** for the moving-segment placement, also
  included in the PDF report.

## Fixed / changed

- Stable ±1 g accelerometer plot with its own aligned vertical-zoom buttons.
- The window starts maximised, so the whole interface fits the screen and can
  be closed normally.

## Meta

- Bumped to 2.0.0 (`pyproject.toml`, `__init__`, `.zenodo.json`, `CITATION.cff`).
- Author metadata: e-mails added for Vítor Samuel Fernandes and Jorge
  Navarro-Dorado; CRediT roles (Supervision · Validation · Writing – review &
  editing) added for Belén Climent and Medardo Hernández for their work on the
  kinematic aspect.
- Runs on Windows/macOS/Linux with Python 3.10–3.12; 272 automated tests;
  GPL-3.0-or-later.
- The version-specific Zenodo DOI is to be minted at release.
