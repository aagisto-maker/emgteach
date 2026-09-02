"""Guided tour content — what each control is and what it means physiologically.

Separated from the widget that draws it (:mod:`emgteach.gui.widgets.coach`) so
the teaching text lives in one readable place and can be revised without
touching interface code.

The tour follows the selected mode: it explains the accelerometer only in the
kinematics practical and agonist/antagonist coordination only in that one.
Explaining a control the user cannot see is worse than not explaining it.

The wording is the teaching content of the application, so it is the author's
to write. Most steps now carry his text, applied as given; the remainder are
still the first pass drafted from the tooltips and are awaiting his revision.
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

    # ── Where the app is configured ───────────────────────────────────
    steps.append(CoachStep(
        tr("Choose the practical first"),
        tr(
            "Everything else follows from this. Each mode records what that "
            "practical needs — one muscle, an agonist/antagonist pair, or a "
            "muscle plus the accelerometer — and the rest of the interface "
            "offers only the measurements that make sense for it."
        ),
        lambda: win._combo_mode,
        tab=TAB_ACQ,
    ))
    steps.append(CoachStep(
        tr("Complexity level"),
        tr(
            "The coloured band shows the level of the practical: basic, "
            "intermediate or advanced. The further along, the more of the "
            "reading is interpretation rather than measurement; the fine "
            "settings appear only in the advanced one."
        ),
        lambda: win._lbl_nivel,
        tab=TAB_ACQ,
    ))

    # ── Acquisition ───────────────────────────────────────────────────
    steps.append(CoachStep(
        tr("Devices the application supports"),
        tr(
            "The recording can be made with either of two devices: BITalino "
            "(Bluetooth) or Arduino (USB)."
        ),
        # On a first run the connection block is on screen and this points
        # straight at the device selector; later it is tucked away with the
        # other one-off settings, so the step falls back to the button.
        lambda: (adq._box_device if adq._box_device.isVisible()
                 else adq._btn_conectar),
        tab=TAB_ACQ,
    ))
    steps.append(CoachStep(
        tr("Connecting the sensor"),
        tr(
            "The board has to be switched on and the electrodes connected: "
            "the positive and the negative go on the midline of the muscle, "
            "while the reference goes on a neutral point, over a bone if "
            "possible."
        ),
        lambda: adq._btn_conectar,
        tab=TAB_ACQ,
    ))
    # Only where there is a name to assign: the kinematics practical fixes its
    # own channel names, so the row is not on screen and a step pointing at it
    # would have nothing to point at.
    if not mode_fixed_labels(mode):
        steps.append(CoachStep(
            tr("Assign the labels"),
            tr(
                "This name is written into the EDF file as the channel label, "
                "so the recording keeps the muscle and the channel identified. "
                "The anatomical name is the one to use."
            ),
            lambda: adq._edit_labels[0],
            tab=TAB_ACQ,
        ))

    if mode_uses_acc(mode):
        steps.append(CoachStep(
            tr("How to place the accelerometer"),
            tr(
                "There are two possibilities: on the muscle it allows the "
                "mechanomyogram (MMG) to be measured, which runs in parallel "
                "with the electrical signal; on the moving segment of the "
                "joint it allows the movement, and the parameters associated "
                "with it, to be measured."
            ),
            lambda: adq._box_acc,
            tab=TAB_ACQ,
        ))

    steps.append(CoachStep(
        tr("Recording"),
        tr(
            "Start recording and ask for the contraction. Watch the live "
            "trace: at rest it should be a flat line with only baseline "
            "noise. A signal that never returns to baseline usually means a "
            "loose electrode or a poor contact, not a tonic muscle."
        ),
        lambda: adq._btn_grabar,
        tab=TAB_ACQ,
    ))
    steps.append(CoachStep(
        tr("Following the recording remotely"),
        tr(
            "Every member of the group making the recording can watch the "
            "trace on their own mobile device. This is done by scanning the "
            "QR code the application generates."
        ),
        lambda: adq._box_aula,
        tab=TAB_ACQ,
    ))
    steps.append(CoachStep(
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
        lambda: adq._box_autoonset,
        tab=TAB_ACQ,
    ))

    if mode_uses_acc(mode):
        steps.append(CoachStep(
            tr("Wizard for the force-velocity experiment"),
            tr(
                "The step-by-step wizard guides you through the contractions "
                "with different loads. With a greater load the velocity is "
                "expected to be lower, and this defines an inverse relation "
                "which is the force-velocity curve. The product of the two "
                "gives the power, which is maximal at intermediate loads."
            ),
            lambda: adq._box_fv_guided,
            tab=TAB_ACQ,
        ))
        steps.append(CoachStep(
            tr("Rehearsal of the force-velocity experiment"),
            tr(
                "As this is the longest and most complex procedure in the "
                "application, a simulation is provided as a rehearsal, so "
                "that what is going to be done live is better understood. It "
                "can be followed step by step or watched as an animation, and "
                "it can also be replayed to see it better."
            ),
            lambda: adq._btn_fv_rehearse,
            tab=TAB_ACQ,
        ))

    steps.append(CoachStep(
        tr("Calibrating the contraction"),
        tr(
            "A maximal voluntary contraction is asked for, and it becomes the "
            "reference against which the live load bars and the measurements "
            "are expressed, making contractions easier to compare."
        ),
        lambda: adq._btn_calibrar,
        tab=TAB_ACQ,
    ))

    # ── Analysis ──────────────────────────────────────────────────────
    # The agonist/antagonist practical offers a different set of panels — one
    # raw trace per muscle and the two envelopes overlaid — so the steps that
    # explain the general three would be pointing at checkboxes that are not
    # there.
    if mode != MODE_PAIR:
        steps.append(CoachStep(
        tr("The basic panels"),
            tr(
                "Raw signal: the signal from the set of fibres that are "
                "contracting. Normalised envelope: shows how activation "
                "changes over time, which is what is compared between "
                "efforts. Power spectrum: how the muscle activity is "
                "distributed across the different frequencies recorded."
            ),
            lambda: ana._chk_paneles[0],
            tab=TAB_ANA,
        ))
        steps.append(CoachStep(
            tr("Fatigue lives in the spectrum"),
            tr(
                "As a sustained contraction fatigues the muscle, the "
                "conduction velocity of the fibres falls and the spectrum "
                "shifts towards low frequencies: the median frequency (MDF) "
                "drops while the amplitude often rises, because more motor "
                "units are recruited to hold the same force."
            ),
            lambda: ana._chk_paneles[2],
            tab=TAB_ANA,
        ))

    if mode == MODE_PAIR:
        steps.append(CoachStep(
            tr("Agonist and antagonist"),
            tr(
                "Calibrate the MVC of both muscles while recording and the "
                "two envelopes are overlaid in % MVC — the only form in "
                "which two different muscles compare at all, since each "
                "one's millivolts depend on its own electrodes and on the "
                "skin and fat beneath them. Without that reference the "
                "panel stays in millivolts and says so. In a clean "
                "movement the agonist activates while the antagonist stays "
                "nearly silent; simultaneous activation is co-contraction, "
                "which holds the joint rigid and is typical of an "
                "unpractised or uncertain movement."
            ),
            lambda: ana._box_compare,
            tab=TAB_ANA,
        ))

    if mode_uses_acc(mode):
        steps.append(CoachStep(
            tr("Force-velocity study"),
            tr(
                "Builds the load-velocity, force-velocity and power curves "
                "from a recording where several known loads were lifted, and "
                "relates them to the EMG amplitude — that is, to how many "
                "motor units had to be recruited for each load."
            ),
            lambda: ana._btn_fv,
            tab=TAB_ANA,
        ))

    steps.append(CoachStep(
        tr("Download the results: report and data"),
        tr(
            "The report gathers the figures and the metrics into a PDF "
            "document. The CSV export saves the recording's data."
        ),
        lambda: ana._btn_informe,
        tab=TAB_ANA,
    ))

    # ── MVC normalisation ─────────────────────────────────────────────
    # That tab greets a new session with its own explanation panel, which
    # covers the very controls these steps point at. During the tour it is
    # redundant — this *is* the explanation — so it is put away first.
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
    steps.append(CoachStep(
        tr("Muscle load"),
        tr(
            "Once the signal is in % MVC, the distribution of load over time "
            "can be read against the Jonsson limits: the static level (P10) "
            "is the load the muscle stays above 90 % of the time, the "
            "background tension it hardly ever lets go of, and the level most "
            "associated with sustained-effort discomfort."
        ),
        lambda: cvm._btn_calcular,
        tab=TAB_MVC,
        on_enter=cvm._dismiss_entry_screen,
    ))

    return steps
