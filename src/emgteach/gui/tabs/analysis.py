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
from matplotlib.figure import Figure
from PySide6.QtCore import QSettings, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
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
from emgteach.fatigue import FATIGUE, INCONCLUSIVE, NO_FATIGUE
from emgteach.figures import draw_emd_note, draw_spectrum_before_filter
from emgteach.gui.help_texts import text as help_text
from emgteach.gui.widgets.calibration_reps import CalibrationRepsDialog
from emgteach.gui.widgets.canvas import ScrollingCanvas
from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog
from emgteach.gui.widgets.help_button import add_help
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.gui.widgets.time_range import TimeRangeSelector
from emgteach.i18n import tr
from emgteach.io import (
    assess_edf_channels,
    edf_duration,
    find_edf_acc_channel,
    list_edf_channels,
    list_edf_emg_channels,
    read_edf_markers,
    read_edf_metadata,
)
from emgteach.modes import (
    DEFAULT_MODE,
    MODE_KINEMATICS,
    MODE_PAIR,
    MODE_SINGLE,
    mode_uses_acc,
)
from emgteach.mvc import mark_excess_over_100, overlay_curves
from emgteach.phases import (
    NO_CALIBRATION,
    parse_phase_markers,
    reference_source_text,
)
from emgteach.profiles import EMG_PROFILE
from emgteach.reports import build_session_report
from emgteach.tuning import build_tuned_edf, tuned_path
from emgteach.workers import AnalysisWorker


