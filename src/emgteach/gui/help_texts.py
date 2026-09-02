"""What each box is for — the text behind its «?».

This is where most of the old seventeen-step tour went. Each entry is a
title and a body, looked up by a short key from the box that owns it, and
shown over that box by :class:`emgteach.gui.widgets.help_button.HelpButton`.
Kept in one file, like the tour, so the teaching text can be revised without
touching interface code. Wording is the author's; the entries that came
from the tour carry his text unchanged.
"""

from __future__ import annotations

from emgteach.i18n import tr


def text(key: str) -> tuple[str, str]:
    """Title and body for ``key``; raises ``KeyError`` for an unknown one."""
    return _TEXTS[key]()


def keys() -> list[str]:
    return list(_TEXTS)


# Functions rather than strings so tr() runs at the moment of showing, in
# the language selected then, not the one at import time.
_TEXTS = {
    # ── Acquisition ────────────────────────────────────────────────────
    "acq.device": lambda: (
        tr("Devices the application supports"),
        tr(
            "The recording can be made with either of two devices: BITalino "
            "(Bluetooth) or Arduino (USB)."
        ) + " " + tr(
            "Choose the device and the port it appears on; on a laboratory "
            "computer this is set once and kept. The student code written "
            "here goes into the file name and the report."
        ),
    ),
    "acq.control": lambda: (
        tr("Recording"),
        tr(
            "Start recording and ask for the contraction. Watch the live "
            "trace: at rest it should be a flat line with only baseline "
            "noise. A signal that never returns to baseline usually means a "
            "loose electrode or a poor contact, not a tonic muscle."
        ) + " " + tr(
            "In the practicals that need a reference, the session asks for "
            "the maximal contraction first and the task afterwards, and "
            "writes both into one file."
        ),
    ),
    "acq.markers": lambda: (
        tr("Marks are put on by themselves"),
        tr(
            "With this ticked the application timestamps each contraction "
            "onset as it finds it — the threshold is the resting level plus "
            "k standard deviations, and k is the knob beside it. The marks "
            "travel inside the EDF, so each effort can be found again during "
            "the analysis. Unticked, nothing is written: marking by hand "
            "during a recording asks the operator to keep up with a signal "
            "that does not wait."
        ),
    ),
    "acq.plots": lambda: (
        tr("The live signal"),
        tr(
            "The upper trace is the raw signal: the sum of the action "
            "potentials of the fibres under the electrodes, in millivolts. "
            "The lower one is its envelope — the raw signal rectified and "
            "smoothed — which follows how hard the muscle is working and is "
            "what the load bars and the analysis are built on."
        ),
    ),
    "acq.load": lambda: (
        tr("Calibrating the contraction"),
        tr(
            "A maximal voluntary contraction is asked for, and it becomes the "
            "reference against which the live load bars and the measurements "
            "are expressed, making contractions easier to compare."
        ) + " " + tr(
            "Three repetitions are recorded and the reference is the "
            "strongest half-second held; a repetition that came out weak can "
            "be discarded afterwards in the analysis."
        ),
    ),
    "acq.classroom": lambda: (
        tr("Following the recording remotely"),
        tr(
            "Every member of the group making the recording can watch the "
            "trace on their own mobile device. This is done by scanning the "
            "QR code the application generates."
        ),
    ),
    # ── Analysis ───────────────────────────────────────────────────────
    "ana.params": lambda: (
        tr("Opening a recording"),
        tr(
            "Open a recording and it is analysed on its own; the channel to "
            "study is the muscle's name from the file. The two buttons "
            "underneath are for afterwards: «Calibration repetitions…» "
            "chooses which maximal efforts fix the reference, and «Select "
            "fragments…» limits the analysis to some of the contractions. "
            "Neither is needed to read a clean recording."
        ),
    ),
    "ana.panels": lambda: (
        tr("The basic panels"),
        tr(
            "Raw signal: the signal from the set of fibres that are "
            "contracting. Normalised envelope: shows how activation "
            "changes over time, which is what is compared between "
            "efforts. Power spectrum: how the muscle activity is "
            "distributed across the different frequencies recorded."
        ) + " " + tr(
            "As a sustained contraction fatigues the muscle, the "
            "conduction velocity of the fibres falls and the spectrum "
            "shifts towards low frequencies: the median frequency (MDF) "
            "drops while the amplitude often rises, because more motor "
            "units are recruited to hold the same force."
        ),
    ),
    "ana.summary": lambda: (
        tr("Reading the numbers"),
        tr(
            "Each card is one figure for the whole analysed span, with its "
            "usual range in grey where one can be given: those ranges are "
            "orientative values for surface EMG in healthy adults, not "
            "limits. The task maximum says how far the effort went against "
            "the calibrated maximum; well above 100 % means the calibration "
            "was not maximal. The fatigue verdict has its own «?». The table "
            "further down gives the same figures contraction by contraction."
        ),
    ),
    # ── MVC normalisation ──────────────────────────────────────────────
    "mvc.params": lambda: (
        tr("Why normalise at all"),
        tr(
            "A raw amplitude cannot be compared between two people, or "
            "between two sessions of the same person: it depends on the "
            "electrodes, the skin and the fat beneath it. Expressing every "
            "value as a percentage of the maximal contraction cancels all of "
            "that out, because the two amplitudes share the same electrodes "
            "and the same skin: what is left is how hard the muscle is "
            "working. The maximum is inside the recording: the session "
            "calibrates without stopping, so nothing else has to be chosen "
            "here."
        ),
    ),
    "mvc.load": lambda: (
        tr("Muscle load"),
        tr(
            "Once the signal is in % MVC, the distribution of load over time "
            "can be read against the Jonsson limits: the static level (P10) "
            "is the load the muscle stays above 90 % of the time, the "
            "background tension it hardly ever lets go of, and the level most "
            "associated with sustained-effort discomfort."
        ),
    ),
}
