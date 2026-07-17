"""Force-velocity / load-velocity study dialog.

Opened from the Analysis tab on a recording that has an accelerometer channel.
The subject has lifted several **known** loads in one recording (one rep per
load); the dialog auto-detects the repetitions from the EMG envelope, lets the
user type the load (kg) of each, and draws the four muscle-function curves:
load-velocity, normalised force-velocity (Hill), power, and load-vs-EMG
(recruitment). See :mod:`emgteach.force_velocity` for the maths and the caveats
(velocity in arbitrary units, force = the known external load).
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from emgteach.dsp import process_offline
from emgteach.force_velocity import (
    force_velocity_curves,
    rep_metrics,
    segment_contractions,
    velocity_from_acc,
)
from emgteach.i18n import tr
from emgteach.io import list_edf_channels, read_edf_mne, read_edf_pyedflib

_GRID = dict(ls="--", color="#DDDDDD", alpha=0.8)


class ForceVelocityDialog(QDialog):
    """Interactive force-velocity / load-velocity study for one recording."""

    def __init__(
        self,
        edf_path: str,
        emg_channel: str,
        acc_channel: str,
        f_env: float = 5.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Force-velocity study"))
        self.resize(980, 620)
        self._path = edf_path
        self._emg_channel = emg_channel
        self._acc_channel = acc_channel
        self._f_env = float(f_env)
        self._emg_amp = np.asarray([])
        self._peak_vel = np.asarray([])

        root = QHBoxLayout(self)

        # -- Left: reps table + note --------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("Repetitions (one per known load):")))
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels([
            tr("Rep"), tr("Load (kg)"), tr("EMG (mV)"), tr("Velocity (a.u.)"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setMinimumWidth(360)
        left.addWidget(self._table, stretch=1)

        note = QLabel(tr(
            "Type the known load lifted in each repetition, then Redraw. "
            "Velocity is in arbitrary units (the accelerometer is "
            "uncalibrated); force is the load you enter."
        ))
        note.setWordWrap(True)
        note.setStyleSheet("color:#666; font-size:11px;")
        left.addWidget(note)

        btn_row = QHBoxLayout()
        self._btn_redraw = QPushButton(tr("Redraw"))
        self._btn_redraw.clicked.connect(self._redraw)
        btn_row.addWidget(self._btn_redraw)
        self._btn_save = QPushButton(tr("Save figure (PNG)"))
        self._btn_save.clicked.connect(self._save_figure)
        btn_row.addWidget(self._btn_save)
        btn_row.addStretch()
        left.addLayout(btn_row)
        root.addLayout(left, stretch=2)

        # -- Right: curves ------------------------------------------------
        right = QVBoxLayout()
        self._fig = Figure(figsize=(6.2, 5.4))
        self._fig.set_layout_engine("constrained")
        self._canvas = FigureCanvasQTAgg(self._fig)
        right.addWidget(self._canvas, stretch=1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        right.addWidget(buttons)
        root.addLayout(right, stretch=3)

        self._load_and_segment()
        self._redraw()

    # -- data ----------------------------------------------------------------

    def _load_and_segment(self) -> None:
        """Read the EMG + ACC, compute the envelope/velocity and detect reps."""
        edf = read_edf_mne(self._path, self._emg_channel)
        emg_raw = np.asarray(edf["emg_raw"], dtype=np.float64)
        fs = float(edf["sfreq"])
        self._fs = fs
        proc = process_offline(emg_raw, fs, f_env=self._f_env)
        self._emg_env = np.asarray(proc["emg_envelope"], dtype=np.float64)

        # ACC read with pyedflib to keep its physical g units.
        try:
            acc_idx = list_edf_channels(self._path).index(self._acc_channel)
            acc_raw = np.asarray(
                read_edf_pyedflib(self._path, channel_index=acc_idx)["emg_raw"],
                dtype=np.float64,
            )
        except Exception:
            acc_raw = np.zeros_like(self._emg_env)
        self._velocity = velocity_from_acc(acc_raw, fs)

        windows = segment_contractions(self._emg_env, fs)
        self._windows = windows
        self._emg_amp, self._peak_vel = rep_metrics(
            self._emg_env, self._velocity, windows
        )
        self._fill_table()

    def _fill_table(self) -> None:
        n = len(self._windows)
        self._table.setRowCount(n)
        read_only = ~Qt.ItemFlag.ItemIsEditable
        for i in range(n):
            rep = QTableWidgetItem(str(i + 1))
            rep.setFlags(rep.flags() & read_only)
            self._table.setItem(i, 0, rep)
            load = QTableWidgetItem("")  # blank — the user must enter the load
            self._table.setItem(i, 1, load)
            emg = QTableWidgetItem(f"{self._emg_amp[i]:.3f}")
            emg.setFlags(emg.flags() & read_only)
            self._table.setItem(i, 2, emg)
            vel = QTableWidgetItem(f"{self._peak_vel[i]:.3f}")
            vel.setFlags(vel.flags() & read_only)
            self._table.setItem(i, 3, vel)

    def _read_loads(self) -> np.ndarray:
        loads = []
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 1)
            try:
                loads.append(float(item.text().replace(",", ".")))
            except (ValueError, AttributeError):
                loads.append(float("nan"))
        return np.asarray(loads, dtype=np.float64)

    # -- plotting ------------------------------------------------------------

    def _redraw(self) -> None:
        self._fig.clear()
        loads = self._read_loads()
        valid = np.isfinite(loads) & (self._peak_vel.size > 0)
        axes = self._fig.subplots(2, 2)
        if self._emg_amp.size == 0 or np.count_nonzero(valid) < 2:
            msg = (
                tr("No repetitions detected in this recording.")
                if self._emg_amp.size == 0
                else tr("Enter the load (kg) of at least two repetitions, "
                        "then press Redraw.")
            )
            axes[0, 0].text(
                0.5, 0.5, msg,
                transform=axes[0, 0].transAxes, ha="center", va="center",
                fontsize=9, color="#888888",
            )
            for ax in axes.flat:
                ax.tick_params(labelsize=7)
            self._canvas.draw()
            return

        loads = loads[valid]
        vel = self._peak_vel[valid]
        emg = self._emg_amp[valid]
        c = force_velocity_curves(loads, vel)
        order = np.argsort(loads)

        # Load-velocity
        ax = axes[0, 0]
        ax.plot(c["load"], c["velocity"], "o-", color="#0d7d7d", lw=1.8)
        ax.set_title(tr("Load-velocity"), fontsize=9)
        ax.set_xlabel(tr("Load (kg)"), fontsize=8)
        ax.set_ylabel(tr("Velocity (a.u.)"), fontsize=8)

        # Force-velocity (normalised, Hill-shaped)
        ax = axes[0, 1]
        ax.plot(c["force_norm"], c["velocity_norm"], "o-", color="#0d7d7d", lw=1.8)
        ax.set_title(tr("Force-velocity (normalised)"), fontsize=9)
        ax.set_xlabel(tr("Force (fraction of max)"), fontsize=8)
        ax.set_ylabel(tr("Velocity (fraction of max)"), fontsize=8)

        # Power
        ax = axes[1, 0]
        ax.plot(c["load"], c["power"], "o-", color="#E1A100", lw=1.8)
        ax.set_title(tr("Power (load × velocity)"), fontsize=9)
        ax.set_xlabel(tr("Load (kg)"), fontsize=8)
        ax.set_ylabel(tr("Power (a.u.)"), fontsize=8)

        # Recruitment: load vs EMG
        ax = axes[1, 1]
        ax.plot(loads[order], emg[order], "o-", color="#C0392B", lw=1.8)
        ax.set_title(tr("Recruitment (load vs EMG)"), fontsize=9)
        ax.set_xlabel(tr("Load (kg)"), fontsize=8)
        ax.set_ylabel(tr("EMG amplitude (mV)"), fontsize=8)

        for ax in axes.flat:
            ax.tick_params(labelsize=7)
            ax.grid(True, **_GRID)
        self._canvas.draw()

    def _save_figure(self) -> None:
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        default = str(Path(self._path).with_name("fuerza_velocidad.png"))
        ruta, _ = QFileDialog.getSaveFileName(
            self, tr("Save figure (PNG)"), default, tr("PNG images (*.png)")
        )
        if ruta:
            if not ruta.lower().endswith(".png"):
                ruta += ".png"
            self._fig.savefig(ruta, dpi=150)
