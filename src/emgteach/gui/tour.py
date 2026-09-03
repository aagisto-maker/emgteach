"""Guided tour content — the five things to know before the first recording.

Separated from the widget that draws it (:mod:`emgteach.gui.widgets.coach`) so
the teaching text lives in one readable place and can be revised without
touching interface code.

Five steps, not seventeen. The tour is offered to a student who wants to
record, and every step past the fifth was about a control they could already
see and would only wonder about when they got to it. That text now lives on
the «?» of each box (:mod:`emgteach.gui.help_texts`), shown over the box
when it is asked for. What is left here is the sequence: choose the
practical, connect, record with the calibration inside, read the analysis
the practical is about, and why everything is in % MVC.

The tour follows the selected mode: it explains the accelerometer only in the
kinematics practical and agonist/antagonist coordination only in that one.
Explaining a control the user cannot see is worse than not explaining it.

The wording is the teaching content of the application, so it is the author's
to write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from emgteach.gui.widgets.coach import CoachStep
from emgteach.i18n import tr
from emgteach.modes import MODE_PAIR, mode_fixed_labels, mode_uses_acc

if TYPE_CHECKING:  # pragma: no cover - typing only
    from emgteach.gui.app import MainWindow

TAB_ACQ, TAB_ANA, TAB_MVC = 0, 1, 2


def build_tour(win: MainWindow) -> list[CoachStep]:
    """The steps for the mode currently selected."""
    mode = win._mode()
    adq, ana, cvm = win._tab_adq, win._tab_ana, win._tab_cvm
    steps: list[CoachStep] = []

    # 1 ── The practical decides everything else.
    steps.append(CoachStep(
        tr("Choose the practical first"),
        tr(
            "Everything else follows from this. Each mode records what that "
            "practical needs — one muscle, an agonist/antagonist pair, or a "
            "muscle plus the accelerometer — and the rest of the interface "
            "offers only the measurements that make sense for it. The "
            "coloured band beside it is the level: basic, intermediate or "
            "advanced."
        ),
        lambda: win._combo_mode,
        tab=TAB_ACQ,
    ))

    # 2 ── Connect: the device, the electrodes, and the names.
    if mode_fixed_labels(mode):
        nombres = tr(
            "This practical names its channel itself, so there is nothing to "
            "type."
        )
    else:
        nombres = tr(
            "Type the name of each muscle in its box, following the order of "
            "the board's channels (Muscle 1 is the one recorded on A1)."
        )
    steps.append(CoachStep(
        tr("Connecting the sensor"),
        tr(
            "The recording can be made with either of two devices: BITalino "
            "(Bluetooth) or Arduino (USB). Switch the board on and connect "
            "the electrodes: the positive and the negative go on the midline "
            "of the muscle, the reference on a neutral point, over a bone if "
            "possible."
        ) + " " + nombres,
        lambda: adq._btn_conectar,
        tab=TAB_ACQ,
    ))

    # 3 ── Record, with the maximum inside the recording.
    steps.append(CoachStep(
        tr("Recording"),
        tr(
            "Press record. The session asks first for a maximal contraction "
            "— the reference every measurement is expressed against — and "
            "then for the task. Both go into one file, so nothing has to be "
            "matched up afterwards. Watch the live trace: at rest it should "
            "be a flat line with only baseline noise. A signal that never "
            "returns to baseline usually means a loose electrode, not a "
            "tonic muscle. Each contraction onset is marked on its own."
        ),
        lambda: adq._btn_grabar,
        tab=TAB_ACQ,
    ))

    # The kinematics practical has two things nobody would guess: where the
    # accelerometer goes, and that the force-velocity experiment can be
    # rehearsed before it is done live.
    if mode_uses_acc(mode):
        steps.append(CoachStep(
            tr("How to place the accelerometer"),
            tr(
                "There are two possibilities: on the muscle it allows the "
                "mechanomyogram (MMG) to be measured, which runs in parallel "
                "with the electrical signal; on the moving segment of the "
                "joint it allows the movement, and the parameters associated "
                "with it, to be measured — including the delay between the "
                "muscle firing and the limb moving."
            ),
            lambda: adq._box_acc,
            tab=TAB_ACQ,
        ))
        steps.append(CoachStep(
            tr("The force-velocity experiment, and its rehearsal"),
            tr(
                "The step-by-step wizard guides you through the contractions "
                "with different loads: with a greater load the velocity is "
                "lower, and that inverse relation is the force-velocity "
                "curve. As it is the longest procedure in the application, a "
                "simulation is provided as a rehearsal, so that what is "
                "going to be done live is understood first."
            ),
            lambda: adq._btn_fv_rehearse,
            tab=TAB_ACQ,
        ))

    # 4 ── What the analysis is about, in this practical.
    if mode == MODE_PAIR:
        steps.append(CoachStep(
            tr("Agonist and antagonist"),
            tr(
                "The recording is analysed as soon as it is opened. Both "
                "muscles were calibrated while recording, so the two "
                "envelopes are overlaid in % MVC — the only form in which two "
                "different muscles compare at all, since each one's "
                "millivolts depend on its own electrodes and skin. In a clean "
                "movement the agonist activates while the antagonist stays "
                "nearly silent; simultaneous activation is co-contraction, "
                "which holds the joint rigid and is typical of an unpractised "
                "or uncertain movement. The table below the panels gives one "
                "row per contraction, and which muscle led it."
            ),
            lambda: ana._box_compare,
            tab=TAB_ANA,
        ))
    elif mode_uses_acc(mode):
        steps.append(CoachStep(
            tr("Force-velocity study"),
            tr(
                "The recording is analysed as soon as it is opened. The study "
                "builds the load-velocity, force-velocity and power curves "
                "from a recording where several known loads were lifted, and "
                "relates them to the EMG amplitude — that is, to how many "
                "motor units had to be recruited for each load. The panels "
                "also show the movement against the EMG and the delay "
                "between the two."
            ),
            lambda: ana._btn_fv,
            tab=TAB_ANA,
        ))
    else:
        steps.append(CoachStep(
            tr("What the analysis shows"),
            tr(
                "The recording is analysed as soon as it is opened. Raw "
                "signal: what the contracting fibres produce. Normalised "
                "envelope: how activation changes over time, which is what is "
                "compared between efforts. Spectrum: how the activity is "
                "distributed across frequencies — as a sustained contraction "
                "fatigues the muscle, the median frequency (MDF) falls. The "
                "cards above the panels carry the numbers with their usual "
                "ranges, and the table below gives one row per contraction."
            ),
            lambda: ana._chk_paneles[0],
            tab=TAB_ANA,
        ))

    # 5 ── Why everything is in % MVC.
    # That tab greets a new session with its own explanation panel, which
    # covers the very controls this step points at; it is put away first.
    steps.append(CoachStep(
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
        lambda: cvm._edit_path,
        tab=TAB_MVC,
        on_enter=cvm._dismiss_entry_screen,
    ))

    return steps
