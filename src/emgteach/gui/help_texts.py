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
from emgteach.profiles import EMG_PROFILE


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
            "The application supports two devices: the BITalino over "
            "Bluetooth and the Arduino + MyoWare 2.0 over USB. Only the "
            "single-muscle practical can use the Arduino; the other two need "
            "the BITalino's second channel or its accelerometer, so they fix "
            "it and the selector does not appear."
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
            "Three sustained maximal efforts are recorded, then three brief "
            "maximal squeezes: a held contraction shows a peak at its start "
            "and then a plateau, and a brief squeeze reaches that peak alone. "
            "The reference is the strongest 0.2 s across all six, so it is a "
            "maximum the task cannot exceed; a repetition that came out weak "
            "can be discarded afterwards in the analysis."
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
        ) + " " + tr(
            "The chips at the end of that line choose which panels are drawn; "
            "hover over «Panels:» for what each one shows."
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
        "<p>" + tr(
            "Each card is one figure for the whole analysed span, with its "
            "usual range in grey where one can be given: those ranges are "
            "orientative values for surface EMG in healthy adults, not "
            "limits. The task maximum says how far the effort went against "
            "the calibrated maximum; well above 100 % means the calibration "
            "was not maximal. The table beside gives the same figures "
            "contraction by contraction."
        ) + "</p><p><b>" + tr("Fatigue") + "</b><br>" + tr(
            "As a muscle fatigues, its action potentials slow down and "
            "the EMG spectrum shifts towards lower frequencies. The "
            "median frequency (MDF) is the frequency that splits the "
            "spectrum in two halves of equal power; it is the standard "
            "measure of that shift."
        ) + " " + tr(
            "The application computes the MDF on successive windows and "
            "fits a straight line to it over time. The verdict follows "
            "that line:"
        ) + "</p><ul><li>" + tr(
            "<b>Detected</b>: the MDF falls clearly and the line fits "
            "the data (high R²)."
        ) + "</li><li>" + tr(
            "<b>Not detected</b>: the MDF stays flat or rises."
        ) + "</li><li>" + tr(
            "<b>Not conclusive</b>: the line does not fit (low R²). "
            "This is usual with short or intermittent contractions; the "
            "recording does not answer the question, which is not the "
            "same as answering “no”."
        ) + "</li></ul><p>" + tr(
            "Fatigue is only meaningful on a sustained contraction of "
            "some tens of seconds. On a series of short contractions the "
            "verdict says nothing about the muscle."
        ) + "</p>",
    ),
    "ana.coact": lambda: (
        tr("Co-activation (Falconer-Winter)"),
        "<p><b>" + tr("What it measures") + "</b><br>" + tr(
            "Of all the activity in the two muscles, how much of it was "
            "shared — how much they worked at the same time. 0 % means one "
            "worked and the other did not; 100 % means both did the same "
            "thing throughout."
        ) + "</p><p><b>" + tr("Why one row per window") + "</b><br>" + tr(
            "The index compares the shape of the two envelopes, so it only "
            "means something over a stretch in which one thing was being "
            "done. Over a whole recording that mixes rest, flexion and "
            "grip it still produces a number, and that number is not a "
            "measurement of anything."
        ) + "</p><p><b>" + tr("Where the windows come from") + "</b><br>"
        + tr(
            "From «{button}», at the top of this tab. Each row of that "
            "dialogue has a name, which the app fills in itself with the "
            "muscle that led the contraction. Consecutive rows with the "
            "same name become one window here — six flexions in a row give "
            "one row in this table, not six."
        ).format(button=tr("Select fragments…"))
        + "</p><p><b>" + tr("If it says «whole recording»")
        + "</b><br>" + tr(
            "Then no window has a name: either the fragment editor has not "
            "been opened, or the names were cleared. Open it and accept "
            "what it proposes."
        ) + "</p>",
    ),
    "ana.contr": lambda: (
        tr("Contractions"),
        "<p>" + tr(
            "Each row is one contraction the application found on its "
            "own, the same ones the fragment editor proposes. With two "
            "muscles, the row belongs to the one that led it; "
            "«Co-contraction» means both worked at once, and the numbers "
            "are the stronger one's."
        ) + "</p><ul><li><b>" + tr("RMS") + "</b>: " + tr(
            "mean amplitude of the filtered signal over the contraction. "
            "Rest is a few hundredths of a millivolt; a firm effort with "
            "surface electrodes is usually 0.1–1 mV, and depends on the "
            "electrodes and the skin, which is why % MVC exists."
        ) + "</li><li><b>" + tr("Peak (% MVC)") + "</b>: " + tr(
            "the highest {w:.1f} s of the contraction against the "
            "maximum. A task effort is usually 20–80 %; above 100 % (in "
            "red) the calibration was not a maximum."
        ).format(w=EMG_PROFILE.mvc_peak_window_s) + "</li><li><b>" + tr("MDF") + "</b>: " + tr(
            "median frequency of the spectrum. Typically 60–150 Hz for "
            "surface EMG of limb muscles; it falls along a sustained "
            "effort as the muscle fatigues. Not shown for contractions "
            "shorter than a quarter of a second."
        ) + "</li><li><b>" + tr("EMD") + "</b>: " + tr(
            "electromechanical delay, from the electrical onset to the "
            "start of the movement measured by the accelerometer on the "
            "limb. Usually 30–100 ms in healthy adults: the time the "
            "muscle takes to take up its slack and build force."
        ) + "</li></ul>",
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
