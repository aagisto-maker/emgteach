Maintenance release for publication: both device backends are selectable again, plus small UI polish.

### Changed
- **Device backend selectable again.** The BITalino (Bluetooth) / Arduino + MyoWare 2.0 (USB) selector is shown again, so both interchangeable backends can be chosen — matching the documented feature set. BITalino remains the default.
- **Neutral splash subtitle.** The start-up splash now reads "Surface EMG acquisition" instead of naming a single backend.

### Fixed
- **Muscle-load tooltip layout.** The muscle-load (APDF) chart's hover tooltip now word-wraps into a compact box instead of forcing a line break after each sentence.

Runs on Windows, macOS and Linux with Python 3.10–3.12; 216 automated tests. Licensed under GPL-3.0-or-later.
