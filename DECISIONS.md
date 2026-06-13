# Architecture Decision Record

This file records the significant architectural decisions taken while
evolving `emgteach`. Each entry lists the date, the options that were
considered, the option chosen, and the reasoning. The most recent
decisions appear first.

The format is a lightweight ADR (Architecture Decision Record). It is
intended to make the *why* behind the structure auditable, both for
future maintainers and for the teaching context in which the package is
used.

---

## 2026-06-13 — Muscle-load analysis (Jonsson APDF) in the MVC tab

### Decision 1 — Implement Jonsson's APDF method, offline first

**Context.** A faithful equivalent of PluxBioSignals' "Muscle Load Analysis"
add-on was requested. That add-on applies **Jonsson's Amplitude Probability
Distribution Analysis (APDA / APDF)** — a published, public-domain method
(Jonsson 1978/1982), not a proprietary algorithm.

**Options evaluated.** Placement: (a) extend the existing MVC tab; (b) a new
dedicated "Muscle load" tab; (c) a selectable panel in the Analysis tab.
Scope: offline post-processing first vs. online (real-time) from the start.

**Chosen: extend the MVC tab, offline first.** The MVC tab already computes
`emg_norm` (the % MVC envelope), which is exactly the input to the APDF, so
the offline analysis reuses almost everything (one new core function, one new
plot panel, one summary line). The online / real-time variant (warning and
danger zones during acquisition) is deferred to a second phase.

### Decision 2 — Method lives in a Qt-free core module

`src/emgteach/apda.py` (`compute_apdf`, `LoadLevel`, `ApdfResult`) implements
the method with numpy only, mirroring `dsp.py` / `mvc.py`, and is unit-tested
in isolation (`tests/test_apda.py`). The three Jonsson levels are the
**static** (P10), **median** (P50) and **peak** (P90) of the % MVC
distribution.

### Decision 3 — Recommended limits live in the SignalProfile

The static / median / peak recommended maxima (% MVC) are profile attributes
(`apda_static_limit`=5, `apda_median_limit`=14, `apda_peak_limit`=70),
following the Hito-1 extension-point pattern, so they are configurable per
modality without touching the worker or GUI. The defaults follow common
ergonomic guidance derived from Jonsson; they are starting values to be
tuned, **not** clinical thresholds.

### Scope note — whole recording, no real-time zones yet

The offline APDF is computed over the **whole recording** (muscle load is a
task-level statistic), independent of the display-window navigator. The
real-time "warning / danger" zones of the Plux add-on belong to the deferred
online phase.

### Decision 4 — MVC-tab redesign + dedicated MVC PDF report

After validation, the MVC tab was reorganised: the muscle-load APDF moved out
of the time-series subplot stack onto its **own (roughly square) canvas** with
a **structured data panel** beside it; the old horizontal summary box was
dropped; the display-window navigator was made **Analysis-style** (at the
bottom, a minimap bar that fills the width plus a compact two-row control
cluster, no box title and no reset button); and the whole visualisation area
**scrolls vertically**. A dedicated one-click PDF report (`build_mvc_report`
in `reports.py`, mirroring `build_session_report`) renders the panels + APDF
and a metrics table with the load levels against their limits.

---

## 2026-06-11 — Hito 3: PDF session reports (+ visual polish)

### Decision 1 — PDF engine: reportlab

**Options evaluated.** reportlab (a document-layout engine) versus
matplotlib's `backend_pdf`.

**Chosen: reportlab.** It produces a genuinely document-like report
(header, metrics/config tables, per-page footer) with the matplotlib
signal figure embedded as an in-memory PNG. It is **pure Python** (no C
extension, installs cleanly on any interpreter — a welcome contrast to
the PyBluez build saga), so adding it as a dependency is low-risk.
`backend_pdf` would have avoided a new dependency but makes headers and
tables awkward.

### Decision 2 — Simple textual header, no institutional logo

Per the maintainer's preference, the report header is just a title
("Informe de registro y análisis de EMG") plus the generation date and
the relevant session data (optional student name/code, source file). No
UCM logo image is embedded; a logo can be added later if wanted.

### Decision 3 — One-click auto-save next to the EDF

The "Generar informe PDF" button (Analysis tab, enabled after an
analysis) writes the PDF **without a save dialog**, next to the source
EDF as `<stem>_informe_<timestamp>.pdf`, matching the acceptance
criterion ("con un click ... se guarda ... con nombre informativo"). The
full path is logged.

