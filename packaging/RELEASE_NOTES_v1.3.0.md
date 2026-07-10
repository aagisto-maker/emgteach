Feature release: a guided, on-screen MVC-calibration wizard for the live muscle-load monitor.

### Added
- **Guided MVC-calibration wizard.** A floating on-screen guide walks the subject through the live-MVC calibration one muscle at a time: a "get ready" countdown, a "contract at maximum" phase with a window-progress bar and a live effort bar, then a relax pause — with an optional **Best of 3** mode (off by default) that repeats each muscle three times and keeps the strongest contraction. New `MvcOverlay` widget and `emgteach.mvc.mvc_from_reps` helper.

Runs on Windows, macOS and Linux with Python 3.10–3.12; 216 automated tests. Licensed under GPL-3.0-or-later.
