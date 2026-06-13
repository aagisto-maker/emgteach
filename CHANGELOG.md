# Changelog

All notable changes to **emgteach** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-06-13

### Added
- **Bilingual interface (English / Spanish).** A lightweight `tr()` layer
  (`emgteach.i18n`) with English-canonical source strings and a Spanish
  translation map (~210 entries). The start-up language is detected from the
  system locale (Spanish → `es`, otherwise `en`) and can be switched
  (English / Español) from the tab-bar corner; the choice is stored in
  `QSettings` and applied on the next launch.
- **Stacked two-channel live view.** With two channels, the raw and filtered
  acquisition plots stack into one vertical lane per channel (instead of
  overlapping on a shared zero), with per-lane reference ticks, a coloured
  zero baseline and the muscle label drawn in each lane. The envelope stays
  overlaid (non-negative → directly comparable). Single-channel behaviour is
  unchanged.
- **Per-channel vertical zoom** (▲ / ▼) that scales an independent gain per
  channel in stacked mode, leaving the lane positions fixed.
- **Report graph picker.** Generating a PDF report now opens a dialog to choose
  which analysis panels are rendered into the document; each selected panel is
  drawn as its own graph (`build_session_report(..., panels=...)`).
- **Muscle-load analysis (Jonsson APDF).** The MVC tab now computes the
  Amplitude Probability Distribution Function of the % MVC envelope and reports
  the **static** (P10), **median** (P50) and **peak** (P90) load levels against
  configurable recommended limits, with a dedicated distribution panel and a
  colour-coded summary. New Qt-free `emgteach.apda` module
  (`compute_apdf`); limits live in `SignalProfile`.

### Changed
- **Compact, themed GUI.** The acquisition tab was reorganised into two compact
  rows. A centralised application stylesheet (`_APP_STYLESHEET` in
  `gui/app.py`) gives all three tabs a consistent steel-blue look with white
  plot areas. The author attribution moved from a permanent status bar to an
  "About" (?) button in the tab-bar corner, freeing vertical space for the
  plots.
- **Analysis / MVC polish.** The Analysis tab gained mouse-wheel zoom over the
  panels, alongside a time-window minimap navigator with a smoother
  move/resize drag — a narrow selection now always pans instead of accidentally
  resizing, and the resize handles are capped and shown as edge grips. The
  drawn window defaults to the whole recording. Typography was unified across
  the MVC tab.

### Fixed
- A few user-facing strings (the analysis progress bar, the fatigue-summary
  verdicts, the MVC-source fallback label and the vertical-zoom sidebar
  letters) bypassed the translation layer and stayed in Spanish in English
  mode; they now follow the selected language.

### Internal
- Test suite grows to 126 passing tests on Python 3.10–3.12.
- The developer layer (code comments and docstrings) is now fully English.

## [0.2.0] — 2026-06-11

### Added
- **Two-channel acquisition** (e.g. agonist / antagonist) with an editable
  label per channel; the data layer is generic over N channels. EDF stores
  raw-only, one channel per sensor (filtered / envelope are recomputed on
  analysis).
- **Automatic contraction-onset detection** (`dsp.OnsetDetector`): baseline
  mean + k·SD threshold with a min-duration debounce and refractory period,
  stored as EDF+ annotations. An enable checkbox and sensitivity (k) control
  were added to the acquisition tab.
- **One-click PDF session reports** (`emgteach.reports`, reportlab +
  matplotlib-Agg, Qt-free): header, signal plot with annotations, metrics
  table (RMS / MNF / MDF / fatigue / IEMG / duration), configuration used and
  a reproducible footer (version + git commit + timestamp).
- **Open-source Arduino firmware** (`firmware/emgteach_arduino/`, 1–2 channels,
  configurable `N_CHANNELS`) shipped in the sdist.
- Mouse-wheel zoom on the Analysis / MVC plots; live event markers drawn on the
  acquisition plots.

### Changed
- **Architectural refactor (non-breaking).** Two extension points were added:
  `SignalProfile` (`profiles.py`, with `EMG_PROFILE`) for new biopotential
  modalities, and a device factory (`devices/factory.py`,
  `create_device` / `register_device`) for new hardware backends. Workers now
  read their defaults from the active profile.

### Deprecated
- Legacy EDF helpers `create_edf_writer` and `write_edf_block`, superseded by
  `BufferedEdfWriter`. Kept for backward compatibility, not removed.

## [0.1.0] — 2026-05-10

### Added
- First public release. A Qt-free analytic core (`io`, `dsp`, `fatigue`,
  `mvc`, `devices`) and a three-tab PySide6 GUI (Acquisition, Analysis, MVC
  normalisation).
- Two interchangeable hardware backends behind a common `AcquisitionDevice`
  interface: **BITalino (revolution)** over Bluetooth and an **Arduino
  RedBoard Plus + MyoWare 2.0** over USB serial.
- **EDF+ output** with the buffered-write pattern that avoids the silent
  corruption artefact characterised in Agis-Torres (2026).
- Reproducible synthetic signals for class assignments and hardware-free CI.
- A BITalino watchdog that releases blocked Bluetooth reads in ~50 ms after
  disconnection.

[0.3.0]: https://github.com/aagisto-maker/emgteach/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/aagisto-maker/emgteach/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aagisto-maker/emgteach/releases/tag/v0.1.0
