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

from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.gui.widgets.time_range import TimeRangeSelector
from emgteach.i18n import tr
from emgteach.io import (
    assess_edf_channels,
    list_edf_channels,
    list_edf_emg_channels,
)
from emgteach.modes import DEFAULT_MODE
from emgteach.mvc import AUTO_COLOR, AUTO_LOAD_MSG, AUTO_SUFFIX
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
        self._last_cvm_dir: str = self._settings.value("cvm/last_cvm_dir", ".")
        # Recording mode and fine-control flag, and whether the explanatory
        # entry screen has already been shown in this session (once per
        # student, reset by "New session").
        self._mode: str = DEFAULT_MODE
        self._advanced: bool = False
        self._entry_shown: bool = False
        # Whether the user has accepted normalising against the test recording
        # itself. Per file: a new recording is a new decision.
        self._auto_aceptada: bool = False

        # Local logger, as the acquisition tab has. The shared LoggerWidget is
        # a single widget and Qt can only show it in one layout, which is the
        # Analysis tab's — so everything this tab logged used to be written
        # somewhere invisible. That included the flat-channel and saturated-
        # channel warnings, the most common mistake a student makes.
        self._local_log = LoggerWidget()

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

        # The reference picker continues the same row: the two are the same
        # kind of thing, and a row each pushed the panels further down for
        # nothing.
        row_cvm = row_test
        row_cvm.addSpacing(16)
        # Caption kept as an attribute: the basic level drops the "(optional)"
        # because at that level a reference recording is compulsory.
        self._lbl_cvm = QLabel(tr("MVC reference EDF (optional):"))
        row_cvm.addWidget(self._lbl_cvm)
        self._edit_cvm_path = QLineEdit()
        self._edit_cvm_path.setPlaceholderText(tr("Leave empty for auto-normalisation…"))
        self._edit_cvm_path.setReadOnly(True)
        row_cvm.addWidget(self._edit_cvm_path)
        self._btn_abrir_cvm = QPushButton(tr("Browse…"))
        self._btn_abrir_cvm.clicked.connect(self._seleccionar_edf_cvm)
        row_cvm.addWidget(self._btn_abrir_cvm)
        self._btn_limpiar_cvm = QPushButton(tr("Remove"))
        self._btn_limpiar_cvm.clicked.connect(self._limpiar_cvm)
        row_cvm.addWidget(self._btn_limpiar_cvm)
        ctrl.addLayout(row_test)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel(tr("EMG channel:")))
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
        self._btn_calcular = QPushButton(tr("Compute MVC"))
        self._btn_calcular.setEnabled(False)
        self._btn_calcular.clicked.connect(self._iniciar_calculo)
        row_params.addWidget(self._btn_calcular)

        # A disabled button that does not say why is the worst of both: the
        # tab looks broken rather than incomplete. This says what is missing,
        # right next to the control that cannot be pressed.
        self._lbl_calcular_bloqueado = QLabel()
        self._lbl_calcular_bloqueado.setWordWrap(True)
        self._lbl_calcular_bloqueado.setStyleSheet("color: #8a5000; font-size: 11px;")
        self._lbl_calcular_bloqueado.setVisible(False)
        row_params.addWidget(self._lbl_calcular_bloqueado, stretch=1)

        # The way out for someone who has already recorded and has no maximal
        # effort to compare against. It is a worse measurement, not a
        # forbidden one, so it is offered rather than hidden — but it says
        # what it costs before it is taken.
        self._btn_usar_mismo = QPushButton(tr("Use this recording"))
        self._btn_usar_mismo.setVisible(False)
        self._btn_usar_mismo.clicked.connect(self._ofrecer_auto_normalizacion)
        row_params.addWidget(self._btn_usar_mismo)

        self._btn_guardar = QPushButton(tr("Save figure (PNG)"))
        self._btn_guardar.setEnabled(False)
        self._btn_guardar.clicked.connect(self._guardar_figura)
        row_params.addWidget(self._btn_guardar)

        self._btn_informe = QPushButton(tr("Generate PDF report"))
        self._btn_informe.setEnabled(False)
        self._btn_informe.clicked.connect(self._generar_informe)
        row_params.addWidget(self._btn_informe)

        # Which of the three panels to draw continues the same row. The tab
        # always drew all three, which is a lot of vertical space for a student
        # who is after one of them — most often the last, the signal in % MVC.
        row_paneles = row_params
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
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas.mpl_connect("scroll_event", self._on_scroll_zoom)

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
                "To do that you need two recordings: the one you want to study, "
                "and a short reference recording in which the subject contracts "
                "the muscle as hard as possible. Record the reference first, "
                "with the electrodes in the same position, and do not remove "
                "them in between."
            ),
            tr(
                "The reference has to be made against something that does not "
                "give way — a fixed object, or the operator's hand — with the "
                "joint held still. This is the force-velocity relationship at "
                "work: with nothing to push against, the muscle shortens at "
                "its fastest and therefore develops its least force, so it "
                "recruits few motor units. A maximum performed in mid-air is "
                "submaximal by construction, and every percentage that follows "
                "comes out too high in the same proportion."
            ),
            tr(
                "Without a reference recording this tab can still work, but the "
                "percentages it produces are not percentages of MVC and the "
                "muscle-load limits do not apply to them."
            ),
        ):
            lbl = QLabel(paragraph)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 12px;")
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

        The advanced flag does two things: it reveals the cut-off control, and
        it decides whether auto-normalisation is on offer at all — see
        _reference_required.
        """
        self._mode = mode
        self._advanced = advanced
        self._box_fenv.setVisible(advanced)
        self._refresh_reference_hint()
        self._refresh_compute_enabled()

    def _reference_required(self) -> bool:
        """Whether an MVC reference file is compulsory right now.

        Auto-normalisation divides the signal by the 95th percentile of
        itself, which makes the Jonsson load limits meaningless: a sustained
        contraction exceeds them by construction, so the tab paints a whole
        recording red and it looks like a finding. That trap is worth keeping
        for someone who knows what it is for, and worth removing otherwise —
        the shape of the signal is already in the Analysis tab, honestly
        labelled as normalised to its own maximum.
        """
        return not self._advanced

    def _refresh_reference_hint(self) -> None:
        """Label and placeholder for the reference picker follow the level."""
        if self._reference_required():
            self._lbl_cvm.setText(tr("MVC reference EDF:"))
            self._edit_cvm_path.setPlaceholderText(
                tr("Required at this interface level — select a reference recording…")
            )
        else:
            self._lbl_cvm.setText(tr("MVC reference EDF (optional):"))
            self._edit_cvm_path.setPlaceholderText(
                tr("Leave empty for auto-normalisation…")
            )

    def _refresh_compute_enabled(self) -> None:
        """Enable "Compute MVC" only when the current level has what it needs,
        and say out loud what is missing when it is not."""
        has_test = bool(self._edit_path.text().strip())
        has_ref = bool(self._edit_cvm_path.text().strip())
        falta_ref = self._reference_required() and not has_ref
        listo = has_test and (has_ref or not falta_ref or self._auto_aceptada)
        self._btn_calcular.setEnabled(listo)

        if listo:
            motivo = ""
        elif not has_test:
            motivo = tr("Select the recording to normalise.")
        else:
            # The one case that looks like a fault rather than a missing step:
            # everything is filled in except a file this practical insists on.
            motivo = tr(
                "A reference recording is required to express the signal as "
                "% MVC and to read it against the Jonsson limits."
            )
        self._lbl_calcular_bloqueado.setText(motivo)
        self._lbl_calcular_bloqueado.setVisible(bool(motivo))
        # Offered only where it is the missing piece, and only once: after it
        # is accepted the button has nothing left to offer.
        self._btn_usar_mismo.setVisible(
            has_test and falta_ref and not self._auto_aceptada
        )

    # ------------------------------------------------------------------
    # File-selection slots
    # ------------------------------------------------------------------

    def adopt_recording(self, path: str, channel: str = "") -> None:
        """Take this recording as the one to normalise.

        ``channel`` is the muscle already chosen for this file elsewhere. When
        it is given the tab uses it and asks nothing: normalising a different
        muscle from the one being analysed is possible but is never what the
        two-questions-in-a-row flow was offering.

        The reference file is left alone: it is a different recording by
        definition — the maximal effort — and guessing it from the test file
        would be wrong more often than right.
        """
        if not path or (self._worker is not None and self._worker.isRunning()):
            return
        self._edit_path.setText(path)
        self._last_edf_dir = str(Path(path).parent)
        self._auto_aceptada = False      # a new recording is a new decision
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
            self._auto_aceptada = False  # a new recording is a new decision
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

    @Slot()
    def _seleccionar_edf_cvm(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select MVC reference EDF"),
            self._last_cvm_dir, tr("EDF files (*.edf *.EDF)"),
        )
        if path:
            self._edit_cvm_path.setText(path)
            self._last_cvm_dir = str(Path(path).parent)
            self._settings.setValue("cvm/last_cvm_dir", self._last_cvm_dir)
            self._refresh_compute_enabled()

    @Slot()
    def _limpiar_cvm(self) -> None:
        self._edit_cvm_path.clear()
        self._refresh_compute_enabled()

    # ------------------------------------------------------------------
    # Launch computation
    # ------------------------------------------------------------------

    @Slot()
    def _ofrecer_auto_normalizacion(self) -> None:
        """Offer the test recording as its own reference, and say what it costs.

        The number stops being a percentage of anything measured: the signal is
        divided by a percentile of itself, so the loudest part of *this*
        recording becomes 100 % whatever the muscle can actually do. The shape
        over time survives, which is what makes it worth offering at all.
        """
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("Normalise against this recording itself?"))
        msg.setText(
            tr(
                "The signal will be divided by the 95th percentile of itself, "
                "so the strongest moment of this recording becomes 100 % — "
                "whatever the muscle can really do. Two recordings normalised "
                "this way cannot be compared with each other, and the Jonsson "
                "load limits do not apply: a sustained contraction exceeds "
                "them by construction.\n\nWhat does survive is the shape over "
                "time: when the muscle worked harder and when it let go."
            )
        )
        btn_si = msg.addButton(
            tr("Use it, showing the shape only"), QMessageBox.ButtonRole.DestructiveRole
        )
        btn_ref = msg.addButton(
            tr("Choose a reference recording"), QMessageBox.ButtonRole.AcceptRole
        )
        msg.setDefaultButton(btn_ref)
        msg.exec()

        if msg.clickedButton() is btn_ref:
            self._seleccionar_edf_cvm()
        elif msg.clickedButton() is btn_si:
            self._auto_aceptada = True
            self._log(
                tr("Normalising against the recording itself — shape only, "
                   "not % MVC.")
            )
            self._refresh_compute_enabled()
            # Saying yes *is* the decision. Leaving the result behind a second
            # button reads as the answer having been ignored.
            self._iniciar_calculo()
            return
        self._refresh_compute_enabled()

    def _confirmar_sin_referencia(self) -> bool:
        """Ask before auto-normalising. True to go ahead with the computation.

        The safe option is the default and it *fixes* the problem rather than
        just describing it: picking a reference here feeds straight back into
        the file picker.
        """
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(tr("No MVC reference recording selected"))
        msg.setText(
            tr(
                "The signal will be normalised to the 95th percentile of "
                "itself. The values will be shown as \"% MVC\", but they are "
                "not percentages of maximum voluntary contraction, and the "
                "Jonsson muscle-load limits (P10, P50, P90) do not apply: a "
                "sustained contraction will exceed them by construction."
            )
            + "\n\n"
            + tr("Use this only to see the shape of the signal.")
        )
        btn_choose = msg.addButton(
            tr("Choose a reference recording"), QMessageBox.ButtonRole.AcceptRole
        )
        btn_continue = msg.addButton(
            tr("Continue without reference"), QMessageBox.ButtonRole.DestructiveRole
        )
        msg.setDefaultButton(btn_choose)
        msg.exec()

        if msg.clickedButton() is btn_choose:
            self._seleccionar_edf_cvm()
            # Only carry on if they actually picked one; cancelling the picker
            # means they never confirmed auto-normalisation.
            return bool(self._edit_cvm_path.text().strip())
        return msg.clickedButton() is btn_continue

    @Slot()
    def _iniciar_calculo(self) -> None:
        path = self._edit_path.text().strip()
        cvm_path = self._edit_cvm_path.text().strip()
        f_env = self._spin_fenv.value()

        # Computing without a reference is the one moment a misleading number
        # is about to be produced, so this is where a modal earns its keep.
        # The basic level never reaches it: there the button stays disabled
        # until a reference is chosen.
        if not cvm_path and not self._reference_required():
            if not self._confirmar_sin_referencia():
                return
            cvm_path = self._edit_cvm_path.text().strip()

        self._set_controles_habilitados(False)
        self._progress.setVisible(True)
        self._btn_cancelar.setVisible(True)
        self._btn_cancelar.setEnabled(True)
        self._btn_guardar.setEnabled(False)
        self._btn_informe.setEnabled(False)

        self._worker = MvcWorker(
            edf_path=path,
            mvc_path=cvm_path,
            f_env=f_env,
            channel_index=self._combo_canal.currentIndex(),
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

        # Initialise the time window: 1/3 of the (plotted) duration.
        t_total = float(result["t_plot"][-1]) if len(result["t_plot"]) > 0 else 60.0
        self._duracion_total = t_total
        dur_ini = t_total / 3.0
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
        self._d_file.setText(f"<b>{tr('File:')}</b> {Path(r['edf_path']).name}")
        self._d_cvm_ref.setText(
            f"<b>{tr('MVC reference:')}</b> {r['mvc_amplitude_ref']:.4f} {dim}")
        is_auto = bool(r.get("mvc_is_auto", False))
        if is_auto:
            self._d_source.setText(
                f"<span style='color:{AUTO_COLOR}'><b>{tr('MVC source:')}</b> "
                f"{tr('auto (not a real %MVC)')}</span>"
            )
        else:
            self._d_source.setText(f"<b>{tr('MVC source:')}</b> {r['mvc_source']}")
        dur = float(r["tiempo"][-1]) if len(r.get("tiempo", [])) else 0.0
        self._d_duration.setText(f"<b>{tr('Duration:')}</b> {dur:.1f} s")

        self._d_mean.setText(self._metric_html(
            tr("Mean activation:"), float(r.get("mean_norm", 0.0)),
            EMG_PROFILE.apda_mean_limit, tr("average activation over the task")))

        if is_auto:
            # Better no number than a number with a footnote: the number is
            # what gets copied into the notebook, the footnote is not.
            self._d_static.setText(
                f"<span style='color:#777777; font-size:11px'>"
                f"{tr(AUTO_LOAD_MSG)}</span>"
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

        # The suffix travels with the figure: it is saved as PNG and lands in
        # the report, and by then nothing else says the reference was faked.
        auto_suffix = tr(AUTO_SUFFIX) if r.get("mvc_is_auto") else ""

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
            ax.axhline(r["mvc_amplitude_ref"], color="red", ls="--", lw=1.5,
                       label=tr("MVC ref: {value:.4f} {units}").format(
                           value=r["mvc_amplitude_ref"], units=r.get("dimension", "")))
            ax.set_xlim(inicio, fin)
            ax.set_title(
                tr("2. Envelope and MVC reference amplitude") + auto_suffix, fontsize=9
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
            ax.fill_between(t_full, r["emg_norm"][:n], alpha=0.25, color="darkorange")
            ax.plot(t_full, r["emg_norm"][:n],
                    color="darkorange", lw=1.8, label=tr("Activation (% MVC)"))
            ax.axhline(100.0, color="red", ls=":", lw=1.2, alpha=0.7,
                       label=tr("100 % MVC"))
            ax.set_xlim(inicio, fin)
            ax.set_title(
                tr("3. EMG signal normalised to MVC (% MVC)") + auto_suffix, fontsize=9
            )
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

        # Against an auto-normalised reference the *distribution* is still a
        # fair description of the recording — how its time is spread across
        # effort levels, which is the shape the offer promises. What means
        # nothing is the comparison with Jonsson's limits: a sustained
        # contraction exceeds them by construction, and drawing them turned a
        # whole recording red and looked like a finding. So the curve is drawn
        # and the limits are not.
        apdf = r["apdf"]
        if r.get("mvc_is_auto"):
            ax.plot(apdf.load, apdf.cumulative, color="#7A8894", lw=1.8)
            for prob in (10, 50, 90):
                ax.axhline(prob, color="#E4E4E4", ls=":", lw=0.7)
            ax.set_xlabel(tr("% of this recording's own maximum"), fontsize=8)
            ax.set_ylabel(tr("Cumulative % of time"), fontsize=8)
            ax.set_ylim(0, 100)
            ax.set_title(
                tr("Distribution of effort over time") + tr(AUTO_SUFFIX),
                fontsize=9,
            )
            ax.text(0.5, 0.06, tr(AUTO_LOAD_MSG), ha="center", va="bottom",
                    fontsize=8, color=AUTO_COLOR, wrap=True,
                    transform=ax.transAxes)
            ax.grid(True, color="#DDDDDD", alpha=0.5)
            ax.tick_params(labelsize=7)
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

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up, alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl,    alignment=Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn, alignment=Qt.AlignmentFlag.AlignHCenter)
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

    def _on_scroll_zoom(self, event) -> None:
        """Mouse-wheel zoom on the panel under the cursor (X and Y), centred
        on the cursor position."""
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
        meta = {
            "student": self._settings.value("analisis/student", ""),
            "student_code": self._settings.value("analisis/student_code", ""),
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
        self._btn_abrir_cvm.setEnabled(habilitado)
        self._btn_limpiar_cvm.setEnabled(habilitado)
        if habilitado:
            self._refresh_compute_enabled()
        else:
            self._btn_calcular.setEnabled(False)
        self._combo_canal.setEnabled(habilitado)
        self._spin_fenv.setEnabled(habilitado)

    # ------------------------------------------------------------------
    # New-session reset
    # ------------------------------------------------------------------

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

        # A new session means a new student, so the explanation is due again:
        # right away if this tab is the one on screen, otherwise the next time
        # it is opened (showEvent does not fire for the tab already showing).
        self._entry_shown = False
        self._dismiss_entry_screen()
        if self.isVisible():
            self._show_entry_screen()

        self._edit_path.clear()
        self._edit_cvm_path.clear()
        self._spin_fenv.setValue(5.0)
        self._combo_canal.blockSignals(True)
        self._combo_canal.clear()
        self._combo_canal.addItem("EMG")
        self._combo_canal.blockSignals(False)

        self._btn_calcular.setEnabled(False)
        self._btn_guardar.setEnabled(False)
        self._btn_informe.setEnabled(False)
        self._progress.setVisible(False)

        for la in (self._d_file, self._d_cvm_ref, self._d_source,
                   self._d_duration, self._d_mean, self._d_static,
                   self._d_median, self._d_peak):
            la.setText("—")

        self._fig.clear()
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