class AnalysisTab(QWidget):
    #: Emitted with the path of the EDF opened here and the muscle chosen for
    #: it, so the MVC tab uses the same recording *and* the same muscle without
    #: asking a question that has just been answered.
    file_opened = Signal(str, str)
    #: One step of the guided sequence: (title, body, the control it points at).
    #: Emitted rather than shown here because the floating panel belongs to the
    #: window — it dims everything outside the control it explains, which a tab
    #: cannot do to its siblings.
    coach_step = Signal(str, str, object)

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
        add_help(grp_ctrl, "ana.params")
        ctrl = QVBoxLayout(grp_ctrl)
        ctrl.setSpacing(4)
        # A little more room under the last row: with the panel chips there,
        # the row sat against the frame and looked cut off.
        ctrl.setContentsMargins(6, 4, 6, 8)

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
        self._btn_analizar.setToolTip(tr(
        "Re-run the analysis with the settings changed since the last one. It lights up only when there is something to redo: opening a file analyses it, and the two editors re-analyse when you accept them."
        ))
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

        # Beside the exports, because that is what it is: the recording
        # written out with the decisions taken on screen inside it. Until
        # now those decisions — which repetitions count, which stretch is
        # the task — lived only in this tab, so the same file opened
        # anywhere else told a different story.
        self._btn_afinado = QPushButton(tr("Save tuned EDF…"))
        self._btn_afinado.setEnabled(False)
        self._btn_afinado.setToolTip(tr(
            "Write a new recording carrying the current selection: the "
            "calibration repetitions kept and the fragments of the task. "
            "The original is never touched, and the new file says where "
            "it came from."
        ))
        self._btn_afinado.clicked.connect(self._guardar_afinado)
        # Added to the second row further down, with the other two tools for
        # afterwards: on the first row, with eight buttons across, the path
        # field was squeezed to sixty pixels on a 1366 px screen.
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
        # Same: goes on the second row (see below).
        ctrl.addLayout(row_file)

        # Line 2: channel + f_env
        row_params = QHBoxLayout()
        row_params.addWidget(QLabel(tr("EMG channel:")))
        self._combo_canal = QComboBox()
        self._combo_canal.setEditable(False)  # pick one of the file's channels
        self._combo_canal.addItem("EMG")
        self._combo_canal.setFixedWidth(110)
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
        # These five feed the worker and none of them re-runs it, which is
        # why the Analyse button survives. It lights up here and nowhere
        # else, so in a session that only opens the two editors it stays
        # dark from beginning to end.
        self._combo_canal.currentIndexChanged.connect(self._marcar_pendiente)
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
        # No caption on a line this full: the partner is stated in the
        # read-only box beside the channel, and its tooltip says what it is.
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
        self._combo_canal2.setFixedWidth(100)
        self._combo_canal2.setEnabled(False)   # read-only: shows the partner
        self._combo_canal2.setToolTip(tr("Partner channel (chosen automatically)."))
        self._chk_compare2.toggled.connect(self._on_compare2_toggled)
        self._chk_compare2.toggled.connect(self._marcar_pendiente)
        self._combo_canal2.currentIndexChanged.connect(self._marcar_pendiente)
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
        # Goes on the advanced row with the region and the two tools (see
        # below): it is a fine control, and on the editors' line it took
        # the width the panel chips needed in the one practical that has
        # six of them.
        # No identifier field here: it was typed at recording time and
        # travels in the EDF header, where the report reads it. Asking for
        # it a second time let the two disagree.
        self._student_code: str = ""
        # row_params is not a row of its own any more: it goes into the
        # single line below, after the two editors.

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
        self._chk_roi.toggled.connect(self._marcar_pendiente)
        self._spin_roi_start.valueChanged.connect(self._marcar_pendiente)
        self._spin_roi_end.valueChanged.connect(self._marcar_pendiente)
        self._spin_fenv.valueChanged.connect(self._marcar_pendiente)
        self._chk_roi.toggled.connect(self._spin_roi_start.setEnabled)
        self._chk_roi.toggled.connect(self._spin_roi_end.setEnabled)
        row_roi.addStretch()

        # The envelope cut-off and the advanced practical's two tools, on an
        # advanced row of their own. Sharing the region row fitted on a
        # Windows font and not on the Linux runner's wider one: 1439 px.
        self._box_tools = QWidget()
        row_tools = QHBoxLayout(self._box_tools)
        row_tools.setContentsMargins(0, 0, 0, 0)
        row_tools.addWidget(self._box_fenv)
        row_tools.addSpacing(12)
        row_tools.addWidget(self._btn_afinado)
        row_tools.addWidget(self._btn_fv)
        row_tools.addStretch()

        # The fragment editor sits in its own container, offered in every
        # practical. Keeping the part of a recording that came out well is not
        # a fine adjustment: a first attempt in a teaching laboratory arrives
        # with movement artefacts, a loose electrode or a false start more
        # often than not, and throwing that away is hygiene rather than
        # expertise. The numeric "from"/"to" boxes above stay a fine control:
        # they ask for two figures the student does not have, where the editor
        # shows the recording and lets them point.
        # One line, in the order things are done: the calibration
        # repetitions first (they fix the reference every % MVC is measured
        # in), then the fragments, then the channels, then which panels to
        # draw — and, in the advanced practical, its two extra tools.
        self._box_fragmentos = QWidget()
        row_frag = QHBoxLayout(self._box_fragmentos)
        row_frag.setContentsMargins(0, 0, 0, 0)
        # Deliberately not part of the fragment editor: the recording is
        # continuous signal and the calibration is a handful of discrete
        # efforts. Two editions, two tools.
        self._btn_reps = QPushButton(tr("Calibration repetitions…"))
        self._btn_reps.setEnabled(False)
        self._btn_reps.clicked.connect(self._editar_repeticiones)
        self._actualizar_ayuda_reps()
        row_frag.addWidget(self._btn_reps)
        self._lbl_reps = QLabel("")
        self._lbl_reps.setStyleSheet("font-size: 11px; color: #8a5000;")
        row_frag.addWidget(self._lbl_reps)

        self._btn_fragmentos = QPushButton(tr("Select fragments…"))
        self._btn_fragmentos.setToolTip(
            tr(
                "Open the assisted editor to keep the significant fragments and "
                "discard the rest. Takes precedence over the region above."
            )
        )
        self._btn_fragmentos.setEnabled(False)
        self._btn_fragmentos.clicked.connect(self._editar_fragmentos)
        row_frag.addWidget(self._btn_fragmentos)
        self._lbl_fragmentos = QLabel("")
        self._lbl_fragmentos.setStyleSheet("font-size: 11px; color: #205080;")
        row_frag.addWidget(self._lbl_fragmentos)

        row_frag.addSpacing(10)
        row_frag.addLayout(row_params)
        row_frag.addSpacing(10)
        # The panel boxes are inserted here once built (see below).
        self._pos_paneles = row_frag.count()
        # The two tools of the advanced practical go on the region row above,
        # which only that practical shows and which has the room; here they
        # squeezed the panel chips to a sliver at 1366 px. No trailing
        # stretch: whatever width is left goes to the chips.
        # Which of the two to do next, said in one line. Both buttons light up
        # together at the end of the first analysis, and nothing said that the
        # calibration comes first — but it does, and not by convention: the
        # reference it fixes is the yardstick for every % MVC the fragments are
        # then measured in, so choosing the fragments first means choosing them
        # against a reference that is about to change.
        self._lbl_siguiente = QLabel("")
        self._lbl_siguiente.setWordWrap(True)
        self._lbl_siguiente.setStyleSheet("font-size: 11px; color: #205080;")
        self._lbl_siguiente.setVisible(False)
        self._selected_segments: list[tuple[float, float]] = []
        #: What the operator calls each fragment, aligned with the list
        #: above. A named fragment is a window of the co-activation table;
        #: an unnamed one is only signal worth keeping.
        self._segment_labels: list[str] = []
        #: Calibration repetitions kept, by channel index. Empty means all
        #: of them, which is what a recording starts as.
        self._cal_keep: dict[int, set[int]] = {}
        # Filter cut-offs chosen in the fragment editor; when set they drive
        # the actual analysis (not just detection). None = use the tab defaults.
        self._analysis_filter_kwargs: dict[str, float] | None = None
        # Whether a setting has changed since the last analysis. The
        # button used to be a step of the sequence — press it once to see
        # the recording, and again after each editor — and pressing the
        # same control for two different reasons is what made the sequence
        # hard to follow. It cannot go: the channel, the second channel,
        # the accelerometer panels, the envelope smoothing and the region
        # of interest all feed the analysis and none of them re-runs it.
        # So it stays for exactly those, and stays dark otherwise.
        self._pendiente = False
        #: Which step of the guided sequence the floating panel last showed,
        #: so it appears when the step changes and not after every re-analysis.
        self._paso_mostrado: str = ""
        row_roi.addStretch()
        ctrl.addWidget(self._box_roi)
        ctrl.addWidget(self._box_tools)
        ctrl.addWidget(self._box_fragmentos)
        ctrl.addWidget(self._lbl_siguiente)

        # Log to the right of the parameters
        grp_log_top = QGroupBox(tr("Event log"))
        log_top_layout = QVBoxLayout(grp_log_top)
        log_top_layout.setContentsMargins(4, 4, 4, 4)
        log_top_layout.addWidget(self._logger)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        # The log takes the height of the parameters box and little of the
        # width: it is a strip of a few lines, not a quarter of the screen.
        top_row.addWidget(grp_ctrl, stretch=6)
        top_row.addWidget(grp_log_top, stretch=1)
        root.addLayout(top_row)

        # --- Panel selection: chips on the same line as the editors and the
        # channels. It used to be a box of its own under the parameters, a
        # row that cost the panels its height for a handful of tick boxes.
        # Each panel sits in a white chip; its tick fills blue when checked.
        paneles_inner = QWidget()
        paneles_inner.setStyleSheet(
            "QCheckBox {"
            "  background-color: #FFFFFF;"
            "  border: 1px solid #A7C2DF;"
            "  border-radius: 4px;"
            "  padding: 2px 5px;"
            "  font-size: 10px;"
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
        paneles_layout = QHBoxLayout(paneles_inner)
        paneles_layout.setContentsMargins(2, 0, 2, 0)
        paneles_layout.setSpacing(6)
        lbl_paneles = QLabel(tr("Panels:"))
        lbl_paneles.setToolTip(help_text("ana.panels")[1])
        paneles_layout.addWidget(lbl_paneles)
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
            if pid in _ACC_PIDS:
                # The only panels whose checkbox changes what is
                # *computed* rather than what is drawn: the worker reads
                # the accelerometer only when one of them is on.
                chk.toggled.connect(self._marcar_pendiente)
            paneles_layout.addWidget(chk)
            # Ticking a box redraws; there is no button to press afterwards.
            chk.toggled.connect(self._redibujar)
            self._chk_paneles.append(chk)
        paneles_layout.addStretch()
        # The advanced practical owns twelve panels, and twelve boxes do not
        # fit on a row at 1400 px: they overflowed into a scroll bar, which
        # is a developer's menu, not a student's. By default it shows its
        # own six — the teaching core and the accelerometer three — and this
        # reveals the rest: the further EMG analyses and the two-muscle
        # panels, for whoever wants them.
        self._mas_paneles = False
        self._btn_mas_paneles = QToolButton()
        self._btn_mas_paneles.setText(tr("More panels…"))
        self._btn_mas_paneles.setCheckable(True)
        self._btn_mas_paneles.setAutoRaise(True)
        self._btn_mas_paneles.setStyleSheet("font-size: 11px;")
        self._btn_mas_paneles.toggled.connect(self._on_mas_paneles)
        self._btn_mas_paneles.setVisible(False)
        paneles_layout.addWidget(self._btn_mas_paneles)
        # No «Redraw» button: the boxes redraw as they are ticked (see the
        # loop above). A button that has to be pressed after every change is
        # a second step for the same intention.

        # Into the editors' line, after the channels. There used to be a
        # «Markers (n): [list] Go» box beside this one, to jump the view to
        # one marker; jumping to a marker is an expert's move, and the
        # student's markers are the automatic onsets, drawn on the panels.
        # Inside a frameless scroll area, as before: a scroll area's minimum
        # width does not depend on what it holds, so thirteen chips — ten
        # of them hidden by the practical — cannot set the window's minimum.
        paneles_scroll = QScrollArea()
        paneles_scroll.setWidget(paneles_inner)
        paneles_scroll.setWidgetResizable(True)
        paneles_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        paneles_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        paneles_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        paneles_scroll.viewport().setStyleSheet("background: transparent;")
        # Measured off the chips themselves, not off this widget's font: the
        # chips carry their own font size, padding and border in a style
        # sheet, so a height derived from the tab's line spacing clipped
        # them by a couple of pixels at the bottom on other machines.
        _alto_chip = max(
            [c.sizeHint().height() for c in self._chk_paneles]
            + [self._btn_mas_paneles.sizeHint().height()]
        )
        # And with room for the horizontal scrollbar. A scroll area of fixed
        # height pays for the bar out of its viewport, so the moment «More
        # panels…» made the row overflow the bar appeared and the chips lost
        # their bottom edge behind it. Reserved always, so the row keeps one
        # height whether the bar is there or not.
        _alto_barra = paneles_scroll.horizontalScrollBar().sizeHint().height()
        paneles_scroll.setFixedHeight(_alto_chip + 8 + _alto_barra)
        paneles_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        row_frag.insertWidget(self._pos_paneles, paneles_scroll, stretch=1)

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

        # --- Numeric summary: a grid of cards ---
        # One card per figure, the caption above and the value below. The
        # old version was a single row of nine "Label: value" pairs with
        # pipes between them, inside a scroll area: to find a number the
        # student had to read a sentence, and the sentence was 11 px high.
        # Here the number is the thing on the card. Two rows of five so the
        # panel keeps its width on a 1366 px screen.
        grp_resumen = QGroupBox(tr("Analysis summary"))
        add_help(grp_resumen, "ana.summary")
        resumen_grid = QGridLayout(grp_resumen)
        resumen_grid.setContentsMargins(8, 2, 8, 6)
        resumen_grid.setHorizontalSpacing(16)
        resumen_grid.setVerticalSpacing(0)

        _cap_st = "font-size: 10px; color: #6B7580;"
        _val_st = "font-size: 13px; font-weight: 600;"

        # Three rows per card: the caption, the value and — where one
        # exists — the usual range in small grey. A median frequency of
        # 130 Hz means nothing to a student who has never seen one; «usual
        # 60–120 Hz» beside it is what turns the number into a reading. The
        # ranges are orientative values for surface EMG, not limits.
        _rango_st = "font-size: 9px; color: #8A94A0;"

        def _ficha(fila: int, col: int, caption: str, tooltip: str = "",
                   ayuda: QToolButton | None = None, rango: str = "") -> QLabel:
            cap = QLabel(caption)
            cap.setStyleSheet(_cap_st)
            val = QLabel("—")
            val.setStyleSheet(_val_st)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if tooltip:
                cap.setToolTip(tooltip)
                val.setToolTip(tooltip)
            base = 3 * fila
            if ayuda is None:
                resumen_grid.addWidget(cap, base, col)
            else:
                cabecera = QHBoxLayout()
                cabecera.setContentsMargins(0, 0, 0, 0)
                cabecera.setSpacing(2)
                cabecera.addWidget(cap)
                cabecera.addWidget(ayuda)
                cabecera.addStretch()
                resumen_grid.addLayout(cabecera, base, col)
            resumen_grid.addWidget(val, base + 1, col)
            if rango:
                lbl_rango = QLabel(rango)
                lbl_rango.setStyleSheet(_rango_st)
                resumen_grid.addWidget(lbl_rango, base + 2, col)
            return val

        # The fatigue verdict is explained in the box's own «?», with the
        # rest of the cards: one help per box, in the corner, all alike.

        self._lbl_mnf = _ficha(
            0, 0, tr("Mean frequency (MNF)"),
            tr("Mean spectral frequency; tends to fall with fatigue."),
            rango=tr("usual 80–170 Hz"),
        )
        self._lbl_mdf = _ficha(
            0, 1, tr("Median frequency (MDF)"),
            tr("Frequency that splits the spectrum into two equal-power halves; "
               "falls with fatigue."),
            rango=tr("usual 60–150 Hz"),
        )
        self._lbl_pendiente = _ficha(
            0, 2, tr("MDF slope"),
            tr("Slope of MDF over time (Hz/s); negative = fatigue."),
        )
        self._lbl_fatiga = _ficha(
            1, 0, tr("Fatigue"),
            tr("Fatigue indicator from the MDF trend over time."),
        )
        # What the task reached against the reference, sustained over the
        # same half second the reference is measured on. Computed for every
        # analysis and, until now, only used to decide whether to warn.
        self._lbl_pico = _ficha(
            1, 1, tr("Task maximum"),
            tr("Highest sustained level ({w:.1f} s) of the task, as % of the "
               "maximal contraction. Well above 100 % means the calibration "
               "was not a maximum.").format(w=EMG_PROFILE.mvc_peak_window_s),
            rango=tr("a task effort is usually 20–80 %"),
        )
        self._lbl_rms_global = _ficha(
            1, 2, tr("Global RMS"),
            tr("Global RMS amplitude: mean intensity of the activation."),
            rango=tr("rest ≈ 0.01 mV · effort 0.1–1 mV"),
        )
        self._lbl_iemg = _ficha(
            2, 0, "iEMG",
            tr("Integral of the rectified EMG — total muscle activation."),
        )
        self._lbl_duracion = _ficha(
            2, 1, tr("Duration"), tr("Analysed signal duration."),
        )
        # Where the yardstick came from. Shown beside the numbers it scales,
        # because a reference the student cannot trace is the same trap as an
        # auto-normalised one, only quieter.
        self._lbl_cvm = _ficha(
            2, 2, tr("MVC"),
            tr("The maximal contraction every % MVC on this recording is "
               "measured against, and where it came from."),
        )
        # No file card: the name is in the path field at the top of the tab.
        # Kept as a label that sits in no layout, since the code that fills
        # the cards writes to it.
        self._lbl_archivo = QLabel("")
        resumen_grid.setColumnStretch(2, 1)
        # Placed at the bottom, beside the contraction table (see below):
        # above the panels it cost them a strip of height on every screen.
        self._grp_resumen = grp_resumen

        # --- Matplotlib canvas with scroll (the 7 panels are tall) ---
        self._fig = Figure(constrained_layout=True)
        # The wheel scrolls the page of panels; it no longer rescales the
        # panel under the cursor. Scale has its buttons in the sidebar.
        self._canvas = ScrollingCanvas(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._mostrar_estado_vacio()

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

        # --- Co-activation table, directly under the panels ---------------
        # Hidden unless the recording can actually support an index: two
        # muscles, and an MVC reference for each. It is a table and not a
        # single figure because the index is computed per marked phase — one
        # number for a recording that mixes rest, flexion and grip would not
        # be a measurement of anything.
        # The method's name is in the «?» beside it, not in the title: a box
        # headed «Falconer-Winter» names two authors the student has never
        # heard of before it names the thing measured.
        self._box_coact = QGroupBox(tr("Co-activation"))
        coact_v = QVBoxLayout(self._box_coact)
        coact_v.setContentsMargins(6, 4, 6, 6)
        coact_v.setSpacing(4)
        # A «?» in the corner, like every other box. What this table needs
        # explaining is not the index but the windows: that they come from the
        # names in the fragment editor, which is a different tab of the same
        # dialogue and not anywhere near this box. Nobody was going to guess
        # that, and the warning that said «mark the phases» named an action
        # that appears nowhere in the interface under that name.
        add_help(self._box_coact, "ana.coact")
        self._lbl_coact_aviso = QLabel("")
        self._lbl_coact_aviso.setWordWrap(True)
        self._lbl_coact_aviso.setStyleSheet("color:#B0243A; font-size:11px;")
        self._lbl_coact_aviso.setVisible(False)
        coact_v.addWidget(self._lbl_coact_aviso)
        self._tbl_coact = QTableWidget(0, 4)
        self._tbl_coact.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._tbl_coact.verticalHeader().setVisible(False)
        self._tbl_coact.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        # Sized to what it holds, not to a fixed 150 px. The practical
        # produces three rows at most and usually one, and the rest of that
        # height was blank table taking room the raw traces needed: with two
        # muscles there are two of those to fit.
        self._tbl_coact.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self._tbl_coact.verticalHeader().setVisible(False)
        self._ajustar_alto_coact()
        coact_v.addWidget(self._tbl_coact)
        self._box_coact.setVisible(False)
        # Joins the bottom band with the other two boxes (see below).

        # One row per contraction. The student makes six efforts and used to
        # receive one global RMS: the figure showed six bursts and the number
        # described the eighteen seconds around them. This is the table a
        # laboratory report is built from, so it is the one the student can
        # copy — and the one place the electromechanical delay is given.
        self._box_contr = QGroupBox(tr("Contractions"))
        contr_v = QVBoxLayout(self._box_contr)
        contr_v.setContentsMargins(6, 4, 6, 6)
        contr_v.setSpacing(4)
        add_help(self._box_contr, "ana.contr")
        self._lbl_contr_resumen = QLabel("")
        self._lbl_contr_resumen.setStyleSheet("font-size: 11px; color: #6B7580;")
        contr_v.addWidget(self._lbl_contr_resumen)
        self._tbl_contr = QTableWidget(0, 7)
        self._tbl_contr.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._tbl_contr.verticalHeader().setVisible(False)
        self._tbl_contr.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl_contr.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self._tbl_contr.setMinimumHeight(38)
        contr_v.addWidget(self._tbl_contr)
        self._box_contr.setVisible(False)

        # Bottom band: the contractions on the left, the summary cards on
        # the right, sharing the width. The summary used to sit above the
        # panels and the table below them, and between the two the panels
        # got a hundred pixels on a laptop.
        bottom_boxes = QHBoxLayout()
        bottom_boxes.setSpacing(6)
        bottom_boxes.addWidget(self._box_coact, stretch=2)
        bottom_boxes.addWidget(self._box_contr, stretch=3)
        bottom_boxes.addWidget(self._grp_resumen, stretch=2)
        root.addLayout(bottom_boxes)

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
        """Take the recording just made as the file to analyse, and analyse it.

        It used to only fill the path in, on the grounds that a run nobody
        asked for would fight whatever the student was reading. But they are
        still on the acquisition tab when this fires, so nothing is fought —
        and arriving at the analysis tab to find a file loaded and no results,
        with a button that has to be pressed once now and again after each
        editor, is the sequence that was hard to follow.

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
        self._btn_fragmentos.setEnabled(True)
        self._selected_segments = []
        self._segment_labels = []
        self._analysis_filter_kwargs = None
        self._actualizar_etiqueta_fragmentos()
        self._logger.append_log(
            tr("Recording loaded for analysis: {path}").format(path=Path(path).name)
        )
        self._logger.append_log(tr("Running the first analysis…"))
        self._iniciar_analisis()

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
            self._btn_fragmentos.setEnabled(True)
            # A new file invalidates any previous fragment selection and its
            # associated filter cut-offs.
            self._selected_segments = []
            self._segment_labels = []
            self._analysis_filter_kwargs = None
            self._actualizar_etiqueta_fragmentos()
            self._btn_guardar.setEnabled(False)
            self._btn_informe.setEnabled(False)
            self._btn_csv.setEnabled(False)
            self._btn_afinado.setEnabled(False)
            self._progress.setValue(0)
            self._progress.setFormat(tr("Ready"))
            # And analyse it, without being asked. Opening a recording in
            # order not to analyse it is not a thing anyone does, and making
            # the first run a button press gave that button two meanings: the
            # first time it means «show me the recording», and afterwards it
            # means «apply what I have just chosen». Pressing the same control
            # twice for two different reasons is what made the sequence hard
            # to follow — so the first one goes.
            self._logger.append_log(tr("Running the first analysis…"))
            self._iniciar_analisis()

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

        # The identifier and the protocol come from the EDF+ header written
        # at recording time; a file recorded before the header carried one
        # falls back to whatever the acquisition tab has.
        meta = read_edf_metadata(path)
        self._edf_protocol = meta.protocol
        self._student_code = meta.student_code or str(
            self._settings.value("adquisicion/student_code", "") or ""
        )

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
                path, canal, filter_kwargs,
                segments=self._selected_segments or None,
                labels=self._segment_labels or None,
                # The recording phase, so the editor cannot reach into the
                # calibration and offer its maximal efforts as fragments of
                # the task.
                span=self._tramo_de_registro(path),
                # A name is only ever read by the co-activation table, which
                # needs the agonist and the antagonist. Analysing one muscle,
                # the column asked for something nothing would look at.
                naming=self._hay_segundo_canal(),
                # And with the antagonist to hand, the editor can fill the
                # column in itself: which muscle led a contraction is a
                # measurement, not a reading.
                channel_name_2=(
                    self._combo_canal2.currentText().strip()
                    if self._hay_segundo_canal() else None
                ),
                # And each muscle's own maximum, so «who led this one» is
                # decided as a share of it. Two different muscles do not
                # compare in millivolts: on the bench of 3 September the
                # flexor's reference was a third of the extensor's, and
                # every flexion came back named «co-contraction».
                mvc_ref=(self._last_result or {}).get("mvc_ref"),
                mvc_ref_2=(self._last_result or {}).get("mvc_ref_2"),
                parent=self,
            )
        except Exception as exc:  # pragma: no cover — GUI feedback only
            self._logger.append_log(
                tr("Could not open the fragment editor: {error}").format(error=exc)
            )
            return
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._selected_segments = dlg.selected_segments()
            self._segment_labels = dlg.labels()
            # Adopt the cut-offs tuned in the editor for the actual analysis so
            # what was previewed is what gets analysed. Reflect f_env in the tab.
            self._analysis_filter_kwargs = dlg.filter_kwargs()
            self._spin_fenv.setValue(self._analysis_filter_kwargs["f_env"])
            self._actualizar_etiqueta_fragmentos()
            # Re-analyse for the same reason the repetitions dialogue does: the
            # panels on screen were computed over the old selection, so leaving
            # them up beside "12 fragment(s) selected" showed two answers to the
            # same question — a table reading "Whole recording" under a label
            # promising twelve fragments.
            if self._last_result is not None:
                self._iniciar_analisis()

    @Slot()
    def _editar_repeticiones(self) -> None:
        """Offer the calibration efforts to keep or discard, then re-analyse.

        Re-analysing is not optional politeness: the reference is the yardstick
        for every % MVC on screen, so leaving the old panels up beside a new
        selection would show two answers to the same question.
        """
        r = self._last_result or {}
        valores = r.get("cal_rep_values") or {}
        if not valores:
            return
        etiquetas = self._labels_por_canal()
        inverso = {n: i for i, n in etiquetas.items()}
        refs = {}
        for nombre, clave in ((r.get("channel_name"), "mvc_ref"),
                              (r.get("channel_name_2"), "mvc_ref_2")):
            canal = inverso.get(str(nombre or "").strip())
            if canal is not None and r.get(clave):
                refs[canal] = float(r[clave])
        dlg = CalibrationRepsDialog(
            valores, etiquetas, references=refs,
            keep=self._cal_keep or None, parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._cal_keep = dlg.keep()
        self._actualizar_etiqueta_reps()
        self._iniciar_analisis()

    def _actualizar_siguiente_paso(self) -> None:
        """One line saying which of the two editors to open next.

        They light up together at the end of the first analysis, side by side,
        and nothing said that one of them comes first. One does: the
        calibration fixes the reference, and every % MVC the fragments are
        then measured in is measured against it — so choosing the fragments
        first means choosing them against a reference that is about to change,
        and the numbers move under you when you go back for the calibration.
        """
        r = self._last_result or {}
        if not r:
            self._lbl_siguiente.setVisible(False)
            return
        hay_reps = bool(r.get("cal_rep_values"))
        reps_hechas = bool(self._cal_keep)
        frags_hechos = bool(self._selected_segments)

        if hay_reps and not reps_hechas:
            paso, boton = "reps", self._btn_reps
            texto = tr(
                "Next: «{button}». It decides which maximal efforts set the "
                "reference, and every % MVC below is measured against it — so "
                "it goes before choosing the fragments."
            ).format(button=tr("Calibration repetitions…"))
        elif not frags_hechos:
            paso, boton = "frags", self._btn_fragmentos
            texto = tr(
                "Next: «{button}», to drop any contraction that did not come "
                "out well. Press «Use these fragments» even if you change "
                "nothing: that is what applies them."
            ).format(button=tr("Select fragments…"))
        else:
            paso, boton, texto = "", None, ""
        self._lbl_siguiente.setText(texto)
        self._lbl_siguiente.setVisible(bool(texto))

        # And the same thing again, floating over the control it names. A line
        # of small print under two buttons is read by whoever was already
        # looking there; the floating panel dims everything else and rings the
        # button, which is what «to see it better» asks for. Only on a *change*
        # of step, or it would come back after every re-analysis.
        if paso and paso != self._paso_mostrado:
            self._paso_mostrado = paso
            self.coach_step.emit(tr("Next step"), texto, boton)
        elif not paso:
            self._paso_mostrado = ""

    @Slot()
    @Slot()
    def _marcar_pendiente(self) -> None:
        """A setting changed: there is now something to re-run."""
        if self._edit_path.text().strip():
            self._pendiente = True
            self._actualizar_boton_analizar()

    def _actualizar_boton_analizar(self) -> None:
        corriendo = self._worker is not None and self._worker.isRunning()
        self._btn_analizar.setEnabled(
            bool(self._edit_path.text().strip())
            and self._pendiente
            and not corriendo
        )

    def _hay_segundo_canal(self) -> bool:
        """Whether this analysis has an antagonist, and so a co-activation
        table for a fragment's name to feed."""
        if not self._chk_compare2.isChecked():
            return False
        c2 = self._combo_canal2.currentText().strip()
        return bool(c2) and c2 != self._combo_canal.currentText().strip()

    def _tramo_de_registro(self, path: str) -> tuple[float, float] | None:
        """The session's recording phase, or ``None`` for a file without one.

        Read from the annotations alone — no samples — so it costs nothing to
        ask before opening a dialogue.
        """
        try:
            fases = parse_phase_markers(read_edf_markers(path))
            return fases.rec_span(edf_duration(path))
        except Exception:
            return None

    def _labels_por_canal(self) -> dict[int, str]:
        """Channel index to the name the recording gave it."""
        try:
            nombres = list_edf_emg_channels(self._edit_path.text().strip())
        except Exception:
            nombres = []
        return dict(enumerate(nombres))

    def _actualizar_ayuda_reps(self) -> None:
        """Explain the button's state, including — above all — when it is off.

        It sits next to «Select fragments…», which lights as soon as a file is
        chosen, and the asymmetry reads as a fault: the repetitions come from
        the *analysis* of the file, not from the file, because what the dialog
        offers is what each effort was worth and that is measured, not stored.
        A disabled control that does not say why is a question the operator
        has to answer by guessing.
        """
        if self._btn_reps.isEnabled():
            self._btn_reps.setToolTip(tr(
                "Keep or discard the maximal efforts the reference is "
                "computed from. Discarding one moves the reference and every "
                "% MVC with it — which is what makes a weak repetition worth "
                "spotting."
            ))
        elif self._last_result is None:
            self._btn_reps.setToolTip(tr(
                "Analyse the recording first: what each maximal effort was "
                "worth is measured from the signal, not stored in the file."
            ))
        else:
            self._btn_reps.setToolTip(tr(
                "This recording carries no calibration. Only sessions "
                "recorded with the guided flow mark their maximal efforts."
            ))

    def _diagnostico_repeticiones(self, r: dict) -> None:
        """Say out loud what the file brought, every time it is analysed.

        A control that is simply grey says nothing about why. This is the same
        lesson the acquisition wizard taught: deducing the cause of a disabled
        button from the outside costs bench sessions, and one line in the log
        settles it. It is also useful in its own right — "this recording
        carries no calibration" is a fact the operator wants at the moment of
        opening the file, not after hunting for a missing panel.
        """
        valores = r.get("cal_rep_values") or {}
        etiquetas = self._labels_por_canal()
        if not valores:
            self._logger.append_log(tr(
                "This recording carries no calibration spans, so the "
                "repetition list stays off. Only sessions recorded with the "
                "guided flow have them."
            ))
            return
        detalle = ", ".join(
            (tr("{name}: 1 repetition") if len(v) == 1
             else tr("{name}: {n} repetitions")).format(
                name=etiquetas.get(c, str(c + 1)), n=len(v))
            for c, v in sorted(valores.items())
        )
        self._logger.append_log(tr(
            "Calibration in the file — {detail}. The repetition list is "
            "available."
        ).format(detail=detalle))

    def _actualizar_etiqueta_reps(self) -> None:
        """Say when the reference is no longer the whole calibration."""
        valores = (self._last_result or {}).get("cal_rep_values") or {}
        descartadas = sum(
            len(v) - len(self._cal_keep.get(c, {x.rep for x in v}))
            for c, v in valores.items()
        )
        if not descartadas:
            texto = ""
        elif descartadas == 1:
            texto = tr("1 repetition discarded")
        else:
            texto = tr("{n} repetitions discarded").format(n=descartadas)
        self._lbl_reps.setText(texto)

    def _actualizar_etiqueta_fragmentos(self) -> None:
        n = len(self._selected_segments)
        if n == 0:
            self._lbl_fragmentos.setText("")
        else:
            # The least that says it: how many. The seconds and the count of
            # named ones were detail nobody read on a row this full.
            self._lbl_fragmentos.setText(
                tr("1 fragment selected") if n == 1
                else tr("{n} fragments selected").format(n=n)
            )
            # A fragment selection overrides the single-region control.
            self._chk_roi.setChecked(False)

    @Slot()
    def _iniciar_analisis(self) -> None:
        # Never start a second run over a first. Further down, `self._worker`
        # is reassigned; if the previous QThread were still running, dropping
        # the last reference to it destroys a live thread, and that kills the
        # process from the C++ side — no traceback, no crash log, nothing.
        # The Analyse button is disabled while a run is in flight, so this only
        # matters for the callers that are not the button: the fragment and
        # repetition dialogues, which re-analyse when they are accepted.
        if self._worker is not None and self._worker.isRunning():
            self._logger.append_log(
                tr("An analysis is already running; wait for it to finish.")
            )
            return
        path = self._edit_path.text().strip()
        canal = self._combo_canal.currentText().strip() or "EMG"
        # Optional second channel for the agonist/antagonist overlay. Same
        # question the fragment editor asks to decide whether naming is worth
        # offering, so both ask it in one place.
        canal2 = (
            self._combo_canal2.currentText().strip()
            if self._hay_segundo_canal() else None
        )
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
        self._btn_afinado.setEnabled(False)
        self._lbl_mnf.setText("—")
        self._lbl_mdf.setText("—")
        self._lbl_fatiga.setText("—")

        roi_start = roi_end = None
        roi_segments = self._selected_segments or None
        roi_labels = self._segment_labels if roi_segments else None
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
            cal_keep=self._cal_keep or None,
            roi_labels=roi_labels or None,
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
    def _refresh_coactivation(self, result: dict) -> None:
        """Fill the co-activation table, or hide it.

        The two mean activations sit beside every index on purpose: a bare
        86 % reads as "both muscles worked hard" when it may equally mean
        "both were equally quiet", and in this practical the antagonist's mean
        *is* the finding — the index only summarises it.
        """
        tabla = result.get("coactivation")
        if not tabla:
            self._box_coact.setVisible(False)
            return

        n1 = result.get("channel_name") or tr("Muscle {n}").format(n=1)
        n2 = result.get("channel_name_2") or tr("Muscle {n}").format(n=2)
        # Two lines per heading: the muscle on the first, what is measured on
        # the second. On one line «FCR — Mean activation (% MVC)» was elided
        # to something unreadable at any width this box gets.
        # Short on purpose: the box is a fifth of the window and four columns
        # have to fit. What the figure is stands in the «?»; the report,
        # which has the width, keeps the long wording.
        cabecera = tr("mean % MVC")
        self._tbl_coact.setHorizontalHeaderLabels([
            tr("Window"), f"{n1}\n{cabecera}", f"{n2}\n{cabecera}",
            tr("Co-activation\nindex"),
        ])
        self._tbl_coact.setRowCount(len(tabla))
        for fila, res in enumerate(tabla):
            valor = res.reason or f"{res.index:.0f} %"
            # The seconds beside the name, because the window is not always
            # what the marks imply: the last one is closed at the end of the
            # effort rather than at the end of the recording, and a table that
            # showed only "Grip" would hide that it was measured over eleven
            # seconds and not twenty-six.
            ini, fin = res.window_s
            ventana = res.label
            if fin > ini:
                ventana = f"{res.label}  ({ini:.1f}–{fin:.1f} s)".strip()
            celdas = [
                ventana, f"{res.mean_1:.0f}", f"{res.mean_2:.0f}", valor,
            ]
            for col, texto in enumerate(celdas):
                item = QTableWidgetItem(texto)
                if col:
                    # Figures under a centred heading, as in the contraction
                    # table; the window's name stays left, it is prose.
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3 and res.index is None:
                    item.setForeground(QColor("#8A6500"))
                elif col == 3:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self._tbl_coact.setItem(fila, col, item)

        sin_marcas = not result.get("coactivation_from_markers", True)
        # Without windows the table holds one row, over the whole recording,
        # and its number is not a measurement of anything — the module says so
        # itself. Since the first analysis now runs on its own when the file is
        # opened, that row was the *first* thing the student saw of this panel:
        # a co-activation index, bold, computed over rest and flexion and
        # extension together.
        self._tbl_coact.setVisible(not sin_marcas)

        # And the red line under it went the same way, for the same reason.
        # It is a warning — «this number does not measure anything» — about a
        # number the student has not asked for yet and can no longer see, at
        # the one moment they have done nothing wrong: the file has just been
        # opened. What to do next is already said twice over, in the line
        # under the two editors and in the panel that floats over the button.
        #
        # It still has a case to answer, and only one: fragments were chosen
        # and every name was cleared. That is a deliberate act with a
        # consequence worth stating, so the warning survives for it — and with
        # it the whole panel, which is otherwise empty and simply waits.
        ha_elegido = bool(self._selected_segments)
        avisar = sin_marcas and ha_elegido
        self._lbl_coact_aviso.setText(
            tr(
                "Whole recording: with no named windows this number does not "
                "measure anything. Open «{button}» and accept what it proposes."
            ).format(button=tr("Select fragments…"))
            if avisar else ""
        )
        self._lbl_coact_aviso.setVisible(avisar)
        self._ajustar_alto_coact()
        self._box_coact.setVisible(not sin_marcas or avisar)

    def _refresh_contractions(self, result: dict) -> None:
        """Fill the per-contraction table, or hide it.

        Hidden rather than empty: a heading over a blank table asks a
        question, and on a recording with no clear efforts the answer is
        that there were none — which the log already says.
        """
        filas = result.get("contractions") or []
        if not filas:
            self._box_contr.setVisible(False)
            return
        dos = bool(result.get("channel_name_2"))
        con_emd = any(f.emd_ms is not None for f in filas)
        cabeceras = [
            "#", tr("Start (s)"), tr("Duration (s)"), tr("Muscle"),
            tr("RMS (mV)"), tr("Peak (% MVC)"), tr("MDF (Hz)"),
        ]
        if con_emd:
            cabeceras.append(tr("EMD (ms)"))
        self._tbl_contr.setColumnCount(len(cabeceras))
        self._tbl_contr.setHorizontalHeaderLabels(cabeceras)
        self._tbl_contr.setColumnHidden(3, not dos)
        self._tbl_contr.setRowCount(len(filas))
        for i, f in enumerate(filas):
            celdas = [
                str(f.n), f"{f.start_s:.1f}", f"{f.duration_s:.2f}", f.muscle,
                f"{f.rms_mv:.3f}",
                "—" if f.peak_pct is None else f"{f.peak_pct:.0f}",
                "—" if f.mdf_hz is None else f"{f.mdf_hz:.0f}",
            ]
            if con_emd:
                celdas.append("—" if f.emd_ms is None else f"{f.emd_ms:.0f}")
            for col, texto in enumerate(celdas):
                item = QTableWidgetItem(texto)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 5 and f.peak_pct is not None and f.peak_pct > 100.0:
                    item.setForeground(QColor("#B0243A"))
                self._tbl_contr.setItem(i, col, item)
        # As tall as its rows, up to a ceiling: a series of twenty efforts
        # scrolls instead of pushing the panels off the window.
        alto = self._tbl_contr.horizontalHeader().height() + 4
        for i in range(len(filas)):
            alto += self._tbl_contr.rowHeight(i)
        # The rows set a floor and the layout hands it the rest of the box,
        # as the co-activation table does: pinned to a fixed height it sat
        # at the bottom of a taller box with a strip of empty box above it.
        # The ceiling on the floor keeps a long series from pushing the
        # panels off the window; beyond it the table scrolls.
        tope = 160 if self.height() >= 850 else 110
        self._tbl_contr.setMinimumHeight(max(38, min(alto, tope)))
        resumen = tr("{n} contractions").format(n=len(filas))
        emd = result.get("emd_ms_mean")
        if emd is not None:
            resumen += "  ·  " + tr("mean electromechanical delay {ms:.0f} ms").format(ms=emd)
        self._lbl_contr_resumen.setText(resumen)
        self._box_contr.setVisible(True)

    def _ajustar_alto_coact(self) -> None:
        """Room for the rows it has, and free to fill the rest of its box.

        It used to be pinned to a fixed height, so it stopped short of the
        bottom of its own box while the two boxes beside it in the band were
        taller: a strip of empty box under the last row. Now the rows set a
        floor and the layout hands it whatever height the band has.
        """
        filas = self._tbl_coact.rowCount()
        cabecera = max(
            self._tbl_coact.horizontalHeader().height(),
            self._tbl_coact.horizontalHeader().sizeHint().height(),
        )
        alto = cabecera + 4
        for i in range(filas):
            alto += self._tbl_coact.rowHeight(i)
        # A floor so an empty table is not a sliver, and a ceiling so a
        # recording marked into many phases scrolls instead of pushing the
        # panels off the window.
        tope = 160 if self.height() >= 850 else 110
        self._tbl_coact.setMinimumHeight(max(38, min(alto, tope)))

    def _on_result(self, result: dict) -> None:
        self._last_result = result
        self._pendiente = False
        self._refresh_coactivation(result)
        self._refresh_contractions(result)
        self._actualizar_siguiente_paso()
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)
        self._btn_guardar.setEnabled(True)
        self._btn_informe.setEnabled(True)
        self._btn_csv.setEnabled(True)
        self._btn_afinado.setEnabled(True)
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
            # Same three states as the summary label, in the wire format the
            # phones already speak: -1 fatigue, +1 none, 0 not conclusive.
            "fatigue": {FATIGUE: -1, NO_FATIGUE: 1}.get(
                r.get("fat_verdict", INCONCLUSIVE), 0
            ),
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
        self._lbl_archivo.setText(Path(r["edf_path"]).name)
        self._lbl_mnf.setText(f"{r['mnf']:.1f} Hz")
        self._lbl_mdf.setText(f"{r['mdf']:.1f} Hz")
        pendiente = r.get("mdf_slope", 0.0)
        r2 = r.get("fat_r_squared", 0.0)
        signo = "+" if pendiente >= 0 else ""
        self._lbl_pendiente.setText(f"{signo}{pendiente:.2f} Hz/s  (R²={r2:.2f})")
        self._lbl_rms_global.setText(f"{r.get('rms_global', 0.0):.2f} mV")
        self._lbl_iemg.setText(f"{r.get('iemg', 0.0):.1f} mV·s")
        self._lbl_duracion.setText(f"{r.get('duration', 0.0):.1f} s")
        self._actualizar_pico_tarea(r)
        self._actualizar_procedencia_cvm(r)
        self._btn_reps.setEnabled(bool(r.get("cal_rep_values")))
        self._actualizar_etiqueta_reps()
        self._actualizar_ayuda_reps()
        self._diagnostico_repeticiones(r)

        decline = r.get("fat_pct_decline", 0.0)
        veredicto = r.get("fat_verdict", INCONCLUSIVE)
        if veredicto == FATIGUE:
            texto = tr("Detected (MDF −{decline:.1f} %)").format(decline=decline)
            color = "#B0243A"
        elif veredicto == NO_FATIGUE:
            texto = tr("Not detected (MDF stable or rising)")
            color = "#1E7A3C"
        else:
            # Not the same as "no fatigue", and it must not be read as one: the
            # recording does not answer the question. It says the fit, because
            # a bare "undetermined" gives the operator nothing to act on.
            texto = tr("Not conclusive (trend does not fit, R²={r2:.2f})").format(r2=r2)
            color = "#8A5A00"
        self._lbl_fatiga.setText(texto)
        self._lbl_fatiga.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {color};"
        )

    def _actualizar_pico_tarea(self, r: dict) -> None:
        """What the task reached against the reference, on its own card.

        The worker has always computed this to decide whether to warn, and
        the warning only fired past 150 %. A task at 135 % of "maximum" got
        no word at all, and the student read the panel as if the maximum
        had been one. Now the number is shown every time, red when it says
        the calibration was not maximal.
        """
        picos = r.get("task_peak_pct") or {}
        partes = []
        for nombre in (r.get("channel_name"), r.get("channel_name_2")):
            if nombre and nombre in picos:
                partes.append(f"{picos[nombre]:.0f} %")
        if not partes:
            self._lbl_pico.setText("—")
            self._lbl_pico.setStyleSheet("font-size: 13px; font-weight: 600;")
            return
        texto = " / ".join(partes) + " " + tr("MVC")
        if r.get("mvc_implausible"):
            self._lbl_pico.setText(texto + " — " + tr("not a maximum"))
            self._lbl_pico.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #B0243A;"
            )
            self._lbl_pico.setToolTip(tr(
                "The task went well past the reference: the calibration did "
                "not capture a maximum, so every % MVC here is too high in the "
                "same proportion. Calibrate again, against something that "
                "cannot move."
            ))
        else:
            self._lbl_pico.setText(texto)
            self._lbl_pico.setStyleSheet("font-size: 13px; font-weight: 600;")

    def _actualizar_procedencia_cvm(self, r: dict) -> None:
        """The reference and where it came from, in the summary bar.

        Amber rather than red when there is none: a recording with no
        calibration is not a fault, it is a recording that cannot answer the
        questions that need one — and saying which is the point.
        """
        ref = r.get("mvc_ref")
        fuente = r.get("mvc_ref_source", NO_CALIBRATION)
        n_reps = len(r.get("cal_reps", {}).get(0, ()) or ())
        if ref:
            self._lbl_cvm.setText(
                f"{ref:.3f} mV — {reference_source_text(fuente, n_reps)}"
            )
            self._lbl_cvm.setStyleSheet("font-size: 13px; font-weight: 600;")
            return
        self._lbl_cvm.setText(reference_source_text(NO_CALIBRATION))
        self._lbl_cvm.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #8A5A00;"
        )

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
            # The one panel that puts two *different* muscles on a single axis.
            # Their millivolts are not comparable — surface amplitude depends
            # on the skin and fat between muscle and electrode, so a biceps can
            # sit above a triceps by anatomy rather than by activation — so the
            # two are drawn in % MVC whenever the recording carries a reference
            # for both. That is the case worth reaching, and the one the MVC
            # calibration exists to make possible.
            env1, env2 = overlay_curves(r)
            lbl1 = r.get("channel_name") or tr("Muscle {n}").format(n=1)
            ax.plot(times, env1.data, color="#4169E1", lw=1.8, label=lbl1)
            if env2 is not None:
                lbl2 = r.get("channel_name_2") or tr("Muscle {n}").format(n=2)
                ax.plot(times, env2.data, color="#D62728", lw=1.8, label=lbl2)
            else:
                ax.text(
                    0.5, 0.5,
                    tr("Enable “Compare 2nd channel” to overlay the antagonist."),
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=8, color="#888888",
                )
            # Extra pad so the fallback warning fits between title and axes.
            ax.set_title(env1.title, fontsize=9,
                         pad=16 if env1.warning else 6)
            ax.set_ylabel(env1.ylabel, fontsize=8)
            if env1.warning:
                # In the figure, not in a tooltip: the figure travels on its
                # own inside the PDF the student hands in.
                ax.text(0.5, 1.005, env1.warning, transform=ax.transAxes,
                        ha="center", va="bottom", fontsize=7,
                        color="#B0243A")
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.set_xlim(inicio_s, fin_s)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, **_grid)
            mark_excess_over_100(ax, env1.ylabel)
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
                draw_emd_note(ax, r)
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
            dos = r.get("psd_2") is not None
            if dos:
                # Both muscles, in the colours of the overlay panel, each
                # with its own median frequency; the raw spectrum and the
                # single-muscle markers would only clutter the comparison.
                n1 = r.get("channel_name") or tr("Muscle {n}").format(n=1)
                n2 = r.get("channel_name_2") or tr("Muscle {n}").format(n=2)
                ax.plot(r["frequencies"], r["psd"], color="#4169E1", lw=1.8,
                        label=f"{n1}  (MDF {r['mdf']:.0f} Hz)")
                ax.plot(r["frequencies_2"], r["psd_2"], color="#D62728", lw=1.8,
                        label=f"{n2}  (MDF {r['mdf_2']:.0f} Hz)")
                ax.axvline(r["mdf"], color="#4169E1", ls="--", lw=1.4, alpha=0.8)
                ax.axvline(r["mdf_2"], color="#D62728", ls="--", lw=1.4, alpha=0.8)
            else:
                draw_spectrum_before_filter(ax, r)
                ax.plot(r["frequencies"], r["psd"], color="#0047AB", lw=1.8,
                        label=tr("After the filter"))
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
            dos = r.get("mdf_seg_2") is not None
            n1 = r.get("channel_name") or tr("Muscle {n}").format(n=1)
            ax.scatter(r["t_seg"], r["mdf_seg"],
                       s=20, alpha=0.7, color="#4169E1" if dos else "#666666",
                       label=(tr("{muscle}: MDF per window").format(muscle=n1)
                              if dos else tr("Median frequency per window")))
            if len(r["t_seg"]) >= 2:
                ax.plot(r["t_seg"], r["fat_fitted"],
                        color="#4169E1" if dos else "#E74C3C", lw=2.5,
                        label=(tr("{muscle}: trend").format(muscle=n1)
                               if dos else tr("Trend (degree-2 polynomial)")))
            if dos:
                # Both muscles on one axis, in the colours of the overlay
                # panel: the question here is whether one tires and the
                # other does not.
                n2 = r.get("channel_name_2") or tr("Muscle {n}").format(n=2)
                ax.scatter(r["t_seg_2"], r["mdf_seg_2"], s=20, alpha=0.7,
                           color="#D62728",
                           label=tr("{muscle}: MDF per window").format(muscle=n2))
                if len(r["t_seg_2"]) >= 2:
                    ax.plot(r["t_seg_2"], r["fat_fitted_2"], color="#D62728",
                            lw=2.5, label=tr("{muscle}: trend").format(muscle=n2))
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
    def _guardar_afinado(self) -> None:
        """Write the recording out with this analysis's decisions inside it.

        The name is proposed rather than asked for, and it never lands on the
        original: tuning throws signal away, so its input has to stay
        recoverable. The dialogue is still shown, because where a file goes is
        the operator's decision — but the default answer is the safe one.
        """
        origen = self._edit_path.text().strip()
        r = self._last_result or {}
        if not origen or not r:
            return
        propuesta = tuned_path(origen)
        destino, _ = QFileDialog.getSaveFileName(
            self, tr("Save tuned recording"), str(propuesta),
            tr("EDF files (*.edf *.EDF)"),
        )
        if not destino:
            return
        if Path(destino).resolve() == Path(origen).resolve():
            self._err(tr(
                "The tuned recording cannot replace the one it comes from: "
                "tuning discards signal, so its source has to stay."
            ))
            return
        etiquetas = self._labels_por_canal()
        inverso = {n: i for i, n in etiquetas.items()}
        refs = {}
        for nombre, clave in ((r.get("channel_name"), "mvc_ref"),
                              (r.get("channel_name_2"), "mvc_ref_2")):
            canal = inverso.get(str(nombre or "").strip())
            if canal is not None and r.get(clave):
                refs[canal] = float(r[clave])
        try:
            resumen = build_tuned_edf(
                origen, destino,
                keep=self._cal_keep or None,
                fragments=self._selected_segments or None,
                fragment_labels=self._segment_labels or None,
                references=refs or None,
                when=datetime.now(),
            )
        except Exception as exc:
            self._err(tr("Could not write the tuned recording: {err}")
                      .format(err=exc))
            return
        self._logger.append_log(tr(
            "Tuned recording saved: {name} — {kept}/{total} calibration "
            "repetition(s), {secs:.1f} s of {full:.1f} s of the task. The "
            "original is untouched."
        ).format(name=Path(destino).name, kept=resumen.reps_kept,
                 total=resumen.reps_total, secs=resumen.kept_s,
                 full=resumen.full_s))

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
            "student_code": self._student_code.strip(),
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

    def _dibujar_marcadores(self, ax, inicio_s: float, fin_s: float) -> None:
        """Marks on the signal: a line each, and a word only where a word says
        something.

        The automatic onsets came with «Onset (auto)» written up each line,
        rotated — twenty-four of them across an eighteen-second recording,
        over the trace they were meant to point at. They are all the same
        word. A thin line places the onset; what it was is in the legend of
        the phase markers, which do keep their text, since «REC start» or a
        named manoeuvre is information the line alone does not carry.
        """
        for t_mark, lbl_mark in self._markers:
            if not (inicio_s <= t_mark <= fin_s):
                continue
            automatica = "(auto)" in str(lbl_mark)
            ax.axvline(t_mark, color="#E67E22", linestyle="--",
                       linewidth=0.7 if automatica else 1.2,
                       alpha=0.45 if automatica else 0.8)
            if automatica:
                continue
            txt = (lbl_mark[:15] + "…") if len(lbl_mark) > 15 else lbl_mark
            ax.text(t_mark, ax.get_ylim()[1], txt,
                    fontsize=7, rotation=90, va="top", ha="right",
                    color="#E67E22")

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

            # Time scale beside the amplitude, where the hand already is. The
            # wheel used to do this over whichever panel it was on; now it
            # scrolls the page, and the scale is a button like the rest.
            btn_in = QToolButton()
            btn_in.setText("▶◀")
            btn_in.setFixedSize(32, 18)
            btn_in.setStyleSheet("font-size: 9px;")
            btn_in.setToolTip(tr("Narrow the time window (÷2)"))
            btn_in.clicked.connect(self._on_tiempo_reducir)
            btn_out = QToolButton()
            btn_out.setText("◀▶")
            btn_out.setFixedSize(32, 18)
            btn_out.setStyleSheet("font-size: 9px;")
            btn_out.setToolTip(tr("Widen the time window (×2)"))
            btn_out.clicked.connect(self._on_tiempo_ampliar)

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addSpacing(4)
            slot_vbox.addWidget(btn_in, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_out, alignment=Qt.AlignmentFlag.AlignHCenter)
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
        self._actualizar_boton_analizar()
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

    def _mostrar_estado_vacio(self) -> None:
        """A blank canvas says nothing; this one says what to do.

        Before the first analysis the panel area was a white rectangle two
        thirds of the screen tall, with no word on it. The next action is one
        line, and it goes in the middle of the space it is about.
        """
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.axis("off")
        ax.text(
            0.5, 0.5,
            tr("Open a recording, or record one in Acquisition: it is "
               "analysed on its own."),
            transform=ax.transAxes, ha="center", va="center",
            fontsize=11, color="#7A8590",
        )
        self._canvas.draw_idle()

    def _reset_summary_labels(self) -> None:
        _st = "font-size: 13px; font-weight: 600;"
        for lbl in (self._lbl_mnf, self._lbl_mdf, self._lbl_fatiga,
                    self._lbl_pendiente, self._lbl_rms_global, self._lbl_iemg,
                    self._lbl_duracion, self._lbl_pico, self._lbl_cvm):
            lbl.setText("—")
            lbl.setStyleSheet(_st)
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
        self._student_code = ""
        self._spin_fenv.setValue(5.0)
        self._combo_canal.blockSignals(True)
        self._combo_canal.clear()
        self._combo_canal.addItem("EMG")
        self._combo_canal.blockSignals(False)

        self._btn_analizar.setEnabled(False)
        self._btn_fragmentos.setEnabled(False)
        self._btn_reps.setEnabled(False)
        self._cal_keep = {}
        self._actualizar_ayuda_reps()
        self._selected_segments = []
        self._segment_labels = []
        self._analysis_filter_kwargs = None
        self._actualizar_etiqueta_fragmentos()
        self._btn_guardar.setEnabled(False)
        self._btn_informe.setEnabled(False)
        self._btn_csv.setEnabled(False)
        self._btn_afinado.setEnabled(False)

        self._reset_summary_labels()
        self._box_contr.setVisible(False)
        self._tbl_contr.setRowCount(0)

        self._progress.setVisible(False)
        self._progress.setValue(0)
        self._progress.setFormat(tr("Ready"))

        self._mostrar_estado_vacio()
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
        self._box_tools.setVisible(advanced)
        # Saving a derived EDF is for whoever curates the recordings, not for
        # the student reading one; and its name explains nothing to them.
        self._btn_afinado.setVisible(advanced)
        # Offered in every practical; see where it is built.
        self._box_fragmentos.setVisible(True)

        self._sync_compare_to_mode()
        # Every practical has panels to reveal; see _panel_is_offered.
        self._btn_mas_paneles.setVisible(True)
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
                "Choose \"Single-muscle contraction\" or \"Muscle "
                "kinematics\" at the top of the window, or open a two "
                "channels recording."
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
        # Each practical opens on its own set; «More panels…» reveals the
        # rest in every practical, since a curious student is not confined
        # to the advanced one. Panels that need what the recording does not
        # have (a second muscle, an accelerometer) stay hidden regardless.
        if mode == MODE_KINEMATICS:
            propios = pid in _CORE_PIDS or pid in _ACC_PIDS
        elif mode == MODE_PAIR:
            # Raw trace of each muscle, the two envelopes overlaid, and the
            # spectrum and the fatigue trend of both: whether one tires and
            # the other does not is a question only a pair can answer.
            propios = pid in (0, _RAW2_PID, _OVERLAY_PID, 4, 6)
        else:
            propios = pid in _CORE_PIDS
        if propios:
            return True
        if not self._mas_paneles:
            return False
        if pid in (_RAW2_PID, _OVERLAY_PID):
            return mode != MODE_SINGLE       # both need a second muscle
        if pid in _ACC_PIDS:
            return mode_uses_acc(mode)
        return True

    @Slot(bool)
    def _on_mas_paneles(self, checked: bool) -> None:
        """Reveal or fold the panels outside the practical's own six."""
        self._mas_paneles = bool(checked)
        self._apply_panel_visibility(self._mode, self._advanced)

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
