"""
MvcTab — tab 3: MVC normalisation (Maximum Voluntary Contraction).

Loads a test EDF and, optionally, an MVC reference EDF. Normalises the EMG
envelope as a % of the reference MVC (95th percentile). If no MVC file is
provided, it uses auto-normalisation over the test signal itself.

Controls:
  - Test EDF file selector (path persisted in QSettings)
  - MVC reference EDF file selector (optional, persisted)
  - EMG channel name
  - Envelope cutoff frequency (editable, default 5.0 Hz)
  - Compute / Save figure button
  - Progress indicator (indeterminate while the worker runs)

Scale controls (same logic as tab_analisis.py):
  - Vertical scale: ▲▼ sidebar per panel (×1.5, 0.01×–100× limits)
  - Time scale: ◀▶ buttons + factor dropdown

Summary panel: reference MVC amplitude, mean activation, source.
Plot: 3 matplotlib panels (filtered signal / envelope / normalised % MVC).
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
from PySide6.QtCore import QEvent, QSettings, Qt, QTimer, Slot
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

from emgteach.gui.widgets.canvas import ScrollingCanvas
from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog
from emgteach.gui.widgets.help_button import add_help
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.gui.widgets.time_range import TimeRangeSelector
from emgteach.i18n import tr
from emgteach.io import (
    assess_edf_channels,
    list_edf_channels,
    list_edf_emg_channels,
    read_edf_markers,
)
from emgteach.modes import DEFAULT_MODE
from emgteach.mvc import (
    AUTO_COLOR,
    NO_LOAD_MSG,
    parse_mvc_ref_markers,
)
from emgteach.phases import (
    NO_CALIBRATION,
    parse_phase_markers,
    reference_source_text,
)
from emgteach.profiles import EMG_PROFILE
from emgteach.reports import build_mvc_report
from emgteach.workers import MvcWorker

# Distinct base colour per Jonsson load level; an out-of-range value is drawn
# with a red ring on top (see _dibujar_apdf / the data panel).
_LEVEL_COLORS = {"static": "#2E86C1", "median": "#E67E22", "peak": "#8E44AD"}
_OUT_COLOR = "#cc0000"

#: The three panels the tab can draw, in order. The identifier is the one the
#: drawing code uses; the name is what the checkbox says.
_PANELES: list[tuple[int, str]] = [
    (0, "1. Filtered and rectified"),
    (1, "2. Envelope and MVC"),
    (2, "3. Normalised (% MVC)"),
]

# Available time-zoom factors (same as tab_analisis)
_ZOOM_FACTORS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

#: Width of the time window the panels open on, in seconds. The panels show a
#: raw trace, which needs a few seconds of width to be legible; the whole
#: recording is always reachable from the minimap.
_DUR_INICIAL_S = 10.0

_BTN_ST = (
    "QToolButton { font-size: 9px; padding: 0px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
# Larger-typeface variant for the time-window controls, same as in the
# acquisition tab (_BTN_ST is reserved for the ▲▼ buttons).
_TBTN_ST = (
    "QToolButton { font-size: 11px; padding: 0px 2px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
_COMBO_ST = (
    "QComboBox { font-size: 11px; padding: 1px 3px; min-width: 60px; max-width: 76px; }"
)


class MvcTab(QWidget):
    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None):
        super().__init__(parent)
        self._logger = logger
        self._settings = settings
        self._worker: MvcWorker | None = None
        self._last_result: dict | None = None
        self._last_edf_dir: str = self._settings.value("cvm/last_edf_dir", ".")
        # Recording mode and fine-control flag, and whether the explanatory
        # entry screen has already been shown in this session (once per
        # student, reset by "New session").
        self._mode: str = DEFAULT_MODE
        self._advanced: bool = False
        self._entry_shown: bool = False
        # Whether the user has accepted normalising against the test recording
        # itself. Per file: a new recording is a new decision.
        #: The phases the open recording carries, read from its
        #: annotations without loading a sample. What the tab needs it
        #: for is to say, before anything is computed, whether there will
        #: be a % MVC at all.
        self._fases_en_fichero = parse_phase_markers([])
        # The references the test file carries in its own annotations, by
        # channel index — written there by the acquisition wizard when the
        # calibration was done with the recording already running.
        self._refs_en_fichero: dict[int, float] = {}
        # Fragments the muscle-load analysis is restricted to; empty = all.
        self._selected_segments: list[tuple[float, float]] = []

        # Local logger, as the acquisition tab has. The shared LoggerWidget is
        # a single widget and Qt can only show it in one layout, which is the
        # Analysis tab's — so everything this tab logged used to be written
        # somewhere invisible. That included the flat-channel and saturated-
        # channel warnings, the most common mistake a student makes.
        self._local_log = LoggerWidget()
        # Five lines rather than the widget's three: the parameters box beside
        # it is three rows tall, and the log used to stop short with blank
        # box underneath. Not unlimited — left to grow, it stretched the
        # whole header to its own preferred height.
        self._local_log.setMaximumHeight(
            int(self._local_log.fontMetrics().lineSpacing() * 5 + 10)
        )

        # ── Vertical-scale state (3 time-series panels: 0=filtered, 1=envelope, 2=norm) ──
        self._y_accum: dict[int, float] = {0: 1.0, 1: 1.0, 2: 1.0}
        self._y_initial_lims: dict[int, tuple[float, float]] = {}
        self._axes_list: list = []   # active matplotlib axes

        # ── Time-scale state ──
        self._duracion_total: float = 60.0   # s; updated when an EDF is loaded
        self._inicio_s: float = 0.0
        self._duracion_s: float = 60.0

        # Debounce for the redraw (400 ms, same as tab_analisis)
        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(400)
        self._redraw_timer.timeout.connect(self._redibujar_con_ventana_actual)

        self._build_ui()

    # ------------------------------------------------------------------
    # Interface construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Entry screen, shown *instead of* the tab the first time it is opened
        # in each session. A dialog that pops up every time becomes a formality
        # nobody reads by the third visit; a panel that replaces the tab once
        # per student gets read.
        self._entry_panel = self._build_entry_panel()
        self._entry_panel.setVisible(False)
        outer.addWidget(self._entry_panel)

        self._box_body = QWidget()
        outer.addWidget(self._box_body)
        root = QVBoxLayout(self._box_body)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Controls panel ──────────────────────────────────────────
        grp_ctrl = QGroupBox(tr("MVC normalisation parameters"))
        add_help(grp_ctrl, "mvc.params")
        ctrl = QVBoxLayout(grp_ctrl)

        row_test = QHBoxLayout()
        row_test.addWidget(QLabel(tr("Test EDF:")))
        self._edit_path = QLineEdit()
        self._edit_path.setPlaceholderText(tr("Select the EDF file to normalise…"))
        self._edit_path.setReadOnly(True)
        row_test.addWidget(self._edit_path)
        self._btn_abrir = QPushButton(tr("Browse…"))
        self._btn_abrir.clicked.connect(self._seleccionar_edf_prueba)
        row_test.addWidget(self._btn_abrir)

        # There is no second file to ask for. The session marks its own
        # calibration, so the maximum is inside the recording being opened;
        # asking for a reference was asking the operator to answer a question
        # the file already answers, and it let the two tabs disagree — the
        # analysis recomputing from the spans while this one used whatever
        # file happened to be in the box.
        ctrl.addLayout(row_test)

        # Same order as the analysis tab: the fragment editor first, then
        # the channel, then the actions and the panel boxes.
        row_params = QHBoxLayout()
        self._combo_canal = QComboBox()
        self._combo_canal.setEditable(False)
        self._combo_canal.addItem("EMG")
        self._combo_canal.setFixedWidth(150)
        self._combo_canal.setToolTip(
            tr(
                "EMG channel to normalise (EMG1/EMG2 for two-channel files; "
                "disabled when there is only one). The whole normalisation uses "
                "this channel — press \"Compute MVC\" after changing it."
            )
        )
        self._combo_canal.currentIndexChanged.connect(self._on_canal_cambiado)

        # Fragment selection. The muscle-load analysis is about the *task*, and
        # a recording that opens with three maximal calibration efforts has an
        # APDF describing those efforts: P90 lands near 100 % because the
        # maximum really is in there, and the Jonsson limits then say the
        # subject is overloaded when what they did was calibrate.
        self._btn_fragmentos = QPushButton(tr("Select fragments…"))
        self._btn_fragmentos.setEnabled(False)
        self._btn_fragmentos.setToolTip(
            tr(
                "Choose which parts of the recording the muscle load is "
                "measured over — leave out the calibration and any pause. The "
                "MVC reference is not affected: it comes from the calibration, "
                "wherever in the file that is."
            )
        )
        self._btn_fragmentos.clicked.connect(self._editar_fragmentos)
        row_params.addWidget(self._btn_fragmentos)
        self._lbl_fragmentos = QLabel("")
        self._lbl_fragmentos.setStyleSheet("font-size: 11px; color: #333333;")
        row_params.addWidget(self._lbl_fragmentos)
        row_params.addSpacing(10)
        row_params.addWidget(QLabel(tr("EMG channel:")))
        row_params.addWidget(self._combo_canal)

        self._box_fenv = QWidget()
        fenv_l = QHBoxLayout(self._box_fenv)
        fenv_l.setContentsMargins(0, 0, 0, 0)
        fenv_l.addWidget(QLabel(tr("Envelope cutoff frequency (Hz):")))
        self._spin_fenv = QDoubleSpinBox()
        self._spin_fenv.setRange(1.0, 20.0)
        self._spin_fenv.setSingleStep(0.5)
        self._spin_fenv.setValue(5.0)
        self._spin_fenv.setFixedWidth(80)
        self._spin_fenv.setToolTip(
            tr("Envelope low-pass cut-off (Hz): lower = smoother envelope.")
        )
        fenv_l.addWidget(self._spin_fenv)
        row_params.addWidget(self._box_fenv)

        row_params.addStretch()
        # The actions on a row of their own. Channel, fragments, envelope
        # cut-off, three buttons and the panel boxes all shared one row, and
        # a row cannot wrap: its minimum width was 1083 px on the simplest
        # practical and 1276 px on the advanced one, which is what set the
        # whole window's minimum — a 1366-pixel laptop could not show it.
        row_acciones = QHBoxLayout()
        self._btn_calcular = QPushButton(tr("Compute MVC"))
        self._btn_calcular.setEnabled(False)
        self._btn_calcular.clicked.connect(self._iniciar_calculo)
        row_acciones.addWidget(self._btn_calcular)

        # A disabled button that does not say why is the worst of both: the
        # tab looks broken rather than incomplete. So it says what is missing,
        # right next to the control that cannot be pressed — but in three or
        # four words. The full sentence used to sit here in a wrapping label
        # that took a stretch of the row and squeezed every button beside it
        # out of shape; it is the tooltip now, one hover away.
        self._lbl_calcular_bloqueado = QLabel()
        self._lbl_calcular_bloqueado.setStyleSheet(
            "color: #8a5000; font-size: 11px; padding: 0 4px;"
        )
        self._lbl_calcular_bloqueado.setVisible(False)
        row_acciones.addWidget(self._lbl_calcular_bloqueado)

        self._btn_guardar = QPushButton(tr("Save figure (PNG)"))
        self._btn_guardar.setEnabled(False)
        self._btn_guardar.clicked.connect(self._guardar_figura)
        row_acciones.addWidget(self._btn_guardar)

        self._btn_informe = QPushButton(tr("Generate PDF report"))
        self._btn_informe.setEnabled(False)
        self._btn_informe.clicked.connect(self._generar_informe)
        row_acciones.addWidget(self._btn_informe)

        # Which of the three panels to draw continues the same row. The tab
        # always drew all three, which is a lot of vertical space for a student
        # who is after one of them — most often the last, the signal in % MVC.
        row_paneles = row_acciones
        row_paneles.addSpacing(16)
        row_paneles.addWidget(QLabel(tr("Panels:")))
        self._chk_paneles: list[QCheckBox] = []
        for pid, nombre in _PANELES:
            chk = QCheckBox(tr(nombre))
            chk.setChecked(True)
            chk.toggled.connect(self._on_panel_toggled)
            row_paneles.addWidget(chk)
            self._chk_paneles.append(chk)
        row_paneles.addStretch()
        ctrl.addLayout(row_params)
        ctrl.addLayout(row_acciones)

        # Event log for this tab. Kept short: what matters is that the
        # flat-channel and saturated-channel warnings are seen before the
        # student reads any numbers off a useless recording.
        grp_log = QGroupBox(tr("Event log"))
        log_layout = QVBoxLayout(grp_log)
        log_layout.setContentsMargins(4, 4, 4, 4)
        log_layout.addWidget(self._local_log)

        # Side by side with the controls rather than under them: stacked, the
        # log cost the panels a strip of height across the whole width, and
        # the controls left that width unused anyway.
        cabecera = QHBoxLayout()
        cabecera.addWidget(grp_ctrl, stretch=3)
        cabecera.addWidget(grp_log, stretch=1)
        root.addLayout(cabecera)

        # ── Progress bar + Cancel ──────────────────────────────────
        progress_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        progress_row.addWidget(self._progress, stretch=1)
        self._btn_cancelar = QPushButton(tr("Cancel"))
        self._btn_cancelar.setVisible(False)
        self._btn_cancelar.clicked.connect(self._cancelar_calculo)
        progress_row.addWidget(self._btn_cancelar)
        root.addLayout(progress_row)

        # ══ Visualisation area (vertical scroll) ════════════════════════
        # Top: the three time-series panels (with the ▲▼ sidebar). Below: the
        # muscle-load APDF on its own square canvas + a structured data panel.
        self._fig = Figure(constrained_layout=True)
        # The wheel scrolls the page of panels; it no longer rescales the
        # panel under the cursor. Scale has its buttons in the sidebar.
        self._canvas = ScrollingCanvas(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._mostrar_estado_vacio()

        self._y_scale_sidebar = QWidget()
        self._y_scale_sidebar.setFixedWidth(38)
        self._y_scale_sidebar_layout = QVBoxLayout(self._y_scale_sidebar)
        self._y_scale_sidebar_layout.setContentsMargins(2, 4, 2, 4)
        self._y_scale_sidebar_layout.setSpacing(0)

        ts_container = QWidget()
        ts_hbox = QHBoxLayout(ts_container)
        ts_hbox.setContentsMargins(0, 0, 0, 0)
        ts_hbox.setSpacing(2)
        ts_hbox.addWidget(self._y_scale_sidebar)
        ts_hbox.addWidget(self._canvas)

        # Muscle-load APDF on its own (roughly square) canvas, ~1/3 of the width.
        self._apdf_fig = Figure(constrained_layout=True)
        self._apdf_canvas = FigureCanvasQTAgg(self._apdf_fig)
        self._apdf_canvas.setFixedSize(360, 120)
        # Wrap in <p> so Qt treats it as rich text and word-wraps it into a
        # compact box on its own (a plain long line would not wrap).
        self._apdf_canvas.setToolTip(
            tr(
                "<p>Amplitude Probability Distribution Function (Jonsson): "
                "the % of time the muscle stays below each load level (% MVC). "
                "The static (P10), median (P50) and peak (P90) levels gauge "
                "overload risk.</p>"
            )
        )

        # Structured data panel (replaces the old summary box).
        self._data_box = self._build_data_panel()

        bottom_block = QWidget()
        bottom_hbox = QHBoxLayout(bottom_block)
        bottom_hbox.setContentsMargins(0, 0, 0, 0)
        bottom_hbox.setSpacing(8)
        bottom_hbox.addWidget(self._apdf_canvas, stretch=0,
                              alignment=Qt.AlignmentFlag.AlignTop)
        bottom_hbox.addWidget(self._data_box, stretch=1,
                              alignment=Qt.AlignmentFlag.AlignTop)

        viz_container = QWidget()
        viz_v = QVBoxLayout(viz_container)
        viz_v.setContentsMargins(0, 0, 0, 0)
        viz_v.setSpacing(6)
        viz_v.addWidget(ts_container)
        viz_v.addWidget(bottom_block)

        scroll = QScrollArea()
        scroll.setWidget(viz_container)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._viz_scroll = scroll
        # Re-size the APDF whenever the scroll viewport's width changes (window
        # resize or scrollbar appearing), so it keeps filling the width left of
        # the data panel.
        scroll.viewport().installEventFilter(self)
        root.addWidget(scroll, stretch=1)

        # ══ Display-window navigator at the bottom (same style as Analysis) ══
        # A minimap bar that fills the width, with the start/duration labels and
        # the scale buttons in a compact two-row cluster on the right. No box
        # title and no reset button (the window updates live).
        self._time_range = TimeRangeSelector()
        self._time_range.setEnabled(False)
        self._time_range.range_changed.connect(self._on_range_changed)
        self._time_range.range_preview.connect(self._on_range_preview)

        self._lbl_inicio_info = QLabel(f"{tr('Start:')} — s")
        self._lbl_duracion_info = QLabel(f"{tr('Duration:')} — s")
        for lbl in (self._lbl_inicio_info, self._lbl_duracion_info):
            lbl.setStyleSheet("font-size: 9px; color: #333333;")

        self._btn_tiempo_ampliar = QToolButton()
        self._btn_tiempo_ampliar.setText("◀▶")
        self._btn_tiempo_ampliar.setToolTip(tr("Widen the window (see more time)"))
        self._btn_tiempo_ampliar.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_ampliar.setFixedSize(32, 20)
        self._btn_tiempo_ampliar.setEnabled(False)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setStyleSheet(_COMBO_ST)
        self._combo_zoom.setFixedSize(58, 20)
        self._combo_zoom.setEnabled(False)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)

        self._btn_tiempo_reducir = QToolButton()
        self._btn_tiempo_reducir.setText("▶◀")
        self._btn_tiempo_reducir.setToolTip(tr("Narrow the window (more detail)"))
        self._btn_tiempo_reducir.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_reducir.setFixedSize(32, 20)
        self._btn_tiempo_reducir.setEnabled(False)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)

        nav_controls = QWidget()
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
        nav_row.addWidget(self._time_range, stretch=1)   # fills the width
        nav_row.addWidget(nav_controls)                  # only as wide as needed
        root.addLayout(nav_row)

    def _build_data_panel(self) -> QGroupBox:
        """Structured panel: the normalisation values and the Jonsson muscle-load
        levels — each (where relevant) with its normal range and a short
        explanation; out-of-range values are shown in red."""
        box = QGroupBox(tr("Normalisation and muscle load"))
        add_help(box, "mvc.load")
        v = QVBoxLayout(box)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)

        def _lbl() -> QLabel:
            la = QLabel("—")
            la.setWordWrap(True)
            la.setTextFormat(Qt.TextFormat.RichText)
            la.setStyleSheet("font-size: 12px;")
            v.addWidget(la)
            return la

        self._d_file = _lbl()
        self._d_cvm_ref = _lbl()
        self._d_source = _lbl()
        self._d_duration = _lbl()
        self._d_mean = _lbl()

        hdr = QLabel(tr("Muscle load (Jonsson APDF)"))
        hdr.setStyleSheet("font-size: 12px; font-weight: bold; color: #1F4E79;")
        v.addWidget(hdr)
        self._d_static = _lbl()
        self._d_median = _lbl()
        self._d_peak = _lbl()
        v.addStretch()
        return box

    @staticmethod
    def _metric_html(label: str, value: float, limit: float,
                     explanation: str, exceeds: bool | None = None) -> str:
        """Rich-text for a metric: value (red if out of range) + its normal
        range and a short explanation."""
        out = (value > limit) if exceeds is None else exceeds
        value_color = _OUT_COLOR if out else "#1a5276"
        return (
            f"<b>{label}</b> "
            f"<span style='color:{value_color}'>{value:.0f} % MVC</span><br>"
            f"<span style='color:#777777; font-size:10px'>"
            f"{tr('Normal range:')} ≤ {limit:.0f} % — {explanation}</span>"
        )

    def eventFilter(self, obj, event) -> bool:
        if (event.type() == QEvent.Type.Resize
                and hasattr(self, "_viz_scroll")
                and obj is self._viz_scroll.viewport()):
            self._update_apdf_layout()
        return super().eventFilter(obj, event)

    def _update_apdf_layout(self) -> None:
        """Size the muscle-load APDF: it fills the width left of the data panel
        (data panel ≤ ~1/3, APDF the rest), and its height is ~1/4 of its width
        (a low, wide chart)."""
        if not hasattr(self, "_apdf_canvas") or not hasattr(self, "_viz_scroll"):
            return
        vp = self._viz_scroll.viewport().width()
        if vp <= 0:
            return
        data_w = max(180, vp // 3)            # data panel: at most ~1/3
        self._data_box.setMaximumWidth(data_w)
        side = max(260, vp - data_w - 16)     # APDF width: fills the rest
        # Chart and data panel share a height so they line up: the larger of the
        # 1/4-of-width default and the data panel's content height (which depends
        # on word-wrapping at the panel's width).
        box_h = self._data_box.heightForWidth(data_w)
        if box_h <= 0:
            box_h = self._data_box.sizeHint().height()
        height = max(120, side // 4, box_h)
        if (abs(side - self._apdf_canvas.width()) > 8
                or abs(height - self._apdf_canvas.height()) > 8):
            self._apdf_canvas.setFixedSize(side, height)
        self._data_box.setMinimumHeight(height)

    # ------------------------------------------------------------------
    # Log helpers — write to the local logger AND the shared one
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self._local_log.append_log(msg)
        self._logger.append_log(msg)

    def _err(self, msg: str) -> None:
        self._local_log.append_error(msg)
        self._logger.append_error(msg)

    # ------------------------------------------------------------------
    # Entry screen and interface level
    # ------------------------------------------------------------------

    def _build_entry_panel(self) -> QWidget:
        """Panel explaining what an MVC is, shown once per session.

        This is the concept the tab takes for granted everywhere else: the
        abbreviation appears in the tab title, in two file pickers, on the
        compute button and on the plot axes, and is never spelled out.
        """
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        title = QLabel(tr("Normalising to maximum voluntary contraction (MVC)"))
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #1F4E79;")
        title.setWordWrap(True)
        lay.addWidget(title)

        for paragraph in (
            tr(
                "A raw EMG amplitude cannot be compared between two people, or "
                "between two sessions of the same person: it depends on the "
                "electrodes, the skin and the fat layer beneath it. "
                "Normalisation solves this by expressing every value as a "
                "percentage of the amplitude that muscle reaches during a "
                "maximal effort."
            ),
            tr(
                "The maximum is recorded inside the session: when the "
                "recording starts, the app asks for a maximal effort of each "
                "muscle and writes it into the same file, before the task. "
                "That is the reference; nothing else has to be chosen here."
            ),
            tr(
                "The reference has to be made against something that cannot "
                "move — the underside of a table, a fixed bar — with the joint "
                "held still. Not a hand, and least of all the subject's own "
                "other hand: a hand yields, and holding oneself splits the "
                "effort between two limbs, which produces less force than "
                "either would alone. This is the force-velocity relationship "
                "at work: whatever the muscle is allowed to shorten against, "
                "it shortens faster and therefore develops less force, so it "
                "recruits fewer motor units. A maximum performed in mid-air "
                "is submaximal by construction, and every percentage that "
                "follows comes out too high in the same proportion."
            ),
            tr(
                "A recording with no calibration inside it cannot be "
                "normalised: without a maximum there is no percentage, and "
                "this tab says so rather than dividing the signal by itself."
            ),
        ):
            lbl = QLabel(paragraph)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 13px;")
            # A measure a reader can follow. Wrapped to the window, each line
            # ran to some 250 characters across a 1400-pixel screen, and the
            # eye lost its place on the way back to the left margin.
            lbl.setMaximumWidth(720)
            lay.addWidget(lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_continue = QPushButton(tr("I understand, continue"))
        btn_continue.setMinimumHeight(32)
        btn_continue.clicked.connect(self._dismiss_entry_screen)
        btn_row.addWidget(btn_continue)
        lay.addLayout(btn_row)
        lay.addStretch()
        return panel

    def showEvent(self, event) -> None:
        """Show the entry screen the first time the tab is opened per session.

        Qt delivers this when the tab becomes the current one; note that a
        Show event never reaches changeEvent(), so this has to live here.
        """
        super().showEvent(event)
        if not self._entry_shown:
            self._show_entry_screen()

    def _show_entry_screen(self) -> None:
        self._entry_shown = True
        self._entry_panel.setVisible(True)
        self._box_body.setVisible(False)

    def _dismiss_entry_screen(self) -> None:
        self._entry_panel.setVisible(False)
        self._box_body.setVisible(True)

    def apply_mode(self, mode: str, advanced: bool) -> None:
        """Normalisation works the same way in every mode, so nothing here
        depends on which practical is selected.

        The mode is kept anyway: with two muscles there are two channels to
        normalise, which the channel picker already handles one at a time.

        The advanced flag reveals the cut-off control and nothing else. It
        used to decide whether auto-normalisation was on offer; there is no
        auto-normalisation to offer.
        """
        self._mode = mode
        self._advanced = advanced
        self._box_fenv.setVisible(advanced)
        self._refresh_compute_enabled()

    def _tiene_calibracion(self) -> bool:
        """Whether the open recording can give this channel a maximum.

        Either it marks the calibration — and then the reference is recomputed
        from those spans — or it carries the cached annotation of a session
        recorded before that flow. Asked per channel, because a file may hold
        the flexor's calibration and not the extensor's.
        """
        canal = self._combo_canal.currentIndex()
        return bool(self._fases_en_fichero.reps_for(canal)
                    or self._refs_en_fichero.get(canal))

    @Slot()
    def _on_canal_cambiado(self) -> None:
        """The calibration travels per channel, so the warning follows it."""
        self._refresh_compute_enabled()

    def _leer_refs_del_fichero(self, path: str) -> None:
        """Read what the recording says about its own calibration.

        Annotations only — :func:`read_edf_markers` loads no samples — so this
        runs on picking the file, long before anything is computed, and the
        tab can say up front whether there will be a % MVC.
        """
        self._refs_en_fichero = {}
        self._fases_en_fichero = parse_phase_markers([])
        try:
            markers = read_edf_markers(path)
        except Exception:
            return
        self._refs_en_fichero = parse_mvc_ref_markers(markers)
        self._fases_en_fichero = parse_phase_markers(markers)
        if self._fases_en_fichero.cal_reps:
            n_reps = len(self._fases_en_fichero.cal_reps)
            self._log((
                tr("This recording marks its own calibration (1 repetition); "
                   "the reference is recomputed from it.")
                if n_reps == 1 else
                tr("This recording marks its own calibration "
                   "({n} repetitions); the reference is recomputed from it.")
            ).format(n=n_reps))
        elif self._refs_en_fichero:
            self._log(tr(
                "This recording carries a calibration recorded with it "
                "({n} channel(s))."
            ).format(n=len(self._refs_en_fichero)))

    @Slot()
    def _editar_fragmentos(self) -> None:
        path = self._edit_path.text().strip()
        if not path:
            return
        try:
            dlg = FragmentSelectionDialog.from_edf(
                path,
                self._combo_canal.currentText().strip() or "EMG",
                {"f_low": EMG_PROFILE.f_low, "f_high": EMG_PROFILE.f_high,
                 "f_notch": EMG_PROFILE.f_notch, "f_env": self._spin_fenv.value()},
                segments=self._selected_segments or None,
                # Same as the analysis tab: the calibration is the most active
                # signal in the file, so an editor allowed to see it proposes
                # its maximal efforts as fragments of the task.
                span=self._tramo_de_registro(path),
                # Naming leads nowhere here: this tab computes one reference
                # per muscle, and only the co-activation table ever reads a
                # fragment's name. The dialogue used to ask for it anyway.
                naming=False,
                parent=self,
            )
        except Exception as exc:
            self._err(tr("Could not open the fragment editor: {error}").format(error=exc))
            return
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._selected_segments = dlg.selected_segments()
            self._spin_fenv.setValue(dlg.filter_kwargs()["f_env"])
            self._actualizar_etiqueta_fragmentos()
            # A reference computed over the old selection is worse than none:
            # every % MVC downstream is measured against it. Recompute.
            if self._last_result is not None:
                self._iniciar_calculo()

    def _tramo_de_registro(self, path: str) -> tuple[float, float] | None:
        """The session's recording phase, from the annotations alone."""
        from emgteach.io import edf_duration

        try:
            return self._fases_en_fichero.rec_span(edf_duration(path))
        except Exception:
            return None

    def _actualizar_etiqueta_fragmentos(self) -> None:
        if not self._selected_segments:
            self._lbl_fragmentos.setText("")
            return
        n = len(self._selected_segments)
        self._lbl_fragmentos.setText(
            tr("1 fragment selected") if n == 1
            else tr("{n} fragments selected").format(n=n)
        )

    def _refresh_compute_enabled(self) -> None:
        """Enable "Compute MVC", and say what this recording will not give.

        A file with no calibration is still worth computing: the signal and
        its envelope do not depend on a reference, and they are two of the
        three panels. What it will not give is the % MVC and the muscle load,
        and that is said here rather than discovered after pressing.
        """
        has_test = bool(self._edit_path.text().strip())
        self._btn_calcular.setEnabled(has_test)
        self._btn_fragmentos.setEnabled(has_test)

        # Short on the row, whole in the tooltip: what is missing has to be
        # readable at a glance, and why it matters has to be readable at all.
        if not has_test:
            motivo = tr("No recording")
            detalle = tr("Select the recording to normalise.")
        elif not self._tiene_calibracion():
            motivo = tr("No calibration")
            detalle = tr(
                "This recording has no maximal effort in it, so there is no "
                "maximum to express the signal as a percentage of: no % MVC "
                "and no muscle-load analysis. The signal and its envelope are "
                "drawn as usual. Record the session again with the guided "
                "flow, which calibrates without stopping the recording."
            )
        else:
            motivo = detalle = ""
        self._lbl_calcular_bloqueado.setText(motivo)
        self._lbl_calcular_bloqueado.setToolTip(detalle)
        self._lbl_calcular_bloqueado.setVisible(bool(motivo))

    # ------------------------------------------------------------------
    # File-selection slots
    # ------------------------------------------------------------------

    def adopt_recording(self, path: str, channel: str = "") -> None:
        """Take this recording as the one to normalise.

        ``channel`` is the muscle already chosen for this file elsewhere. When
        it is given the tab uses it and asks nothing: normalising a different
        muscle from the one being analysed is possible but is never what the
        two-questions-in-a-row flow was offering.

        """
        if not path or (self._worker is not None and self._worker.isRunning()):
            return
        self._edit_path.setText(path)
        self._last_edf_dir = str(Path(path).parent)
        self._populate_channels(path, ask=not channel)
        if channel:
            idx = self._combo_canal.findText(channel)
            if idx >= 0:
                self._combo_canal.setCurrentIndex(idx)
        self._refresh_compute_enabled()
        self._btn_guardar.setEnabled(False)
        self._log(
            tr("Recording loaded to normalise: {path}").format(path=Path(path).name)
        )
        # And compute, as the analysis tab does since it started analysing on
        # open: a tab that receives a recording and waits for a button press
        # to show anything is the same "press once to see, again to apply"
        # that made the sequence hard to follow there.
        if self._btn_calcular.isEnabled():
            self._log(tr("Running the first computation…"))
            self._iniciar_calculo()

    @Slot()
    def _seleccionar_edf_prueba(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select test EDF"),
            self._last_edf_dir, tr("EDF files (*.edf *.EDF)"),
        )
        if path:
            self._edit_path.setText(path)
            self._last_edf_dir = str(Path(path).parent)
            self._settings.setValue("cvm/last_edf_dir", self._last_edf_dir)
            self._populate_channels(path)
            self._refresh_compute_enabled()
            self._btn_guardar.setEnabled(False)

    def _populate_channels(self, path: str, ask: bool = True) -> None:
        """Fill the channel picker with the test file's EMG channels (excludes
        ACC).

        With a single EMG channel the picker is disabled (nothing to choose);
        with two it is enabled so the user selects EMG1 or EMG2. The whole
        normalisation is computed for the selected channel — after changing it,
        press "Compute MVC" to recompute for that channel.
        """
        self._leer_refs_del_fichero(path)
        self._selected_segments = []      # a new recording, a new selection
        self._actualizar_etiqueta_fragmentos()
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
        self._combo_canal.setEnabled(len(labels) >= 2)

        # Normalisation is about one muscle. With two in the file, taking the
        # first without asking would put a reference amplitude, a load
        # distribution and a PDF report against a muscle nobody chose.
        if ask and len(labels) >= 2:
            self._ask_which_channel(labels)

        # Warn if a channel is flat (no signal) or saturated (bad contact).
        for label, status in assess_edf_channels(path):
            if status == "flat":
                self._err(
                    tr("Channel «{ch}»: flat — no signal (electrode not "
                       "connected?).").format(ch=label)
                )
            elif status == "saturated":
                self._err(
                    tr("Channel «{ch}»: saturated — the trace is pinned at the "
                       "rails (check the electrode contact or the gain).").format(
                        ch=label
                    )
                )



    # ------------------------------------------------------------------
    # Launch computation
    # ------------------------------------------------------------------



    @Slot()
    def _iniciar_calculo(self) -> None:
        # See the analysis tab: `self._worker` is reassigned below, and letting
        # go of a QThread that is still running kills the process from the C++
        # side, with no traceback to show for it.
        if self._worker is not None and self._worker.isRunning():
            self._log(tr("A calculation is already running; wait for it to "
                         "finish."))
            return
        path = self._edit_path.text().strip()
        f_env = self._spin_fenv.value()

        # There used to be a modal here, asking whether to normalise against
        # the recording itself. It was the last thing standing between the
        # student and a set of numbers that were wrong in a way no wording
        # could fix; the route is gone, so the question is too.
        self._set_controles_habilitados(False)
        self._progress.setVisible(True)
        self._btn_cancelar.setVisible(True)
        self._btn_cancelar.setEnabled(True)
        self._btn_guardar.setEnabled(False)
        self._btn_informe.setEnabled(False)

        self._worker = MvcWorker(
            edf_path=path,
            f_env=f_env,
            channel_index=self._combo_canal.currentIndex(),
            roi_segments=self._selected_segments or None,
            # The whole recording, not the worker's default first 10 s. The
            # numbers on this tab — mean % MVC, the Jonsson APDF — are computed
            # over the whole file, so a plot that stopped at 10 s described a
            # recording the operator could not see, and the minimap below drew
            # the whole signal against an axis that ended at 10 s: the shape
            # under the selection was never the shape in the panels.
            plot_duration_s=0,
        )
        self._worker.result_ready.connect(self._on_result)
        self._worker.log.connect(self._log)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_calculo_finished)
        self._worker.start()

    @Slot()
    def _cancelar_calculo(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._btn_cancelar.setEnabled(False)
            self._log(tr("Cancelling…"))
            self._worker.stop()

    @Slot()
    def _on_calculo_finished(self) -> None:
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

    @Slot(dict)
    def _on_result(self, result: dict) -> None:
        self._last_result = result
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)
        self._btn_guardar.setEnabled(True)
        self._btn_informe.setEnabled(True)
        self._actualizar_resumen(result)

        # Initialise the time window. The minimap now spans the whole recording,
        # which can be minutes long, and a raw trace opened at that width is a
        # solid block: open on the first 10 s (or the whole file, if shorter)
        # and let the bar below say where that sits in the recording.
        t_total = float(result["t_plot"][-1]) if len(result["t_plot"]) > 0 else 60.0
        self._duracion_total = t_total
        dur_ini = min(t_total, _DUR_INICIAL_S)
        self._inicio_s = 0.0
        self._duracion_s = dur_ini
        self._time_range.set_total_duration(t_total)
        # The envelope, not the raw trace: at the width of the bar a raw EMG
        # is a solid block, while the envelope shows where the efforts are,
        # which is what the window is being aimed at.
        self._time_range.set_overview(result.get("emg_envelope"))
        self._time_range.set_range(self._inicio_s, self._duracion_s)
        self._time_range.setEnabled(True)

        # Enable the time-scale controls
        for w in (self._btn_tiempo_ampliar, self._btn_tiempo_reducir, self._combo_zoom):
            w.setEnabled(True)
        self._sync_combo_zoom()
        self._update_info_labels()

        # Reset the Y scales; draw the time-series panels and the APDF.
        self._y_accum = {0: 1.0, 1: 1.0, 2: 1.0}
        self._dibujar_apdf(result)
        self._dibujar_paneles(result)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._err(msg)
        self._set_controles_habilitados(True)
        self._progress.setVisible(False)

    # ------------------------------------------------------------------
    # Numeric summary
    # ------------------------------------------------------------------

    def _actualizar_resumen(self, r: dict) -> None:
        dim = r.get("dimension", "")
        ref = r.get("mvc_amplitude_ref")
        self._d_file.setText(f"<b>{tr('File:')}</b> {Path(r['edf_path']).name}")
        self._d_cvm_ref.setText(
            f"<b>{tr('MVC reference:')}</b> {ref:.4f} {dim}" if ref
            else f"<span style='color:{AUTO_COLOR}'><b>"
                 f"{tr('MVC reference:')}</b> {tr('none')}</span>"
        )
        # The provenance is worded from a token, never branched on translated
        # text — the same rule the analysis tab follows, and the reason the
        # old ``mvc_is_auto`` flag had to exist beside a translated sentence.
        self._d_source.setText(
            f"<b>{tr('Reference from:')}</b> "
            f"{reference_source_text(r.get('mvc_ref_source', NO_CALIBRATION), int(r.get('cal_reps_n', 0)))}"
        )
        dur = float(r["tiempo"][-1]) if len(r.get("tiempo", [])) else 0.0
        self._d_duration.setText(f"<b>{tr('Duration:')}</b> {dur:.1f} s")

        self._d_mean.setText(
            "" if r.get("mean_norm") is None else self._metric_html(
                tr("Mean activation:"), float(r["mean_norm"]),
                EMG_PROFILE.apda_mean_limit,
                tr("average activation over the task"))
        )

        if r.get("apdf") is None:
            # Better no number than a number with a footnote: the number is
            # what gets copied into the notebook, the footnote is not.
            self._d_static.setText(
                f"<span style='color:#777777; font-size:11px'>"
                f"{tr(NO_LOAD_MSG)}</span>"
            )
            self._d_median.setText("")
            self._d_peak.setText("")
        else:
            apdf = r["apdf"]
            self._d_static.setText(self._metric_html(
                tr("Static (P10):"), apdf.static.value, apdf.static.limit,
                tr("near-continuous background load"), apdf.static.exceeds))
            self._d_median.setText(self._metric_html(
                tr("Median (P50):"), apdf.median.value, apdf.median.limit,
                tr("typical working load"), apdf.median.exceeds))
            self._d_peak.setText(self._metric_html(
                tr("Peak (P90):"), apdf.peak.value, apdf.peak.limit,
                tr("recurrent high-effort load"), apdf.peak.exceeds))

        # The data panel just grew; re-match the chart height to it.
        self._update_apdf_layout()

    # ------------------------------------------------------------------
    # Drawing the 3 panels
    # ------------------------------------------------------------------

    def _ask_which_channel(self, labels: list[str]) -> None:
        """Two muscles recorded, one to normalise: let the student say which.

        The buttons carry the channel labels themselves, so the choice is
        between "Biceps" and "Triceps" rather than between EMG1 and EMG2 —
        which is the whole reason the labels are typed at recording time.
        """
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(tr("Which muscle is being normalised?"))
        msg.setText(
            tr(
                "This recording has two muscles. Normalisation is about one of "
                "them: the reference amplitude, the load distribution and the "
                "report will all be about the channel chosen here."
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
        self._log(tr("Normalising {muscle}.").format(muscle=elegido))

    def _paneles_activos(self) -> list[int]:
        """Identifiers of the ticked panels, in display order.

        Never empty: with nothing ticked the tab would draw a blank canvas and
        look broken, so the first panel stands in.
        """
        activos = [pid for (pid, _), chk in zip(_PANELES, self._chk_paneles)
                   if chk.isChecked()]
        return activos or [_PANELES[0][0]]

    @Slot()
    def _on_panel_toggled(self) -> None:
        """Redraw with the new selection, if there is anything to redraw."""
        if self._last_result is not None:
            self._dibujar_paneles(self._last_result)

    def _dibujar_paneles(self, r: dict) -> None:
        self._fig.clear()

        n = r["n_plot"]
        t_full = r["t_plot"]

        # Time window: selection via xlim (full data, axis adjustment)
        inicio = self._inicio_s
        fin = inicio + self._duracion_s

        ref = r.get("mvc_amplitude_ref")
        activos = self._paneles_activos()
        creados = self._fig.subplots(len(activos), 1, sharex=False, squeeze=False)
        axes = {pid: fila[0] for pid, fila in zip(activos, creados)}
        self._axes_list = [axes[pid] for pid in activos]

        # Panel 1: filtered + rectified signal
        if 0 in axes:
            ax = axes[0]
            ax.plot(t_full, r["emg_filtered"][:n],
                    color="royalblue", lw=0.8, label=tr("Filtered EMG (20-450 Hz)"))
            ax.plot(t_full, r["emg_rectified"][:n],
                    color="tomato", lw=0.8, alpha=0.8, label=tr("Rectified EMG"))
            ax.set_xlim(inicio, fin)
            ax.set_title(tr("1. Filtered and rectified EMG signal"), fontsize=9)
            ax.set_ylabel(
                tr("Amplitude ({units})").format(units=r.get('dimension', '')), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Panel 2: envelope + MVC line
        if 1 in axes:
            ax = axes[1]
            ax.plot(t_full, r["emg_envelope"][:n],
                    color="purple", lw=2.0, label=tr("LP envelope (zero-phase)"))
            if ref:
                ax.axhline(ref, color="red", ls="--", lw=1.5,
                           label=tr("MVC ref: {value:.4f} {units}").format(
                               value=ref, units=r.get("dimension", "")))
            ax.set_xlim(inicio, fin)
            ax.set_title(
                tr("2. Envelope and MVC reference amplitude") if ref
                else tr("2. Envelope (no calibration in this recording)"),
                fontsize=9,
            )
            ax.set_ylabel(
                tr("Amplitude ({units})").format(units=r.get('dimension', '')), fontsize=8)
            ax.set_xlabel(tr("Time (s)"), fontsize=8)
            ax.tick_params(labelsize=7)
            ax.legend(loc="upper right", fontsize=7)
            ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Panel 3: signal normalised % MVC
        if 2 in axes:
            ax = axes[2]
            if r.get("emg_norm") is None:
                # The panel keeps its place rather than vanishing: a tab that
                # silently shows two panels where it showed three teaches
                # nothing, and the student who forgot to calibrate needs to
                # read why, not to wonder what happened.
                ax.text(0.5, 0.5, tr(NO_LOAD_MSG), ha="center", va="center",
                        fontsize=9, color=AUTO_COLOR, wrap=True,
                        transform=ax.transAxes)
                ax.set_xticks([])
                ax.set_yticks([])
                ax.set_title(tr("3. Signal as % MVC — not available"), fontsize=9)
            else:
                ax.fill_between(t_full, r["emg_norm"][:n], alpha=0.25,
                                color="darkorange")
                ax.plot(t_full, r["emg_norm"][:n],
                        color="darkorange", lw=1.8, label=tr("Activation (% MVC)"))
                ax.axhline(100.0, color="red", ls=":", lw=1.2, alpha=0.7,
                           label=tr("100 % MVC"))
                ax.set_xlim(inicio, fin)
                ax.set_title(
                    tr("3. EMG signal normalised to MVC (% MVC)"), fontsize=9)
                ax.set_ylabel(tr("% MVC"), fontsize=8)
                ax.set_xlabel(tr("Time (s)"), fontsize=8)
                ax.set_ylim(0, r["ylim_max"])
                ax.tick_params(labelsize=7)
                ax.legend(loc="upper right", fontsize=7)
                ax.grid(True, color="#DDDDDD", alpha=0.5)

        # Save the initial ylims and reset the accumulators
        self._y_initial_lims = {i: ax.get_ylim() for i, ax in enumerate(self._axes_list)}
        self._y_accum = {i: 1.0 for i in range(len(self._axes_list))}

        self._canvas.setMinimumHeight(len(self._axes_list) * 165)
        self._canvas.updateGeometry()
        self._canvas.draw_idle()

        # Rebuild the ▲▼ sidebar
        self._rebuild_y_sidebar()

    def _redibujar_con_ventana_actual(self) -> None:
        """Redraw applying the current time window without re-analysing."""
        if self._last_result is None:
            return
        self._dibujar_paneles(self._last_result)

    def _dibujar_apdf(self, r: dict) -> None:
        """Draw the muscle-load APDF (whole recording) on its own square canvas.

        It is a distribution, so the time window does not apply; it is drawn
        once per analysis, not on every window change.
        """
        self._apdf_fig.clear()
        ax = self._apdf_fig.add_subplot(111)

        apdf = r.get("apdf")
        if apdf is None:
            # No curve at all, not a grey one. The APDF's x axis is "% MVC";
            # without a maximum there is no axis to draw it against, and a
            # distribution against the recording's own peak is a different
            # quantity wearing this one's chart.
            ax.text(0.5, 0.5, tr(NO_LOAD_MSG), ha="center", va="center",
                    fontsize=8, color=AUTO_COLOR, wrap=True,
                    transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            self._apdf_canvas.draw_idle()
            return

        ax.plot(apdf.load, apdf.cumulative, color="#0047AB", lw=1.8)
        for prob in (10, 50, 90):
            ax.axhline(prob, color="#cccccc", ls=":", lw=0.7)
        for lvl, prob, name in (
            (apdf.static, 10, tr("Static")),
            (apdf.median, 50, tr("Median")),
            (apdf.peak, 90, tr("Peak")),
        ):
            base = _LEVEL_COLORS[lvl.name]
            ax.plot([lvl.value], [prob], "o", ms=9, zorder=5,
                    markerfacecolor=base, markeredgecolor=base, markeredgewidth=0.6,
                    label=f"{name}: {lvl.value:.0f} % (≤{lvl.limit:.0f} %)")
            if lvl.exceeds:
                # Out of range: a larger hollow red ring around the coloured dot
                # (white gap between them) so it stands out.
                ax.plot([lvl.value], [prob], "o", ms=20, zorder=6,
                        markerfacecolor="none", markeredgecolor=_OUT_COLOR,
                        markeredgewidth=2.2)
        ax.set_title(tr("Muscle-load distribution (APDF, Jonsson)"), fontsize=9)
        ax.set_xlabel(tr("Load (% MVC)"), fontsize=8)
        ax.set_ylabel(tr("Cumulative % of time"), fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_xlim(0, float(apdf.load[-1]))
        ax.tick_params(labelsize=7)
        # Legend key for the out-of-range marker (the red ring drawn above).
        ax.plot([], [], "o", linestyle="none", markersize=11,
                markerfacecolor="none", markeredgecolor=_OUT_COLOR,
                markeredgewidth=2.0, label=tr("Out of normal range"))
        ax.legend(loc="lower right", fontsize=7)
        ax.grid(True, color="#DDDDDD", alpha=0.5)
        self._apdf_canvas.draw_idle()

    # ------------------------------------------------------------------
    # Vertical-scale sidebar (▲▼ per panel)
    # ------------------------------------------------------------------

    def _rebuild_y_sidebar(self) -> None:
        # Clear previous widgets
        while self._y_scale_sidebar_layout.count():
            item = self._y_scale_sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        labels_panel = [f"P{i + 1}" for i in range(len(self._axes_list))]
        for panel_idx, ax in enumerate(self._axes_list):
            slot = QWidget()
            slot_vbox = QVBoxLayout(slot)
            slot_vbox.setContentsMargins(0, 0, 0, 0)
            slot_vbox.setSpacing(1)

            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(32, 18)
            btn_up.setStyleSheet(_BTN_ST)
            btn_up.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, True)
            )

            lbl = QLabel(labels_panel[panel_idx])
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 7px; color: #666666;")

            btn_dn = QToolButton()
            btn_dn.setText("▼")
            btn_dn.setFixedSize(32, 18)
            btn_dn.setStyleSheet(_BTN_ST)
            btn_dn.clicked.connect(
                lambda checked=False, a=ax, pi=panel_idx: self._y_zoom(pi, a, False)
            )

            # Time scale beside the amplitude, as in the analysis tab: the
            # wheel scrolls the page now, and the scale is a button.
            btn_in = QToolButton()
            btn_in.setText("▶◀")
            btn_in.setFixedSize(32, 18)
            btn_in.setStyleSheet(_BTN_ST)
            btn_in.setToolTip(tr("Narrow the window (more detail)"))
            btn_in.clicked.connect(self._on_tiempo_reducir)
            btn_out = QToolButton()
            btn_out.setText("◀▶")
            btn_out.setFixedSize(32, 18)
            btn_out.setStyleSheet(_BTN_ST)
            btn_out.setToolTip(tr("Widen the window (see more time)"))
            btn_out.clicked.connect(self._on_tiempo_ampliar)

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl,    alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addSpacing(4)
            slot_vbox.addWidget(btn_in, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_out, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addStretch()

            self._y_scale_sidebar_layout.addWidget(slot, stretch=1)

    def _y_zoom(self, panel_idx: int, ax, zoom_in: bool) -> None:
        """Change the amplitude of panel ``panel_idx`` by ×1.5.

        Anchored on **zero**, not on the middle of the current view. These
        signals sit on a baseline of zero — an envelope and a % MVC cannot be
        negative — so scaling about the midpoint lifts the floor off zero and
        the trace appears to *move up* rather than grow, which is exactly what
        it did. The analysis tab always scaled about zero; this one did not.
        """
        factor = 1.5
        accum = self._y_accum.get(panel_idx, 1.0)
        escala = 1.0 / factor if zoom_in else factor
        nuevo = accum * escala
        if not 0.01 <= nuevo <= 100.0:
            return
        ymin, ymax = ax.get_ylim()
        if ymin <= 0.0 <= ymax:
            ax.set_ylim(ymin * escala, ymax * escala)
        else:
            # A window that does not straddle zero has no baseline to hold, so
            # its own centre is the only sensible anchor.
            centro = (ymin + ymax) / 2.0
            media = (ymax - ymin) / 2.0 * escala
            ax.set_ylim(centro - media, centro + media)
        self._y_accum[panel_idx] = nuevo
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Time-scale controls
    # ------------------------------------------------------------------

    @Slot(float, float)
    def _on_range_changed(self, inicio: float, duracion: float) -> None:
        self._inicio_s = inicio
        self._duracion_s = duracion
        self._sync_combo_zoom()
        self._update_info_labels()
        self._redraw_timer.start()

    @Slot(float, float)
    def _on_range_preview(self, inicio: float, duracion: float) -> None:
        self._inicio_s = inicio
        self._duracion_s = duracion
        self._update_info_labels()

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        """◀▶ — double the visible duration."""
        nueva_dur = min(self._duracion_s * 2.0, self._duracion_total)
        nueva_dur = max(nueva_dur, 0.5)
        nuevo_inicio = min(self._inicio_s, self._duracion_total - nueva_dur)
        self._inicio_s = nuevo_inicio
        self._duracion_s = nueva_dur
        self._time_range.set_range(self._inicio_s, self._duracion_s)
        self._sync_combo_zoom()
        self._update_info_labels()
        self._redraw_timer.start()

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        """▶◀ — halve the visible duration."""
        nueva_dur = max(self._duracion_s / 2.0, 0.5)
        nuevo_inicio = min(self._inicio_s, self._duracion_total - nueva_dur)
        self._inicio_s = nuevo_inicio
        self._duracion_s = nueva_dur
        self._time_range.set_range(self._inicio_s, self._duracion_s)
        self._sync_combo_zoom()
        self._update_info_labels()
        self._redraw_timer.start()

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva_dur = self._duracion_total / factor
        nueva_dur = max(nueva_dur, 0.5)
        nuevo_inicio = min(self._inicio_s, self._duracion_total - nueva_dur)
        self._inicio_s = nuevo_inicio
        self._duracion_s = nueva_dur
        self._time_range.set_range(self._inicio_s, self._duracion_s)
        self._update_info_labels()
        self._redraw_timer.start()

    def _sync_combo_zoom(self) -> None:
        if self._duracion_total <= 0:
            return
        factor_actual = self._duracion_total / self._duracion_s
        best_idx, best_diff = 0, float("inf")
        for i, f in enumerate(_ZOOM_FACTORS):
            d = abs(factor_actual - f)
            if d < best_diff:
                best_diff, best_idx = d, i
        self._combo_zoom.blockSignals(True)
        self._combo_zoom.setCurrentIndex(best_idx)
        self._combo_zoom.blockSignals(False)

        model = self._combo_zoom.model()
        for i, f in enumerate(_ZOOM_FACTORS):
            item = model.item(i)
            if item:
                item.setEnabled((self._duracion_total / f) >= 0.5)

    def _update_info_labels(self) -> None:
        self._lbl_inicio_info.setText(f"{tr('Start:')} {self._inicio_s:.1f} s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')} {self._duracion_s:.1f} s")

    # ------------------------------------------------------------------
    # Save figure
    # ------------------------------------------------------------------

    @Slot()
    def _guardar_figura(self) -> None:
        if self._last_result is None:
            return
        carpeta = str(Path(self._last_result["edf_path"]).parent)
        nombre = Path(self._last_result["edf_path"]).stem + "_cvm_norm.png"
        ruta_default = str(Path(carpeta) / nombre)
        ruta, _ = QFileDialog.getSaveFileName(
            self, tr("Save figure"), ruta_default, tr("PNG images (*.png)"),
        )
        if ruta:
            self._fig.savefig(ruta, dpi=150, bbox_inches="tight")
            self._log(tr("Figure saved to: {path}").format(path=ruta))

    def _pedir_rango_informe(self) -> tuple[float, float] | None:
        """Small dialog to pick the time range plotted in the report,
        pre-filled with the currently visible window."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Report time range"))
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(QLabel(tr("Time range to plot (s):")))
        total = max(self._duracion_total, self._inicio_s + self._duracion_s)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Start:")))
        spin_ini = QDoubleSpinBox()
        spin_ini.setRange(0.0, max(0.0, total))
        spin_ini.setDecimals(1)
        spin_ini.setSingleStep(0.5)
        spin_ini.setValue(float(self._inicio_s))
        row.addWidget(spin_ini)
        row.addWidget(QLabel(tr("Duration:")))
        spin_dur = QDoubleSpinBox()
        spin_dur.setRange(0.5, max(0.5, total))
        spin_dur.setDecimals(1)
        spin_dur.setSingleStep(0.5)
        spin_dur.setValue(float(self._duracion_s))
        row.addWidget(spin_dur)
        row.addStretch()
        lay.addLayout(row)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        x0 = float(spin_ini.value())
        x1 = min(x0 + float(spin_dur.value()), float(total))
        return (x0, x1)

    @Slot()
    def _generar_informe(self) -> None:
        """Generate the MVC / muscle-load PDF report next to the source EDF."""
        if self._last_result is None:
            return
        rango = self._pedir_rango_informe()
        if rango is None:
            return  # cancelled by the user
        edf_path = Path(str(self._last_result.get("edf_path", "")) or "sesion.edf")
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Ask where and under what name to save the PDF (same UX as "Save
        # figure"), pre-filled next to the EDF with a timestamped name.
        ruta_default = str(edf_path.with_name(f"{edf_path.stem}_informe_cvm_{ts}.pdf"))
        ruta, _ = QFileDialog.getSaveFileName(
            self, tr("Save PDF report"), ruta_default,
            tr("PDF documents (*.pdf)"),
        )
        if not ruta:
            return  # cancelled by the user
        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"
        out = Path(ruta)
        # The identifier travels in the EDF header since recording time;
        # a file from before that carries none, and the acquisition tab's
        # current one is the best guess left.
        from emgteach.io import read_edf_metadata

        try:
            codigo = read_edf_metadata(self._edit_path.text().strip()).student_code
        except Exception:
            codigo = ""
        meta = {
            "student": "",
            "student_code": codigo or str(
                self._settings.value("adquisicion/student_code", "") or ""
            ),
        }
        try:
            build_mvc_report(out, self._last_result, meta, time_range=rango)
            self._log(tr("PDF report generated: {path}").format(path=out))
        except Exception as exc:
            self._err(
                tr("Error generating the PDF report: {error}").format(error=exc)
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_controles_habilitados(self, habilitado: bool) -> None:
        self._btn_abrir.setEnabled(habilitado)
        if habilitado:
            self._refresh_compute_enabled()
        else:
            self._btn_calcular.setEnabled(False)
        self._combo_canal.setEnabled(habilitado)
        self._spin_fenv.setEnabled(habilitado)

    # ------------------------------------------------------------------
    # New-session reset
    # ------------------------------------------------------------------

    def _mostrar_estado_vacio(self) -> None:
        """One line in the middle of the empty panel, saying what comes next.

        Same idea as the analysis tab: a white rectangle with nothing on it
        is a question, and the answer costs one sentence.
        """
        ax = self._fig.add_subplot(111)
        ax.axis("off")
        ax.text(
            0.5, 0.5,
            tr("Open a recording with calibration, or record one in "
               "Acquisition: the reference is computed on its own."),
            transform=ax.transAxes, ha="center", va="center",
            fontsize=11, color="#7A8590",
        )

    def reset(self) -> None:
        """Clear the tab to its just-opened state (new student): loaded files,
        result, plots and data panel."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        self._worker = None
        self._last_result = None
        self._duracion_total = 60.0
        self._inicio_s = 0.0
        self._duracion_s = 60.0

        self._local_log.clear()

        # Once per run of the application, and «New session» does not bring
        # it back. It used to, on the grounds that a new session is a new
        # student — but from the operator's seat the panel they had already
        # dismissed reappeared over a tab they were using, which reads as the
        # tab changing its mind. Dismissed stays dismissed; never opened, it
        # still greets the first opening.
        self._dismiss_entry_screen()

        self._edit_path.clear()
        self._spin_fenv.setValue(5.0)
        self._combo_canal.blockSignals(True)
        self._combo_canal.clear()
        self._combo_canal.addItem("EMG")
        self._combo_canal.blockSignals(False)

        self._refs_en_fichero = {}
        self._fases_en_fichero = parse_phase_markers([])
        self._selected_segments = []
        self._actualizar_etiqueta_fragmentos()

        self._btn_calcular.setEnabled(False)
        self._btn_fragmentos.setEnabled(False)
        self._btn_guardar.setEnabled(False)
        self._btn_informe.setEnabled(False)
        self._progress.setVisible(False)

        for la in (self._d_file, self._d_cvm_ref, self._d_source,
                   self._d_duration, self._d_mean, self._d_static,
                   self._d_median, self._d_peak):
            la.setText("—")

        self._fig.clear()
        self._mostrar_estado_vacio()
        self._canvas.draw_idle()
        self._apdf_fig.clear()
        self._apdf_canvas.draw_idle()
        self._axes_list = []
        self._rebuild_y_sidebar()

        self._time_range.setEnabled(False)
        self._time_range.set_total_duration(60.0)
        self._time_range.set_range(0.0, 10.0)
        for w in (self._btn_tiempo_ampliar, self._btn_tiempo_reducir,
                  self._combo_zoom):
            w.setEnabled(False)
        self._lbl_inicio_info.setText(f"{tr('Start:')} — s")
        self._lbl_duracion_info.setText(f"{tr('Duration:')} — s")

    def cleanup(self) -> None:
        """Called by MainWindow.closeEvent — cancels and waits for the worker."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)
