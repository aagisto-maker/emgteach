"""Rehearsal of the guided force-velocity acquisition — the player.

Plays the whole procedure with no hardware and no subject: the real plan
dialog, then the real cue panel running the real sequence of prompts over a
synthetic recording, then the real force-velocity study on the result. Each
step is narrated with what is happening and why, and the run can be paused,
stepped and replayed — which the real thing, tied to a subject holding a
weight, cannot be.

The point is that almost nothing here is a mock-up. The plan dialog, the cue
panel, the log wording and the final study are the application's own; what
this module adds is a clock, a synthetic subject
(:mod:`emgteach.fv_rehearsal`) and the explanations. A rehearsal built out of
imitations would drift from the procedure it is meant to teach, and would do
it silently.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.fv_rehearsal import (
    PHASE_DONE,
    PHASE_LIFT,
    PHASE_MVC_CONTRACT,
    PHASE_MVC_READY,
    PHASE_MVC_REST,
    PHASE_PREPARE,
    PHASE_REST,
    REHEARSAL_ACC_CHANNEL,
    REHEARSAL_EMG_CHANNEL,
    cue_script,
    synthetic_trial,
    total_seconds,
    write_rehearsal_edf,
)
from emgteach.gui.widgets.mvc_overlay import MvcOverlay
from emgteach.i18n import tr

__all__ = ["ForceVelocityRehearsalDialog"]

#: Wall-clock tick. The rehearsal's own clock advances by this times the speed
#: multiplier, so the default ×2 turns a 48-second protocol into 24.
_TICK_MS = 40

#: Points kept for the plot. The recording is ~48 000 samples and is redrawn
#: 25 times a second; at full resolution the player stutters and the bursts
#: are no easier to see for it.
_PLOT_POINTS = 3000

_SPEEDS = ((1.0, "×1"), (2.0, "×2"), (4.0, "×4"), (10.0, "×10"))


def _narration(phase: str, kg: float) -> tuple[str, str]:
    """What is happening now, and why it is done that way.

    The "why" is the part a student cannot get from watching: every phase of
    this protocol exists for a reason that is invisible while it runs.
    """
    if phase == PHASE_MVC_READY:
        return (
            tr("Get ready — the maximum comes first, with no weight."),
            tr("The maximum is recorded before any load: it is the 100 % the "
               "other contractions are read against. Doing it first also keeps "
               "it clear of the fatigue the loads are about to cause."),
        )
    if phase == PHASE_MVC_CONTRACT:
        return (
            tr("A sustained maximum, held for a few seconds."),
            tr("Held, because a true maximum takes about a second to reach. "
               "It is isometric — nothing moves, so the accelerometer stays "
               "flat here. This contraction sets the amplitude reference, not "
               "a velocity."),
        )
    if phase == PHASE_MVC_REST:
        return (
            tr("Recovery, and the first weight is set up."),
            tr("Longer than the pauses between loads: the subject has just "
               "given a maximum, and the first load should not be lifted "
               "tired."),
        )
    if phase == PHASE_PREPARE:
        return (
            tr("Prepare {kg:g} kg — take the weight and the starting position.")
            .format(kg=kg),
            tr("Nothing is being recorded as a repetition yet. The countdown "
               "is there so the load is handed over and the position taken "
               "without hurrying."),
        )
    if phase == PHASE_LIFT:
        return (
            tr("Lift {kg:g} kg — one quick movement, not a hold.").format(kg=kg),
            tr("The study reads the shortening velocity from the "
               "accelerometer, and a slow or held contraction has none. As "
               "this cue appears the application writes a marker into the "
               "file with the load — which is why the study can fill the load "
               "column by itself."),
        )
    if phase == PHASE_REST:
        return (
            tr("Relax, and change the weight."),
            tr("Short on purpose: long enough to change the load, not long "
               "enough to lose the thread. If more than one repetition per "
               "load was asked for, this is where it goes back for another."),
        )
    return (
        tr("Recorded — the loads are already in the file."),
        tr("Stop the recording and open the force-velocity study in the "
           "Analysis tab. Nothing has to be typed: every window carries its "
           "load."),
    )


class ForceVelocityRehearsalDialog(QDialog):
    """Plays the guided force-velocity protocol without hardware."""

    @classmethod
    def run(cls, parent=None) -> ForceVelocityRehearsalDialog | None:
        """Ask for a load plan with the real dialog, then rehearse it.

        The plan dialog is the first thing the operator meets in the real
        procedure, so it is the first thing the rehearsal shows — the actual
        dialog, not a picture of one.
        """
        from emgteach.gui.widgets.force_velocity_plan_dialog import (
            ForceVelocityPlanDialog,
        )

        plan = ForceVelocityPlanDialog(parent, placement="limb")
        plan.setWindowTitle(
            tr("Rehearsal — guided force-velocity acquisition")
        )
        plan._edit_loads.setText("2, 4, 6, 8")
        if plan.exec() != QDialog.DialogCode.Accepted:
            return None
        dlg = cls(plan.loads(), plan.reps(), plan.prep_seconds(),
                  plan.window_seconds(), parent)
        dlg.show()
        return dlg

    def __init__(
        self,
        loads: list[float],
        reps: int = 1,
        prep_s: float = 5.0,
        lift_s: float = 1.5,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Rehearsal — guided force-velocity acquisition"))
        self.setModal(False)          # a rehearsal is watched, not answered
        self.resize(1240, 720)

        self._cues = cue_script(loads, reps, prep_s, lift_s)
        self._trial = synthetic_trial(loads, reps, cues=self._cues)
        self._total = total_seconds(self._cues)
        self._loads = list(loads)
        self._t = 0.0
        self._cue_index = -1
        self._speed = 2.0
        self._edf: str | None = None

        self._prepare_signals()
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._apply_cue(0)
        self._refresh_plot()

    # -- data ----------------------------------------------------------------

    def _prepare_signals(self) -> None:
        """Envelope and velocity for the plot, decimated for drawing."""
        from emgteach.dsp import process_offline
        from emgteach.force_velocity import velocity_from_acc

        fs = float(self._trial["fs"])
        self._fs = fs
        emg = np.asarray(self._trial["emg_raw"], dtype=np.float64)
        env = np.asarray(
            process_offline(emg, fs, f_env=5.0)["emg_envelope"], dtype=np.float64
        )
        vel = velocity_from_acc(
            np.asarray(self._trial["acc_raw"], dtype=np.float64), fs
        )
        self._env_full = env

        step = max(1, emg.size // _PLOT_POINTS)
        self._step = step
        self._t_plot = np.arange(0, emg.size, step) / fs
        self._emg_plot = emg[::step]
        self._env_plot = env[::step]
        self._vel_plot = vel[::step]

        # The MVC reference the wizard would compute, from the same window and
        # the same function it uses — so the log line shows a real number.
        from emgteach.gui.tabs.acquisition import MVC_PEAK_WINDOW_S
        from emgteach.mvc import mvc_from_reps

        mvc = next(c for c in self._cues if c.phase == PHASE_MVC_CONTRACT)
        seg = env[int(mvc.start * fs):int(mvc.end * fs)]
        self._mvc_ref = float(
            mvc_from_reps([seg], 100.0, window_samples=max(
                1, round(MVC_PEAK_WINDOW_S * fs)))
        ) if seg.size else 0.0

    # -- construction --------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(8)

        plan = ", ".join(f"{k:g}" for k in self._loads)
        header = QLabel(tr(
            "No hardware and no subject: the prompts, in the order and at the "
            "speed the wizard will show them. Loads: {loads} kg."
        ).format(loads=plan))
        header.setWordWrap(True)
        header.setStyleSheet("color:#4A5A68; font-size:11px;")
        root.addWidget(header)

        middle = QHBoxLayout()
        middle.setSpacing(10)

        # -- the recording as it is made, with the cue panel over it ---------
        self._canvas_host = QWidget()
        host_lay = QVBoxLayout(self._canvas_host)
        host_lay.setContentsMargins(0, 0, 0, 0)
        self._fig = Figure(figsize=(6.6, 4.2))
        self._fig.set_layout_engine("constrained")
        self._canvas = FigureCanvasQTAgg(self._fig)
        host_lay.addWidget(self._canvas)
        self._ax_emg, self._ax_vel = self._fig.subplots(
            2, 1, sharex=True, height_ratios=[2, 1]
        )
        self._init_axes()
        middle.addWidget(self._canvas_host, stretch=4)

        # The acquisition tab's own panel, floating over the plots exactly as
        # it does during a real recording. It covers part of the trace, which
        # is what the subject sees too; the trace is there to be read on the
        # replay, and the panel can be got out of the way by pausing and
        # stepping back.
        self._overlay = MvcOverlay(self._canvas_host)

        # -- event log -------------------------------------------------------
        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(QLabel(tr("Event log")))
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("font-family: monospace; font-size: 10px;")
        self._log.setMinimumWidth(250)
        right.addWidget(self._log, stretch=1)
        middle.addLayout(right, stretch=1)
        root.addLayout(middle, stretch=1)

        # -- narration -------------------------------------------------------
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(10, 8, 10, 8)
        box_lay.setSpacing(3)
        self._lbl_step = QLabel()
        self._lbl_step.setStyleSheet(
            "font-size: 11px; color: #4A5A68; font-weight: bold;")
        box_lay.addWidget(self._lbl_step)
        self._lbl_what = QLabel()
        self._lbl_what.setWordWrap(True)
        self._lbl_what.setStyleSheet("font-size: 12px; font-weight: bold;")
        box_lay.addWidget(self._lbl_what)
        self._lbl_why = QLabel()
        self._lbl_why.setWordWrap(True)
        self._lbl_why.setStyleSheet("font-size: 11px; color: #33475B;")
        box_lay.addWidget(self._lbl_why)
        root.addWidget(box)

        # -- transport -------------------------------------------------------
        row = QHBoxLayout()
        self._btn_play = QPushButton(tr("Play"))
        self._btn_play.clicked.connect(self._toggle)
        row.addWidget(self._btn_play)
        btn_step = QPushButton(tr("Next step"))
        btn_step.clicked.connect(self._next_step)
        row.addWidget(btn_step)
        btn_restart = QPushButton(tr("Restart"))
        btn_restart.clicked.connect(self._restart)
        row.addWidget(btn_restart)

        row.addSpacing(12)
        row.addWidget(QLabel(tr("Speed:")))
        self._combo_speed = QComboBox()
        for mult, label in _SPEEDS:
            self._combo_speed.addItem(label, mult)
        # ×2. At ×4 the run is over before the narration of each
        # phase has been read, which is the half that cannot be
        # caught up with later.
        self._combo_speed.setCurrentIndex(1)
        self._combo_speed.currentIndexChanged.connect(self._on_speed)
        self._combo_speed.setToolTip(tr(
            "×1 is the real duration of the protocol; the faster settings are "
            "for reviewing the sequence."
        ))
        row.addWidget(self._combo_speed)
        row.addStretch()

        self._btn_study = QPushButton(tr("Open the study…"))
        self._btn_study.setEnabled(False)
        self._btn_study.setToolTip(tr(
            "Opens the real force-velocity study on the rehearsal's recording."
        ))
        self._btn_study.clicked.connect(self._open_study)
        row.addWidget(self._btn_study)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        row.addWidget(buttons)
        root.addLayout(row)

    def _init_axes(self) -> None:
        grid = {"ls": "--", "color": "#DDDDDD", "alpha": 0.8}
        self._ax_emg.set_ylabel(tr("EMG (mV)"), fontsize=8)
        self._ax_vel.set_ylabel(tr("Velocity (a.u.)"), fontsize=8)
        self._ax_vel.set_xlabel(tr("Time (s)"), fontsize=8)
        for ax in (self._ax_emg, self._ax_vel):
            ax.set_xlim(0, self._total)
            ax.tick_params(labelsize=7)
            ax.grid(True, **grid)
        pad = 1.15
        self._ax_emg.set_ylim(
            -pad * float(np.max(np.abs(self._emg_plot))),
            pad * float(np.max(np.abs(self._emg_plot))),
        )
        vmax = pad * float(np.max(np.abs(self._vel_plot))) or 1.0
        self._ax_vel.set_ylim(-vmax, vmax)

        # Every lift window shaded, so the shape of the protocol is visible
        # from the start rather than only in hindsight.
        for cue in self._cues:
            if cue.is_lift:
                for ax in (self._ax_emg, self._ax_vel):
                    ax.axvspan(cue.start, cue.end, color="#E1A100", alpha=0.14)
                self._ax_emg.annotate(
                    tr("{kg:g} kg").format(kg=cue.load),
                    (cue.start, 1.0), xycoords=("data", "axes fraction"),
                    fontsize=7, color="#8a6500", ha="left", va="bottom",
                )
            elif cue.phase == PHASE_MVC_CONTRACT:
                for ax in (self._ax_emg, self._ax_vel):
                    ax.axvspan(cue.start, cue.end, color="#2E86DE", alpha=0.12)
                self._ax_emg.annotate(
                    tr("maximum"), (cue.start, 1.0),
                    xycoords=("data", "axes fraction"),
                    fontsize=7, color="#1B4F82", ha="left", va="bottom",
                )

        (self._ln_emg,) = self._ax_emg.plot([], [], lw=0.6, color="#B0BEC5")
        (self._ln_env,) = self._ax_emg.plot([], [], lw=1.4, color="#16202A")
        (self._ln_vel,) = self._ax_vel.plot([], [], lw=1.2, color="#0d7d7d")
        self._cursor_emg = self._ax_emg.axvline(0, color="#C0392B", lw=1.0)
        self._cursor_vel = self._ax_vel.axvline(0, color="#C0392B", lw=1.0)

    # -- playing -------------------------------------------------------------

    def _cue_at(self, t: float) -> int:
        for i, cue in enumerate(self._cues):
            if t < cue.end:
                return i
        return len(self._cues) - 1

    def _toggle(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._btn_play.setText(tr("Play"))
        else:
            if self._t >= self._total:
                self._restart()
            self._timer.start()
            self._btn_play.setText(tr("Pause"))

    def _on_speed(self, index: int) -> None:
        self._speed = float(self._combo_speed.itemData(index))

    def _next_step(self) -> None:
        """Jump to the start of the next prompt."""
        i = min(self._cue_at(self._t) + 1, len(self._cues) - 1)
        self._t = self._cues[i].start
        self._apply_cue(i)
        self._refresh_plot()

    def _restart(self) -> None:
        self._t = 0.0
        self._cue_index = -1
        self._log.clear()
        self._btn_study.setEnabled(False)
        self._apply_cue(0)
        self._refresh_plot()

    def _tick(self) -> None:
        self._t += (_TICK_MS / 1000.0) * self._speed
        if self._t >= self._total:
            self._t = self._total
            self._timer.stop()
            self._btn_play.setText(tr("Play"))
        self._apply_cue(self._cue_at(self._t))
        self._refresh_plot()

    def _apply_cue(self, index: int) -> None:
        cue = self._cues[index]
        entering = index != self._cue_index
        self._cue_index = index

        if entering:
            what, why = _narration(cue.phase, cue.load)
            self._lbl_what.setText(what)
            self._lbl_why.setText(why)
            self._lbl_step.setText(tr("Step {i} of {n}").format(
                i=index + 1, n=len(self._cues)))
            self._log_for(cue)

        self._drive_overlay(cue)

    def _drive_overlay(self, cue) -> None:
        """Show the cue panel exactly as the wizard's state machine does."""
        elapsed = max(0.0, self._t - cue.start)
        kg = cue.load
        n_loads, reps = len(self._loads), max(
            1, len({(c.index, c.rep) for c in self._cues if c.is_lift})
            // max(1, len(self._loads))
        )
        prog = tr(" (load {i}/{n}, rep {r}/{rn})").format(
            i=cue.index, n=n_loads, r=cue.rep, rn=reps
        )
        count = max(1, int(np.ceil(cue.seconds - elapsed)))

        if cue.phase == PHASE_MVC_READY:
            self._overlay.show_ready(
                tr("Get ready — maximum contraction (no load)"), count,
                tr("Contract at maximum when the count reaches 0"))
        elif cue.phase == PHASE_MVC_CONTRACT:
            # The effort bar follows the synthetic envelope, so it rises and
            # settles the way a real maximum does.
            i = int((cue.start + elapsed) * self._fs)
            seg = self._env_full[int(cue.start * self._fs):max(i + 1, 1)]
            peak = float(np.max(seg)) if seg.size else 1.0
            effort = float(seg[-1] / peak) if seg.size and peak > 0 else 0.0
            self._overlay.show_contract(
                tr("Contract at maximum! (no load)"),
                max(0.0, cue.seconds - elapsed),
                min(1.0, elapsed / cue.seconds), effort)
        elif cue.phase == PHASE_MVC_REST:
            self._overlay.show_relax(tr("Relax — now the loads, lightest first"))
        elif cue.phase == PHASE_PREPARE:
            self._overlay.show_ready(
                tr("Prepare {kg:g} kg{prog}").format(kg=kg, prog=prog), count,
                tr("Lift {kg:g} kg when the count reaches 0").format(kg=kg))
        elif cue.phase == PHASE_LIFT:
            self._overlay.show_action(
                tr("Lift {kg:g} kg!").format(kg=kg), prog.strip())
        elif cue.phase == PHASE_REST:
            last = cue.index == len(self._loads) and cue.rep == reps
            nxt = self._loads[cue.index] if cue.index < len(self._loads) else kg
            self._overlay.show_relax(
                tr("Relax — another rep of {kg:g} kg").format(kg=kg)
                if cue.rep < reps and not last
                else tr("Relax — change to {kg:g} kg").format(kg=nxt))
        else:
            self._overlay.show_done(
                tr("Loads recorded"),
                tr("{n} loads marked.\nStop recording, then open the "
                   "Force-velocity study.").format(n=len(self._loads)))
        self._centre_overlay()

    def _centre_overlay(self) -> None:
        r = self._canvas_host.rect()
        self._overlay.move(
            r.center().x() - self._overlay.width() // 2,
            r.center().y() - self._overlay.height() // 2,
        )
        self._overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._centre_overlay()

    def _log_for(self, cue) -> None:
        """The lines the acquisition tab would write, at the same moments."""
        stamp = f"{int(cue.start) // 60:02d}:{int(cue.start) % 60:02d}"
        line = ""
        if cue.phase == PHASE_MVC_REST and self._mvc_ref > 0:
            line = tr("F-V: MVC reference {ref:.2f} mV.").format(ref=self._mvc_ref)
        elif cue.is_lift:
            line = tr("Force-velocity: contraction with {kg:g} kg.").format(
                kg=cue.load)
        elif cue.phase == PHASE_DONE:
            line = tr("Force-velocity acquisition finished: {n} loads.").format(
                n=len(self._loads))
            self._btn_study.setEnabled(True)
        if line:
            self._log.appendPlainText(f"{stamp}  {line}")

    def _refresh_plot(self) -> None:
        n = int(np.searchsorted(self._t_plot, self._t))
        self._ln_emg.set_data(self._t_plot[:n], self._emg_plot[:n])
        self._ln_env.set_data(self._t_plot[:n], self._env_plot[:n])
        self._ln_vel.set_data(self._t_plot[:n], self._vel_plot[:n])
        for cursor in (self._cursor_emg, self._cursor_vel):
            cursor.set_xdata([self._t, self._t])
        self._canvas.draw_idle()

    # -- the study -----------------------------------------------------------

    def _open_study(self) -> None:
        """Open the real study dialog on the rehearsal's own recording."""
        from emgteach.gui.widgets.force_velocity_dialog import ForceVelocityDialog

        if self._edf is None:
            path = Path(tempfile.gettempdir()) / "emgteach_ensayo_fv.edf"
            self._edf = write_rehearsal_edf(self._trial, path)
        dlg = ForceVelocityDialog(
            self._edf, REHEARSAL_EMG_CHANNEL, REHEARSAL_ACC_CHANNEL, parent=self
        )
        dlg.setWindowTitle(
            tr("Force-velocity study — rehearsal recording")
        )
        dlg.show()
        self._study = dlg          # kept alive; it is modeless

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