### Known limitation — device not stored in the EDF

The report's configuration section lists the filters, sampling rate and
channel (the `AnalysisWorker` now returns its `config`), but the
**acquisition device is not recorded in the EDF**, so it shows as "no
almacenado en el EDF". Writing the device into the EDF header (and the
buffer-then-flush writer) is deferred so as not to touch the verified
`io.py` write path; it is a clean follow-up.

### Visual polish delivered alongside (same day)

- Mouse-wheel zoom on the Analysis and MVC matplotlib plots (the
  acquisition pyqtgraph plots already had it).
- Event markers are now drawn **live** as vertical lines on the
  acquisition plots (manual and automatic), not only as text — this was
  the missing visual feedback; the marker data path itself was correct.
- The single-channel default label reverted from "Canal 1" to **"EMG"**
  (with a one-time settings migration), restoring the classic channel
  name; two channels default to "EMG"/"EMG 2".

### Outcome

The report core (`src/emgteach/reports.py`, Qt-free, reportlab +
matplotlib-Agg) and its Analysis-tab button are covered by tests
(valid non-empty PDF, with/without markers/config, no-fatigue case) and
an end-to-end GUI smoke. Suite at 119 tests, all passing; `ruff` clean.

---

## 2026-06-11 — Hito 2: annotation system

Most of the annotation system was already in place before this work
(manual markers with a labelled button + ``M`` shortcut, EDF+ annotation
persistence, reader extraction of markers, and marker display/navigation
in the analysis tab). The remaining piece was **automatic
contraction-onset detection**, plus closing the end-to-end acceptance
criterion.

### Decision 1 — Onset threshold: baseline mean + k·SD

**Context.** Surface-EMG onset detection needs a threshold on the
amplitude (envelope). The threshold definition must be robust across
subjects and hardware (BITalino ±3.3 V vs Arduino+MyoWare 5 V).

**Options evaluated.**

- **A — Baseline + k·SD (chosen).** Threshold = mean + ``k``·SD of the
  initial resting window. ``k`` configurable (default 3).
- **B — Fraction of the maximum** envelope (e.g. 15 % of peak).
- **C — Absolute threshold in mV.**

**Chosen: A.** It is the classical single-threshold EMG onset rule, it
auto-adapts to each recording and hardware (no gain dependence), and it
matches the teaching protocol of "rest, then contract" (the rest window
calibrates the baseline). The sensitivity ``k`` is the single
user-facing knob.

### Decision 2 — Detection runs in real time during acquisition

Chosen over an offline-only detector. The acceptance criterion requires
that auto-detected onsets are *saved in the EDF* and visible on reload,
so detection runs live in the acquisition worker (one detector per
channel on the envelope) and records onsets as automatic markers
("Inicio (auto)") through the same path as manual markers. An offline
"detect onsets on a loaded EDF" button was deferred to Phase 2.

### Decision 3 — Minimum-duration debounce (found during testing)

The first implementation fired on single-sample noise excursions above
threshold. Real onset detectors require the signal to *stay* above the
threshold for a minimum duration. A ``min_duration_s`` parameter
(default 50 ms) was added: an onset is declared only after the envelope
has been continuously above threshold for that long, timed at the
crossing, with a refractory period before the next onset. This removed
the false positives. The four onset parameters (``onset_k``,
``onset_baseline_s``, ``onset_refractory_s``, ``onset_min_duration_s``)
live in ``SignalProfile``, following the single-source pattern of the
filter parameters.

### Outcome

Delivered as four commits on branch `feature/annotations` (off `main`):
the onset detector core + profile fields; worker integration (automatic
markers); acquisition-tab controls (enable + sensitivity ``k``); and
end-to-end verification. The suite grew from 105 to 115 tests, all
passing; ``ruff`` clean. The acceptance criterion is covered by tests:
a session with a manual marker *and* an automatic onset round-trips to
the EDF, and both MNE and pyedflib recover the annotations on reload.
The buffer-then-flush writer in ``io.py`` was not modified.

---

## 2026-06-11 — Dual-channel acquisition (agonist/antagonist)

Requested before Hito 2: record two EMG channels simultaneously so that
agonist/antagonist muscle pairs can be studied. Built on top of the
Hito 1 branch (it reuses `SignalProfile` and the device factory).
Strategic note: the Arduino + MyoWare backend is the priority for the
student lab (cheaper, more boards per budget) even though it is
single-channel today, so the architecture is generic over N channels
rather than BITalino-specific.

