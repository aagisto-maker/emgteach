"""Force-velocity / load-velocity study dialog.

Opened from the Analysis tab on a recording that has an accelerometer channel.
The subject has lifted several **known** loads in one recording; the dialog
takes the rows of the tab's contraction table — one per lift, with the load
its marker gave it, its RMS and the segment's peak velocity — lets the user
untick a bad one or type a missing load, and draws the four muscle-function
curves: load-velocity, normalised force-velocity (Hill), power, and
load-vs-EMG (recruitment). It used to segment the recording on its own, from
the markers or the envelope, and drew a table that did not match the one
beside it; segmenting from the file remains as the fallback for a recording
opened with no analysis run. See :mod:`emgteach.force_velocity` for the maths
and the caveats (velocity in arbitrary units, force = the known external load).
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
    assign_loads_to_reps,
    force_velocity_curves,
    parse_fv_load_markers,
    rep_metrics,
    segment_contractions,
    velocity_from_acc,
    windows_from_markers,
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
        *,
        rows=None,
        loads=None,
        acc_flat: bool = False,
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
        #: The contraction table's rows and the load of each, when the tab
        #: hands them over; ``None`` reads the file and segments it here.
        self._rows = list(rows) if rows else None
        self._rows_loads = list(loads) if loads is not None else None
        self._acc_flat_dado = bool(acc_flat)

        root = QHBoxLayout(self)

        # -- Left: reps table + note --------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("Repetitions (one per contraction):")))
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            tr("Use"), tr("Rep"), tr("Load (kg)"),
            tr("EMG (mV)"), tr("Velocity (a.u.)"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setMinimumWidth(400)
        left.addWidget(self._table, stretch=1)

        nota = tr(
            "Untick any contraction that is clearly not valid, then Redraw. "
            "Repetitions at the same load are averaged. Velocity is in "
            "arbitrary units (the accelerometer is uncalibrated); force is the "
            "entered load."
        )
        if self._rows:
            nota += " " + tr(
                "The rows are those of the contraction table: to change them, "
                "edit the fragments in the Analysis tab."
            )
        note = QLabel(nota)
        note.setWordWrap(True)
        note.setStyleSheet("color:#666; font-size:11px;")
        left.addWidget(note)

        # Warns when the accelerometer barely moved (flat/pinned at a rail), so
        # a column of 0.000 velocities is understood, not mistaken for a bug.
        self._acc_warn = QLabel("")
        self._acc_warn.setWordWrap(True)
        self._acc_warn.setStyleSheet("color:#b00020; font-size:11px;")
        self._acc_warn.setVisible(False)
        left.addWidget(self._acc_warn)

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

        if self._rows:
            self._load_from_rows()
        else:
            self._load_and_segment()
        self._redraw()

    # -- data ----------------------------------------------------------------

    def _load_from_rows(self) -> None:
        """The rows of the contraction table, as they are.

        One per lift, numbered as the table numbers them, with the load its
        marker gave it (blank where none did, for typing), its RMS as the
        EMG amplitude and the segment's peak velocity — the same numbers the
        table and the chart by load show, so the three say the same thing.
        """
        filas = self._rows
        self._fs = 0.0
        self._load_markers = []
        self._windows = [(0, 0)] * len(filas)
        cargas = self._rows_loads or []
        self._marker_loads = [
            float(cargas[i]) if i < len(cargas) and cargas[i] is not None else None
            for i in range(len(filas))
        ]
        self._emg_amp = np.asarray([float(r.rms_mv) for r in filas])
        self._peak_vel = np.asarray([
            float(r.velocity_au) if r.velocity_au is not None else 0.0 for r in filas
        ])
        self._acc_flat = self._acc_flat_dado
        self._avisar_acc_plano()
        self._fill_table(reps=[int(r.n) for r in filas])

    def _avisar_acc_plano(self) -> None:
        """Flag a flat / rail-pinned accelerometer: then every velocity is ~0
        (the column of 0.000 the operator sees), which is a placement
        problem, not a bug."""
        if self._acc_flat:
            self._acc_warn.setText(tr(
                "⚠ The accelerometer barely moved (flat / pinned at a rail), so "
                "the velocities are ~0. Put it on the moving segment, oriented "
                "so its resting value sits mid-range (not at ±1 g), and lift "
                "quickly."
            ))
        self._acc_warn.setVisible(self._acc_flat)

    def _load_and_segment(self) -> None:
        """Read the EMG + ACC, compute the envelope/velocity and detect reps."""
        edf = read_edf_mne(self._path, self._emg_channel)
        emg_raw = np.asarray(edf["emg_raw"], dtype=np.float64)
        fs = float(edf["sfreq"])
        self._fs = fs
        # Loads written by the guided wizard, if any — used to pre-fill the
        # table so the loads need not be typed by hand.
        self._load_markers = parse_fv_load_markers(edf.get("markers", []))
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
        # ~0.02 g of peak-to-peak is essentially no movement.
        self._acc_flat = bool(acc_raw.size and float(np.ptp(acc_raw)) < 0.02)
        self._avisar_acc_plano()

        # A guided recording carries one marker per contraction: take the rep
        # windows straight from the markers (robust to the amplitude gap between
        # the MVC maximum and the light loads). A free recording falls back to
        # auto-detecting bursts from the EMG envelope.
        if self._load_markers:
            windows, self._marker_loads = windows_from_markers(
                self._load_markers, fs, self._emg_env.size
            )
        else:
            windows = segment_contractions(self._emg_env, fs)
            self._marker_loads = None
        self._windows = windows
        self._emg_amp, self._peak_vel = rep_metrics(
            self._emg_env, self._velocity, windows
        )
        self._fill_table()

    def _fill_table(self, reps: list[int] | None = None) -> None:
        """``reps`` numbers the rows as the contraction table does; without
        it they count from one."""
        n = len(self._windows)
        self._table.setRowCount(n)
        read_only = ~Qt.ItemFlag.ItemIsEditable
        # Loads come from the guided markers directly (windows built from them)
        # or, for a free recording, are matched to any markers by time.
        if self._marker_loads is not None:
            marker_loads: list = list(self._marker_loads)
        else:
            marker_loads = assign_loads_to_reps(
                self._windows, self._fs, self._load_markers
            )
        for i in range(n):
            use = QTableWidgetItem()
            use.setFlags(
                (use.flags() & read_only)
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            use.setCheckState(Qt.CheckState.Checked)   # valid by default
            self._table.setItem(i, 0, use)
            rep = QTableWidgetItem(str(reps[i] if reps is not None else i + 1))
            rep.setFlags(rep.flags() & read_only)
            self._table.setItem(i, 1, rep)
            kg = marker_loads[i] if i < len(marker_loads) else None
            load = QTableWidgetItem("" if kg is None else f"{kg:g}")
            self._table.setItem(i, 2, load)
            emg = QTableWidgetItem(f"{self._emg_amp[i]:.3f}")
            emg.setFlags(emg.flags() & read_only)
            self._table.setItem(i, 3, emg)
            vel = QTableWidgetItem(f"{self._peak_vel[i]:.3f}")
            vel.setFlags(vel.flags() & read_only)
            self._table.setItem(i, 4, vel)

    def _read_loads(self) -> np.ndarray:
        loads = []
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 2)
            try:
                loads.append(float(item.text().replace(",", ".")))
            except (ValueError, AttributeError):
                loads.append(float("nan"))
        return np.asarray(loads, dtype=np.float64)

    def _use_mask(self) -> np.ndarray:
        """Per-row 'valid' state from the Use checkboxes."""
        used = []
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            used.append(
                item is not None and item.checkState() == Qt.CheckState.Checked
            )
        return np.asarray(used, dtype=bool)

    @staticmethod
    def _average_by_load(
        loads: np.ndarray, vel: np.ndarray, emg: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Collapse repetitions at the same load to their mean, sorted by load."""
        uniq = np.unique(loads)
        vmean = np.array([float(np.mean(vel[loads == u])) for u in uniq])
        emean = np.array([float(np.mean(emg[loads == u])) for u in uniq])
        return uniq, vmean, emean

    # -- plotting ------------------------------------------------------------

    def _redraw(self) -> None:
        self._fig.clear()
        loads = self._read_loads()
        valid = np.isfinite(loads) & self._use_mask() & (self._peak_vel.size > 0)
        axes = self._fig.subplots(2, 2)
        # Need at least two *distinct* loads (after averaging) to draw a curve.
        n_loads = (
            len(np.unique(loads[valid])) if np.any(valid) else 0
        )
        if self._emg_amp.size == 0 or n_loads < 2:
            msg = (
                tr("No repetitions detected in this recording.")
                if self._emg_amp.size == 0
                else tr("Tick at least two valid repetitions with a load "
                        "(kg) entered, then press Redraw.")
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

        # Average the valid repetitions of each load to one point per load.
        loads, vel, emg = self._average_by_load(
            loads[valid], self._peak_vel[valid], self._emg_amp[valid]
        )
        c = force_velocity_curves(loads, vel)
        order = np.argsort(loads)

        # With a flat accelerometer the velocity is meaningless noise, so the
        # three velocity-based panels would draw a misleading curve. Show a note
        # instead; the EMG-based recruitment panel below stays valid.
        def _flat_note(ax, title, xlabel, ylabel):
            ax.text(0.5, 0.5,
                    tr("No velocity — accelerometer flat\n(see the warning)"),
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=8, color="#b00020")
            ax.set_title(title, fontsize=9)
            ax.set_xlabel(xlabel, fontsize=8)
            ax.set_ylabel(ylabel, fontsize=8)

        # Load-velocity
        ax = axes[0, 0]
        if self._acc_flat:
            _flat_note(ax, tr("Load-velocity"), tr("Load (kg)"),
                       tr("Velocity (a.u.)"))
        else:
            ax.plot(c["load"], c["velocity"], "o-", color="#0d7d7d", lw=1.8)
            ax.set_title(tr("Load-velocity"), fontsize=9)
            ax.set_xlabel(tr("Load (kg)"), fontsize=8)
            ax.set_ylabel(tr("Velocity (a.u.)"), fontsize=8)

        # Force-velocity (normalised, Hill-shaped)
        ax = axes[0, 1]
        if self._acc_flat:
            _flat_note(ax, tr("Force-velocity (normalised)"),
                       tr("Force (fraction of max)"),
                       tr("Velocity (fraction of max)"))
        else:
            ax.plot(c["force_norm"], c["velocity_norm"], "o-",
                    color="#0d7d7d", lw=1.8)
            ax.set_title(tr("Force-velocity (normalised)"), fontsize=9)
            ax.set_xlabel(tr("Force (fraction of max)"), fontsize=8)
            ax.set_ylabel(tr("Velocity (fraction of max)"), fontsize=8)

        # Power
        ax = axes[1, 0]
        if self._acc_flat:
            _flat_note(ax, tr("Power (load × velocity)"), tr("Load (kg)"),
                       tr("Power (a.u.)"))
        else:
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
