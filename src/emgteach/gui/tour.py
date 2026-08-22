"""Guided tour content — what each control is and what it means physiologically.

Separated from the widget that draws it (:mod:`emgteach.gui.widgets.coach`) so
the teaching text lives in one readable place and can be revised without
touching interface code.

The tour follows the selected mode: it explains the accelerometer only in the
kinematics practical and agonist/antagonist coordination only in that one.
Explaining a control the user cannot see is worse than not explaining it.

DRAFT TEXT. The physiology here is a first pass written from the existing
tooltips and is meant to be reviewed and rewritten by the author before
release; the wording is the teaching content of the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from emgteach.gui.widgets.coach import CoachStep
from emgteach.i18n import tr
from emgteach.modes import MODE_PAIR, mode_uses_acc

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
        tr("Everything else is optional"),
        tr(
            "The fine controls — filter cut-offs, fatigue thresholds, region "
            "of interest, classroom broadcast — are shared by all three modes "
            "and stay out of the way until you tick this."
        ),
        lambda: win._chk_advanced,
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
        tr("Connect the sensor"),
        tr(
            "The board has to be switched on and the electrodes connected. "
            "The surface electrodes go on the belly of the muscle, in line "
            "with the fibres, with the reference on a bony point that does "
            "not contract."
        ),
        lambda: adq._btn_conectar,
        tab=TAB_ACQ,
    ))
    steps.append(CoachStep(
        tr("Assign the labels"),
        tr(
            "This name is written into the EDF file as the channel label, so "
            "the recording keeps the muscle and the channel identified. The "
            "anatomical name is the one worth using."
        ),
        lambda: adq._edit_labels[0],
        tab=TAB_ACQ,
    ))

    if mode_uses_acc(mode):
        steps.append(CoachStep(
            tr("Where the accelerometer goes"),
            tr(
                "On the muscle it measures mechanomyogram (MMG): the "
                "transverse bulging of the fibres as they shorten, that is, "
                "the mechanical counterpart of the electrical signal. On the "
                "moving segment it measures the movement itself — its "
                "acceleration, and from that velocity and tremor."
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
        tr("Follow the recording from several devices"),
        tr(
            "A read-only live view over the local network: the group can "
            "watch the trace on their own phones while one person wears the "
            "electrodes. Nobody installs anything — a link is opened, or the "
            "QR code scanned."
        ),
        lambda: adq._box_aula,
        tab=TAB_ACQ,
    ))
    steps.append(CoachStep(
        tr("Mark what happens"),
        tr(
            "Press MARK to timestamp an event — the start of an effort, a "
            "change of load, the moment the subject reports fatigue. The "
            "marks travel inside the EDF and let you find each phase again "
            "during the analysis."
        ),
        lambda: adq._btn_marcar,
        tab=TAB_ACQ,
    ))

    if mode_uses_acc(mode):
        steps.append(CoachStep(
            tr("Guided force-velocity"),
            tr(
                "This wizard walks through one contraction per load. With "
                "increasing loads the shortening velocity falls: that inverse "
                "relation is the force-velocity curve, and the product of the "
                "two gives the power, which peaks at intermediate loads."
            ),
            lambda: adq._box_fv_guided,
            tab=TAB_ACQ,
        ))

    steps.append(CoachStep(
        tr("Calibrate the maximum contraction"),
        tr(
            "A maximal voluntary contraction recorded now becomes the "
            "reference the live load bars are expressed against. Without that "
            "reference the amplitude stays in millivolts, and a millivolt "
            "does not measure the muscle alone: it also depends on where the "
            "electrodes were stuck and how much skin and fat lie between them "
            "and the fibres. That is why two recordings in millivolts cannot "
            "be compared."
        ),
        lambda: adq._btn_calibrar,
        tab=TAB_ACQ,
    ))

    # ── Analysis ──────────────────────────────────────────────────────
    steps.append(CoachStep(
        tr("The three basic panels"),
        tr(
            "Raw signal: the interference pattern of the motor units firing. "
            "Normalised envelope: how activation changes over time, which is "
            "what you compare between efforts. Power spectrum: how that "
            "activity is distributed in frequency."
        ),
        lambda: ana._chk_paneles[0],
        tab=TAB_ANA,
    ))
    steps.append(CoachStep(
        tr("Fatigue lives in the spectrum"),
        tr(
            "As a sustained contraction fatigues the muscle, the conduction "
            "velocity of the fibres falls and the spectrum shifts towards low "
            "frequencies: the median frequency (MDF) drops while the "
            "amplitude often rises, because more motor units are recruited to "
            "hold the same force."
        ),
        lambda: ana._chk_paneles[2],
        tab=TAB_ANA,
    ))

    if mode == MODE_PAIR:
        steps.append(CoachStep(
            tr("Agonist and antagonist"),
            tr(
                "With two channels the envelopes can be overlaid. In a clean "
                "movement the agonist activates while the antagonist stays "
                "nearly silent; simultaneous activation is co-contraction, "
                "which holds the joint rigid and is typical of an unpractised "
                "or "
                "uncertain movement."
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
                "relates them to the EMG amplitude — that is, to how much the "
                "muscle had to be recruited for each load."
            ),
            lambda: ana._btn_fv,
            tab=TAB_ANA,
        ))

    steps.append(CoachStep(
        tr("Download the results: report and data"),
        tr(
            "The report gathers the figures and the metrics into a PDF "
            "document. Export CSV saves the recording's data."
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
            "working."
        ),
        lambda: cvm._edit_cvm_path,
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