### Decision 1 — Device contract: `read()` returns `(n_samples, n_channels)`

**Context.** Every layer assumed a single channel: `read()` returned a
1-D array; the worker ran one filter chain and wrote three EDF channels.

**Options evaluated.**

- **A — `read()` always returns 2-D `(n_samples, n_channels)` (chosen)**,
  with an `n_channels` property (default 1) on the ABC.
- **B — Keep 1-D for one channel, 2-D for many.** Branchy worker code.

**Chosen: A.** A single, uniform shape keeps the worker loop simple
(iterate columns) and the contract honest. All implementers and tests
are in-tree, so the breakage was contained. `BitalinoDevice` returns its
requested analogue columns; `ArduinoDevice` gained an `n_channels`
argument and de-interleaves frame-interleaved samples.

### Decision 2 — EDF schema: store only the raw signal per sensor

**Context.** EDF+ channel labels are limited to **16 ASCII characters**.
The previous schema stored three channels per signal
(`<label>`, `<label>_Filtered`, `<label>_Envelope`); with descriptive
multi-sensor labels (e.g. `Antagonista_Filtered` = 20 chars) the derived
labels overflow and are silently truncated. Separately, the app never
reads the stored filtered/envelope channels back — analysis recomputes
them from the raw channel via `process_offline`.

**Options evaluated.**

- **A — One raw channel per sensor (chosen).** Derived signals are
  recomputed on analysis.
- **B — Three channels per sensor** with compact suffixes and truncation
  of long labels.
- **C — Hybrid:** three channels for the single-sensor case, raw-only for
  extra sensors.

**Chosen: A (raw-only).** The raw signal is the scientifically
meaningful datum; the filtered signal and envelope are deterministic
functions of it. Storing only raw sidesteps the label-length limit,
halves-or-better the file size, and loses nothing the application uses.
This does change the single-channel EDF (previously three channels), a
trade-off the maintainer accepted explicitly.

### Decision 3 — Live view layout: overlaid channels (option A)

The three real-time plots (raw, filtered, envelope) overlay one curve
per channel in a consistent per-channel colour (blue = channel 1,
red = channel 2) with a colour legend, rather than one column of plots
per channel. Chosen for compactness and because direct superposition is
the most didactic way to compare agonist/antagonist activation.

### Decision 4 — Arduino firmware: write it now, versioned, 1–2 channels

The repository previously tracked **no** Arduino firmware. A new
`firmware/emgteach_arduino/` sketch (configurable `N_CHANNELS`, matching
the existing wire protocol, frame-interleaved samples) is committed and
shipped in the sdist, so the MyoWare 2-channel path is ready to flash
once a second sensor is wired to `A1`. It is **not** validated by CI (no
hardware in the loop) and must be verified on a real board before use.

### Out of scope (unchanged here)

- Side-by-side dual analysis and the dual-view polish remain for Phase 2.
- The Arduino EDF physical-range correction (5 V vs ±3.3 V) is still a
  separate, behaviour-changing decision (see the Hito 1 entry).

### Outcome

Delivered as five commits on branch `feature/dual-channel` (off the
Hito 1 branch): N-channel data layer; Arduino firmware + sdist;
dual live acquisition view; Analysis/MVC channel selection. The suite
grew from 97 to 105 tests, all passing; `ruff` clean; the GUI boots
offscreen and a simulated two-channel feed renders both channels. The
buffer-then-flush writer in `io.py` was not modified.

---

## 2026-06-11 — Hito 1: architectural refactor

Phase 1 of the planned work. The goal is a more mature architecture
*without* changing user-visible behaviour, in preparation for the
annotation system (Hito 2) and PDF reports (Hito 3).

### Decision 1 — Scope of the refactor: surgical (no file moves)

**Context.** On inspection, the package is already cleanly stratified
into a Qt-free analytic core (`devices/`, `dsp.py`, `fatigue.py`,
`mvc.py`, `io.py`), a Qt bridge (`workers/`) and a presentation layer
(`gui/`). The README already documents this split. The layer separation
requested for Hito 1 is therefore largely *already done*.

**Options evaluated.**

- **A — Surgical (chosen).** Keep the current file layout. Add only the
  missing extension points (a `SignalProfile` domain object and a device
  factory) and remove duplication. No module moves.
- **B — Hybrid.** Surgical plus a new `core/` subpackage to group the new
  abstractions; existing analytic modules stay in place.
- **C — Full reorganization.** Move every module into explicit
  `acquisition/ processing/ persistence/ presentation/` packages.

