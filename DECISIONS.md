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
pattern (Agis-Torres, 2026, BSPC) was designed to replace.

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
which is consistent with the methodological contribution of the BSPC
paper.

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
