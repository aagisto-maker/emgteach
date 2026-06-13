"""
AcquisitionTab — tab 1: real-time EMG acquisition with BITalino.

Controls:
  - BITalino MAC address (persisted with QSettings)
  - Destination folder for the EDF (persisted with QSettings)
  - Connect / Disconnect button
  - Start / Stop recording button

Channels:
  - 1 or 2 simultaneous channels (e.g. agonist/antagonist), with an
    editable label per channel. Each channel is drawn overlaid in its own colour.

Visualisation (pyqtgraph):
  - Raw EMG signal
  - Filtered signal (notch + band-pass)
  - Envelope

Scale controls:
  - Vertical scale: ▲▼ buttons per plot (×1.5 factor, 0.01×–100× of the initial limits)
  - Time scale: factor dropdown + ◀▶ buttons (sliding window over the
    ring buffer; lets you see from 0.5 s up to MAX_POINTS/fs seconds)

The tab never blocks the UI: all acquisition runs in AcquisitionWorker (QThread).
"""

from __future__ import annotations

from collections import deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.devices import (
    BACKEND_ARDUINO,
    BACKEND_BITALINO,
    ArduinoDevice,
    create_device,
)
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.i18n import tr
from emgteach.profiles import EMG_PROFILE
from emgteach.workers import AcquisitionWorker

# Number of samples in the ring buffer (= 30 s at 1000 Hz)
# The visible window can be smaller thanks to the time-zoom control.
MAX_POINTS = 30_000
FS = EMG_PROFILE.sample_frequency  # nominal Hz (taken from the signal profile)

# Maximum number of simultaneous channels the interface offers. The data
# layer supports N, but the UI is limited to 2 for now (agonist/antagonist).
MAX_CHANNELS = 2

# Maximum number of event markers drawn live at once (a reusable pool of
# lines per plot; more than enough for a 30 s window).
MAX_MARKER_LINES = 40

# Per-channel colour, consistent across the three plots: a colour always
# identifies the same sensor (blue = channel 1, red = channel 2).
_CHANNEL_COLORS = [(65, 105, 225), (214, 39, 40)]
_CHANNEL_COLOR_HEX = ["#4169E1", "#D62728"]
_CHANNEL_DEFAULT_LABELS = ["EMG", "EMG 2"]
# Defaults briefly used in an earlier version; they are migrated to the ones
# above if still stored in QSettings (this does not overwrite names chosen by
# the user, only the old defaults).
_OLD_DEFAULT_LABELS = ["Canal 1", "Canal 2"]

# With 2 channels the raw and filtered plots stack (one lane per channel)
# instead of overlapping. The mV axis is no longer absolute, so each lane
# shows reference ticks at 0/±_CALIB_MV·gain (an honest calibration that does
# not hide the signal). Real signal mV per plot (0=raw, 1=filtered); the
# envelope (2) never stacks.
_CALIB_MV = {0: 1.0, 1: 0.2}

# Default MAC of the UCM lab's BITalino (editable in the field).
DEFAULT_MAC = "98:D3:91:FE:44:E4"

# Interval (ms) after the last received data beyond which there is considered
# to be no traffic (the LED goes from green to yellow).
LED_IDLE_MS = 500

# Available time-zoom factors (denominator: how many times the visible window
# fits in the total buffer). Factor ×1 → see the whole buffer.
_ZOOM_FACTORS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