**Chosen: A (surgical).**

**Reasoning.** The existing separation is good and, critically, the
buffer-then-flush EDF writer (`io.py`) and its 73-test safety net have
been *empirically verified*. Mass file moves (option C) would generate
import churn across the whole codebase and the test suite for a mostly
cosmetic gain, raising the risk of silently disturbing the verified
write path. The real, missing architectural value is in extension points
and de-duplication, which option A delivers with localized, easily
verified changes.

### Decision 2 — Biopotential extension point: a `SignalProfile` object

**Context.** The `AcquisitionDevice` ABC is already an extension point
for new *hardware*, but there is no extension point for new *signal
modalities* (ECG, EEG, EOG). The parameters that define *what a signal
is* — filter band (20–450 Hz), mains notch (50 Hz), envelope cut-off
(5 Hz), RMS window, segment parameters, channel schema
(`EMG`/`EMG_Filtered`/`EMG_Envelope`), physical ranges — were hardcoded
and duplicated across the three worker classes and the GUI tabs.

**Options evaluated.**

- **A — A single `SignalProfile` dataclass (chosen)** bundling
  acquisition, filtering, analysis, channel-schema and display
  parameters, with a module-level `EMG_PROFILE` default.
- **B — Several separate config objects** (`AcquisitionConfig`,
  `ProcessingConfig`, `ChannelSchema`, `DisplayConfig`).

**Chosen: A (single `SignalProfile`).**

**Reasoning.** For a teaching package with a small, fixed number of
modalities, one cohesive, frozen, immutable object is easier to read,
pass around and reason about than four interacting objects. Adding a new
biopotential type becomes "define one new `SignalProfile`", which is the
explicit goal of Hito 1. `EMG_PROFILE` reproduces the exact values used
today, so the refactor is behaviour-preserving by construction.

### Decision 3 — Legacy EDF helpers: deprecate, do not remove

**Context.** `io.create_edf_writer` and `io.write_edf_block` are part of
the public API (`__init__.py`) since v0.1.0, but are not used anywhere in
the package or the test suite — only the original prototype used them.
They implement the *unsafe* per-block write that the buffer-then-flush
pattern (Agis-Torres, 2026) was designed to replace.

**Options evaluated.**

- **A — Deprecate (chosen).** Keep them, emit a `DeprecationWarning`, and
  point the docstring to `BufferedEdfWriter`.
- **B — Leave them unchanged.**
- **C — Remove them.**

**Chosen: A (deprecate).**

**Reasoning.** Removal (C) would be a breaking change to an already
published, citable release. Leaving them silent (B) keeps an unsafe path
discoverable without any warning. Deprecation (A) preserves backward
compatibility while actively steering users towards the safe writer,
which is consistent with the methodological contribution of the
buffered-write paper.

### Out of scope for Hito 1 (flagged, not changed)

These are real improvements but change *behaviour*, not structure, so
they are deferred to an explicit decision rather than folded silently
into the refactor:

- Exposing all DSP filter parameters in the acquisition GUI (currently
  the acquisition tab does not forward any filter settings to the
  worker). This is a feature, not a refactor.
- Correcting the EDF physical range for the Arduino + MyoWare backend
  (5 V) versus the BITalino default (±3.3 V). This changes the
  digital↔physical mapping of saved files and should be a conscious,
  separately verified change.

### Outcome

Delivered as five commits on branch ``refactor/hito-1-arquitectura``:

1. ``src/emgteach/profiles.py`` — ``SignalProfile`` + ``EMG_PROFILE``,
   the biopotential extension point.
2. The three workers source their DSP/analysis/channel defaults from a
   profile; the triple-duplicated filter literals are gone.
3. ``src/emgteach/devices/factory.py`` — ``create_device`` /
   ``register_device`` registry; the acquisition tab builds devices
   through it instead of importing concrete classes.
4. The acquisition tab sources its display ranges, marker vocabulary and
   nominal sampling rate from ``EMG_PROFILE``; the legacy EDF helpers now
   emit ``DeprecationWarning``.

Verification: the full suite grew from 74 to 97 tests, all passing
(``pytest -m "not hardware"``), ``ruff check`` clean, and the GUI boots
offscreen with the profile-driven values live. The buffer-then-flush
writer in ``io.py`` was not modified and its round-trip tests still pass,
confirming the central buffered-write pattern is intact. ``mypy`` reports only the
same pre-existing QSettings/Qt typing notes present before the refactor.
