Teaching-focused release: a simpler live view, save-as dialogs, a fully Spanish interface and didactic tooltips.

### Changed
- **Teaching-focused live view.** The Acquisition tab now plots only the raw signal and the envelope; the intermediate filtered trace is no longer shown (it is still computed for the envelope, and the EDF keeps the raw channel).
- **BITalino-only interface.** The Arduino + MyoWare backend is hidden in the device selector (its code path is unchanged), matching how the teaching lab is equipped.
- **Teaching panel selection.** The Analysis "Panels to show" defaults to the three panels used in class — raw signal, normalised envelope and PSD — renumbered 1A / 2 / 3; the remaining panels follow as 4–8, unchecked but still selectable, consistent on screen and in the PDF report.
- **Author credit.** The splash and About box now read "Dr. Agis-Torres et al.".
- **APDF legend key.** The muscle-load distribution chart (MVC tab and PDF report) now labels the red out-of-range ring in its legend.

### Added
- **Choose where recordings are saved.** Starting a recording opens a "Save as…" dialog to pick the EDF file name and folder.
- **Choose where reports are saved.** The Analysis and MVC PDF reports are written through a "Save as…" dialog (name + folder).
- **iEMG hint** and **didactic tooltips** across the "Panels to show" options, the envelope cut-off, the analysis-summary metrics and the muscle-load (APDF) chart.

### Fixed
- **Complete Spanish interface.** Translated the strings that still showed in English (fragment editor, CSV export, region-of-interest, Protocol field, CSV headers, fatigue verdicts, marker deletion, fragment "reason" labels) plus a hard-coded axis label in the PDF report.
- **Quieter console.** Suppressed a benign `QFont::setPointSize: Point size <= 0` pyqtgraph warning.

Runs on Windows, macOS and Linux with Python 3.10–3.12; 216 automated tests. Licensed under GPL-3.0-or-later.