# Shared style for the small scale buttons
_BTN_ST = (
    "QToolButton { font-size: 9px; padding: 0px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
# Larger-typeface variant for the time-window controls (1-2 pt more than
# _BTN_ST, which is reserved for the small ▲▼ sidebar buttons).
_TBTN_ST = (
    "QToolButton { font-size: 11px; padding: 0px 2px; border: 1px solid #aaa; "
    "border-radius: 2px; background: #f5f5f5; }"
    "QToolButton:hover { background: #dde8ff; }"
    "QToolButton:pressed { background: #b0c8ff; }"
)
_COMBO_ST = (
    "QComboBox { font-size: 11px; padding: 1px 3px; min-width: 60px; max-width: 76px; }"
)


class AcquisitionTab(QWidget):
    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None):
        super().__init__(parent)
        self._logger = logger
        self._settings = settings
        self._worker: AcquisitionWorker | None = None
        self._profile = EMG_PROFILE

        # Number of active channels (1 or 2), persisted in QSettings.
        saved_n = int(self._settings.value("adquisicion/n_channels", 1))
        self._n_channels = min(max(saved_n, 1), MAX_CHANNELS)

        # Per-channel ring buffers for the three signals (30 s at 1000 Hz).
        # MAX_CHANNELS are always allocated; only the active channels are filled.
        self._buf_raw = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(MAX_CHANNELS)
        ]
        self._buf_filt = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(MAX_CHANNELS)
        ]
        self._buf_env = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(MAX_CHANNELS)
        ]
        self._new_data = False  # flag: there is new data to draw

        # Events for drawing live lines: (time_s, label). The total number of
        # acquired samples places each marker within the sliding window.
        self._marker_events: list[tuple[float, str]] = []
        self._total_samples = 0

        # ---- Vertical-scale state (per plot: 0=raw, 1=filt, 2=env) ----
        # Initial Y ranges taken from the signal profile (restored in
        # _reset_y_scales). Changing modality = changing profile.
        self._y_ranges_init: list[tuple[float, float]] = [
            self._profile.ylim_raw,       # raw
            self._profile.ylim_filtered,  # filtered
            self._profile.ylim_envelope,  # envelope
        ]
        self._y_accum: list[float] = [1.0, 1.0, 1.0]  # accumulated factor per plot
        # Per-plot data gain, used ONLY in stacked mode (2 channels) on
        # raw/filtered: the ▲▼ zoom multiplies the signal while keeping the
        # lanes fixed, instead of scaling the ViewBox. Unused in 1-channel mode.
        self._y_gain: list[float] = [1.0, 1.0, 1.0]

        # ---- Time-scale state ----
        # Number of visible samples in each plot. Starts showing 5 s.
        self._n_visible: int = 5 * FS   # visible samples (adjustable with zoom)

        # Independent render timer — decouples data reception from redrawing.
        # 33 ms ≈ 30 FPS max, regardless of the worker's speed.
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self._refresh_plots)

        # Watchdog: fires every 1 s during recording and checks that the
        # worker keeps receiving samples. If no data arrives within 3 s, it
        # forces a disconnection to unblock a read() hung by a lost BT link.
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.setInterval(1000)
        self._watchdog_timer.timeout.connect(self._check_watchdog)
        self._watchdog_umbral_s = 3.0

        # Local logger: own instance shown in this tab. Messages are mirrored
        # to the shared logger (self._logger) so the analysis tab also receives
        # them if it needs them.
        self._local_log = LoggerWidget()

        self._build_ui()

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
    # Interface construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # The styling (gray background, steel-blue boxes, title margins) is
        # centralised in gui/app.py and applied to all tabs. Here we only tag
        # the plot frame with the objectName "plotsBox" so it stays white
        # (below).
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ══ Top row: Configuration (left) | Event log (right) ══
        row_top = QHBoxLayout()
        row_top.setSpacing(4)

        # — Device configuration (half width) —
        grp_config = QGroupBox(tr("Device configuration"))
        cfg_outer = QVBoxLayout(grp_config)
        cfg_outer.setContentsMargins(6, 3, 6, 3)
        cfg_outer.setSpacing(3)

        # Row 1: device type + connection (MAC or COM)
        cfg_row1 = QHBoxLayout()
        cfg_row1.setSpacing(6)

        # Device-type combo
        self._combo_device_type = QComboBox()
        self._combo_device_type.addItem("BITalino (Bluetooth)")
        self._combo_device_type.addItem("Arduino + MyoWare 2.0 (USB)")
        saved_type = int(self._settings.value("adquisicion/device_type", 0))
        self._combo_device_type.setCurrentIndex(saved_type)
        self._combo_device_type.currentIndexChanged.connect(self._on_device_type_changed)
        cfg_row1.addWidget(self._combo_device_type, stretch=1)

        # Conditional central area: MAC (BITalino) or COM (Arduino)
        # Wrapped in a QWidget so the content can change without rebuilding the layout
        self._widget_mac = QWidget()
        mac_inner = QHBoxLayout(self._widget_mac)
        mac_inner.setContentsMargins(0, 0, 0, 0)
        mac_inner.setSpacing(4)
        self._edit_mac = QLineEdit()
        self._edit_mac.setPlaceholderText("98:D3:91:FE:44:E4")
        self._edit_mac.setText(self._settings.value("adquisicion/mac", DEFAULT_MAC))
        mac_inner.addWidget(self._edit_mac)
        btn_reset_mac = QPushButton(tr("Default"))
        btn_reset_mac.setFixedWidth(84)
        btn_reset_mac.setToolTip(tr("Restore default MAC ({mac})").format(mac=DEFAULT_MAC))
        btn_reset_mac.clicked.connect(self._reset_mac)
        mac_inner.addWidget(btn_reset_mac)

        self._widget_arduino = QWidget()
        ard_inner = QHBoxLayout(self._widget_arduino)
        ard_inner.setContentsMargins(0, 0, 0, 0)
        ard_inner.setSpacing(4)
        self._combo_port = QComboBox()
        ard_inner.addWidget(self._combo_port)
        btn_refresh_ports = QPushButton(tr("Refresh"))
        btn_refresh_ports.setFixedWidth(84)
        btn_refresh_ports.setToolTip(tr("Refresh the list of available serial ports"))
        btn_refresh_ports.clicked.connect(self._refresh_ports)
        ard_inner.addWidget(btn_refresh_ports)

        # Container that switches between _widget_mac and _widget_arduino
        self._stack_conn = QWidget()
        stack_layout = QHBoxLayout(self._stack_conn)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(self._widget_mac)
        stack_layout.addWidget(self._widget_arduino)
        cfg_row1.addWidget(self._stack_conn, stretch=2)
        cfg_outer.addLayout(cfg_row1)

        # Row 2: destination folder + Browse
        cfg_row2 = QHBoxLayout()
        cfg_row2.setSpacing(6)
        self._edit_dir = QLineEdit()
        self._edit_dir.setPlaceholderText(tr("EDF destination folder"))
        self._edit_dir.setText(self._settings.value("adquisicion/save_dir", "."))
        cfg_row2.addWidget(self._edit_dir, stretch=1)
        btn_dir = QPushButton(tr("Browse…"))
        btn_dir.setFixedWidth(84)
        btn_dir.clicked.connect(self._seleccionar_directorio)
        cfg_row2.addWidget(btn_dir)
        cfg_outer.addLayout(cfg_row2)

        # Initial visibility of the connection area
        self._widget_mac.setVisible(saved_type == 0)
        self._widget_arduino.setVisible(saved_type == 1)
        self._refresh_ports()

        # Row 3: number of channels and per-channel labels
        ch_row = QHBoxLayout()
        ch_row.setSpacing(6)
        ch_row.addWidget(QLabel(tr("Channels:")))
        self._combo_n_channels = QComboBox()
        self._combo_n_channels.addItem(tr("1 (single sensor)"))
        self._combo_n_channels.addItem(tr("2 (agonist / antagonist)"))
        self._combo_n_channels.setCurrentIndex(self._n_channels - 1)
        self._combo_n_channels.currentIndexChanged.connect(self._on_n_channels_changed)
        ch_row.addWidget(self._combo_n_channels)

        ch_row.addWidget(QLabel(tr("Labels:")))
        self._edit_labels: list[QLineEdit] = []
        for i in range(MAX_CHANNELS):
            edit = QLineEdit()
            edit.setMaxLength(16)  # EDF channel-label limit
            edit.setToolTip(
                tr(
                    "Name of this channel's muscle/sensor (max. 16 characters; "
                    "used as the channel label in the EDF file)."
                )
            )
            stored = self._settings.value(
                f"adquisicion/label_{i}", _CHANNEL_DEFAULT_LABELS[i]
            )
            if stored == _OLD_DEFAULT_LABELS[i]:
                stored = _CHANNEL_DEFAULT_LABELS[i]  # migrate old default
            edit.setText(stored)
            edit.textChanged.connect(self._on_label_changed)
            self._edit_labels.append(edit)
            ch_row.addWidget(edit, stretch=1)
        cfg_outer.addLayout(ch_row)

        row_top.addWidget(grp_config, stretch=1)

        # — Event log (shares the row with the configuration) —
        grp_log = QGroupBox(tr("Event log"))
        log_layout = QVBoxLayout(grp_log)
        log_layout.setContentsMargins(4, 4, 4, 4)
        # The top row (Configuration + Log) is ~3 rows tall; the log fills that
        # box and the remaining window space goes to the real-time plots.
        self._local_log.setMaximumHeight(90)
        log_layout.addWidget(self._local_log)
        row_top.addWidget(grp_log, stretch=1)

        root.addLayout(row_top)

        # ══ Actions row: Control | Markers (one line each) ══
        row_actions = QHBoxLayout()
        row_actions.setSpacing(4)

        # — Acquisition control (single line) —
        grp_control = QGroupBox(tr("Acquisition control"))
        ctrl_layout = QHBoxLayout(grp_control)
        ctrl_layout.setContentsMargins(6, 3, 6, 3)
        ctrl_layout.setSpacing(6)

        self._btn_conectar = QPushButton(tr("Connect"))
        self._btn_conectar.setCheckable(True)
        self._btn_conectar.clicked.connect(self._toggle_conexion)
        ctrl_layout.addWidget(self._btn_conectar)

        self._btn_grabar = QPushButton(tr("Start recording"))
        self._btn_grabar.setCheckable(True)
        self._btn_grabar.setEnabled(False)
        self._btn_grabar.clicked.connect(self._toggle_grabacion)
        ctrl_layout.addWidget(self._btn_grabar)

        self._led = QLabel()
        self._led.setFixedSize(16, 16)
        self._led.setToolTip(tr("Device communication status"))
        ctrl_layout.addWidget(self._led)
        self._lbl_estado = QLabel(tr("Status: disconnected"))
        ctrl_layout.addWidget(self._lbl_estado)
        ctrl_layout.addStretch()

        row_actions.addWidget(grp_control, stretch=1)

        # LED idle timer
        self._led_idle_timer = QTimer(self)
        self._led_idle_timer.setSingleShot(True)
        self._led_idle_timer.setInterval(LED_IDLE_MS)
        self._led_idle_timer.timeout.connect(lambda: self._set_led("idle"))
        self._set_led("off")

        # — Event markers (single line) —
        grp_markers = QGroupBox(tr("Event markers"))
        markers_layout = QHBoxLayout(grp_markers)
        markers_layout.setContentsMargins(6, 3, 6, 3)
        markers_layout.setSpacing(6)

        self._combo_etiqueta = QComboBox()
        for etiq in self._profile.marker_presets:
            self._combo_etiqueta.addItem(tr(etiq))
        self._combo_etiqueta.setEnabled(False)
        markers_layout.addWidget(self._combo_etiqueta, stretch=1)

        self._btn_marcar = QPushButton(tr("MARK"))
        self._btn_marcar.setMinimumHeight(30)
        self._btn_marcar.setStyleSheet("font-size: 12px; font-weight: bold;")
        self._btn_marcar.setEnabled(False)
        self._btn_marcar.clicked.connect(self._on_marcar)
        markers_layout.addWidget(self._btn_marcar)

        # Automatic contraction-onset detection (compact, inline). Added
        # markers are reflected in the "Event log".
        self._chk_auto = QCheckBox(tr("Auto-onset"))
        self._chk_auto.setToolTip(
            tr(
                "Automatically marks the contraction onset when the envelope "
                "exceeds the threshold (baseline + k·SD of the resting period)."
            )
        )
        self._chk_auto.setChecked(
            self._settings.value("adquisicion/auto_detect", False, type=bool)
        )
        self._chk_auto.toggled.connect(self._on_auto_toggled)
        markers_layout.addWidget(self._chk_auto)
        markers_layout.addWidget(QLabel("k:"))
        self._spin_k = QDoubleSpinBox()
        self._spin_k.setRange(1.0, 10.0)
        self._spin_k.setSingleStep(0.5)
        self._spin_k.setValue(
            self._settings.value(
                "adquisicion/onset_k", self._profile.onset_k, type=float
            )
        )
        self._spin_k.setFixedWidth(60)
        self._spin_k.setToolTip(
            tr(
                "Threshold in standard deviations above the resting period "
                "(lower = more sensitive)."
            )
        )
        self._spin_k.valueChanged.connect(
            lambda v: self._settings.setValue("adquisicion/onset_k", v)
        )
        self._spin_k.setEnabled(self._chk_auto.isChecked())
        markers_layout.addWidget(self._spin_k)

        row_actions.addWidget(grp_markers, stretch=1)

        root.addLayout(row_actions)

        # Keyboard shortcut M
        self._shortcut_m = QShortcut(QKeySequence("M"), self)
        self._shortcut_m.setEnabled(False)
        self._shortcut_m.activated.connect(self._on_marcar_rapido)

        # ── Plots + scale controls ──────────────────────────────
        grp_plots = QGroupBox(tr("Real-time EMG signal"))
        grp_plots.setObjectName("plotsBox")  # stays white (see setStyleSheet)
        plots_root = QVBoxLayout(grp_plots)
        plots_root.setContentsMargins(6, 8, 6, 3)
        plots_root.setSpacing(3)

        # -- Time-scale bar (above the plots) -----------
        row_tiempo = QHBoxLayout()
        row_tiempo.addWidget(QLabel(tr("Time window:")))

        self._btn_tiempo_ampliar = QToolButton()
        self._btn_tiempo_ampliar.setText("◀▶")
        self._btn_tiempo_ampliar.setToolTip(tr("Widen the window (see more time)"))
        self._btn_tiempo_ampliar.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_ampliar.setFixedSize(32, 26)
        self._btn_tiempo_ampliar.clicked.connect(self._on_tiempo_ampliar)
        row_tiempo.addWidget(self._btn_tiempo_ampliar)

        self._combo_zoom = QComboBox()
        self._combo_zoom.setStyleSheet(_COMBO_ST)
        self._combo_zoom.setFixedSize(76, 26)
        for f in _ZOOM_FACTORS:
            self._combo_zoom.addItem(f"×{f}")
        self._combo_zoom.setCurrentIndex(0)   # ×1 = the whole buffer
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)
        row_tiempo.addWidget(self._combo_zoom)

        self._btn_tiempo_reducir = QToolButton()
        self._btn_tiempo_reducir.setText("▶◀")
        self._btn_tiempo_reducir.setToolTip(tr("Narrow the window (see less time, more detail)"))
        self._btn_tiempo_reducir.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_reducir.setFixedSize(32, 26)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)
        row_tiempo.addWidget(self._btn_tiempo_reducir)

        self._lbl_ventana_info = QLabel(f"{MAX_POINTS // FS} {tr('s visible')}")
        self._lbl_ventana_info.setStyleSheet("font-size: 8px; color: #444;")
        row_tiempo.addWidget(self._lbl_ventana_info)

        row_tiempo.addSpacing(12)
        self._lbl_legend = QLabel()
        self._lbl_legend.setStyleSheet("font-size: 9px; font-weight: bold;")
        self._lbl_legend.setToolTip(tr("Colour of each channel in the plots"))
        row_tiempo.addWidget(self._lbl_legend)

        row_tiempo.addStretch()

        btn_reset_escala = QPushButton(tr("Reset scales"))
        btn_reset_escala.setFixedHeight(26)
        btn_reset_escala.setStyleSheet("font-size: 10px;")
        btn_reset_escala.setToolTip(tr("Restore Y ranges and time window to initial values"))
        btn_reset_escala.clicked.connect(self._reset_all_scales)
        row_tiempo.addWidget(btn_reset_escala)

        plots_root.addLayout(row_tiempo)

        # -- Plot area with vertical-scale sidebar -------------
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")

        # Vertical sidebar (▲▼ per plot)
        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(38)
        sidebar_vbox = QVBoxLayout(self._sidebar)
        sidebar_vbox.setContentsMargins(2, 4, 2, 4)
        sidebar_vbox.setSpacing(0)

        # Plots container
        plots_col = QWidget()
        plots_col_vbox = QVBoxLayout(plots_col)
        plots_col_vbox.setContentsMargins(0, 0, 0, 0)
        plots_col_vbox.setSpacing(4)

        canvas_hbox = QHBoxLayout()
        canvas_hbox.setContentsMargins(0, 0, 0, 0)
        canvas_hbox.setSpacing(2)
        canvas_hbox.addWidget(self._sidebar)
        canvas_hbox.addWidget(plots_col)
        plots_root.addLayout(canvas_hbox)

        # One curve per channel in each plot (colour = channel). MAX_CHANNELS
        # curves are allocated; those of inactive channels stay hidden.
        self._curves_raw: list = []
        self._curves_filt: list = []
        self._curves_env: list = []

        # Raw signal
        self._plot_raw = pg.PlotWidget(title=tr("Raw EMG signal (mV)"))
        self._plot_raw.setYRange(*self._y_ranges_init[0])
        self._plot_raw.setLabel("left", "mV")
        self._plot_raw.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_raw.append(
                self._plot_raw.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=1))
            )
        plots_col_vbox.addWidget(self._plot_raw)

        # Filtered signal
        self._plot_filt = pg.PlotWidget(
            title=tr("Filtered EMG (notch 50 Hz + band-pass 20-450 Hz)")
        )
        self._plot_filt.setYRange(*self._y_ranges_init[1])
        self._plot_filt.setLabel("left", "mV")
        self._plot_filt.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_filt.append(
                self._plot_filt.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=1))
            )
        plots_col_vbox.addWidget(self._plot_filt)

        # Envelope
        self._plot_env = pg.PlotWidget(
            title=tr("Envelope (5 Hz low-pass filter, causal with continuous state)")
        )
        self._plot_env.setYRange(*self._y_ranges_init[2])
        self._plot_env.setLabel("left", "mV")
        self._plot_env.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_env.append(
                self._plot_env.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=2))
            )
        plots_col_vbox.addWidget(self._plot_env)

        # Reusable pool of vertical lines for the event markers, one collection
        # per plot (repositioned on each refresh according to the sliding
        # window; orange, like in the Analysis tab).
        marker_pen = pg.mkPen(color=(230, 126, 34), width=1, style=Qt.PenStyle.DashLine)
        self._marker_lines: list[list] = []
        for pw in (self._plot_raw, self._plot_filt, self._plot_env):
            pool = []
            for _ in range(MAX_MARKER_LINES):
                line = pg.InfiniteLine(angle=90, movable=False, pen=marker_pen)
                line.hide()
                pw.addItem(line, ignoreBounds=True)
                pool.append(line)
            self._marker_lines.append(pool)

        # Stacked-mode annotations (2 channels), only on raw and filtered: a
        # horizontal baseline per channel (its "zero") and the muscle label
        # next to each lane. The calibration is presented as reference ticks on
        # the axis (see _set_calib_ticks). Hidden in 1-channel mode.
        self._baselines: dict[int, list] = {}
        self._lane_labels: dict[int, list] = {}
        for idx, pw in ((0, self._plot_raw), (1, self._plot_filt)):
            base_lines = []
            lane_labels = []
            for c in range(MAX_CHANNELS):
                bl = pg.InfiniteLine(
                    angle=0,
                    movable=False,
                    pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=1,
                                 style=Qt.PenStyle.DotLine),
                )
                bl.hide()
                pw.addItem(bl, ignoreBounds=True)
                base_lines.append(bl)

                txt = pg.TextItem(anchor=(0, 0.5), fill=(255, 255, 255, 200))
                txt.setColor(_CHANNEL_COLORS[c])
                txt.hide()
                pw.addItem(txt, ignoreBounds=True)
                lane_labels.append(txt)
            self._baselines[idx] = base_lines
            self._lane_labels[idx] = lane_labels

        # Build the ▲▼ buttons in the sidebar (one per plot)
        self._plots_widgets = [self._plot_raw, self._plot_filt, self._plot_env]
        labels = ["B", "F", "E"]   # button per plot: raw / filtered / envelope
        for i, (pw, lbl_txt) in enumerate(zip(self._plots_widgets, labels)):
            slot = QWidget()
            slot_vbox = QVBoxLayout(slot)
            slot_vbox.setContentsMargins(0, 0, 0, 0)
            slot_vbox.setSpacing(1)

            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(32, 18)
            btn_up.setStyleSheet(_BTN_ST)
            btn_up.setToolTip(tr("Zoom in (vertical) — {label}").format(label=lbl_txt))
            btn_up.clicked.connect(
                lambda checked=False, idx=i: self._y_zoom(idx, zoom_in=True)
            )

            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet("font-size: 7px; color: #666;")
            from PySide6.QtCore import Qt as _Qt
            lbl.setAlignment(_Qt.AlignmentFlag.AlignCenter)

            btn_dn = QToolButton()
            btn_dn.setText("▼")
            btn_dn.setFixedSize(32, 18)
            btn_dn.setStyleSheet(_BTN_ST)
            btn_dn.setToolTip(tr("Zoom out (vertical) — {label}").format(label=lbl_txt))
            btn_dn.clicked.connect(
                lambda checked=False, idx=i: self._y_zoom(idx, zoom_in=False)
            )

            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up,  alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl,     alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn,  alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addStretch()

            sidebar_vbox.addWidget(slot, stretch=1)

        root.addWidget(grp_plots, stretch=1)

        # Update the combo so it reflects the initial n_visible
        self._sync_combo_zoom()

        # Show only the active channels and paint the legend
        self._apply_channel_visibility()
        self._update_legend()
        # Configure the plot mode (overlaid or stacked) according to the
        # persisted number of channels.
        self._apply_stacking_mode()

    # ------------------------------------------------------------------
    # Device-control slots
    # ------------------------------------------------------------------

    @Slot()
    def _seleccionar_directorio(self) -> None:
        directorio = QFileDialog.getExistingDirectory(
            self, tr("Select destination folder"),
            self._edit_dir.text() or ".",
        )
        if directorio:
            self._edit_dir.setText(directorio)
            self._settings.setValue("adquisicion/save_dir", directorio)

    @Slot()
    def _reset_mac(self) -> None:
        """Restore the lab's default MAC."""
        self._edit_mac.setText(DEFAULT_MAC)
        self._settings.setValue("adquisicion/mac", DEFAULT_MAC)

    @Slot(int)
    def _on_device_type_changed(self, index: int) -> None:
        """Show the MAC field (BITalino) or the COM-port selector (Arduino)."""
        self._widget_mac.setVisible(index == 0)
        self._widget_arduino.setVisible(index == 1)

    # ------------------------------------------------------------------
    # Channels (1 or 2: agonist/antagonist)
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_n_channels_changed(self, index: int) -> None:
        self._n_channels = index + 1
        self._settings.setValue("adquisicion/n_channels", self._n_channels)
        self._apply_channel_visibility()
        self._update_legend()
        # Switching 1↔2 channels reconfigures the plots (stacked vs overlaid)
        # and resets the stacking gain.
        self._y_gain = [1.0, 1.0, 1.0]
        self._apply_stacking_mode()

    @Slot()
    def _on_label_changed(self) -> None:
        for i, edit in enumerate(self._edit_labels):
            self._settings.setValue(f"adquisicion/label_{i}", edit.text())
        self._update_legend()

    def _active_labels(self) -> list[str]:
        """Labels of the active channels, falling back to the defaults."""
        labels = []
        for i in range(self._n_channels):
            text = self._edit_labels[i].text().strip()
            labels.append(text or _CHANNEL_DEFAULT_LABELS[i])
        return labels

    def _apply_channel_visibility(self) -> None:
        """Show only the widgets and curves of the active channels."""
        for i, edit in enumerate(self._edit_labels):
            edit.setVisible(i < self._n_channels)
        for c in range(MAX_CHANNELS):
            visible = c < self._n_channels
            self._curves_raw[c].setVisible(visible)
            self._curves_filt[c].setVisible(visible)
            self._curves_env[c].setVisible(visible)

    def _update_legend(self) -> None:
        parts = [
            f'<span style="color:{_CHANNEL_COLOR_HEX[i]}">&#9679; {lbl}</span>'
            for i, lbl in enumerate(self._active_labels())
        ]
        self._lbl_legend.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        # Keep the stacked-mode lane labels in sync.
        if hasattr(self, "_lane_labels"):
            self._refresh_lane_label_texts()

    # ------------------------------------------------------------------
    # Stacked mode (2 channels) on raw / filtered
    # ------------------------------------------------------------------

    def _is_stacked(self, idx: int) -> bool:
        """True if plot idx (0=raw, 1=filtered) stacks 2 channels."""
        return self._n_channels == 2 and idx in (0, 1)

    def _lane_half(self, idx: int) -> float:
        """Half-height of plot idx's initial range (= height of one lane)."""
        lo, hi = self._y_ranges_init[idx]
        return (hi - lo) / 2.0

    def _lane_baseline(self, idx: int, channel: int) -> float:
        """Baseline (offset) of the channel in plot idx: channel 0 on top (+A),
        channel 1 below (-A)."""
        a = self._lane_half(idx)
        return a if channel == 0 else -a

    def _set_calib_ticks(self, idx: int) -> None:
        """Reference ticks at 0 and ±_CALIB_MV·gain on each lane. They replace
        the absolute mV axis (misleading when stacking) with an honest
        calibration that does not hide the signal."""
        axis = self._plots_widgets[idx].getAxis("left")
        calib = _CALIB_MV[idx]
        g = self._y_gain[idx]
        major = []
        for c in range(self._n_channels):
            base = self._lane_baseline(idx, c)
            major.append((base, "0"))
            major.append((base + g * calib, f"+{calib:g}"))
            major.append((base - g * calib, f"−{calib:g}"))
        axis.setTicks([major])

    def _refresh_lane_label_texts(self) -> None:
        """Update the text, colour, position and visibility of the lane labels
        according to the active labels and the stacking mode."""
        labels = self._active_labels()
        for idx in (0, 1):
            a = self._lane_half(idx)
            for c in range(MAX_CHANNELS):
                txt = self._lane_labels[idx][c]
                if self._is_stacked(idx) and c < self._n_channels:
                    txt.setText(f" {labels[c]}")
                    txt.setColor(_CHANNEL_COLORS[c])
                    txt.setPos(0.0, self._lane_baseline(idx, c) + a * 0.78)
                    txt.show()
                else:
                    txt.hide()

    def _apply_stacking_mode(self) -> None:
        """Configure the Y range, calibration ticks and baselines of the raw
        and filtered plots according to the number of channels (1 = overlaid on
        zero, 2 = two stacked lanes). The envelope never stacks."""
        for idx in (0, 1):
            pw = self._plots_widgets[idx]
            axis = pw.getAxis("left")
            a = self._lane_half(idx)
            if self._is_stacked(idx):
                pw.setYRange(-2 * a, 2 * a, padding=0)
                self._set_calib_ticks(idx)
                for c in range(MAX_CHANNELS):
                    bl = self._baselines[idx][c]
                    if c < self._n_channels:
                        bl.setPos(self._lane_baseline(idx, c))
                        bl.show()
                    else:
                        bl.hide()
            else:
                pw.setYRange(*self._y_ranges_init[idx], padding=0)
                axis.setTicks(None)  # restore automatic ticks (absolute mV)
                for c in range(MAX_CHANNELS):
                    self._baselines[idx][c].hide()
        self._refresh_lane_label_texts()

    def _set_channel_controls_enabled(self, enabled: bool) -> None:
        self._combo_n_channels.setEnabled(enabled)
        for edit in self._edit_labels:
            edit.setEnabled(enabled)

    def _reset_buffers(self) -> None:
        """Clear every per-channel ring buffer back to silence."""
        for bufs in (self._buf_raw, self._buf_filt, self._buf_env):
            for buf in bufs:
                buf.clear()
                buf.extend([0.0] * MAX_POINTS)

    @Slot(bool)
    def _on_auto_toggled(self, checked: bool) -> None:
        self._spin_k.setEnabled(checked)
        self._settings.setValue("adquisicion/auto_detect", checked)

    def _set_auto_controls_enabled(self, enabled: bool) -> None:
        self._chk_auto.setEnabled(enabled)
        self._spin_k.setEnabled(enabled and self._chk_auto.isChecked())

    @Slot()
    def _refresh_ports(self) -> None:
        """Repopulate the COM-port combo with those available on the system."""
        ports = ArduinoDevice.list_ports()
        saved_port = self._settings.value("adquisicion/port", "")
        self._combo_port.blockSignals(True)
        self._combo_port.clear()
        for p in ports:
            self._combo_port.addItem(p)
        if saved_port in ports:
            self._combo_port.setCurrentText(saved_port)
        elif ports:
            self._combo_port.setCurrentIndex(0)
        self._combo_port.blockSignals(False)

    @Slot()
    def _toggle_conexion(self) -> None:
        if self._btn_conectar.isChecked():
            self._conectar()
        else:
            self._desconectar()

    def _conectar(self) -> None:
        device_idx = self._combo_device_type.currentIndex()
        if device_idx == 0:  # BITalino
            desc = self._edit_mac.text().strip()
            if not desc:
                self._err(
                    tr("Enter the BITalino MAC address before connecting.")
                )
                self._btn_conectar.setChecked(False)
                return
            self._settings.setValue("adquisicion/mac", desc)
        else:  # Arduino
            desc = self._combo_port.currentText().strip()
            if not desc:
                self._err(
                    tr("Select a COM port for the Arduino before connecting.")
                )
                self._btn_conectar.setChecked(False)
                return
            self._settings.setValue("adquisicion/port", desc)
        self._settings.setValue("adquisicion/device_type", device_idx)

        self._btn_conectar.setText(tr("Disconnect"))
        self._btn_grabar.setEnabled(True)
        self._combo_device_type.setEnabled(False)
        self._widget_mac.setEnabled(False)
        self._widget_arduino.setEnabled(False)
        self._edit_dir.setEnabled(False)
        self._set_channel_controls_enabled(False)
        self._lbl_estado.setText(tr("Status: connected (ready to record)"))
        self._set_led("idle")
        self._log(tr("Device configured: {desc}. Press 'Start recording'.").format(desc=desc))

    def _desconectar(self) -> None:
        self._watchdog_timer.stop()
        if self._worker and self._worker.isRunning():
            self._detener_grabacion()
        self._btn_conectar.setText(tr("Connect"))
        self._btn_conectar.setChecked(False)
        self._btn_grabar.setEnabled(False)
        self._btn_grabar.setChecked(False)
        self._btn_grabar.setText(tr("Start recording"))
        self._combo_device_type.setEnabled(True)
        self._widget_mac.setEnabled(True)
        self._widget_arduino.setEnabled(True)
        self._edit_dir.setEnabled(True)
        self._set_channel_controls_enabled(True)
        self._lbl_estado.setText(tr("Status: disconnected"))
        self._set_led("off")
        self._led_idle_timer.stop()
        self._log(tr("Device disconnected."))

    @Slot()
    def _toggle_grabacion(self) -> None:
        if self._btn_grabar.isChecked():
            self._iniciar_grabacion()
        else:
            self._detener_grabacion()

    def _iniciar_grabacion(self) -> None:
        save_dir = self._edit_dir.text().strip() or "."

        self._reset_buffers()
        self._marker_events.clear()
        self._total_samples = 0
        for pool in self._marker_lines:
            for line in pool:
                line.hide()
        self._reset_y_scales()

        n = self._n_channels
        labels = self._active_labels()
        for i, lbl in enumerate(labels):
            self._settings.setValue(f"adquisicion/label_{i}", lbl)

        if self._combo_device_type.currentIndex() == 0:
            device = create_device(
                BACKEND_BITALINO,
                mac=self._edit_mac.text().strip(),
                fs=FS,
                channels=list(range(n)),
            )
        else:
            device = create_device(
                BACKEND_ARDUINO,
                port=self._combo_port.currentText().strip(),
                fs=FS,
                n_channels=n,
            )
        self._settings.setValue("adquisicion/auto_detect", self._chk_auto.isChecked())
        self._settings.setValue("adquisicion/onset_k", self._spin_k.value())
        self._worker = AcquisitionWorker(
            device=device,
            save_dir=save_dir,
            sensor_labels=labels,
            auto_detect=self._chk_auto.isChecked(),
            onset_k=self._spin_k.value(),
        )
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.log.connect(self._log)
        self._worker.error.connect(self._on_error)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.marker_added.connect(self._on_marker_added)
        self._worker.start()
        self._render_timer.start()
        # The watchdog starts in _on_data_ready after the first sample is read;
        # not here, so it does not fire during device.open() (can take ~3 s).

        self._btn_grabar.setText(tr("Stop recording"))
        self._btn_conectar.setEnabled(False)
        self._lbl_estado.setText(tr("Status: recording…"))
        self._combo_etiqueta.setEnabled(True)
        self._btn_marcar.setEnabled(True)
        self._shortcut_m.setEnabled(True)
        self._set_auto_controls_enabled(False)
        self._log(tr("Press M to quickly add a marker with the selected label."))

    def _detener_grabacion(self) -> None:
        self._watchdog_timer.stop()
        self._render_timer.stop()
        if self._worker:
            self._worker.stop()
        self._btn_grabar.setText(tr("Start recording"))
        self._btn_grabar.setChecked(False)
        self._btn_conectar.setEnabled(True)
        self._lbl_estado.setText(tr("Status: connected (ready to record)"))
        self._combo_etiqueta.setEnabled(False)
        self._btn_marcar.setEnabled(False)
        self._shortcut_m.setEnabled(False)
        self._set_auto_controls_enabled(True)

    # ------------------------------------------------------------------
    # Worker slots
    # ------------------------------------------------------------------

    @Slot(dict)
    def _on_data_ready(self, data: dict) -> None:
        # Start the watchdog on the first received sample (not before, so it
        # does not fire during device.open(), which can take up to 3 s on Arduino).
        if not self._watchdog_timer.isActive():
            self._watchdog_timer.start()
        # data_ready carries one array per channel; append each to its buffer.
        raw = data["raw_mv"]
        filt = data["filtered"]
        env = data["envelope"]
        for c in range(min(len(raw), MAX_CHANNELS)):
            self._buf_raw[c].extend(raw[c].tolist())
            self._buf_filt[c].extend(filt[c].tolist())
            self._buf_env[c].extend(env[c].tolist())
        if raw:
            self._total_samples += len(raw[0])
        self._new_data = True
        # Green LED: there is traffic. The timer will set it back to yellow if
        # no new block arrives within LED_IDLE_MS ms.
        self._set_led("ok")
        self._led_idle_timer.start()

    def _refresh_plots(self, force: bool = False) -> None:
        """Called every 33 ms by _render_timer. Draws only if there is new data
        (or if `force`, e.g. when changing the stacking gain)."""
        if not self._new_data and not force:
            return
        self._new_data = False

        n = min(self._n_visible, MAX_POINTS)
        # X axis in seconds relative to the start of the visible window (all
        # buffers have the same length, so it is computed only once).
        t = np.arange(n) / FS

        # In stacked mode (2 channels) raw/filtered are drawn shifted to their
        # lane and scaled by the gain: displayed = baseline + gain·signal.
        stacked_raw = self._is_stacked(0)
        stacked_filt = self._is_stacked(1)

        for c in range(self._n_channels):
            arr_raw = np.array(list(self._buf_raw[c]))[-n:]
            arr_filt = np.array(list(self._buf_filt[c]))[-n:]
            arr_env = np.array(list(self._buf_env[c]))[-n:]
            if stacked_raw:
                arr_raw = self._lane_baseline(0, c) + self._y_gain[0] * arr_raw
            if stacked_filt:
                arr_filt = self._lane_baseline(1, c) + self._y_gain[1] * arr_filt
            self._curves_raw[c].setData(t, arr_raw)
            self._curves_filt[c].setData(t, arr_filt)
            self._curves_env[c].setData(t, arr_env)

        # Reposition the marker lines: each event is placed according to how
        # many samples ago it occurred, within the visible window.
        win_s = n / FS
        visible = [
            win_s - (self._total_samples - tiempo * FS) / FS
            for tiempo, _label in self._marker_events
            if 0 <= self._total_samples - tiempo * FS <= n
        ]
        visible = visible[-MAX_MARKER_LINES:]
        for pool in self._marker_lines:
            for i, line in enumerate(pool):
                if i < len(visible):
                    line.setPos(visible[i])
                    line.show()
                elif line.isVisible():
                    line.hide()

    # ------------------------------------------------------------------
    # Markers
    # ------------------------------------------------------------------

    @Slot()
    def _on_marcar(self) -> None:
        etiqueta = self._combo_etiqueta.currentText()
        if etiqueta == tr("Other…"):
            text, ok = QInputDialog.getText(
                self, tr("Custom marker"),
                tr("Description (max. 60 characters):"),
            )
            if not ok or not text.strip():
                return
            etiqueta = text.strip()[:60].replace("\n", " ")
        if self._worker and self._worker.isRunning():
            self._worker.add_marker(etiqueta)

    @Slot()
    def _on_marcar_rapido(self) -> None:
        if not self._worker or not self._worker.isRunning():
            return
        etiqueta = self._combo_etiqueta.currentText()
        if etiqueta == tr("Other…"):
            etiqueta = tr("Other")
        self._worker.add_marker(etiqueta)

    @Slot(float, str)
    def _on_marker_added(self, tiempo: float, etiqueta: str) -> None:
        # The marker is reflected in the "Event log" (log).
        self._log(tr("Marker added: t={t:.1f} s — {label}").format(t=tiempo, label=etiqueta))
        # Record the event to draw it live over the plots.
        self._marker_events.append((tiempo, etiqueta))

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._err(msg)
        self._restaurar_controles()

    @Slot(str)
    def _on_finished(self, edf_path: str) -> None:
        self._restaurar_controles()
        if edf_path:
            self._log(tr("Recording finished. File: {path}").format(path=edf_path))

    def _restaurar_controles(self) -> None:
        self._btn_grabar.setChecked(False)
        self._btn_grabar.setText(tr("Start recording"))
        self._btn_conectar.setEnabled(True)
        self._lbl_estado.setText(tr("Status: connected (ready to record)"))
        self._combo_etiqueta.setEnabled(False)
        self._btn_marcar.setEnabled(False)
        self._shortcut_m.setEnabled(False)
        self._set_auto_controls_enabled(True)

    # ------------------------------------------------------------------
    # Vertical scale (▲▼ per plot)
    # ------------------------------------------------------------------

    def _y_zoom(self, idx: int, zoom_in: bool) -> None:
        """Adjust the vertical scale of plot `idx` by a factor of 1.5.

        In stacked mode (raw/filtered with 2 channels) it scales the data gain
        while keeping the lanes fixed; otherwise it scales the ViewBox.
        """
        factor = 1.5

        if self._is_stacked(idx):
            gain = self._y_gain[idx]
            new_gain = gain / factor if zoom_in else gain * factor
            if new_gain < 0.01 or new_gain > 100.0:
                return
            self._y_gain[idx] = new_gain
            self._set_calib_ticks(idx)
            self._refresh_plots(force=True)
            return

        pw = self._plots_widgets[idx]
        accum = self._y_accum[idx]

        if zoom_in:
            new_accum = accum / factor
            if new_accum < 0.01:
                return
            vb = pw.getViewBox()
            ymin, ymax = vb.viewRange()[1]
            centro = (ymin + ymax) / 2
            half = (ymax - ymin) / 2 / factor
            pw.setYRange(centro - half, centro + half, padding=0)
        else:
            new_accum = accum * factor
            if new_accum > 100.0:
                return
            vb = pw.getViewBox()
            ymin, ymax = vb.viewRange()[1]
            centro = (ymin + ymax) / 2
            half = (ymax - ymin) / 2 * factor
            pw.setYRange(centro - half, centro + half, padding=0)

        self._y_accum[idx] = new_accum

    def _reset_y_scales(self) -> None:
        """Restore the vertical scale of the three plots to their initial state."""
        self._y_accum = [1.0, 1.0, 1.0]
        self._y_gain = [1.0, 1.0, 1.0]
        # Envelope: never stacked, direct initial range.
        self._plot_env.setYRange(*self._y_ranges_init[2], padding=0)
        # Raw/filtered: the mode (stacked or overlaid) sets range and annotations.
        self._apply_stacking_mode()

    # ------------------------------------------------------------------
    # Time scale (sliding window)
    # ------------------------------------------------------------------

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        """◀▶ — double the visible window (less detail, more context)."""
        nueva = min(self._n_visible * 2, MAX_POINTS)
        nueva = max(nueva, int(0.5 * FS))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        """▶◀ — halve the visible window (more detail)."""
        nueva = max(self._n_visible // 2, int(0.5 * FS))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva = MAX_POINTS // factor
        nueva = max(nueva, int(0.5 * FS))
        self._n_visible = nueva
        self._update_ventana_label()

    def _sync_combo_zoom(self) -> None:
        """Update the combo so it reflects the current n_visible."""
        if MAX_POINTS <= 0:
            return
        factor_actual = MAX_POINTS / self._n_visible
        best_idx, best_diff = 0, float("inf")
        for i, f in enumerate(_ZOOM_FACTORS):
            d = abs(factor_actual - f)
            if d < best_diff:
                best_diff, best_idx = d, i
        self._combo_zoom.blockSignals(True)
        self._combo_zoom.setCurrentIndex(best_idx)
        self._combo_zoom.blockSignals(False)

        # Disable factors whose resulting window would be < 0.5 s
        model = self._combo_zoom.model()
        for i, f in enumerate(_ZOOM_FACTORS):
            n = MAX_POINTS // f
            item = model.item(i)
            if item:
                enabled = n >= int(0.5 * FS)
                item.setEnabled(enabled)

    def _update_ventana_label(self) -> None:
        segundos = self._n_visible / FS
        if segundos >= 1.0:
            self._lbl_ventana_info.setText(f"{segundos:.1f} {tr('s visible')}")
        else:
            self._lbl_ventana_info.setText(f"{segundos * 1000:.0f} {tr('ms visible')}")

    def _reset_all_scales(self) -> None:
        """Full reset: Y ranges + time window back to the initial state."""
        self._reset_y_scales()
        self._n_visible = 5 * FS
        self._sync_combo_zoom()
        self._update_ventana_label()

    # ------------------------------------------------------------------
    # Communication-status LED
    # ------------------------------------------------------------------

    def _set_led(self, state: str) -> None:
        """
        Set the communication LED.
        state: 'off'  → red    (disconnected)
               'idle' → yellow (connected, no traffic)
               'ok'   → green  (receiving data)
        """
        colors = {
            "off":  ("#C0392B", "#7B241C"),   # red
            "idle": ("#F1C40F", "#B7950B"),   # yellow
            "ok":   ("#27AE60", "#196F3D"),   # green
        }
        fill, border = colors.get(state, colors["off"])
        self._led.setStyleSheet(
            f"background-color: {fill};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
        )

    # ------------------------------------------------------------------
    # BITalino connection watchdog
    # ------------------------------------------------------------------

    @Slot()
    def _check_watchdog(self) -> None:
        """Check every 1 s that the worker keeps receiving samples."""
        if self._worker is None or not self._worker.isRunning():
            return
        # Only monitor once the worker is in its reading phase
        if not self._worker.is_streaming():
            return
        silencio = self._worker.time_since_last_sample()
        if silencio > self._watchdog_umbral_s:
            if silencio == float("inf") or silencio > 999:
                msg = tr("No data from the device — connection not established.")
            else:
                msg = tr(
                    "No data from the device for {s:.1f} s — forcing disconnection."
                ).format(s=silencio)
            self._err(msg)
            self._watchdog_timer.stop()
            self._worker.stop_forced()
            self._worker.wait(2000)
            self._desconectar()

    # ------------------------------------------------------------------
    # Cleanup on window close
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """
        Called by MainWindow.closeEvent before destroying the window.
        Stops timers, stops the worker (forced if necessary) and waits for it
        to finish to ensure the EDF is closed correctly.
        """
        self._watchdog_timer.stop()
        self._render_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.stop_forced()
            self._worker.wait(5000)
