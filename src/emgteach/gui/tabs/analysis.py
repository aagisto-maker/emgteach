"""
AnalysisTab — tab 2: full offline analysis of an EMG signal.

Reproduces the 7 panels of analisis_emg_completo.py with matplotlib embedded
in Qt (FigureCanvasQTAgg). Processing runs in AnalysisWorker (QThread) so the
UI does not block during analysis.

Controls:
  - EDF file selector (path persisted in QSettings)
  - EMG channel name
  - Envelope cutoff frequency (editable, default 5.0 Hz)
  - Analyse / Save figure button
  - Progress bar

Summary panel: MNF, MDF, fatigue indicator.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

try:
    matplotlib.use("QtAgg")
except Exception:
    # Headless environment (e.g. CI without a display): the GUI is never
    # rendered there, and the tabs create FigureCanvasQTAgg explicitly.
    pass
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QSettings, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_ZOOM_FACTORS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

# Teaching panel layout. The three panels relevant to physiology students
# (raw, normalised envelope, PSD) come first, renumbered 1A, 2, 3 and checked
# by default; the remaining panels follow, renumbered 4-8, unchecked but still
# selectable. Each entry is (original panel index, display number): the
# original index (0-7) is the identity used by the plotting code and the PDF
# report; the display number is what the student sees.
# Canonical panel index 8 is the two-channel overlay (agonist/antagonist);
# it is only meaningful when a second channel is analysed. Indices 9-11 are the
# accelerometer panels (EMG vs MMG, tremor FFT, movement vs EMG), only
# meaningful when the recording has an accelerometer channel.
_OVERLAY_PID = 8
_MMG_PID = 9
_TREMOR_PID = 10
_MOVEMENT_PID = 11
#: Raw trace of the second muscle. Only the agonist/antagonist practical
#: records two, and there the point is to see each muscle before comparing
#: them, so one raw panel is not enough.
_RAW2_PID = 12
# Panels that require an accelerometer channel to be usable.
_ACC_PIDS = (_MMG_PID, _TREMOR_PID, _MOVEMENT_PID)

_PANEL_LAYOUT: list[tuple[int, str]] = [
    (0, "1A"),  # raw signal
    (_RAW2_PID, "1B"),  # raw signal of the second muscle (agonist/antagonist)
    (3, "2"),   # normalised envelope
    (4, "3"),   # PSD with MNF/MDF
    (1, "4"),   # filtered + rectified
    (2, "5"),   # envelope vs RMS
    (5, "6"),   # RMS per window
    (6, "7"),   # MDF vs time (fatigue)
    (7, "8"),   # RMS vs MDF
    (_OVERLAY_PID, "9"),  # overlaid envelopes (agonist/antagonist)
    (_MMG_PID, "10"),     # EMG vs MMG (accelerometer on the muscle)
    (_TREMOR_PID, "11"),  # tremor FFT (accelerometer)
    (_MOVEMENT_PID, "12"),  # movement vs EMG (accelerometer on the limb)
]
# Panels checked by default (original indices): raw, normalised envelope, PSD.
# The overlay panel (8) is checked dynamically when a 2nd channel is compared.
_DEFAULT_PANELS: tuple[int, ...] = (0, 3, 4)

# Panels always offered, in _PANEL_LAYOUT display order: 1A. Raw,
# 2. Env. norm. and 3. PSD — the same three that are checked by default and
# the teaching core of the tab. What follows depends on mode and flag.
#: The teaching core, by identifier rather than by position: raw signal,
#: normalised envelope and PSD. Positions moved when the second muscle's raw
#: trace was inserted after the first, and an index-based rule would have
#: silently changed which panels counted as basic.
_CORE_PIDS: tuple[int, ...] = (0, 3, 4)

# Full panel names (report dialog), in display order and renumbered.
_PANEL_NOMBRES = [
    "1A. Raw signal",
    "1B. Raw signal — 2nd muscle",
    "2. Normalised envelope",
    "3. PSD with MNF/MDF",
    "4. Filtered + rectified",
    "5. Envelope vs RMS",
    "6. RMS per window",
    "7. MDF vs time (fatigue)",
    "8. RMS vs MDF",
    "9. Overlaid envelopes (agonist/antagonist)",
    "10. EMG vs MMG (electrical vs mechanical)",
    "11. Tremor (accelerometer FFT)",
    "12. Movement vs EMG (limb kinematics)",
]

# Short labels (on-screen checkbox row), in display order and renumbered.
_PANEL_SHORT_LABELS = [
    "1A. Raw",
    "1B. Raw (2nd)",
    "2. Env. norm.",
    "3. PSD",
    "4. Filt.+rect.",
    "5. Env. vs RMS",
    "6. RMS/window",
    "7. MDF/time",
    "8. RMS vs MDF",
    "9. Env. overlay",
    "10. EMG vs MMG",
    "11. Tremor",
    "12. Move vs EMG",
]

# Display number per original panel index (sidebar labels, etc.).
_PANEL_SHORT_NAMES = {pid: num for pid, num in _PANEL_LAYOUT}

# Short, didactic tooltip per original panel index — what the panel shows.
_PANEL_TOOLTIPS = {
    0: "Raw EMG signal, unfiltered.",
    3: "Envelope normalised to its maximum (0-1): the activation time course.",
    4: "Power spectrum; MNF and MDF summarise its frequency content.",
    _OVERLAY_PID: "Both channels' envelopes overlaid — agonist/antagonist "
                  "coordination (needs a 2nd channel).",
    _MMG_PID: "Electrical (EMG) vs mechanical (MMG, from the accelerometer on "
              "the muscle) envelope — needs an accelerometer channel.",
    _TREMOR_PID: "Frequency spectrum of the accelerometer with the tremor peak "
                 "(physiological ~8-12 Hz) — needs an accelerometer channel.",
    _MOVEMENT_PID: "Movement (from the accelerometer on the moving segment) vs "
                   "the EMG envelope — movement follows contraction; needs an "
                   "accelerometer channel.",
    1: "Band-pass filtered (20-450 Hz) and rectified signal.",
    2: "Linear envelope vs the RMS envelope of the signal.",
    5: "RMS amplitude per window: how the intensity evolves.",
    6: "Median frequency over time; a fall indicates fatigue.",
    7: "Amplitude-frequency relation (force vs fatigue).",
    _RAW2_PID: "Raw EMG signal of the second muscle, unfiltered (needs a 2nd "
               "channel).",
}

from emgteach.broadcast import BroadcastServer
from emgteach.exports import write_analysis_csv
from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.gui.widgets.time_range import TimeRangeSelector
from emgteach.i18n import tr
from emgteach.io import (
    assess_edf_channels,
    edf_duration,
    find_edf_acc_channel,
    list_edf_channels,
    list_edf_emg_channels,
    read_edf_metadata,
)
from emgteach.modes import DEFAULT_MODE, MODE_FREE, MODE_PAIR, mode_uses_acc
from emgteach.profiles import EMG_PROFILE
from emgteach.reports import build_session_report
from emgteach.workers import AnalysisWorker


class AnalysisTab(QWidget):
    #: Emitted with the path of the EDF opened here and the muscle chosen for
    #: it, so the MVC tab uses the same recording *and* the same muscle without
    #: asking a question that has just been answered.
    file_opened = Signal(str, str)

    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None,
                 broadcast: BroadcastServer | None = None):
        super().__init__(parent)
        self._logger = logger
        self._settings = settings
        self._broadcast = broadcast   # shared classroom-broadcast server (or None)
        self._worker: AnalysisWorker | None = None
        self._last_result: dict | None = None
        # Accelerometer channel of the loaded file (name + placement), if any.
        self._acc_channel_name: str | None = None
        self._acc_placement: str = "unknown"
        self._last_edf_dir: str = self._settings.value("analisis/last_dir", ".")

        self._duracion_total: float = 60.0
        self._markers: list[tuple[float, str]] = []
        self._axes_list: list = []
        self._y_accum: dict[int, float] = {}
        self._y_initial_lims: dict[int, tuple[float, float]] = {}

        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(400)
        self._redraw_timer.timeout.connect(self._redibujar_con_ventana_actual)

        self._build_ui()

    # ------------------------------------------------------------------
    # Interface construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Top row: Parameters (stretch 3) + Log (stretch 2) ---
        grp_ctrl = QGroupBox(tr("Analysis parameters"))
        ctrl = QVBoxLayout(grp_ctrl)
        ctrl.setSpacing(4)
        ctrl.setContentsMargins(6, 4, 6, 4)

        # Line 1: EDF file + Analyse + Save
        row_file = QHBoxLayout()
        row_file.addWidget(QLabel(tr("EDF file:")))
        self._edit_path = QLineEdit()
        self._edit_path.setPlaceholderText(tr("Select an EDF file…"))
        self._edit_path.setReadOnly(True)
        row_file.addWidget(self._edit_path, stretch=1)
        self._btn_abrir = QPushButton(tr("Browse…"))
        self._btn_abrir.setFixedWidth(84)
        self._btn_abrir.clicked.connect(self._seleccionar_archivo)
        row_file.addWidget(self._btn_abrir)
        self._btn_analizar = QPushButton(tr("Analyse"))
        self._btn_analizar.setEnabled(False)
        self._btn_analizar.clicked.connect(self._iniciar_analisis)
        row_file.addWidget(self._btn_analizar)
        self._btn_guardar = QPushButton(tr("Save figure (PNG)"))
        self._btn_guardar.setEnabled(False)
        self._btn_guardar.clicked.connect(self._guardar_figura)
        row_file.addWidget(self._btn_guardar)
        self._btn_informe = QPushButton(tr("Generate PDF report"))
        self._btn_informe.setEnabled(False)
        self._btn_informe.clicked.connect(self._generar_informe)
        row_file.addWidget(self._btn_informe)
        self._btn_csv = QPushButton(tr("Export CSV"))
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._exportar_csv)
        row_file.addWidget(self._btn_csv)
        # Force-velocity study (needs an accelerometer channel in the file).
        self._btn_fv = QPushButton(tr("Force-velocity study…"))
        self._btn_fv.setEnabled(False)
        self._btn_fv.setToolTip(
            tr(
                "Build the load-velocity, force-velocity, power and recruitment "
                "curves from one recording where several known loads were "
                "lifted. Needs an accelerometer channel."
            )
        )
        self._btn_fv.clicked.connect(self._abrir_estudio_fv)
        row_file.addWidget(self._btn_fv)
        ctrl.addLayout(row_file)

        # Line 2: channel + f_env
        row_params = QHBoxLayout()
        row_params.addWidget(QLabel(tr("EMG channel:")))
        self._combo_canal = QComboBox()
        self._combo_canal.setEditable(False)  # pick one of the file's channels
        self._combo_canal.addItem("EMG")
        self._combo_canal.setFixedWidth(150)
        self._combo_canal.setToolTip(
            tr(
                "EMG channel to analyse. Every panel and the report use only "
                "this channel. Filled with the file's channels (EMG1/EMG2) when "
                "you select it."
            )
        )
        self._combo_canal.currentIndexChanged.connect(
            self._on_primary_channel_changed
        )
        row_params.addWidget(self._combo_canal)
        # Optional second channel: overlay the agonist/antagonist envelopes. The
        # partner channel is chosen automatically (the other one), so the picker
        # is read-only; it only lights up when comparing is on.
        self._box_compare = QWidget()
        compare_l = QHBoxLayout(self._box_compare)
        compare_l.setContentsMargins(0, 0, 0, 0)
        # Shown only in the agonist/antagonist mode, where comparing the two
        # channels is the point of the practical. The pair comes from the
        # recording, so it is stated rather than asked for.
        compare_l.addWidget(QLabel(tr("Compared with:")))
        # Kept to drive the overlay logic and gate panel 9, but never shown:
        # in this mode there is nothing to opt into.
        self._chk_compare2 = QCheckBox(tr("Compare channels:"))
        self._chk_compare2.setVisible(False)
        self._chk_compare2.setToolTip(
            tr(
                "Overlay the envelope of the two channels (agonist/antagonist). "
                "The partner channel is set automatically to the other one. "
                "Only available for two-channel recordings."
            )
        )
        self._chk_compare2.setEnabled(False)
        compare_l.addWidget(self._chk_compare2)
        self._combo_canal2 = QComboBox()
        self._combo_canal2.setEditable(False)
        self._combo_canal2.setFixedWidth(150)
        self._combo_canal2.setEnabled(False)   # read-only: shows the partner
        self._combo_canal2.setToolTip(tr("Partner channel (chosen automatically)."))
        self._chk_compare2.toggled.connect(self._on_compare2_toggled)
        compare_l.addWidget(self._combo_canal2)
        row_params.addWidget(self._box_compare)

        self._box_fenv = QWidget()
        fenv_l = QHBoxLayout(self._box_fenv)
        fenv_l.setContentsMargins(0, 0, 0, 0)
        fenv_l.addWidget(QLabel(tr("Envelope cutoff frequency (Hz):")))
        self._spin_fenv = QDoubleSpinBox()
        self._spin_fenv.setRange(1.0, 20.0)
        self._spin_fenv.setSingleStep(0.5)
        self._spin_fenv.setValue(5.0)
        self._spin_fenv.setFixedWidth(72)
        self._spin_fenv.setToolTip(
            tr("Envelope low-pass cut-off (Hz): lower = smoother envelope.")
        )
        fenv_l.addWidget(self._spin_fenv)
        row_params.addWidget(self._box_fenv)
        row_params.addWidget(QLabel(tr("Student:")))
        self._edit_student = QLineEdit()
        self._edit_student.setFixedWidth(150)
        self._edit_student.setText(self._settings.value("analisis/student", ""))
        self._edit_student.textChanged.connect(
            lambda v: self._settings.setValue("analisis/student", v)
        )
        row_params.addWidget(self._edit_student)
        row_params.addWidget(QLabel(tr("Code:")))
        self._edit_student_code = QLineEdit()
        self._edit_student_code.setFixedWidth(90)
        self._edit_student_code.setText(
            self._settings.value("analisis/student_code", "")
        )
        self._edit_student_code.textChanged.connect(
            lambda v: self._settings.setValue("analisis/student_code", v)
        )
        row_params.addWidget(self._edit_student_code)
        row_params.addStretch()
        ctrl.addLayout(row_params)

        # Line 3: region of interest (optional analysis sub-window) and the
        # fragment editor. The whole row is advanced, so it lives in a named
        # container the basic level can hide in one call — its "from"/"to"
        # captions are plain labels that could not be hidden individually.
        self._box_roi = QWidget()
        row_roi = QHBoxLayout(self._box_roi)
        row_roi.setContentsMargins(0, 0, 0, 0)
        self._chk_roi = QCheckBox(tr("Analyse only a region:"))
        self._chk_roi.setToolTip(
            tr(
                "Restrict every metric (spectrum, RMS, fatigue) to the time "
                "window below instead of the whole recording."
            )
        )
        row_roi.addWidget(self._chk_roi)
        row_roi.addWidget(QLabel(tr("from")))
        self._spin_roi_start = QDoubleSpinBox()
        self._spin_roi_start.setRange(0.0, 1_000_000.0)
        self._spin_roi_start.setDecimals(2)
        self._spin_roi_start.setSingleStep(0.5)
        self._spin_roi_start.setSuffix(" s")
        self._spin_roi_start.setFixedWidth(96)
        self._spin_roi_start.setEnabled(False)
        row_roi.addWidget(self._spin_roi_start)
        row_roi.addWidget(QLabel(tr("to")))
        self._spin_roi_end = QDoubleSpinBox()
        self._spin_roi_end.setRange(0.0, 1_000_000.0)
        self._spin_roi_end.setDecimals(2)
        self._spin_roi_end.setSingleStep(0.5)
        self._spin_roi_end.setSuffix(" s")
        self._spin_roi_end.setFixedWidth(96)
        self._spin_roi_end.setEnabled(False)
        row_roi.addWidget(self._spin_roi_end)
        self._chk_roi.toggled.connect(self._spin_roi_start.setEnabled)
        self._chk_roi.toggled.connect(self._spin_roi_end.setEnabled)
        row_roi.addSpacing(12)
        # Assisted multi-fragment selection (auto-suggested, user-edited).
        self._btn_fragmentos = QPushButton(tr("Select fragments…"))
        self._btn_fragmentos.setToolTip(
            tr(
                "Open the assisted editor to keep the significant fragments and "
                "discard the rest. Takes precedence over the region above."
            )
        )
        self._btn_fragmentos.setEnabled(False)
        self._btn_fragmentos.clicked.connect(self._editar_fragmentos)
        row_roi.addWidget(self._btn_fragmentos)
        self._lbl_fragmentos = QLabel("")
        row_roi.addWidget(self._lbl_fragmentos)
        self._selected_segments: list[tuple[float, float]] = []
        # Filter cut-offs chosen in the fragment editor; when set they drive
        # the actual analysis (not just detection). None = use the tab defaults.
        self._analysis_filter_kwargs: dict[str, float] | None = None
        row_roi.addStretch()
        ctrl.addWidget(self._box_roi)

        # Log to the right of the parameters
        grp_log_top = QGroupBox(tr("Event log"))
        log_top_layout = QVBoxLayout(grp_log_top)
        log_top_layout.setContentsMargins(4, 4, 4, 4)
        log_top_layout.addWidget(self._logger)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        top_row.addWidget(grp_ctrl, stretch=3)
        top_row.addWidget(grp_log_top, stretch=2)
        root.addLayout(top_row)

        # --- Panel selection — one compact line with horizontal scroll ---
        grp_paneles = QGroupBox(tr("Panels to show"))
        # Box identical to the others (same steel fill and border), like
        # "Markers". Each panel description sits in a white chip; its tick box
        # is white and fills blue when checked.
        grp_paneles.setStyleSheet(
            "QGroupBox {"
            "  background-color: #DCE7F4;"
            "  border: 1px solid #A7C2DF;"
            "  border-radius: 6px;"
            "  margin-top: 16px;"
            "  padding-top: 4px;"
            "  font-weight: bold;"
            "}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin;"
            "  subcontrol-position: top left;"
            "  left: 8px;"
            "  padding: 0 4px;"
            "  color: #1F4E79;"
            "}"
            "QCheckBox {"
            "  background-color: #FFFFFF;"
            "  border: 1px solid #A7C2DF;"
            "  border-radius: 4px;"
            "  padding: 3px 8px;"
            "  font-size: 11px;"
            "}"
            "QCheckBox::indicator {"
            "  width: 14px; height: 14px;"
            "  border: 1px solid #A7C2DF;"
            "  border-radius: 3px;"
            "  background-color: #FFFFFF;"
            "}"
            "QCheckBox::indicator:checked {"
            "  background-color: #4169E1;"
            "  border: 1px solid #2E50B0;"
            "}"
        )
        paneles_inner = QWidget()
        paneles_layout = QHBoxLayout(paneles_inner)
        paneles_layout.setContentsMargins(2, 0, 2, 0)
        paneles_layout.setSpacing(6)
        # Checkboxes in teaching display order; original panel index per
        # checkbox is kept in _panel_pids so the plotting/report code can map
        # back to the canonical panel identity. Only the teaching panels are
        # checked by default.
        self._panel_pids: list[int] = [pid for pid, _ in _PANEL_LAYOUT]
        self._chk_paneles: list[QCheckBox] = []
        # Tick state of panels the current mode hides, keyed by display index,
        # so switching back to a mode that offers them restores the selection.
        self._hidden_panels_checked: dict[int, bool] = {}
        # Set by apply_mode; initialised here because loading a file consults
        # the mode and may happen before the first apply_mode call.
        self._mode: str = DEFAULT_MODE
        self._advanced: bool = False
        for (pid, _num), label in zip(_PANEL_LAYOUT, _PANEL_SHORT_LABELS):
            chk = QCheckBox(tr(label))
            chk.setChecked(pid in _DEFAULT_PANELS)
            chk.setToolTip(tr(_PANEL_TOOLTIPS[pid]))
            # The overlay panel is only usable while comparing two channels;
            # the accelerometer panels only when the file has an ACC channel.
            if pid in (_OVERLAY_PID, *_ACC_PIDS):
                chk.setEnabled(False)
            paneles_layout.addWidget(chk)
            self._chk_paneles.append(chk)
        paneles_layout.addStretch()
        self._btn_redibujar = QPushButton(tr("Redraw"))
        self._btn_redibujar.setEnabled(False)
        self._btn_redibujar.clicked.connect(self._redibujar)
        paneles_layout.addWidget(self._btn_redibujar)

        paneles_scroll = QScrollArea()
        paneles_scroll.setWidget(paneles_inner)
        paneles_scroll.setWidgetResizable(True)
        paneles_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        paneles_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        paneles_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # Transparent viewport: let the box's steel background show in the gaps
        # between chips (otherwise an inner light-gray rectangle remains).
        paneles_scroll.viewport().setStyleSheet("background: transparent;")
        _fm = QFontMetrics(self.font())
        paneles_scroll.setFixedHeight(_fm.lineSpacing() * 2 + 10)

        paneles_outer = QVBoxLayout(grp_paneles)
        paneles_outer.setContentsMargins(4, 2, 4, 2)
        paneles_outer.addWidget(paneles_scroll)

        # --- Second row: Markers (stretch=2) + Panels to show (stretch=5),
        #     just below Parameters and Event log ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        grp_markers_bar = QGroupBox(tr("Markers"))
        markers_inner = QHBoxLayout(grp_markers_bar)
        markers_inner.setContentsMargins(6, 2, 6, 2)
        markers_inner.setSpacing(6)
        self._lbl_markers_bar = QLabel(tr("Markers ({n}):").format(n=0))
        self._lbl_markers_bar.setStyleSheet("font-size: 11px;")
        markers_inner.addWidget(self._lbl_markers_bar)
        self._combo_markers = QComboBox()
        self._combo_markers.setStyleSheet("font-size: 11px;")
        self._combo_markers.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._combo_markers.setEnabled(False)
        self._combo_markers.addItem(tr("No markers"))
        markers_inner.addWidget(self._combo_markers, stretch=1)
        self._btn_ir_marcador = QPushButton(tr("Go"))
        self._btn_ir_marcador.setFixedWidth(40)
        self._btn_ir_marcador.setFixedHeight(26)
        self._btn_ir_marcador.setStyleSheet("font-size: 11px;")
        self._btn_ir_marcador.setEnabled(False)
        self._btn_ir_marcador.clicked.connect(self._on_ir_marcador)
        markers_inner.addWidget(self._btn_ir_marcador)
        bottom_row.addWidget(grp_markers_bar, stretch=2)

        bottom_row.addWidget(grp_paneles, stretch=5)
        root.addLayout(bottom_row)

        # --- Display-window navigator widgets (assembled in the bottom row) ---
        # No box title (its meaning is obvious) and no reset button (the window
        # updates live as you drag).
        self._time_range = TimeRangeSelector()
        self._time_range.setEnabled(False)
        self._time_range.range_changed.connect(self._on_range_changed)
        self._time_range.range_preview.connect(self._on_range_preview)

        self._lbl_inicio_info   = QLabel(f"{tr('Start:')} 0.0 s")
        self._lbl_duracion_info = QLabel(f"{tr('Duration:')} 10.0 s")
        for lbl in (self._lbl_inicio_info, self._lbl_duracion_info):
            lbl.setStyleSheet("font-size: 9px; color: #333333;")

        _btn_st = "font-size: 9px;"
        self._btn_tiempo_ampliar = QPushButton("◀▶")
        self._btn_tiempo_ampliar.setToolTip(tr("Widen the time window (×2)"))
        self._btn_tiempo_ampliar.setFixedSize(30, 20)
        self._btn_tiempo_ampliar.setStyleSheet(_btn_st)
        self._btn_tiempo_ampliar.setEnabled(False)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setFixedSize(58, 20)
        self._combo_zoom.setStyleSheet(_btn_st)
        self._combo_zoom.setEnabled(False)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)

        self._btn_tiempo_reducir = QPushButton("▶◀")
        self._btn_tiempo_reducir.setToolTip(tr("Narrow the time window (÷2)"))
        self._btn_tiempo_reducir.setFixedSize(30, 20)
        self._btn_tiempo_reducir.setStyleSheet(_btn_st)
        self._btn_tiempo_reducir.setEnabled(False)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)

        # --- Barra de progreso + Cancelar ---
        progress_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat(tr("Ready"))
        self._progress.setVisible(False)
        progress_row.addWidget(self._progress, stretch=1)
        self._btn_cancelar = QPushButton(tr("Cancel"))
        self._btn_cancelar.setVisible(False)
        self._btn_cancelar.clicked.connect(self._cancelar_analisis)
        progress_row.addWidget(self._btn_cancelar)
        root.addLayout(progress_row)

        # --- Numeric summary panel (one row) ---
        grp_resumen = QGroupBox(tr("Analysis summary"))
        grp_resumen.setContentsMargins(4, 2, 4, 2)
        resumen_inner = QWidget()
        resumen_row = QHBoxLayout(resumen_inner)
        resumen_row.setContentsMargins(4, 0, 4, 0)
        resumen_row.setSpacing(0)

        _st = "font-size: 11px; padding: 0 6px;"
        _sep_st = "font-size: 11px; color: #999999; padding: 0 2px;"

        def _sep():
            s = QLabel("|")
            s.setStyleSheet(_sep_st)
            return s

        self._lbl_mnf = QLabel(f"{tr('Mean frequency (MNF):')} —")
        self._lbl_mdf = QLabel(f"{tr('Median frequency (MDF):')} —")
        self._lbl_fatiga = QLabel(f"{tr('Fatigue:')} —")
        self._lbl_pendiente = QLabel(f"{tr('MDF slope:')} —")
        self._lbl_rms_global = QLabel(f"{tr('Global RMS:')} —")
        self._lbl_iemg = QLabel("iEMG: —")
        self._lbl_iemg.setToolTip(
            tr("Integral of the rectified EMG — total muscle activation.")
        )
        self._lbl_duracion = QLabel(f"{tr('Duration:')} —")
        self._lbl_archivo = QLabel("")

        # Didactic tooltips: what each summary metric means.
        self._lbl_mnf.setToolTip(tr("Mean spectral frequency; tends to fall with fatigue."))
        self._lbl_mdf.setToolTip(
            tr("Frequency that splits the spectrum into two equal-power halves; "
               "falls with fatigue.")
        )
        self._lbl_fatiga.setToolTip(tr("Fatigue indicator from the MDF trend over time."))
        self._lbl_pendiente.setToolTip(tr("Slope of MDF over time (Hz/s); negative = fatigue."))
        self._lbl_rms_global.setToolTip(
            tr("Global RMS amplitude: mean intensity of the activation.")
        )
        self._lbl_duracion.setToolTip(tr("Analysed signal duration."))
        self._lbl_archivo.setToolTip(tr("Analysed EDF file."))

        for lbl in (self._lbl_mnf, self._lbl_mdf, self._lbl_fatiga, self._lbl_pendiente,
                    self._lbl_rms_global, self._lbl_iemg, self._lbl_duracion, self._lbl_archivo):
            lbl.setStyleSheet(_st)

        for lbl in (self._lbl_mnf, _sep(), self._lbl_mdf, _sep(), self._lbl_fatiga, _sep(),
                    self._lbl_pendiente, _sep(), self._lbl_rms_global, _sep(),
                    self._lbl_iemg, _sep(), self._lbl_duracion, _sep(), self._lbl_archivo):
            resumen_row.addWidget(lbl)
        resumen_row.addStretch()

        resumen_scroll = QScrollArea()
        resumen_scroll.setWidget(resumen_inner)
        resumen_scroll.setWidgetResizable(True)
        resumen_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        resumen_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        resumen_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        resumen_scroll.setFixedHeight(36)

        resumen_vbox = QVBoxLayout(grp_resumen)
        resumen_vbox.setContentsMargins(0, 0, 0, 0)
        resumen_vbox.addWidget(resumen_scroll)

        root.addWidget(grp_resumen)

        # --- Matplotlib canvas with scroll (the 7 panels are tall) ---
        self._fig = Figure(constrained_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Mouse-wheel zoom on the panel under the cursor.
        self._canvas.mpl_connect("scroll_event", self._on_scroll_zoom)

        # Vertical-scale sidebar: one ▲▼ pair per active panel
        self._y_scale_sidebar = QWidget()
        self._y_scale_sidebar.setFixedWidth(38)
        self._y_scale_sidebar_layout = QVBoxLayout(self._y_scale_sidebar)
        self._y_scale_sidebar_layout.setContentsMargins(2, 4, 2, 4)
        self._y_scale_sidebar_layout.setSpacing(0)

        canvas_container = QWidget()
        canvas_hbox = QHBoxLayout(canvas_container)
        canvas_hbox.setContentsMargins(0, 0, 0, 0)
        canvas_hbox.setSpacing(2)
        canvas_hbox.addWidget(self._y_scale_sidebar)
        canvas_hbox.addWidget(self._canvas)

        scroll = QScrollArea()
        scroll.setWidget(canvas_container)
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, stretch=1)

        # Display-window navigator at the very bottom: the minimap takes ~80 %
        # of the width; a compact two-row cluster (start/duration labels on top,
        # scale buttons below) shares the row on the right. The mouse wheel over
        # the panels still zooms too; _time_range defines the drawn segment
        # (see _on_result / _dibujar_paneles).
        nav_controls = QWidget()
        # Only as wide as the controls need; the bar takes all the rest.
        nav_controls.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        nav_ctrl_v = QVBoxLayout(nav_controls)
        nav_ctrl_v.setContentsMargins(0, 0, 0, 0)
        nav_ctrl_v.setSpacing(1)

        nav_info_row = QHBoxLayout()
        nav_info_row.setContentsMargins(0, 0, 0, 0)
        nav_info_row.setSpacing(8)
        nav_info_row.addWidget(self._lbl_inicio_info)
        nav_info_row.addWidget(self._lbl_duracion_info)
        nav_info_row.addStretch()
        nav_ctrl_v.addLayout(nav_info_row)

        nav_btn_row = QHBoxLayout()
        nav_btn_row.setContentsMargins(0, 0, 0, 0)
        nav_btn_row.setSpacing(4)
        nav_btn_row.addWidget(self._btn_tiempo_ampliar)
        nav_btn_row.addWidget(self._combo_zoom)
        nav_btn_row.addWidget(self._btn_tiempo_reducir)
        nav_btn_row.addStretch()
        nav_ctrl_v.addLayout(nav_btn_row)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(4, 2, 4, 2)
        nav_row.setSpacing(8)
        nav_row.addWidget(self._time_range, stretch=1)   # takes all remaining width
        nav_row.addWidget(nav_controls)                  # only as wide as needed
        root.addLayout(nav_row)

    # ------------------------------------------------------------------
    # Control slots
    # ------------------------------------------------------------------

    def adopt_recording(self, path: str) -> None:
        """Take the recording just made as the file to analyse.

        Only fills it in — it does not run the analysis. Loading is cheap and
        expected; computing is neither, and a run nobody asked for would fight
        whatever the student was reading.

        This is where the muscle gets chosen for a two-channel recording, and
        the choice travels on from here: asking again in the MVC tab would be
        putting the same question twice in a row.
        """
        if not path or (self._worker is not None and self._worker.isRunning()):
            return
        self._edit_path.setText(path)
        self._last_edf_dir = str(Path(path).parent)
        self._populate_channels(path)
        self.file_opened.emit(path, self._combo_canal.currentText().strip())
        self._btn_analizar.setEnabled(True)
        self._btn_fragmentos.setEnabled(True)
        self._selected_segments = []
        self._analysis_filter_kwargs = None
        self._actualizar_etiqueta_fragmentos()
        self._logger.append_log(
            tr("Recording loaded for analysis: {path}").format(path=Path(path).name)
        )

    @Slot()
    def _seleccionar_archivo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select EDF file"),
            self._last_edf_dir,
            tr("EDF files (*.edf *.EDF)"),
        )
        if path:
            self._edit_path.setText(path)
            self._last_edf_dir = str(Path(path).parent)
            self._settings.setValue("analisis/last_dir", self._last_edf_dir)
            self._populate_channels(path)
            self.file_opened.emit(path, self._combo_canal.currentText().strip())
            self._btn_analizar.setEnabled(True)
            self._btn_fragmentos.setEnabled(True)
            # A new file invalidates any previous fragment selection and its
            # associated filter cut-offs.
            self._selected_segments = []
            self._analysis_filter_kwargs = None
            self._actualizar_etiqueta_fragmentos()
            self._btn_guardar.setEnabled(False)
            self._btn_informe.setEnabled(False)
            self._btn_csv.setEnabled(False)
            self._progress.setValue(0)
            self._progress.setFormat(tr("Ready"))

    def _populate_channels(self, path: str) -> None:
        """Fill the channel picker with the file's EMG channels (excludes ACC).

        Detects whether the recording has one or two EMG channels: with one,
        the channel is fixed and "Compare channels" is disabled; with two, the
        user picks EMG1 or EMG2 and every panel/report uses only that channel.
        Comparing is off by default and, when turned on, the partner channel is
        set automatically to the other one.
        """
        labels = list_edf_emg_channels(path) or list_edf_channels(path)
        if not labels:
            return
        current = self._combo_canal.currentText().strip()
        self._combo_canal.blockSignals(True)
        self._combo_canal.clear()
        self._combo_canal.addItems(labels)
        idx = self._combo_canal.findText(current)
        self._combo_canal.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo_canal.blockSignals(False)

        # Fill the (read-only) partner picker with the same channels.
        self._combo_canal2.blockSignals(True)
        self._combo_canal2.clear()
        self._combo_canal2.addItems(labels)
        self._combo_canal2.blockSignals(False)

        # One channel -> no comparison possible; two -> the agonist/antagonist
        # mode turns it on by itself (_sync_compare_to_mode), since the pair is
        # a property of the recording rather than something to opt into.
        has_two = len(labels) >= 2
        self._chk_compare2.blockSignals(True)
        self._chk_compare2.setChecked(False)
        self._chk_compare2.setEnabled(has_two)
        self._chk_compare2.blockSignals(False)
        self._sync_second_channel()
        self._gate_overlay_panel(active=False)   # overlay only when comparing
        self._sync_compare_to_mode()
        if self._mode == MODE_PAIR and not has_two:
            self._warn_mode_mismatch(len(labels))
        elif has_two and self._mode != MODE_PAIR:
            # Two muscles in the file, a practical that studies one: without
            # asking, the tab quietly takes the first channel and every panel,
            # metric and report is about a muscle nobody chose.
            self._ask_which_channel(labels)

        # Warn if any channel is flat (no signal) or saturated (bad contact).
        self._warn_channel_quality(path)

        # Detect an accelerometer channel and enable its panels (EMG vs MMG,
        # tremor); default-check the one matching how the ACC was placed.
        acc = find_edf_acc_channel(path)
        if acc is not None:
            self._acc_channel_name, self._acc_placement = acc
        else:
            self._acc_channel_name, self._acc_placement = None, "unknown"
        self._gate_acc_panels(acc is not None)

        # Default the region-of-interest window to the whole recording.
        dur = edf_duration(path)
        if dur > 0.0:
            self._spin_roi_start.setMaximum(dur)
            self._spin_roi_end.setMaximum(dur)
            self._spin_roi_start.setValue(0.0)
            self._spin_roi_end.setValue(dur)

        # Pre-fill student/protocol from the EDF+ header written at recording
        # time, without clobbering anything the user already typed here.
        meta = read_edf_metadata(path)
        self._edf_protocol = meta.protocol
        if meta.student_name and not self._edit_student.text().strip():
            self._edit_student.setText(meta.student_name)
        if meta.student_code and not self._edit_student_code.text().strip():
            self._edit_student_code.setText(meta.student_code)

    @Slot()
    def _editar_fragmentos(self) -> None:
        path = self._edit_path.text().strip()
        if not path:
            return
        canal = self._combo_canal.currentText().strip() or "EMG"
        # Reopen with the previously chosen cut-offs, else the tab defaults.
        if self._analysis_filter_kwargs is not None:
            filter_kwargs = dict(self._analysis_filter_kwargs)
        else:
            filter_kwargs = dict(EMG_PROFILE.filter_kwargs())
            filter_kwargs["f_env"] = self._spin_fenv.value()
        try:
            dlg = FragmentSelectionDialog.from_edf(
                path, canal, filter_kwargs, segments=self._selected_segments or None,
                parent=self,
            )
        except Exception as exc:  # pragma: no cover — GUI feedback only
            self._logger.append_log(
                tr("Could not open the fragment editor: {error}").format(error=exc)
            )
            return
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._selected_segments = dlg.selected_segments()
            # Adopt the cut-offs tuned in the editor for the actual analysis so
            # what was previewed is what gets analysed. Reflect f_env in the tab.
            self._analysis_filter_kwargs = dlg.filter_kwargs()
            self._spin_fenv.setValue(self._analysis_filter_kwargs["f_env"])
            self._actualizar_etiqueta_fragmentos()

    def _actualizar_etiqueta_fragmentos(self) -> None:
        n = len(self._selected_segments)
        if n == 0:
            self._lbl_fragmentos.setText("")
        else:
            total = sum(b - a for a, b in self._selected_segments)
            self._lbl_fragmentos.setText(
                tr("{n} fragment(s) selected ({d:.1f} s)").format(n=n, d=total)
            )
            # A fragment selection overrides the single-region control.
            self._chk_roi.setChecked(False)

    @Slot()
    def _iniciar_analisis(self) -> None:
        path = self._edit_path.text().strip()
        canal = self._combo_canal.currentText().strip() or "EMG"
        # Optional second channel for the agonist/antagonist overlay.
        canal2 = None
        if self._chk_compare2.isChecked():
            c2 = self._combo_canal2.currentText().strip()
            if c2 and c2 != canal:
                canal2 = c2
        # Accelerometer channel — only analysed when an ACC panel is selected.
        acc_channel = None
        if self._acc_channel_name and self._any_acc_panel_checked():
            acc_channel = self._acc_channel_name
        # Filter cut-offs: use the ones tuned in the fragment editor if any,
        # else the tab's f_env with the profile band/notch defaults.
        fk = self._analysis_filter_kwargs
        f_low = fk["f_low"] if fk else None
        f_high = fk["f_high"] if fk else None
        f_notch = fk["f_notch"] if fk else None
        f_env = fk["f_env"] if fk else self._spin_fenv.value()

        self._set_controles_habilitados(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._progress.setFormat(tr("Analysing…  %p%"))
        self._btn_cancelar.setVisible(True)
        self._btn_cancelar.setEnabled(True)
        self._btn_guardar.setEnabled(False)
        self._btn_informe.setEnabled(False)
        self._btn_csv.setEnabled(False)
        self._lbl_mnf.setText(f"{tr('Mean frequency (MNF):')} —")
        self._lbl_mdf.setText(f"{tr('Median frequency (MDF):')} —")
        self._lbl_fatiga.setText(f"{tr('Fatigue:')} —")

        roi_start = roi_end = None
        roi_segments = self._selected_segments or None
        if roi_segments is None and self._chk_roi.isChecked():
            roi_start = self._spin_roi_start.value()
            roi_end = self._spin_roi_end.value()

        self._worker = AnalysisWorker(
            edf_path=path,
            channel_name=canal,
            channel_name_2=canal2,
            acc_channel=acc_channel,
            acc_placement=self._acc_placement,
            f_low=f_low,
            f_high=f_high,
            f_notch=f_notch,
            f_env=f_env,
            plot_duration_s=0,
            roi_start_s=roi_start,
            roi_end_s=roi_end,
            roi_segments=roi_segments,
        )
        self._worker.result_ready.connect(self._on_result)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._logger.append_log)
        self._worker.error.connect(self._on_error)
        # finished fires after run() returns for any reason (result, error or
        # cancel); it guarantees the UI is restored even when the worker aborts
        # at a checkpoint without emitting a result.
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.start()

    @Slot()
    def _cancelar_analisis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._btn_cancelar.setEnabled(False)
            self._logger.append_log(tr("Cancelling analysis…"))
            self._worker.stop()

    @Slot()
    def _on_analysis_finished(self) -> None:
        # Restore the UI regardless of how the run ended. If no result was
        # produced (cancelled), re-enable the controls that _on_result would
        # otherwise have handled.
        self._btn_cancelar.setVisible(False)
        self._btn_cancelar.setEnabled(False)
        if self._last_result is None or (
            self._worker is not None and self._worker.is_cancelled()
        ):
            self._progress.setVisible(False)
            self._set_controles_habilitados(True)

    # ------------------------------------------------------------------
    # Worker slots
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_progress(self, value: int) -> None:
        self._progress.setValue(value)

    @Slot(dict)
    def _on_result(self, result: dict) -> None:
        self._last_result = result
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)
        self._btn_guardar.setEnabled(True)
        self._btn_informe.setEnabled(True)
        self._btn_csv.setEnabled(True)
        self._btn_redibujar.setEnabled(True)
        duracion_total = float(result["times"][-1])
        self._duracion_total = duracion_total
        self._time_range.set_total_duration(duracion_total)
        # The envelope, not the raw trace: at the width of the bar the raw
        # interference pattern is a solid block, while the envelope shows
        # where the efforts are, which is what the window is aimed at.
        self._time_range.set_overview(result.get("emg_envelope"))
        # The window selector defaults to the whole recording; narrow it with
        # the minimap (or the ◀▶ / zoom controls) to inspect a segment.
        _dur_ini = duracion_total
        self._time_range.set_range(0.0, _dur_ini)
        self._lbl_inicio_info.setText(f"{tr('Start:')} 0.0 s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')}{_dur_ini:.1f} s")
        self._markers = result.get("markers", [])
        self._actualizar_lista_marcadores()
        self._update_combo_items()
        self._sync_combo_zoom()
        self._actualizar_resumen(result)
        self._dibujar_paneles(result)
        self._bcast_results(result)

    @Slot(float, float)
    def _on_range_changed(self, inicio: float, duracion: float) -> None:
        self._lbl_inicio_info.setText(f"{tr('Start:')}{inicio:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')}{duracion:.1f} s")
        self._sync_combo_zoom()
        self._redraw_timer.start()

    @Slot(float, float)
    def _on_range_preview(self, inicio: float, duracion: float) -> None:
        self._lbl_inicio_info.setText(f"{tr('Start:')}{inicio:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')}{duracion:.1f} s")

    @Slot()
    def _redibujar_con_ventana_actual(self) -> None:
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    @Slot()
    def _redibujar(self) -> None:
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._logger.append_error(msg)
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)

    # ------------------------------------------------------------------
    # Classroom broadcast of the analysis results / downloads
    # ------------------------------------------------------------------

    def _broadcast_on(self) -> bool:
        return self._broadcast is not None and self._broadcast.is_running()

    def _bcast_results(self, r: dict) -> None:
        """Push the analysis metrics to the student followers."""
        if not self._broadcast_on():
            return
        self._broadcast.broadcast({
            "t": "results",
            "file": Path(str(r.get("edf_path", ""))).name,
            "mnf": round(float(r.get("mnf", 0.0)), 1),
            "mdf": round(float(r.get("mdf", 0.0)), 1),
            "mdf_slope": round(float(r.get("mdf_slope", 0.0)), 2),
            "rms": round(float(r.get("rms_global", 0.0)), 3),
            "iemg": round(float(r.get("iemg", 0.0)), 1),
            "duration": round(float(r.get("duration", 0.0)), 1),
            "fatigue": int(r.get("fat_slope_sign", 0)),
        })

    def _bcast_download(self, kind: str, path: str, data: bytes,
                        content_type: str, filename: str) -> None:
        """Register a file for download and tell the followers it is ready."""
        if not self._broadcast_on():
            return
        self._broadcast.register_download(path, data, content_type, filename)
        self._broadcast.broadcast(
            {"t": "download", "kind": kind, "url": path, "name": filename}
        )

    # ------------------------------------------------------------------
    # Numeric summary
    # ------------------------------------------------------------------

    def _actualizar_resumen(self, r: dict) -> None:
        self._lbl_archivo.setText(f"{tr('File:')} {Path(r['edf_path']).name}")
        self._lbl_mnf.setText(f"{tr('Mean frequency (MNF):')}{r['mnf']:.1f} Hz")
        self._lbl_mdf.setText(f"{tr('Median frequency (MDF):')}{r['mdf']:.1f} Hz")
        pendiente = r.get("mdf_slope", 0.0)
        r2 = r.get("fat_r_squared", 0.0)
        signo = "+" if pendiente >= 0 else ""
        self._lbl_pendiente.setText(
            f"{tr('MDF slope:')}{signo}{pendiente:.2f} Hz/s  (R²={r2:.2f})"
        )
        self._lbl_rms_global.setText(f"{tr('Global RMS:')}{r.get('rms_global', 0.0):.2f} mV")
        self._lbl_iemg.setText(f"iEMG: {r.get('iemg', 0.0):.1f} mV·s")
        self._lbl_duracion.setText(f"{tr('Duration:')}{r.get('duration', 0.0):.1f} s")

        sign = r["fat_slope_sign"]
        decline = r.get("fat_pct_decline", 0.0)
        if sign < 0:
            texto = tr("Fatigue: DETECTED (MDF −{decline:.1f}%)").format(decline=decline)
            color = "#cc0000"
        elif sign > 0:
            texto = tr("Fatigue: Not detected (MDF stable or increasing)")
            color = "#007700"
        else:
            texto = tr("Fatigue: Undetermined (insufficient signal)")
            color = "#885500"
        self._lbl_fatiga.setText(texto)
        self._lbl_fatiga.setStyleSheet(f"font-size: 9px; padding: 0 4px; color: {color};")

    # ------------------------------------------------------------------
    # Drawing the 7 panels (replicates analisis_emg_completo.py)
    # ------------------------------------------------------------------

    def _abrir_estudio_fv(self) -> None:
        """Open the force-velocity study dialog for the loaded recording."""
        path = self._edit_path.text().strip()
        if not path or not self._acc_channel_name:
            return
        canal = self._combo_canal.currentText().strip() or "EMG"
        try:
            from emgteach.gui.widgets.force_velocity_dialog import (
                ForceVelocityDialog,
            )

            dlg = ForceVelocityDialog(
                path, canal, self._acc_channel_name,
                f_env=self._spin_fenv.value(), parent=self,
            )
            dlg.exec()
        except Exception as exc:  # pragma: no cover — GUI feedback only
            self._logger.append_error(
                tr("Could not open the force-velocity study: {error}").format(
                    error=exc
                )
            )

    def _warn_channel_quality(self, path: str) -> None:
        """Log a per-channel warning when a loaded channel is flat or saturated.

        Surfaces the common recording faults right when the file is opened, so
        a flat (disconnected) or saturated (bad-contact) channel is obvious
        before running the analysis.
        """
        for label, status in assess_edf_channels(path):
            if status == "flat":
                self._logger.append_error(
                    tr("Channel «{ch}»: flat — no signal (electrode not "
                       "connected?).").format(ch=label)
                )
            elif status == "saturated":
                self._logger.append_error(
                    tr("Channel «{ch}»: saturated — the trace is pinned at the "
                       "rails (check the electrode contact or the gain).").format(
                        ch=label
                    )
                )
            elif status == "weak":
                self._logger.append_log(
                    tr("Channel «{ch}»: weak signal (low amplitude).").format(
                        ch=label
                    )
                )

    @Slot(int)
    def _on_primary_channel_changed(self, _index: int) -> None:
        """When the analysed channel changes, keep the partner in sync."""
        self._sync_second_channel()

    @Slot(bool)
    def _on_compare2_toggled(self, checked: bool) -> None:
        """Turn the overlay on/off: sync the partner channel and gate panel 9."""
        self._sync_second_channel()
        self._gate_overlay_panel(active=checked)

    def _sync_second_channel(self) -> None:
        """Set the (read-only) partner picker to the channel not being analysed.

        Selecting EMG1 makes the partner EMG2 and vice versa. With a single
        channel there is no partner.
        """
        n = self._combo_canal2.count()
        if n < 2:
            return
        other = 1 if self._combo_canal.currentIndex() == 0 else 0
        self._combo_canal2.blockSignals(True)
        self._combo_canal2.setCurrentIndex(other)
        self._combo_canal2.blockSignals(False)

    def _gate_overlay_panel(self, active: bool) -> None:
        """Check+enable (active) or uncheck+disable the overlay panel checkbox.

        The overlaid-envelopes panel (9) is only meaningful when comparing two
        channels, so it cannot be ticked otherwise — avoiding confusion on
        single-channel recordings.
        """
        try:
            pos = self._panel_pids.index(_OVERLAY_PID)
        except ValueError:
            return
        chk = self._chk_paneles[pos]
        chk.setChecked(active)
        chk.setEnabled(active)

    def _any_acc_panel_checked(self) -> bool:
        """True if any accelerometer panel (EMG-vs-MMG, tremor, movement) is
        ticked."""
        for pid in _ACC_PIDS:
            try:
                pos = self._panel_pids.index(pid)
            except ValueError:
                continue
            if self._chk_paneles[pos].isChecked():
                return True
        return False

    def _gate_acc_panels(self, has_acc: bool) -> None:
        """Enable the accelerometer panels when the file has an ACC channel.

        On enabling, the panel matching the ACC placement is ticked by default
        (MMG for an ACC on the muscle, movement-vs-EMG for one on the moving
        segment); without an ACC channel they are all unticked and locked.
        """
        default_pid = (
            _MOVEMENT_PID if self._acc_placement == "limb" else _MMG_PID
        )
        for pid in _ACC_PIDS:
            try:
                pos = self._panel_pids.index(pid)
            except ValueError:
                continue
            chk = self._chk_paneles[pos]
            chk.setEnabled(has_acc)
            chk.setChecked(has_acc and pid == default_pid)
        # The force-velocity study also needs the accelerometer.
        self._btn_fv.setEnabled(has_acc)

    def _dibujar_paneles(self, r: dict) -> None:
        self._fig.clear()
        self._fig.set_constrained_layout_pads(hspace=0.12, h_pad=0.08)

        # Map checked boxes (in teaching display order) back to their canonical
        # panel indices; the subplot order follows the display order.
        selected = [
            self._panel_pids[i]
            for i, chk in enumerate(self._chk_paneles) if chk.isChecked()
        ]
        if not selected:
            self._canvas.draw_idle()
            return

        times = r["times"]
        inicio_s, dur_s = self._time_range.get_range()
        fin_s = inicio_s + dur_s
        f_high = r["f_high"]

        n_panels = len(selected)
        raw_axes = self._fig.subplots(n_panels, 1, sharex=False)
        axes_list = [raw_axes] if n_panels == 1 else list(raw_axes)
        ax_map = {panel_idx: axes_list[pos] for pos, panel_idx in enumerate(selected)}

        _grid = dict(ls="--", color="#DDDDDD", alpha=0.8)

        # --- 1A: Raw signal ---
        if 0 in ax_map:
            ax = ax_map[0]
            ax.plot(times, r["emg_raw"],
                    color="#333333", lw=0.8, alpha=0.7)
            ax.set_title(tr("1A. Raw EMG signal"), fontsize=9)
            ax.set_ylabel(tr("Amplitude (mV)"), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 1B: Raw signal of the second muscle ---
        if _RAW2_PID in ax_map:
            ax = ax_map[_RAW2_PID]
            crudo2 = r.get("emg_raw_2")
            if crudo2 is not None:
                ax.plot(times, crudo2, color="#333333", lw=0.8, alpha=0.7)
            nombre2 = r.get("channel_name_2") or tr("Muscle {n}").format(n=2)
            ax.set_title(
                tr("1B. Raw EMG signal — {muscle}").format(muscle=nombre2),
                fontsize=9,
            )
            ax.set_ylabel(tr("Amplitude (mV)"), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- Filtered + rectified ---
        if 1 in ax_map:
            ax = ax_map[1]
            ax.plot(times, r["emg_filtered"],
                    color="#1f77b4", lw=1.2, label=tr("Filtered EMG (20-450 Hz)"))
            ax.plot(times, r["emg_rectified"],
                    color="#d62728", lw=1.2, alpha=0.9, label=tr("Rectified EMG"))
            ax.set_title(tr("4. Filtered + rectified EMG signal"), fontsize=9)
            ax.set_ylabel(tr("Amplitude (mV)"), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 2: Envelope ---
        if 2 in ax_map:
            ax = ax_map[2]
            ax.plot(times, r["emg_rectified"],
                    color="#E74C3C", lw=1.2, alpha=0.6, label=tr("Rectified EMG"))
            ax.plot(times, r["emg_envelope"],
                    color="#9467bd", lw=2.0, label=tr("LP envelope (zero-phase)"))
            ax.plot(times, r["rms_sliding"],
                    color="#2ca02c", lw=1.5, ls="--", label=tr("RMS envelope"))
            ax.set_title(tr("5. EMG signal envelope"), fontsize=9)
            ax.set_ylabel(tr("Amplitude (mV)"), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 3: Normalised envelope ---
        if 3 in ax_map:
            ax = ax_map[3]
            ax.plot(times, r["emg_envelope_normalised"],
                    color="#9467bd", lw=1.8, label=tr("Normalised envelope (max=1)"))
            ax.axhline(1.0, color="#E74C3C", ls=":", lw=1.5, alpha=0.8)
            ax.set_title(tr("2. Envelope normalised to maximum"), fontsize=9)
            ax.set_ylabel(tr("Normalised amplitude (0-1)"), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.set_ylim(0, 1.15)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- Overlaid envelopes (agonist/antagonist) ---
        if _OVERLAY_PID in ax_map:
            ax = ax_map[_OVERLAY_PID]
            # Each muscle against its own maximum, never millivolts. This is
            # the one panel that puts two *different* muscles on one axis, and
            # their millivolts are not comparable: the amplitude depends on
            # where each pair of electrodes sits and how much skin and fat lie
            # between them and the fibres — the very reason the MVC tab
            # exists. Read in mV, a thicker biceps would look like
            # co-contraction. What the question actually asks is *when* each
            # muscle is active, and how hard relative to its own effort, and
            # that is exactly what survives normalisation.
            # A channel that never contracted has no maximum to divide by, so
            # its baseline noise arrives magnified to full height. That is the
            # correct *finding* — the muscle stayed silent — but a solid line
            # at full scale states the opposite, so it is drawn as what it is:
            # faint, dashed, and named.
            def _dibujar(env, colour, nombre, contrajo) -> None:
                if contrajo:
                    ax.plot(times, env, color=colour, lw=1.8, label=nombre)
                else:
                    ax.plot(times, env, color="#9AA6B2", lw=1.0, ls=(0, (4, 3)),
                            alpha=0.85,
                            label=tr("{name} — no contraction (baseline noise)")
                            .format(name=nombre))

            lbl1 = r.get("channel_name") or tr("Muscle {n}").format(n=1)
            _dibujar(r["emg_envelope_normalised"], "#4169E1", lbl1,
                     r.get("emg_contracted", True))
            env2 = r.get("emg_envelope_normalised_2")
            if env2 is not None:
                lbl2 = r.get("channel_name_2") or tr("Muscle {n}").format(n=2)
                _dibujar(env2, "#D62728", lbl2, r.get("emg_contracted_2", True))
            else:
                ax.text(
                    0.5, 0.5,
                    tr("Enable “Compare 2nd channel” to overlay the antagonist."),
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=8, color="#888888",
                )
            ax.set_title(tr("9. Overlaid envelopes (agonist/antagonist)"), fontsize=9)
            ax.set_ylabel(tr("Normalised amplitude (0-1)"), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.set_ylim(0, 1.15)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7,
                      title=tr("each ÷ its own maximum"), title_fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- EMG vs MMG (electrical vs mechanical) ---
        if _MMG_PID in ax_map:
            ax = ax_map[_MMG_PID]
            mmg = r.get("acc_mmg_envelope")
            emg_lbl = r.get("channel_name") or "EMG"
            ax.plot(times, r["emg_envelope"], color="#4169E1", lw=1.8,
                    label=tr("EMG — {ch} (electrical)").format(ch=emg_lbl))
            if mmg is not None:
                ax2 = ax.twinx()
                ax2.plot(times, mmg, color="#2ca02c", lw=1.6,
                         label=tr("MMG envelope (mechanical)"))
                ax2.set_ylabel(tr("MMG (g)"), fontsize=8, color="#2ca02c")
                ax2.tick_params(axis="y", labelsize=7, colors="#2ca02c")
                ax2.set_xlim(inicio_s, fin_s)
                ax2.legend(loc="upper right", fontsize=7)
                # Remind that the MMG belongs to the muscle carrying the ACC.
                ax.text(0.5, 0.98,
                        tr("MMG is paired with «{ch}» — the muscle carrying the "
                           "accelerometer.").format(ch=emg_lbl),
                        transform=ax.transAxes, ha="center", va="top",
                        fontsize=7, color="#888888")
            else:
                ax.text(0.5, 0.5,
                        tr("No accelerometer channel in this recording."),
                        transform=ax.transAxes, ha="center", va="center",
                        fontsize=8, color="#888888")
            ax.set_title(tr("10. EMG vs MMG (electrical vs mechanical)"), fontsize=9)
            ax.set_ylabel(tr("EMG (mV)"), fontsize=8, color="#4169E1")
            ax.tick_params(axis="y", labelsize=7, colors="#4169E1")
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(axis="x", labelsize=7)
            ax.legend(loc="upper left", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- Tremor (accelerometer FFT) ---
        if _TREMOR_PID in ax_map:
            ax = ax_map[_TREMOR_PID]
            freqs = r.get("acc_tremor_freqs")
            psd = r.get("acc_tremor_psd")
            if freqs is not None and psd is not None:
                ax.plot(freqs, psd, color="#8c564b", lw=1.6)
                peak = float(r.get("acc_tremor_peak_hz", 0.0))
                if peak > 0:
                    ax.axvline(peak, color="#E74C3C", ls="--", lw=1.8,
                               label=tr("Peak: {hz:.1f} Hz").format(hz=peak))
                    ax.legend(loc="upper right", fontsize=7)
                ax.set_xlim(0, 25)
            else:
                ax.text(0.5, 0.5,
                        tr("No accelerometer channel in this recording."),
                        transform=ax.transAxes, ha="center", va="center",
                        fontsize=8, color="#888888")
            ax.set_title(tr("11. Tremor — accelerometer spectrum"), fontsize=9)
            ax.set_xlabel(tr("Frequency (Hz)"), fontsize=8)
            ax.set_ylabel("PSD (g²/Hz)", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.grid(True, **_grid)

        # --- Movement vs EMG (accelerometer on the moving segment) ---
        if _MOVEMENT_PID in ax_map:
            ax = ax_map[_MOVEMENT_PID]
            move = r.get("acc_movement_envelope")
            emg_lbl = r.get("channel_name") or "EMG"
            ax.plot(times, r["emg_envelope"], color="#4169E1", lw=1.8,
                    label=tr("EMG — {ch} (electrical)").format(ch=emg_lbl))
            if move is not None:
                ax2 = ax.twinx()
                ax2.plot(times, move, color="#D35400", lw=1.6,
                         label=tr("Movement (limb kinematics)"))
                ax2.set_ylabel(tr("Movement (a.u.)"), fontsize=8, color="#D35400")
                ax2.tick_params(axis="y", labelsize=7, colors="#D35400")
                ax2.set_xlim(inicio_s, fin_s)
                ax2.legend(loc="upper right", fontsize=7)
                # The accelerometer is uncalibrated, so the movement trace is in
                # arbitrary units — the point is that it tracks the contraction.
                ax.text(0.5, 0.98,
                        tr("Movement from the accelerometer on the moving "
                           "segment — follows «{ch}» (arbitrary units).")
                        .format(ch=emg_lbl),
                        transform=ax.transAxes, ha="center", va="top",
                        fontsize=7, color="#888888")
            else:
                ax.text(0.5, 0.5,
                        tr("No accelerometer channel in this recording."),
                        transform=ax.transAxes, ha="center", va="center",
                        fontsize=8, color="#888888")
            ax.set_title(tr("12. Movement vs EMG (limb kinematics)"), fontsize=9)
            ax.set_ylabel(tr("EMG (mV)"), fontsize=8, color="#4169E1")
            ax.tick_params(axis="y", labelsize=7, colors="#4169E1")
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(axis="x", labelsize=7)
            ax.legend(loc="upper left", fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 4: PSD ---
        if 4 in ax_map:
            ax = ax_map[4]
            ax.plot(r["frequencies"], r["psd"], color="#0047AB", lw=1.8)
            ax.axvline(r["mnf"], color="#FF8C00", ls="--", lw=2.0,
                       label=f"MNF: {r['mnf']:.1f} Hz")
            ax.axvline(r["mdf"], color="#C71585", ls="--", lw=2.0,
                       label=f"MDF: {r['mdf']:.1f} Hz")
            ax.set_title(tr("3. Power spectral density (PSD)"), fontsize=9)
            ax.set_xlabel(tr("Frequency (Hz)"), fontsize=8)
            ax.set_ylabel("PSD (mV²/Hz)", fontsize=8)
            ax.set_xlim(0, f_high + 50)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)

        # --- 5: RMS per window ---
        if 5 in ax_map:
            ax = ax_map[5]
            ax.plot(r["t_seg"], r["rms_seg"],
                    color="#2ca02c", lw=1.5, marker="o", ms=4,
                    label=tr("RMS per 1 s window"))
            ax.set_title(tr("6. RMS amplitude over time"), fontsize=9)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_ylabel("RMS (mV)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 6: MDF vs time ---
        if 6 in ax_map:
            ax = ax_map[6]
            ax.scatter(r["t_seg"], r["mdf_seg"],
                       s=20, alpha=0.7, color="#666666",
                       label=tr("Median frequency per window"))
            if len(r["t_seg"]) >= 2:
                ax.plot(r["t_seg"], r["fat_fitted"],
                        color="#E74C3C", lw=2.5,
                        label=tr("Trend (degree-2 polynomial)"))
            ax.set_title(
                tr(
                    "7. Fatigue trend: median frequency vs. time\n"
                    "   (a decrease indicates muscle fatigue)"
                ),
                fontsize=9, pad=8,
            )
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_ylabel("MDF (Hz)", fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)
            self._dibujar_marcadores(ax, inicio_s, fin_s)

        # --- 7: RMS vs MDF (scatter) ---
        if 7 in ax_map:
            ax = ax_map[7]
            t_seg = r["t_seg"]
            sc = ax.scatter(r["mdf_seg"], r["rms_seg"],
                            c=t_seg, cmap="viridis", s=60, alpha=0.8, zorder=3)
            ax.plot(r["rms_mdf_range"], r["rms_mdf_fitted"],
                    color="#E74C3C", lw=2.5, label=tr("Degree-2 polynomial fit"))
            cbar = self._fig.colorbar(sc, ax=ax, orientation="vertical", pad=0.02)
            cbar.set_label(tr("Time (s)"), fontsize=8)
            cbar.ax.tick_params(labelsize=7)
            ax.set_title(tr("8. Amplitude (force) vs median frequency (fatigue)"), fontsize=9)
            ax.set_xlabel("MDF (Hz)", fontsize=8)
            ax.set_ylabel("RMS (mV)", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7)
            ax.grid(True, **_grid)

        self._axes_list = axes_list
        self._y_initial_lims = {pi: ax.get_ylim() for pi, ax in zip(selected, axes_list)}
        self._y_accum = {pi: 1.0 for pi in selected}
        self._canvas.setMinimumHeight(n_panels * 180)
        self._canvas.setMinimumWidth(0)
        self._canvas.draw_idle()
        self._rebuild_y_sidebar(selected)

    # ------------------------------------------------------------------
    # Save figure
    # ------------------------------------------------------------------

    @Slot()
    def _guardar_figura(self) -> None:
        if self._last_result is None:
            return
        carpeta = str(Path(self._last_result["edf_path"]).parent)
        nombre = Path(self._last_result["edf_path"]).stem + "_analisis_emg.png"
        ruta_default = str(Path(carpeta) / nombre)

        ruta, _ = QFileDialog.getSaveFileName(
            self, tr("Save figure"),
            ruta_default,
            tr("PNG images (*.png)"),
        )
        if ruta:
            self._fig.savefig(ruta, dpi=150, bbox_inches="tight")
            self._logger.append_log(tr("Figure saved to: {path}").format(path=ruta))

    @Slot()
    def _exportar_csv(self) -> None:
        if self._last_result is None:
            return
        carpeta = str(Path(self._last_result["edf_path"]).parent)
        nombre = Path(self._last_result["edf_path"]).stem + "_analisis_emg.csv"
        ruta_default = str(Path(carpeta) / nombre)

        ruta, _ = QFileDialog.getSaveFileName(
            self, tr("Export CSV"),
            ruta_default,
            tr("CSV files (*.csv)"),
        )
        if not ruta:
            return
        try:
            write_analysis_csv(self._last_result, ruta)
        except Exception as exc:  # pragma: no cover — GUI feedback only
            self._logger.append_log(tr("CSV export error: {error}").format(error=exc))
            return
        self._logger.append_log(tr("CSV exported to: {path}").format(path=ruta))
        self._bcast_download("csv", "/dl/resultados.csv",
                             Path(ruta).read_bytes(), "text/csv", Path(ruta).name)

    @Slot()
    def _pedir_paneles_informe(self) -> tuple[list[int], tuple[float, float]] | None:
        """Modal dialog to choose which graphs (and time range) go in the report.

        Returns ``(panel_indices, (start, end))`` — the checked panels (0-7) and
        the time range to plot — or ``None`` if the user cancels. The panels are
        pre-checked from the on-screen selection and the range is pre-filled
        with the currently visible window.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Report graphs"))
        dlg.setMinimumWidth(340)
        # Styling consistent with the app: gray background, blue header and each
        # graph in a white box (chip), like in "Panels to show".
        dlg.setStyleSheet(
            "QDialog { background-color: #E1E6EB; }"
            "QLabel#dlgHeader { color: #1F4E79; font-weight: bold; font-size: 12px; }"
            "QCheckBox {"
            "  background-color: #FFFFFF;"
            "  border: 1px solid #A7C2DF;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "}"
            "QCheckBox::indicator {"
            "  width: 14px; height: 14px;"
            "  border: 1px solid #A7C2DF;"
            "  border-radius: 3px;"
            "  background-color: #FFFFFF;"
            "}"
            "QCheckBox::indicator:checked {"
            "  background-color: #4169E1;"
            "  border: 1px solid #2E50B0;"
            "}"
            "QPushButton {"
            "  background-color: #DCE7F4;"
            "  border: 1px solid #A7C2DF;"
            "  border-radius: 4px;"
            "  padding: 4px 14px;"
            "}"
            "QPushButton:hover { background-color: #cfe0f2; }"
            "QPushButton:pressed { background-color: #b9d2ee; }"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        encabezado = QLabel(tr("Tick the graphs to add to the report:"))
        encabezado.setObjectName("dlgHeader")
        lay.addWidget(encabezado)

        comparing = self._chk_compare2.isChecked()
        has_acc = self._acc_channel_name is not None
        checks: list[QCheckBox] = []
        for i, nombre in enumerate(_PANEL_NOMBRES):
            cb = QCheckBox(tr(nombre))
            cb.setChecked(i < len(self._chk_paneles) and self._chk_paneles[i].isChecked())
            pid = self._panel_pids[i]
            # The overlay panel needs two compared channels; the accelerometer
            # panels need an ACC channel — otherwise they cannot be reported.
            locked = (pid == _OVERLAY_PID and not comparing) or (
                pid in _ACC_PIDS and not has_acc
            )
            if locked:
                cb.setChecked(False)
                cb.setEnabled(False)
            lay.addWidget(cb)
            checks.append(cb)

        lay.addSpacing(6)
        rango_lbl = QLabel(tr("Time range to plot (s):"))
        rango_lbl.setObjectName("dlgHeader")
        lay.addWidget(rango_lbl)
        ini0, dur0 = self._time_range.get_range()
        total = max(self._duracion_total, ini0 + dur0)
        rango_row = QHBoxLayout()
        rango_row.addWidget(QLabel(tr("Start:")))
        spin_ini = QDoubleSpinBox()
        spin_ini.setRange(0.0, max(0.0, total))
        spin_ini.setDecimals(1)
        spin_ini.setSingleStep(0.5)
        spin_ini.setValue(float(ini0))
        rango_row.addWidget(spin_ini)
        rango_row.addWidget(QLabel(tr("Duration:")))
        spin_dur = QDoubleSpinBox()
        spin_dur.setRange(0.5, max(0.5, total))
        spin_dur.setDecimals(1)
        spin_dur.setSingleStep(0.5)
        spin_dur.setValue(float(dur0))
        rango_row.addWidget(spin_dur)
        rango_row.addStretch()
        lay.addLayout(rango_row)

        lay.addSpacing(6)
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(dlg.accept)
        botones.rejected.connect(dlg.reject)
        lay.addWidget(botones)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        # Map checked boxes (display order) to canonical panel indices.
        paneles = [
            self._panel_pids[i] for i, cb in enumerate(checks) if cb.isChecked()
        ]
        x0 = float(spin_ini.value())
        x1 = min(x0 + float(spin_dur.value()), float(total))
        return paneles, (x0, x1)

    def _generar_informe(self) -> None:
        """Generate the PDF session report next to the source EDF.

        Before building it, asks which graphs to include (tick dialog).
        """
        if self._last_result is None:
            return
        seleccion = self._pedir_paneles_informe()
        if seleccion is None:
            return  # cancelled by the user
        paneles, rango = seleccion
        edf_path = Path(str(self._last_result.get("edf_path", "")) or "sesion.edf")
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Ask where and under what name to save the PDF (same UX as "Export CSV"
        # / "Save figure"), pre-filled next to the EDF with a timestamped name.
        ruta_default = str(edf_path.with_name(f"{edf_path.stem}_informe_{ts}.pdf"))
        ruta, _ = QFileDialog.getSaveFileName(
            self, tr("Save PDF report"), ruta_default,
            tr("PDF documents (*.pdf)"),
        )
        if not ruta:
            return  # cancelled by the user
        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"
        out = Path(ruta)
        meta = {
            "student": self._edit_student.text().strip(),
            "student_code": self._edit_student_code.text().strip(),
            "protocol": getattr(self, "_edf_protocol", ""),
        }
        try:
            build_session_report(out, self._last_result, meta, panels=paneles,
                                 time_range=rango)
            self._logger.append_log(tr("PDF report generated: {path}").format(path=out))
            self._bcast_download("report", "/dl/informe.pdf",
                                 out.read_bytes(), "application/pdf", out.name)
        except Exception as exc:
            self._logger.append_error(
                tr("Error generating the PDF report: {error}").format(error=exc)
            )

    # ------------------------------------------------------------------
    # Marcadores
    # ------------------------------------------------------------------

    def _on_scroll_zoom(self, event) -> None:
        """Mouse-wheel zoom on the panel under the cursor (X and Y), centred
        on the cursor position — mirrors the pyqtgraph behaviour of the
        acquisition tab."""
        ax = event.inaxes
        if ax is None or event.xdata is None or event.ydata is None:
            return
        scale = 1.0 / 1.2 if event.button == "up" else 1.2
        x, y = event.xdata, event.ydata
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.set_xlim(x - (x - x0) * scale, x + (x1 - x) * scale)
        ax.set_ylim(y - (y - y0) * scale, y + (y1 - y) * scale)
        self._canvas.draw_idle()

    def _dibujar_marcadores(self, ax, inicio_s: float, fin_s: float) -> None:
        for t_mark, lbl_mark in self._markers:
            if inicio_s <= t_mark <= fin_s:
                ax.axvline(t_mark, color="#E67E22", linestyle="--",
                           linewidth=1.2, alpha=0.8)
                txt = (lbl_mark[:15] + "…") if len(lbl_mark) > 15 else lbl_mark
                ax.text(t_mark, ax.get_ylim()[1], txt,
                        fontsize=7, rotation=90, va="top", ha="right",
                        color="#E67E22")

    def _actualizar_lista_marcadores(self) -> None:
        sorted_m = sorted(self._markers, key=lambda x: x[0])
        n = len(sorted_m)
        self._lbl_markers_bar.setText(tr("Markers ({n}):").format(n=n))
        self._combo_markers.blockSignals(True)
        self._combo_markers.clear()
        if sorted_m:
            for tiempo, etiqueta in sorted_m:
                self._combo_markers.addItem(f"t={tiempo:.1f} s — {etiqueta}")
            self._combo_markers.setEnabled(True)
            self._btn_ir_marcador.setEnabled(True)
        else:
            self._combo_markers.addItem(tr("No markers"))
            self._combo_markers.setEnabled(False)
            self._btn_ir_marcador.setEnabled(False)
        self._combo_markers.blockSignals(False)

    def _on_ir_marcador(self) -> None:
        sorted_m = sorted(self._markers, key=lambda x: x[0])
        idx = self._combo_markers.currentIndex()
        if idx < 0 or idx >= len(sorted_m):
            return
        tiempo, _ = sorted_m[idx]
        _, dur = self._time_range.get_range()
        nuevo_inicio = max(0.0, min(tiempo - dur / 2, self._duracion_total - dur))
        self._time_range.set_range(nuevo_inicio, dur)
        self._lbl_inicio_info.setText(f"{tr('Start:')}{nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')}{dur:.1f} s")
        self._sync_combo_zoom()
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    # ------------------------------------------------------------------
    # Per-panel vertical scale
    # ------------------------------------------------------------------

    def _rebuild_y_sidebar(self, selected: list[int]) -> None:
        while self._y_scale_sidebar_layout.count():
            item = self._y_scale_sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for panel_idx, ax in zip(selected, self._axes_list):
            slot = QWidget()
            slot_vbox = QVBoxLayout(slot)
            slot_vbox.setContentsMargins(0, 0, 0, 0)
            slot_vbox.setSpacing(1)

            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(32, 18)
            btn_up.setStyleSheet("font-size: 9px;")
            btn_up.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, True)
            )

            lbl = QLabel(f"P{_PANEL_SHORT_NAMES[panel_idx]}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 7px; color: #666666;")

            btn_dn = QToolButton()
            btn_dn.setText("▼")
            btn_dn.setFixedSize(32, 18)
            btn_dn.setStyleSheet("font-size: 9px;")
            btn_dn.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, False)
            )

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addStretch()

            self._y_scale_sidebar_layout.addWidget(slot, stretch=1)

    def _y_zoom(self, panel_idx: int, ax, zoom_in: bool) -> None:
        factor = 1.5
        accum = self._y_accum.get(panel_idx, 1.0)
        if zoom_in:
            new_accum = accum / factor
            if new_accum < 0.01:
                return
            ymin, ymax = ax.get_ylim()
            ax.set_ylim(ymin / factor, ymax / factor)
        else:
            new_accum = accum * factor
            if new_accum > 100.0:
                return
            ymin, ymax = ax.get_ylim()
            ax.set_ylim(ymin * factor, ymax * factor)
        self._y_accum[panel_idx] = new_accum
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Time-scale controls
    # ------------------------------------------------------------------

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        inicio, dur = self._time_range.get_range()
        nueva_dur = min(dur * 2.0, self._duracion_total)
        nueva_dur = max(nueva_dur, 0.5)
        nuevo_inicio = min(inicio, self._duracion_total - nueva_dur)
        self._time_range.set_range(nuevo_inicio, nueva_dur)
        self._lbl_inicio_info.setText(f"{tr('Start:')}{nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')}{nueva_dur:.1f} s")
        self._sync_combo_zoom()
        self._redraw_timer.start()

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        inicio, dur = self._time_range.get_range()
        nueva_dur = max(dur / 2.0, 0.5)
        nuevo_inicio = min(inicio, self._duracion_total - nueva_dur)
        self._time_range.set_range(nuevo_inicio, nueva_dur)
        self._lbl_inicio_info.setText(f"{tr('Start:')}{nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')}{nueva_dur:.1f} s")
        self._sync_combo_zoom()
        self._redraw_timer.start()

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva_dur = self._duracion_total / factor
        if nueva_dur < 0.5:
            return
        inicio, _ = self._time_range.get_range()
        nuevo_inicio = min(inicio, self._duracion_total - nueva_dur)
        self._time_range.set_range(nuevo_inicio, nueva_dur)
        self._lbl_inicio_info.setText(f"{tr('Start:')}{nuevo_inicio:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')}{nueva_dur:.1f} s")
        self._redraw_timer.start()

    def _sync_combo_zoom(self) -> None:
        if self._duracion_total <= 0:
            return
        _, dur = self._time_range.get_range()
        factor = self._duracion_total / dur
        best_idx, best_diff = 0, float("inf")
        for i, f in enumerate(_ZOOM_FACTORS):
            diff = abs(factor - f)
            if diff < best_diff:
                best_diff, best_idx = diff, i
        self._combo_zoom.blockSignals(True)
        self._combo_zoom.setCurrentIndex(best_idx)
        self._combo_zoom.blockSignals(False)

    def _update_combo_items(self) -> None:
        model = self._combo_zoom.model()
        for i, f in enumerate(_ZOOM_FACTORS):
            item = model.item(i)
            if item is None:
                continue
            enabled = (self._duracion_total / f) >= 0.5
            flags = item.flags()
            if enabled:
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            else:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_controles_habilitados(self, habilitado: bool) -> None:
        self._btn_abrir.setEnabled(habilitado)
        self._btn_analizar.setEnabled(habilitado and bool(self._edit_path.text()))
        self._combo_canal.setEnabled(habilitado)
        self._spin_fenv.setEnabled(habilitado)
        self._chk_roi.setEnabled(habilitado)
        self._btn_fragmentos.setEnabled(
            habilitado and bool(self._edit_path.text())
        )
        roi_on = habilitado and self._chk_roi.isChecked()
        self._spin_roi_start.setEnabled(roi_on)
        self._spin_roi_end.setEnabled(roi_on)
        has_data = habilitado and self._last_result is not None
        self._time_range.setEnabled(has_data)
        self._btn_tiempo_ampliar.setEnabled(has_data)
        self._btn_tiempo_reducir.setEnabled(has_data)
        self._combo_zoom.setEnabled(has_data)

    # ------------------------------------------------------------------
    # New-session reset
    # ------------------------------------------------------------------

    def _reset_summary_labels(self) -> None:
        _st = "font-size: 11px; padding: 0 6px;"
        self._lbl_mnf.setText(f"{tr('Mean frequency (MNF):')} —")
        self._lbl_mdf.setText(f"{tr('Median frequency (MDF):')} —")
        self._lbl_fatiga.setText(f"{tr('Fatigue:')} —")
        self._lbl_fatiga.setStyleSheet(_st)
        self._lbl_pendiente.setText(f"{tr('MDF slope:')} —")
        self._lbl_rms_global.setText(f"{tr('Global RMS:')} —")
        self._lbl_iemg.setText("iEMG: —")
        self._lbl_duracion.setText(f"{tr('Duration:')} —")
        self._lbl_archivo.setText("")

    def reset(self) -> None:
        """Clear the tab to its just-opened state (new student): loaded file,
        results, student name/code, plots and summary."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        self._worker = None
        self._last_result = None
        self._markers = []
        self._duracion_total = 60.0

        self._edit_path.clear()
        # Clearing the student fields also clears their persisted QSettings
        # values (textChanged is wired to setValue).
        self._edit_student.clear()
        self._edit_student_code.clear()
        self._spin_fenv.setValue(5.0)
        self._combo_canal.blockSignals(True)
        self._combo_canal.clear()
        self._combo_canal.addItem("EMG")
        self._combo_canal.blockSignals(False)

        self._btn_analizar.setEnabled(False)
        self._btn_fragmentos.setEnabled(False)
        self._selected_segments = []
        self._analysis_filter_kwargs = None
        self._actualizar_etiqueta_fragmentos()
        self._btn_guardar.setEnabled(False)
        self._btn_informe.setEnabled(False)
        self._btn_csv.setEnabled(False)
        self._btn_redibujar.setEnabled(False)

        self._reset_summary_labels()
        self._actualizar_lista_marcadores()

        self._progress.setVisible(False)
        self._progress.setValue(0)
        self._progress.setFormat(tr("Ready"))

        self._fig.clear()
        self._canvas.draw_idle()
        self._axes_list = []
        self._rebuild_y_sidebar([])

        self._time_range.setEnabled(False)
        self._time_range.set_total_duration(60.0)
        self._time_range.set_range(0.0, 10.0)
        self._btn_tiempo_ampliar.setEnabled(False)
        self._btn_tiempo_reducir.setEnabled(False)
        self._combo_zoom.setEnabled(False)
        self._lbl_inicio_info.setText(f"{tr('Start:')} 0.0 s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')} 10.0 s")

    def apply_mode(self, mode: str, advanced: bool) -> None:
        """Offer the analyses that belong to one practical.

        Whole containers are hidden rather than individual widgets: the region
        and cut-off controls sit beside plain QLabels ("from", "to", "Envelope
        cutoff frequency (Hz):") that are not kept as attributes and would
        otherwise be left behind.
        """
        self._mode = mode
        self._advanced = advanced

        # Comparing two channels only means something with two of them, and
        # the force-velocity study needs the accelerometer.
        self._box_compare.setVisible(mode == MODE_PAIR)
        # Shares its row with Save / PDF / CSV, which stay; it carries its own
        # caption, so hiding it alone leaves nothing behind.
        self._btn_fv.setVisible(mode_uses_acc(mode))

        # Shared by every mode: fine control.
        self._box_fenv.setVisible(advanced)
        self._box_roi.setVisible(advanced)

        self._sync_compare_to_mode()
        self._apply_panel_visibility(mode, advanced)

    def _sync_compare_to_mode(self) -> None:
        """Comparing follows the mode and the file, never a separate tick.

        In the agonist/antagonist mode the two channels come from the
        recording, so the overlay is simply on whenever the file really has
        two. Any other mode leaves it off.
        """
        # setEnabled() tracks whether the loaded file has a second channel.
        want = self._mode == MODE_PAIR and self._chk_compare2.isEnabled()
        if self._chk_compare2.isChecked() != want:
            self._chk_compare2.setChecked(want)

    def _warn_mode_mismatch(self, n_channels: int) -> None:
        """The file cannot support the chosen practical — say so, and say what
        to do about it. Left to itself the tab would silently behave as a
        single-channel analysis while the mode still claimed two muscles."""
        msg = tr(
            "This recording has {n} EMG channel(s), and the agonist / "
            "antagonist mode needs two."
        ).format(n=n_channels)
        self._logger.append_error(msg)
        QMessageBox.warning(
            self,
            tr("The recording does not match the mode"),
            msg
            + "\n\n"
            + tr(
                "Choose \"Single-muscle contraction\" or \"Muscle kinematics\" "
                "at the top of the window, or open a recording made with two "
                "channels."
            ),
        )

    def _ask_which_channel(self, labels: list[str]) -> None:
        """Two muscles recorded, one to be analysed: let the student say which.

        The buttons carry the channel labels themselves, so the choice is
        between "Biceps" and "Triceps" rather than between EMG1 and EMG2 —
        which is the whole reason the labels are typed at recording time.
        """
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(tr("Which muscle is being analysed?"))
        msg.setText(
            tr(
                "This recording has two muscles. This practical studies one at "
                "a time, so every panel, metric and report will be about the "
                "channel chosen here."
            )
        )
        botones = [msg.addButton(name, QMessageBox.ButtonRole.AcceptRole)
                   for name in labels[:2]]
        msg.setDefaultButton(botones[0])
        msg.exec()

        elegido = next(
            (n for b, n in zip(botones, labels) if msg.clickedButton() is b),
            labels[0],
        )
        idx = self._combo_canal.findText(elegido)
        if idx >= 0:
            self._combo_canal.setCurrentIndex(idx)
        self._logger.append_log(
            tr("Analysing {muscle}.").format(muscle=elegido)
        )

    def _panel_is_offered(self, index: int, mode: str, advanced: bool) -> bool:
        """Whether the panel at this display position suits mode and flag.

        The agonist/antagonist practical is a closed set: the raw trace of
        each muscle and the two envelopes overlaid, and nothing else. Adding a
        spectrum or a fatigue slope there would be about one of the two
        muscles, which is not what the practical is asking.

        Elsewhere the first three (raw, normalised envelope, PSD) are the
        teaching core and are always offered; the next five are further EMG
        analyses that apply to any practical, so they follow the fine-control
        level; the rest belong to one practical each.
        """
        pid = self._panel_pids[index]
        if mode == MODE_FREE:
            return True                      # everything: that is what it is for
        if mode == MODE_PAIR:
            return pid in (0, _RAW2_PID, _OVERLAY_PID)
        if pid in (_RAW2_PID, _OVERLAY_PID):
            return False                     # both need a second muscle
        if pid in _ACC_PIDS:
            return mode_uses_acc(mode)
        return pid in _CORE_PIDS

    def _apply_panel_visibility(self, mode: str, advanced: bool) -> None:
        """Hide the panels this practical does not use, and untick them.

        Hiding the checkbox is not enough: the plotting code selects panels by
        isChecked(), so a panel ticked under one mode would still be drawn
        under another, with no visible way to turn it off. What gets hidden is
        remembered, so coming back restores the selection.
        """
        for i, chk in enumerate(self._chk_paneles):
            offered = self._panel_is_offered(i, mode, advanced)
            if offered:
                chk.setVisible(True)
                was = self._hidden_panels_checked.pop(i, None)
                # Panels unavailable for the loaded file (overlay without a
                # second channel, ACC panels without an ACC channel) stay off.
                if was and chk.isEnabled():
                    chk.setChecked(True)
            else:
                if i not in self._hidden_panels_checked:
                    self._hidden_panels_checked[i] = chk.isChecked()
                chk.setChecked(False)
                chk.setVisible(False)

    def cleanup(self) -> None:
        """Called by MainWindow.closeEvent — cancels and waits for the worker."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
