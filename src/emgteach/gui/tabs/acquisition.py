"""
AcquisitionTab — tab 1: real-time EMG acquisition with BITalino.

Controls:
  - BITalino Bluetooth virtual COM port (persisted with QSettings)
  - Destination folder for the EDF (persisted with QSettings)
  - Connect / Disconnect button
  - Start / Stop recording button

Channels:
  - 1 or 2 simultaneous channels (e.g. agonist/antagonist), with an
    editable label per channel. Each channel is drawn overlaid in its own colour.

Visualisation (pyqtgraph):
  - Raw EMG signal
  - Envelope

The filtered signal (notch + band-pass) is still computed for the envelope
and written pipeline, but it is not shown on screen: for physiology students
the intermediate filtered trace is not relevant to their study.

Scale controls:
  - Vertical scale: ▲▼ buttons per plot (×1.5 factor, 0.01×–100× of the initial limits)
  - Time scale: factor dropdown + ◀▶ buttons (sliding window over the
    ring buffer; lets you see from 0.5 s up to MAX_POINTS/fs seconds)

The tab never blocks the UI: all acquisition runs in AcquisitionWorker (QThread).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSettings, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.apda import OnlineLoad
from emgteach.broadcast import BroadcastServer
from emgteach.devices import (
    BACKEND_ARDUINO,
    BACKEND_BITALINO,
    ArduinoDevice,
    create_device,
)
from emgteach.dsp import LiveQualityMonitor, process_offline
from emgteach.gui.widgets.help_button import add_help
from emgteach.gui.widgets.load_bar import LoadBar
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.gui.widgets.mvc_overlay import MvcOverlay
from emgteach.i18n import tr
from emgteach.io import (
    RecordingMetadata,
    list_edf_channels,
    list_edf_emg_channels,
    read_edf_mne,
)
from emgteach.modes import (
    DEFAULT_MODE,
    MODE_SINGLE,
    mode_channels,
    mode_fixed_labels,
    mode_protocol,
    mode_requires_calibration,
    mode_uses_acc,
    normalise_mode,
)
from emgteach.mvc import mvc_from_reps, mvc_ref_marker
from emgteach.phases import (
    CALIBRATION,
    PREPARATION,
    RECORDING,
    WARMUP,
    cal_end_marker,
    cal_start_marker,
    parse_phase_markers,
    phase_spans,
    prep_start_marker,
    rec_start_marker,
    warmup_start_marker,
)
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

# Guided MVC-calibration wizard timing.
MVC_TICK_MS = 100   # state-machine tick
MVC_READY_S = 3.0   # "get ready" countdown before each contraction
MVC_REST_S = 2.0    # relax pause between reps / muscles
#: Blocks of data (~10 per second) the armed session flow keeps trying for
#: before handing the calibration back to the operator.
MVC_FLOW_MAX_TRIES = 30
# The strongest-sustained window now lives in SignalProfile, so the
# acquisition and the analysis judge a reference by the same measure.

# Guided force-velocity: the opening MVC maximum is a *sustained* effort (a few
# seconds to reach the true maximum), whereas each loaded rep is a *quick lift*
# — the point is the shortening velocity, which a long isometric hold does not
# show (and the accelerometer barely registers). The per-load lift duration is
# taken from the plan dialog; the MVC hold is fixed here.
FV_MVC_HOLD_S = 3.0
# Longer recovery pause between the (maximal) MVC and the first loaded lift, so
# the subject recovers from the maximum and sets up the first load in peace.
FV_MVC_TO_LOADS_REST_S = 5.0

# Headroom applied to the live plots when they auto-scale after calibration:
# the envelope top is this multiple of the MVC reference (so >100 %MVC phasic
# bursts stay visible), the raw plot spans ±(peak × factor).
AUTOSCALE_ENV_FACTOR = 1.5
AUTOSCALE_RAW_FACTOR = 1.25

# Style per live signal-quality status code (green ok / red saturation /
# amber flat-disconnected).
_QUALITY_STYLES = {
    "ok": "color: #1a7f37; font-weight: bold;",
    "saturation": "color: #b00020; font-weight: bold;",
    "flat": "color: #b06a00; font-weight: bold;",
}

# Per-channel colour, consistent across the three plots: a colour always
# identifies the same sensor (blue = channel 1, red = channel 2).
_CHANNEL_COLORS = [(65, 105, 225), (214, 39, 40)]
_CHANNEL_COLOR_HEX = ["#4169E1", "#D62728"]
_CHANNEL_DEFAULT_LABELS = ["EMG1", "EMG2"]
#: What the empty boxes suggest, and what a recording gets when they are
#: left empty. A name a student can read back — «agonist», «antagonist» —
#: rather than a channel number; the anatomical one is still theirs to
#: type. Callables so tr() runs in the language of the moment.
_LABEL_HINTS = [lambda: tr("Agonist — e.g. FCR"), lambda: tr("Antagonist — e.g. ECR")]
_LABEL_FALLBACKS = [lambda: tr("Agonist"), lambda: tr("Antagonist")]
# Defaults used in earlier versions; they are migrated to the ones above if
# still stored in QSettings (this does not overwrite names chosen by the user,
# only the old defaults). One tuple of superseded defaults per channel.
_OLD_DEFAULT_LABELS = [("Canal 1", "EMG"), ("Canal 2", "EMG 2")]

#: The analogue input the accelerometer is wired to, as an index: A2. The
#: muscle takes A1. A convention the tab states rather than a setting it
#: offers (see the kinematics block of _apply_mode).
_ACC_INPUT = 1

# With 2 channels the raw plot stacks (one lane per channel) instead of
# overlapping. The mV axis is no longer absolute, so each lane shows reference
# ticks at 0/±_CALIB_MV·gain (an honest calibration that does not hide the
# signal). Real signal mV per stacking plot (0=raw); the envelope (1) never
# stacks.
_CALIB_MV = {0: 1.0}

# Default BITalino address (editable in the field). The lab's MAC is stable
# across PCs; BitalinoDevice resolves it to the local virtual COM port. The
# field also accepts an explicit COMx, or empty for autodetection.
DEFAULT_BITALINO_ADDR = "98:D3:91:FE:44:E4"

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
    #: Emitted with the path of the EDF just written. The other tabs pick it
    #: up so the recording does not have to be hunted for three times: what a
    #: student almost always wants is to analyse the one they just made.
    recording_saved = Signal(str)

    def __init__(self, logger: LoggerWidget, settings: QSettings, parent=None,
                 broadcast: BroadcastServer | None = None):
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
        self._buf_env = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(MAX_CHANNELS)
        ]
        # Optional BITalino accelerometer (A4): a single extra raw channel,
        # kept out of the EMG channel machinery (load monitor, MVC wizard,
        # stacking) and shown in its own auto-scaled plot.
        self._acc_enabled = self._settings.value(
            "adquisicion/acc", False, type=bool
        )
        # Whether the channel-config controls are currently editable (idle, not
        # recording). Used together with the ACC placement to gate the channel
        # count (MMG placement forces a single muscle).
        self._channel_controls_enabled = True
        self._buf_acc = deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
        # The live ACC plot has a stable ±1 g range (the accelerometer signal
        # uses the full normalised range); the ▲▼ buttons magnify around the
        # trace's current level. >1 zooms in.
        self._acc_zoom = 1.0
        self._new_data = False  # flag: there is new data to draw
        #: True while the plots show a finished recording instead of the
        #: live stream. The live refresh is a no-op then: it would redraw
        #: the ring buffer over the session on the next frame.
        self._revisando = False
        #: The pyqtgraph items the review added, to take back out again.
        self._revision_items: list = []

        # Events for drawing live lines: (time_s, label). The total number of
        # acquired samples places each marker within the sliding window.
        self._marker_events: list[tuple[float, str]] = []
        self._total_samples = 0

        # Live-load zone thresholds (% MVC). Default from the signal profile,
        # but adjustable in the UI once an MVC is calibrated and remembered
        # across sessions (QSettings). warning < danger is always enforced.
        self._load_warning = float(self._settings.value(
            "adquisicion/load_warning", self._profile.apda_warning_limit, type=float))
        self._load_danger = float(self._settings.value(
            "adquisicion/load_danger", self._profile.apda_danger_limit, type=float))
        if self._load_danger <= self._load_warning:
            self._load_danger = self._load_warning + 1.0

        # ── Online muscle-load monitor (live MVC) ──
        # Per-channel MVC reference (mV) from a quick calibration, an OnlineLoad
        # accumulator and a calibration buffer; the live bars update per block
        # and the static/median/peak readout on a slower timer.
        self._mvc_ref: list[float | None] = [None] * MAX_CHANNELS
        self._online: list[OnlineLoad] = [
            OnlineLoad(self._load_warning, self._load_danger)
            for _ in range(MAX_CHANNELS)
        ]
        # ── Guided MVC-calibration wizard (per-muscle, sequential) ──
        # A small state machine driven by a 100 ms tick and the live envelope
        # stream: for each active channel it runs a 3-2-1 countdown, a fixed
        # maximal-contraction window, then a relax pause, optionally repeated
        # (best of N). The reference is the best per-rep P95 of the envelope.
        self._mvc_active = False
        self._mvc_phase = ""          # "ready" | "contract" | "rest" | "done"
        self._mvc_muscle = 0
        self._mvc_rep = 0
        self._mvc_reps = 1
        self._mvc_bursts = 0
        self._mvc_elapsed = 0.0       # seconds spent in the current phase
        self._mvc_peak = 0.0          # running peak of the current contraction
        self._mvc_cur = 0.0           # current (recent) effort of the contraction
        self._mvc_cur_buf: list[float] = []                  # current rep envelope
        self._mvc_capture: list[list] = [[] for _ in range(MAX_CHANNELS)]
        self._mvc_rest_buf: list[float] = []
        #: The *other* channels' envelope during the current repetition, and the
        #: same accumulated per repetition. This is what tells a two-muscle
        #: montage apart from two electrode pairs reading the same muscle.
        self._mvc_cross_buf: dict[int, list[float]] = {}
        self._mvc_cross: list[dict[int, list]] = [{} for _ in range(MAX_CHANNELS)]
        #: Channels whose calibration did not look like a maximum.
        self._mvc_no_maximas: list[str] = []
        self._mvc_raw_peak = [0.0] * MAX_CHANNELS   # for post-calibration autoscale
        self._mvc_timer = QTimer(self)
        self._mvc_timer.setInterval(MVC_TICK_MS)
        self._mvc_timer.timeout.connect(self._mvc_tick)

        # The two-phase session. When the practical needs a calibration the
        # record button runs the whole flow — calibration, a preparation pause,
        # then the recording proper — and the acquisition never stops in
        # between, so the file is continuous and the phases are annotations in
        # it. `_mvc_flow_auto` is what tells the wizard it is part of that flow
        # rather than a calibration someone asked for in the middle of a
        # recording; only the flow writes PREP/REC, because only in the flow is
        # the calibration at the start of the file.
        #
        #: The practical this tab is set up for. apply_mode keeps it up to date,
        #: but it has to exist before anyone calls that — and _flow_needs_
        #: calibration reads it on every press of the record button.
        self._mode = DEFAULT_MODE
        self._mvc_flow_auto = False
        self._mvc_flow_pending = False    # start it on the first block of data
        #: Blocks of data seen while the flow was armed and could not start.
        #: The flow is a convenience; failing to run it must never leave the
        #: session with no way to calibrate at all.
        self._mvc_flow_tries = 0
        #: The calibration's verdict, carried into the preparation countdown.
        #: A weak calibration is the one result nobody must scroll past, and
        #: the countdown is what is on screen for the next five seconds.
        self._prep_aviso = ""
        self._prep_elapsed = 0.0
        self._prep_timer = QTimer(self)
        self._prep_timer.setInterval(MVC_TICK_MS)
        self._prep_timer.timeout.connect(self._prep_tick)
        # Floating guide drawn over the plots during the wizard.
        self._mvc_overlay = MvcOverlay(self)

        # Guided force-velocity acquisition wizard: steps through a list of
        # known loads, one short recording window each, auto-marking every
        # window with its load so the F-V study reads the loads directly. Shares
        # the floating overlay with the MVC wizard (they never run together).
        # Phases: an MVC maximum first (no load) — "mvc_ready"/"mvc_contract"/
        # "mvc_rest" — then, per load and per rep, a discrete contraction:
        # "ready" (prepare countdown) → "contract" (contract with this load) →
        # "rest", ending in "done".
        self._fv_active = False
        self._fv_phase = ""
        self._fv_loads: list[float] = []
        self._fv_idx = 0              # index into _fv_loads
        self._fv_rep = 0              # current repetition within the load
        self._fv_reps = 1             # contractions to perform per load
        self._fv_prep_s = 5.0         # "prepare" countdown before each contraction
        self._fv_window_s = 6.0       # duration of each contraction window
        self._fv_elapsed = 0.0        # seconds spent in the current phase
        self._fv_mvc_buf: list[float] = []   # envelope during the MVC maximum
        self._fv_mvc_peak = 0.0
        self._fv_mvc_cur = 0.0
        self._fv_timer = QTimer(self)
        self._fv_timer.setInterval(MVC_TICK_MS)
        self._fv_timer.timeout.connect(self._fv_tick)

        self._load_timer = QTimer(self)
        self._load_timer.setInterval(400)
        self._load_timer.timeout.connect(self._update_load_readout)

        # ---- Vertical-scale state (per plot: 0=raw, 1=env) ----
        # Initial Y ranges taken from the signal profile (restored in
        # _reset_y_scales). Changing modality = changing profile.
        self._y_ranges_init: list[tuple[float, float]] = [
            self._profile.ylim_raw,       # raw
            self._profile.ylim_envelope,  # envelope
        ]
        self._y_accum: list[float] = [1.0, 1.0]  # accumulated factor per plot
        # Per-plot data gain, used ONLY in stacked mode (2 channels) on the raw
        # plot: the ▲▼ zoom multiplies the signal while keeping the lanes fixed,
        # instead of scaling the ViewBox. Unused in 1-channel mode.
        self._y_gain: list[float] = [1.0, 1.0]

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

        # Classroom broadcast: re-streams the live monitor to student browsers
        # over the local network (the operator PC owns the single BITalino link).
        # Shared with the Analysis tab when given by MainWindow.
        self._broadcast = broadcast if broadcast is not None else BroadcastServer(parent=self)
        self._broadcast.clients_changed.connect(self._on_broadcast_clients)

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
        add_help(grp_config, "acq.device")
        cfg_outer = QVBoxLayout(grp_config)
        cfg_outer.setContentsMargins(6, 3, 6, 3)
        cfg_outer.setSpacing(3)

        # Row 1: device type + connection (COM port for both backends).
        # Wrapped in a named container so the basic UI level can hide the whole
        # row at once — hiding the individual widgets would leave their labels.
        self._box_device = QWidget()
        cfg_row1 = QHBoxLayout(self._box_device)
        cfg_row1.setContentsMargins(0, 0, 0, 0)
        cfg_row1.setSpacing(6)

        # Device-type combo. Both interchangeable backends are offered — the
        # BITalino (Bluetooth) and the Arduino + MyoWare 2.0 (USB) — matching
        # the documented, published feature set. BITalino is the default.
        self._combo_device_type = QComboBox()
        self._combo_device_type.addItem("BITalino (Bluetooth)")
        self._combo_device_type.addItem("Arduino + MyoWare 2.0 (USB)")
        saved_type = int(self._settings.value("adquisicion/device_type", 0))
        self._combo_device_type.setCurrentIndex(saved_type)
        self._combo_device_type.currentIndexChanged.connect(self._on_device_type_changed)
        # In the practicals that can only be done with the BITalino the
        # selector is hidden and this caption stands in for it, so the
        # address field beside it does not sit there unnamed.
        self._lbl_device_fixed = QLabel(tr("Device: BITalino"))
        self._lbl_device_fixed.setVisible(False)
        cfg_row1.addWidget(self._lbl_device_fixed)
        cfg_row1.addWidget(self._combo_device_type, stretch=1)

        # Conditional central area: COM port (BITalino) or COM selector (Arduino)
        # Wrapped in a QWidget so the content can change without rebuilding the layout
        self._widget_mac = QWidget()
        mac_inner = QHBoxLayout(self._widget_mac)
        mac_inner.setContentsMargins(0, 0, 0, 0)
        mac_inner.setSpacing(4)
        self._edit_mac = QLineEdit()
        self._edit_mac.setPlaceholderText("98:D3:91:FE:44:E4   ·   COM5   ·   (auto)")
        self._edit_mac.setToolTip(
            tr(
                "BITalino MAC address (recommended — stable on every PC), or an "
                "explicit COM port (e.g. COM5), or leave empty to autodetect. Pair "
                "the BITalino in Windows Bluetooth settings first. No PyBluez is used."
            )
        )
        self._edit_mac.setText(
            self._settings.value("adquisicion/port", DEFAULT_BITALINO_ADDR)
        )
        mac_inner.addWidget(self._edit_mac)
        btn_reset_mac = QPushButton(tr("Default"))
        btn_reset_mac.setFixedWidth(84)
        btn_reset_mac.setToolTip(
            tr("Restore default address ({addr})").format(addr=DEFAULT_BITALINO_ADDR)
        )
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
        # Shown only when the basic level reveals this row because no port has
        # been saved yet, so a first-time user knows it is a one-off step.
        self._lbl_first_setup = QLabel(tr("One-off setup"))
        self._lbl_first_setup.setStyleSheet("font-size: 9px; color: #1F4E79;")
        self._lbl_first_setup.setVisible(False)
        cfg_row1.addWidget(self._lbl_first_setup)
        cfg_outer.addWidget(self._box_device)

        # Row 2: destination folder + Browse
        cfg_row2 = QHBoxLayout()
        cfg_row2.setSpacing(6)
        # With a folder saved, the placeholder never shows, and the row was a
        # bare text box beside a Browse button: a field nobody could name.
        cfg_row2.addWidget(QLabel(tr("Output path and file:")))
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
        # Channel-count block in its own container: the basic level hides it
        # together with its label, keeping the per-channel names visible.
        self._box_nchan = QWidget()
        nchan_l = QHBoxLayout(self._box_nchan)
        nchan_l.setContentsMargins(0, 0, 0, 0)
        nchan_l.setSpacing(6)
        nchan_l.addWidget(QLabel(tr("Channels:")))
        self._combo_n_channels = QComboBox()
        self._combo_n_channels.addItem(tr("1 (single sensor)"))
        self._combo_n_channels.addItem(tr("2 (agonist / antagonist)"))
        # Capped: the second item is long, and left to size itself it starves
        # the channel-name boxes next to it. The full text stays in the popup.
        self._combo_n_channels.setMaximumWidth(150)
        self._combo_n_channels.setToolTip(
            tr("How many EMG sensors are being recorded.")
        )
        self._combo_n_channels.setCurrentIndex(self._n_channels - 1)
        self._combo_n_channels.currentIndexChanged.connect(self._on_n_channels_changed)
        nchan_l.addWidget(self._combo_n_channels)
        ch_row.addWidget(self._box_nchan)

        # Named container: a practical that fixes its channel names hides the
        # whole thing, caption included, rather than leaving "Labels:" over an
        # empty stretch of row.
        self._box_labels = QWidget()
        labels_row = QHBoxLayout(self._box_labels)
        labels_row.setContentsMargins(0, 0, 0, 0)
        labels_row.addWidget(QLabel(tr("Labels:")))
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
            stored = self._settings.value(f"adquisicion/label_{i}", "")
            # A stored default is not a name the operator gave: the box
            # starts empty, with a hint of what goes in it. «EMG1» in the
            # practical whose whole point is telling two muscles apart was
            # the wrong answer pre-filled.
            if stored in _OLD_DEFAULT_LABELS[i] or stored == _CHANNEL_DEFAULT_LABELS[i]:
                stored = ""
            edit.setText(stored)
            edit.setPlaceholderText(_LABEL_HINTS[i]())
            # Room for the 16 characters the EDF label allows: these are the
            # muscle names, the one thing on this row the student really reads.
            edit.setMinimumWidth(130)
            edit.textChanged.connect(self._on_label_changed)
            self._edit_labels.append(edit)
            labels_row.addWidget(edit, stretch=1)
        ch_row.addWidget(self._box_labels, stretch=1)
        # Whole accelerometer block in one container, shown only by the
        # kinematics mode. Its caption is a plain label so that hiding the
        # container takes it along.
        self._box_acc = QWidget()
        acc_l = QHBoxLayout(self._box_acc)
        acc_l.setContentsMargins(0, 0, 0, 0)
        acc_l.setSpacing(6)
        acc_l.addWidget(QLabel(tr("Accelerometer:")))
        # The mode decides whether the accelerometer is recorded, so this
        # checkbox is never shown: it exists to drive the slots that enable the
        # rest of the block, and is set from apply_mode. Leaving it on screen
        # would offer the user a way to contradict the mode they chose.
        self._chk_acc = QCheckBox(tr("ACC"))
        self._chk_acc.setVisible(False)
        self._chk_acc.setToolTip(
            tr(
                "Also record the BITalino accelerometer (A4) in its own plot and "
                "EDF channel. Useful to relate muscle activation to movement, "
                "flag motion artefacts, or show tremor. BITalino only."
            )
        )
        self._chk_acc.setChecked(bool(self._acc_enabled))
        self._chk_acc.toggled.connect(self._on_acc_toggled)
        acc_l.addWidget(self._chk_acc)   # hidden; drives the slots
        # Where the accelerometer is placed decides which analyses make sense
        # (muscle → MMG; moving segment → kinematics/tremor). Stored in the ACC
        # channel label so the Analysis tab knows.
        self._combo_acc_place = QComboBox()
        self._combo_acc_place.addItem(tr("on the muscle (MMG)"), "muscle")
        self._combo_acc_place.addItem(tr("on the moving segment (tremor)"), "limb")
        saved_place = self._settings.value("adquisicion/acc_placement", "muscle")
        self._combo_acc_place.setCurrentIndex(1 if saved_place == "limb" else 0)
        self._combo_acc_place.setEnabled(bool(self._acc_enabled))
        self._combo_acc_place.setToolTip(
            tr("Where the accelerometer is stuck — sets which ACC analyses apply.")
        )
        self._combo_acc_place.currentIndexChanged.connect(self._on_acc_place_changed)
        acc_l.addWidget(self._combo_acc_place)
        # The wiring is a convention, not a setting: the muscle on A1, the
        # accelerometer on A2. It used to be a selector with a «find it»
        # diagnostic beside it, and on the bench the diagnostic found nothing
        # while the convention was right all along.
        self._lbl_acc_wiring = QLabel(tr("Muscle on A1 · accelerometer on A2"))
        self._lbl_acc_wiring.setStyleSheet("color: #6B7580; font-size: 11px;")
        acc_l.addWidget(self._lbl_acc_wiring)
        # Which analogue input the accelerometer is wired to. The BITalino packs
        # enabled channels consecutively, so this must be the physical input;
        # it defaults to A4 but is configurable (see the channel diagnostic).
        self._combo_acc_channel = QComboBox()
        for idx in range(6):
            self._combo_acc_channel.addItem(f"A{idx + 1}", idx)
        saved_acc_ch = self._settings.value("adquisicion/acc_channel", _ACC_INPUT, type=int)
        self._combo_acc_channel.setCurrentIndex(
            saved_acc_ch if 0 <= saved_acc_ch < 6 else _ACC_INPUT
        )
        self._combo_acc_channel.setEnabled(bool(self._acc_enabled))
        self._combo_acc_channel.setToolTip(
            tr("Analogue input the accelerometer is connected to (default A4). "
               "Use \"Find ACC channel…\" if unsure.")
        )
        self._combo_acc_channel.currentIndexChanged.connect(
            self._on_acc_channel_changed
        )
        # Which analogue input the sensor is wired to, and the diagnostic that
        # finds it: one-off wiring details, like the port. Own container so the
        # advanced flag can hide them without touching the placement choice.
        self._box_acc_wiring = QWidget()
        wiring_l = QHBoxLayout(self._box_acc_wiring)
        wiring_l.setContentsMargins(0, 0, 0, 0)
        wiring_l.setSpacing(6)
        wiring_l.addWidget(QLabel(tr("ACC ch:")))
        wiring_l.addWidget(self._combo_acc_channel)
        # Diagnostic: find which analogue input the accelerometer really is on.
        self._btn_acc_diag = QPushButton(tr("Find ACC channel…"))
        self._btn_acc_diag.setEnabled(False)
        self._btn_acc_diag.setToolTip(
            tr("Read all six analogue inputs live to see which one responds when "
               "you tilt the accelerometer. Connect the BITalino first, and do "
               "not run it while recording.")
        )
        self._btn_acc_diag.clicked.connect(self._on_acc_diagnose)
        wiring_l.addWidget(self._btn_acc_diag)
        acc_l.addWidget(self._box_acc_wiring)
        acc_l.addStretch()
        cfg_outer.addLayout(ch_row)
        # The accelerometer gets its own line. Sharing one with the channel
        # names left both cramped, and the muscle names are what matter here.
        cfg_outer.addWidget(self._box_acc)

        # Row 4: the test identifier, written to the EDF+ header, sharing the
        # line with the classroom broadcast.
        # An identifier, and only that. The name used to be asked for here
        # and written into the EDF header as ``patientname``, which meant
        # every recording carried it out of the laboratory — into the marking
        # pile, into whatever is shared with a colleague, into an archive. It
        # is called a *test* identifier rather than a student code because
        # that is what it names: one student's recording, a pair's, a whole
        # bench's, or the third attempt of the same person.
        self._edit_student_code = QLineEdit()
        self._edit_student_code.setFixedWidth(120)
        self._edit_student_code.setPlaceholderText(tr("e.g. bench 3, attempt 2"))
        self._edit_student_code.setToolTip(tr(
            "Goes into the EDF header and the report. One student, a pair, "
            "a bench or a repeat — whatever tells this recording apart."
        ))
        self._edit_student_code.setText(
            self._settings.value("adquisicion/student_code", "")
        )
        self._edit_student_code.textChanged.connect(
            lambda v: self._settings.setValue("adquisicion/student_code", v)
        )
        # No protocol field. It asked the operator to type what the
        # application already knew — the practical is chosen at the top of the
        # window — and let the header disagree with the mode it was recorded
        # in. It is written from the mode now; see modes.mode_protocol().

        # Classroom broadcast — students follow on their phone browser — on
        # the same line as the identifier. Named container: the basic level
        # hides the whole row, status label included.
        self._box_aula = QWidget()
        aula_row = QHBoxLayout(self._box_aula)
        aula_row.setContentsMargins(0, 0, 0, 0)
        aula_row.setSpacing(6)
        aula_row.addWidget(QLabel(tr("Test identifier:")))
        aula_row.addWidget(self._edit_student_code)
        aula_row.addSpacing(14)
        self._chk_aula = QCheckBox(tr("Broadcast to phones (in the laboratory)"))
        self._chk_aula.setToolTip(
            tr(
                "Serve a read-only live view over the local network so students "
                "can follow on their phone/tablet browser (no install). One "
                "device drives the BITalino; the others just watch."
            )
        )
        self._chk_aula.toggled.connect(self._on_toggle_broadcast)
        aula_row.addWidget(self._chk_aula)
        self._btn_copy_url = QPushButton(tr("Copy link"))
        self._btn_copy_url.setToolTip(
            tr(
                "Copy the follower link to the clipboard, e.g. to email it to "
                "the students. The link only works for this session: stopping "
                "the broadcast invalidates it."
            )
        )
        self._btn_copy_url.setVisible(False)
        self._btn_copy_url.clicked.connect(self._copy_broadcast_url)
        aula_row.addWidget(self._btn_copy_url)
        self._btn_aula_qr = QPushButton(tr("QR"))
        self._btn_aula_qr.setToolTip(
            tr("Show a QR code students can scan to open the follower page.")
        )
        self._btn_aula_qr.clicked.connect(self._on_aula_qr)
        self._btn_aula_qr.setEnabled(False)
        aula_row.addWidget(self._btn_aula_qr)
        self._lbl_aula = QLabel("")
        self._lbl_aula.setStyleSheet("font-size: 11px; color: #1F4E79; font-weight: bold;")
        self._lbl_aula.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        aula_row.addWidget(self._lbl_aula, stretch=1)
        cfg_outer.addWidget(self._box_aula)

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
        add_help(grp_control, "acq.control")
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
        # The way out of a guided procedure — the calibration, the
        # force-velocity plan — before it ends on its own. Shown only while
        # one runs; Esc does the same from anywhere on the tab. On the bench
        # there was no way out but to wait for the six efforts to pass.
        self._btn_cancelar_guia = QPushButton(tr("Cancel guide (Esc)"))
        self._btn_cancelar_guia.setVisible(False)
        self._btn_cancelar_guia.setToolTip(
            tr("Stop the guided procedure now; the recording goes on."))
        self._btn_cancelar_guia.clicked.connect(self._cancelar_guiado)
        ctrl_layout.addWidget(self._btn_cancelar_guia)
        atajo_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        atajo_esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        atajo_esc.activated.connect(self._cancelar_guiado)

        self._led = QLabel()
        self._led.setFixedSize(16, 16)
        self._led.setToolTip(tr("Device communication status"))
        ctrl_layout.addWidget(self._led)
        self._lbl_estado = QLabel(tr("Status: disconnected"))
        ctrl_layout.addWidget(self._lbl_estado)
        ctrl_layout.addStretch()

        # Live signal-quality indicator (updated per acquired block).
        self._lbl_calidad = QLabel("")
        self._lbl_calidad.setToolTip(
            tr("Live signal quality: saturation or a flat (disconnected) signal.")
        )
        self._lbl_calidad.setVisible(False)
        ctrl_layout.addWidget(self._lbl_calidad)
        self._quality_monitor: LiveQualityMonitor | None = None

        row_actions.addWidget(grp_control, stretch=1)

        # — Muscle load (live MVC), between Control and Markers —
        row_actions.addWidget(self._build_load_panel(), stretch=2)

        # LED idle timer
        self._led_idle_timer = QTimer(self)
        self._led_idle_timer.setSingleShot(True)
        self._led_idle_timer.setInterval(LED_IDLE_MS)
        self._led_idle_timer.timeout.connect(lambda: self._set_led("idle"))
        self._set_led("off")

        # — Event markers —
        #
        # Marking by hand during the recording is gone. It was never used on
        # the bench: the recording runs faster than anyone can label it, and
        # the honest place to name a stretch is afterwards, over a signal you
        # can see. What is left is the detection the application does by
        # itself — a checkbox and its threshold — and a short list of what it
        # has found, so the operator can see it working without reading the
        # log. With the box unticked no marks are written at all.
        #
        # The row that went: the preset label combo, the MARK button, the
        # Delete button and the M shortcut. Four controls and a scrolling list
        # for a feature nobody pressed, in the tab where vertical space is
        # worth the most: it is the one with the live plots in it.
        grp_markers = QGroupBox(tr("Event markers"))
        add_help(grp_markers, "acq.markers")
        markers_outer = QVBoxLayout(grp_markers)
        markers_outer.setContentsMargins(6, 3, 6, 3)
        markers_outer.setSpacing(4)
        markers_layout = QHBoxLayout()
        markers_layout.setSpacing(6)

        self._box_autoonset = QWidget()
        auto_l = QHBoxLayout(self._box_autoonset)
        auto_l.setContentsMargins(0, 0, 0, 0)
        auto_l.setSpacing(6)
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
        auto_l.addWidget(self._chk_auto)
        # The sensitivity lives in a container of its own so the practicals
        # can hide it: a student does not know what k is and should not be
        # deciding it. The fine controls of the advanced practical show it.
        self._box_k = QWidget()
        k_l = QHBoxLayout(self._box_k)
        k_l.setContentsMargins(0, 0, 0, 0)
        k_l.setSpacing(6)
        k_l.addWidget(QLabel("k:"))
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
        k_l.addWidget(self._spin_k)
        auto_l.addWidget(self._box_k)
        markers_layout.addWidget(self._box_autoonset)
        markers_layout.addStretch()
        markers_outer.addLayout(markers_layout)
        # What k is, in the box and not only in the «?»: the help text
        # named it, the box did not show it, and a knob that is explained
        # but absent is worse than either. On its own line under the
        # controls, where it costs height and not width.
        self._lbl_k_explica = QLabel(tr("threshold = rest + k × noise (3 is usual)"))
        self._lbl_k_explica.setStyleSheet("font-size: 10px; color: #6B7580;")
        markers_outer.addWidget(self._lbl_k_explica)

        # The last two onsets found, so the detection is visibly working
        # without going to the log for it. Two lines: it is a sign of life,
        # not a table — the whole list is in the recording, and the analysis
        # is where it gets read.
        self._list_markers = QListWidget()
        self._list_markers.setFixedHeight(44)
        self._list_markers.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._list_markers.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list_markers.setToolTip(
            tr("The most recent onsets detected. They all travel in the EDF.")
        )
        markers_outer.addWidget(self._list_markers)

        row_actions.addWidget(grp_markers, stretch=1)

        root.addLayout(row_actions)

        # ── Plots + scale controls ──────────────────────────────
        grp_plots = QGroupBox(tr("Real-time EMG signal"))
        add_help(grp_plots, "acq.plots")
        self._grp_plots = grp_plots  # for positioning the floating MVC guide
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
        self._combo_zoom.activated.connect(self._on_combo_zoom_changed)
        row_tiempo.addWidget(self._combo_zoom)

        self._btn_tiempo_reducir = QToolButton()
        self._btn_tiempo_reducir.setText("▶◀")
        self._btn_tiempo_reducir.setToolTip(tr("Narrow the window (see less time, more detail)"))
        self._btn_tiempo_reducir.setStyleSheet(_TBTN_ST)
        self._btn_tiempo_reducir.setFixedSize(32, 26)
        self._btn_tiempo_reducir.clicked.connect(self._on_tiempo_reducir)
        row_tiempo.addWidget(self._btn_tiempo_reducir)

        # Written from the window that is actually set, not from the size of
        # the buffer. It opened saying "30 s visible" over a five-second
        # window, so the first press of ◀▶ appeared to *shrink* it — the
        # caption fell from 30 to 10 while the window doubled.
        self._lbl_ventana_info = QLabel()
        self._lbl_ventana_info.setStyleSheet("font-size: 8px; color: #444;")
        row_tiempo.addWidget(self._lbl_ventana_info)
        self._update_ventana_label()

        row_tiempo.addSpacing(12)
        self._lbl_legend = QLabel()
        self._lbl_legend.setStyleSheet("font-size: 9px; font-weight: bold;")
        self._lbl_legend.setToolTip(tr("Colour of each channel in the plots"))
        row_tiempo.addWidget(self._lbl_legend)

        row_tiempo.addStretch()

        # Kept as an attribute so the practicals can hide it with the ▲▼
        # sidebar: with the raw range on the device's own full scale and the
        # envelope auto-ranging, a student has nothing to reset.
        self._btn_reset_escala = QPushButton(tr("Reset scales"))
        self._btn_reset_escala.setFixedHeight(26)
        self._btn_reset_escala.setStyleSheet("font-size: 10px;")
        self._btn_reset_escala.setToolTip(
            tr("Restore Y ranges and time window to initial values")
        )
        self._btn_reset_escala.clicked.connect(self._reset_all_scales)
        row_tiempo.addWidget(self._btn_reset_escala)

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
        self._curves_env: list = []

        # Raw signal
        self._plot_raw = pg.PlotWidget(title=tr("Raw EMG signal (mV)"))
        # pyqtgraph rescales a small-valued axis by itself and labels it
        # «mV (x0.000)» with ticks 0–500 — what the envelope plot said on
        # every screen, and what no student can read as millivolts. The unit
        # is the unit; the ticks carry the decimals. Disabled *before* the
        # first setYRange: turned off afterwards, the ×1000 already chosen
        # stays — the axis only recomputes it while the option is on.
        self._plot_raw.getAxis("left").enableAutoSIPrefix(False)
        self._plot_raw.setYRange(*self._y_ranges_init[0])
        self._plot_raw.setLabel("left", "mV")
        self._plot_raw.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_raw.append(
                self._plot_raw.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=1))
            )
        # Equal stretch + a small minimum so the three plots share the height
        # (the ACC plot is not squeezed to a sliver) and stay aligned with their
        # ▲▼ sidebar slots, while still shrinking to fit the screen.
        self._plot_raw.setMinimumHeight(70)
        plots_col_vbox.addWidget(self._plot_raw, stretch=1)

        # Envelope
        # The title names what is drawn; how it is computed is a hover away.
        # «Envelope (5 Hz low-pass filter, causal with continuous state)» put
        # three terms the student has not met into the one line they read.
        self._plot_env = pg.PlotWidget(title=tr("Envelope (mV)"))
        self._plot_env.setToolTip(tr(
            "The rectified signal smoothed with a 5 Hz low-pass filter, "
            "computed as the samples arrive: it follows the level of "
            "activation."
        ))
        self._plot_env.getAxis("left").enableAutoSIPrefix(False)   # see above
        self._plot_env.setYRange(*self._y_ranges_init[1])
        self._plot_env.setLabel("left", "mV")
        self._plot_env.showGrid(x=True, y=True, alpha=0.3)
        for c in range(MAX_CHANNELS):
            self._curves_env.append(
                self._plot_env.plot(pen=pg.mkPen(color=_CHANNEL_COLORS[c], width=2))
            )
        self._plot_env.setMinimumHeight(70)
        plots_col_vbox.addWidget(self._plot_env, stretch=1)

        # Accelerometer (A4) — an auto-scaled extra plot, shown only when the
        # ACC checkbox is on. It is deliberately kept out of the ▲▼ scale
        # machinery and the EMG channel logic (single, self-scaling channel).
        self._plot_acc = pg.PlotWidget(
            title=tr("Accelerometer (normalised g)")
        )
        self._plot_acc.setLabel("left", "g")
        self._plot_acc.showGrid(x=True, y=True, alpha=0.3)
        self._plot_acc.setYRange(-1.0, 1.0, padding=0)
        self._curve_acc = self._plot_acc.plot(
            pen=pg.mkPen(color="#2ca02c", width=1)
        )
        self._plot_acc.setVisible(bool(self._acc_enabled))
        self._plot_acc.setMinimumHeight(70)
        plots_col_vbox.addWidget(self._plot_acc, stretch=1)

        # Reusable pool of vertical lines for the event markers, one collection
        # per plot (repositioned on each refresh according to the sliding
        # window; orange, like in the Analysis tab).
        marker_pen = pg.mkPen(color=(230, 126, 34), width=1, style=Qt.PenStyle.DashLine)
        self._marker_lines: list[list] = []
        for pw in (self._plot_raw, self._plot_env):
            pool = []
            for _ in range(MAX_MARKER_LINES):
                line = pg.InfiniteLine(angle=90, movable=False, pen=marker_pen)
                line.hide()
                pw.addItem(line, ignoreBounds=True)
                pool.append(line)
            self._marker_lines.append(pool)

        # Stacked-mode annotations (2 channels), only on the raw plot: a
        # horizontal baseline per channel (its "zero") and the muscle label
        # next to each lane. The calibration is presented as reference ticks on
        # the axis (see _set_calib_ticks). Hidden in 1-channel mode.
        self._baselines: dict[int, list] = {}
        self._lane_labels: dict[int, list] = {}
        for idx, pw in ((0, self._plot_raw),):
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

        # Build the ▲▼ buttons in the sidebar (one slot per plot). Each slot has
        # stretch=1 so it spans the height of its plot; the ACC slot is shown or
        # hidden together with the ACC plot so the buttons stay aligned with
        # their plot whether there are two plots (raw+env) or three (+ACC).
        from PySide6.QtCore import Qt as _Qt

        self._plots_widgets = [self._plot_raw, self._plot_env]

        def _make_zoom_slot(label_txt, on_up, on_down, up_tip, down_tip):
            slot = QWidget()
            slot_vbox = QVBoxLayout(slot)
            slot_vbox.setContentsMargins(0, 0, 0, 0)
            slot_vbox.setSpacing(1)
            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(32, 18)
            btn_up.setStyleSheet(_BTN_ST)
            btn_up.setToolTip(up_tip)
            btn_up.clicked.connect(on_up)
            lbl = QLabel(label_txt)
            lbl.setStyleSheet("font-size: 7px; color: #666;")
            lbl.setAlignment(_Qt.AlignmentFlag.AlignCenter)
            btn_dn = QToolButton()
            btn_dn.setText("▼")
            btn_dn.setFixedSize(32, 18)
            btn_dn.setStyleSheet(_BTN_ST)
            btn_dn.setToolTip(down_tip)
            btn_dn.clicked.connect(on_down)
            slot_vbox.addStretch()
            slot_vbox.addWidget(btn_up, alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(lbl, alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addWidget(btn_dn, alignment=_Qt.AlignmentFlag.AlignHCenter)
            slot_vbox.addStretch()
            sidebar_vbox.addWidget(slot, stretch=1)
            return slot

        labels = [tr("R"), tr("E")]   # button per plot: raw / envelope
        for i, lbl_txt in enumerate(labels):
            _make_zoom_slot(
                lbl_txt,
                lambda checked=False, idx=i: self._y_zoom(idx, zoom_in=True),
                lambda checked=False, idx=i: self._y_zoom(idx, zoom_in=False),
                tr("Zoom in (vertical) — {label}").format(label=lbl_txt),
                tr("Zoom out (vertical) — {label}").format(label=lbl_txt),
            )

        # ACC slot: its ▲▼ magnify/shrink the auto-ranged accelerometer trace.
        self._acc_sidebar_slot = _make_zoom_slot(
            tr("A"),
            lambda checked=False: self._acc_zoom_step(zoom_in=True),
            lambda checked=False: self._acc_zoom_step(zoom_in=False),
            tr("Zoom in (vertical) — accelerometer"),
            tr("Zoom out (vertical) — accelerometer"),
        )
        self._acc_sidebar_slot.setVisible(bool(self._acc_enabled))

        root.addWidget(grp_plots, stretch=1)

        # Update the combo so it reflects the initial n_visible
        self._sync_combo_zoom()

        # Show only the active channels and paint the legend
        self._apply_channel_visibility()
        self._update_legend()
        # Configure the plot mode (overlaid or stacked) according to the
        # persisted number of channels — with the raw range set to the saved
        # device's full scale first, which applies the stacking on its way.
        self._ajustar_rango_bruto_al_dispositivo(
            self._combo_device_type.currentIndex()
        )
        # Apply the ACC-placement channel-count constraint to the initial state
        # (MMG placement forces a single muscle).
        self._apply_acc_placement_constraints()

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
        """Restore the default BITalino address (the lab's MAC)."""
        self._edit_mac.setText(DEFAULT_BITALINO_ADDR)
        self._settings.setValue("adquisicion/port", DEFAULT_BITALINO_ADDR)

    @Slot(int)
    def _on_device_type_changed(self, index: int) -> None:
        """Show the COM-port field (BITalino) or the COM-port selector (Arduino)."""
        self._widget_mac.setVisible(index == 0)
        self._widget_arduino.setVisible(index == 1)
        self._ajustar_rango_bruto_al_dispositivo(index)

    def _ajustar_rango_bruto_al_dispositivo(self, index: int) -> None:
        """Draw the raw plot to the device's own full scale.

        The profile's ±3.3 mV predates the gain correction: a BITalino cannot
        exceed ±1.635 mV, so the trace lived in the middle half of the panel
        with dead space above and below it; the Arduino front end reaches
        ±12.5 mV and was clipped by the same number. The full scale is a
        property of the device, so it is read off the device class rather
        than kept as a second copy here.
        """
        from emgteach.devices.arduino import ArduinoDevice
        from emgteach.devices.bitalino import BitalinoDevice

        clase = BitalinoDevice if index == 0 else ArduinoDevice
        try:
            gain = getattr(clase, "_GAIN_EMG", None) or clase._GAIN
            amp = clase._V_REF / 2.0 * 1000.0 / gain
        except Exception:  # pragma: no cover — a backend without the constants
            amp = self._profile.ylim_raw[1]
        self._y_ranges_init[0] = (-amp, amp)
        if not (self._worker and self._worker.isRunning()):
            self._apply_stacking_mode()

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
        self._y_gain = [1.0, 1.0]
        self._apply_stacking_mode()
        self._bcast_config()

    @Slot()
    def _on_label_changed(self) -> None:
        for i, edit in enumerate(self._edit_labels):
            self._settings.setValue(f"adquisicion/label_{i}", edit.text())
        self._update_legend()
        if hasattr(self, "_load_name_labels"):
            labels = self._active_labels()
            for c in range(self._n_channels):
                self._load_name_labels[c].setText(labels[c])
        self._bcast_config()

    def _active_labels(self) -> list[str]:
        """Names of the active channels: the practical's, or the operator's.

        A practical that fixes its channel names answers here rather than by
        writing into the boxes. Writing into them looked simpler and was
        wrong twice over: the name stayed behind on the next practical — an
        agonist/antagonist recording came out labelled "Muscle" and "EMG2" —
        and it went through ``_on_label_changed`` into QSettings, so choosing
        the single-muscle practical once overwrote the muscle name the
        operator had saved.
        """
        fijas = mode_fixed_labels(self._mode)
        labels = []
        for i in range(self._n_channels):
            if i < len(fijas):
                labels.append(tr(fijas[i]))
                continue
            text = self._edit_labels[i].text().strip()
            # One muscle has no agonist: its generic name is «Muscle».
            if text:
                labels.append(text)
            elif self._n_channels == 1:
                labels.append(tr("Muscle"))
            else:
                labels.append(_LABEL_FALLBACKS[i]())
        return labels

    def _apply_channel_visibility(self) -> None:
        """Show only the widgets and curves of the active channels."""
        for i, edit in enumerate(self._edit_labels):
            edit.setVisible(i < self._n_channels)
        for c in range(MAX_CHANNELS):
            visible = c < self._n_channels
            self._curves_raw[c].setVisible(visible)
            self._curves_env[c].setVisible(visible)
        if hasattr(self, "_load_rows"):
            labels = self._active_labels()
            for c in range(MAX_CHANNELS):
                vis = c < self._n_channels
                self._load_rows[c].setVisible(vis)
                self._load_name_labels[c].setText(labels[c] if vis else "")

    def _update_legend(self) -> None:
        """The colour key, offered only where there are two curves to tell apart.

        With one channel it named the only trace on screen, in the colour that
        trace already is. With two it earns its place — but only because of the
        envelope plot: the raw plot writes each muscle's name inside its own
        lane, and the envelope overlays both curves with nothing naming them.
        """
        labels = self._active_labels()
        parts = [
            f'<span style="color:{_CHANNEL_COLOR_HEX[i]}">&#9679; {lbl}</span>'
            for i, lbl in enumerate(labels)
        ]
        self._lbl_legend.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        self._lbl_legend.setVisible(len(labels) > 1)
        # Keep the stacked-mode lane labels in sync.
        if hasattr(self, "_lane_labels"):
            self._refresh_lane_label_texts()

    # ------------------------------------------------------------------
    # Stacked mode (2 channels) on raw / filtered
    # ------------------------------------------------------------------

    def _is_stacked(self, idx: int) -> bool:
        """True if plot idx (0=raw) stacks 2 channels."""
        return self._n_channels == 2 and idx == 0

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
        for idx in (0,):
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
        plot according to the number of channels (1 = overlaid on zero, 2 = two
        stacked lanes). The envelope never stacks."""
        for idx in (0,):
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
        self._channel_controls_enabled = enabled
        for edit in self._edit_labels:
            edit.setEnabled(enabled)
        # ACC is only available on the BITalino backend and is fixed for the
        # duration of a recording.
        is_bitalino = self._combo_device_type.currentIndex() == 0
        self._chk_acc.setEnabled(enabled and is_bitalino)
        self._combo_acc_place.setEnabled(
            enabled and is_bitalino and self._acc_enabled
        )
        # The channel-count combo also depends on the ACC placement (MMG = 1).
        self._apply_acc_placement_constraints()

    @Slot(bool)
    def _on_acc_toggled(self, checked: bool) -> None:
        """Show/hide the accelerometer plot and remember the choice."""
        self._acc_enabled = bool(checked)
        self._settings.setValue("adquisicion/acc", self._acc_enabled)
        self._plot_acc.setVisible(self._acc_enabled)
        # Keep the ACC ▲▼ sidebar slot in sync with its plot so the raw/envelope
        # buttons stay aligned with their own plots.
        self._acc_sidebar_slot.setVisible(self._acc_enabled)
        self._combo_acc_place.setEnabled(self._acc_enabled)
        self._combo_acc_channel.setEnabled(self._acc_enabled)
        self._apply_acc_placement_constraints()
        self._update_fv_button()

    @Slot(int)
    def _on_acc_place_changed(self, _index: int) -> None:
        """Persist the ACC placement and apply its channel-count constraint."""
        self._settings.setValue(
            "adquisicion/acc_placement", self._combo_acc_place.currentData()
        )
        self._apply_acc_placement_constraints()
        self._update_fv_button()

    @Slot(int)
    def _on_acc_channel_changed(self, _index: int) -> None:
        """Persist which analogue input carries the accelerometer."""
        self._settings.setValue(
            "adquisicion/acc_channel", self._combo_acc_channel.currentData()
        )

    @Slot()
    def _on_acc_diagnose(self) -> None:
        """Open the analogue-channel diagnostic to locate the ACC's real input.

        Opens its own BITalino connection to all six analogue inputs, so it can
        only run while connected and not recording.
        """
        if self._worker and self._worker.isRunning():
            return
        if self._combo_device_type.currentIndex() != 0:
            return
        from emgteach.gui.widgets.channel_diagnostic_dialog import (
            ChannelDiagnosticDialog,
        )

        port = self._edit_mac.text().strip()

        def _make_device():
            return create_device(
                BACKEND_BITALINO, port=port, fs=FS,
                channels=[0, 1, 2, 3, 4, 5],
            )

        dlg = ChannelDiagnosticDialog(_make_device, self)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        if accepted and dlg.found_channel is not None:
            # Point the ACC at the analogue input the diagnostic identified.
            idx = self._combo_acc_channel.findData(dlg.found_channel)
            if idx >= 0:
                self._combo_acc_channel.setCurrentIndex(idx)
                self._log(
                    tr("Accelerometer set to A{n}.").format(
                        n=dlg.found_channel + 1
                    )
                )

    def _refresh_fv_config_label(self) -> None:
        """Show the last-used guided-F-V reps and loads next to the button."""
        loads = self._settings.value("adquisicion/fv_loads", "", type=str)
        reps = self._settings.value("adquisicion/fv_reps", 1, type=int)
        if loads:
            self._lbl_fv_config.setText(
                tr("{reps}× · loads: {loads} kg").format(reps=reps, loads=loads)
            )
        else:
            self._lbl_fv_config.setText(tr("(loads not set)"))

    def _update_fv_button(self) -> None:
        """Enable the guided force-velocity button when it can be launched.

        Available once a BITalino is connected with the accelerometer on (the
        wizard starts the recording itself if needed), whether idle or already
        recording, and while no other wizard is running. Placement is not
        gated — the plan dialog warns if the ACC is not on the moving segment.
        """
        connected = self._btn_conectar.isChecked()
        bitalino = self._combo_device_type.currentIndex() == 0
        busy = self._mvc_active or self._fv_active
        self._btn_fv_guided.setEnabled(
            connected and bool(self._acc_enabled) and bitalino and not busy
        )
        # The channel diagnostic opens its own connection, so only when idle
        # (connected but not recording) and not during a wizard.
        recording = bool(self._worker and self._worker.isRunning())
        self._btn_acc_diag.setEnabled(
            connected and bitalino and not recording and not busy
        )

    def _apply_acc_placement_constraints(self) -> None:
        """Force a single EMG channel when the accelerometer is on a muscle.

        An MMG accelerometer measures one muscle's vibration, so it can only be
        paired with one EMG channel; two channels would be ambiguous. The
        channel-count selector is therefore locked to 1 while the ACC is on and
        placed on the muscle, and restored otherwise.
        """
        mmg = self._acc_enabled and self._combo_acc_place.currentData() == "muscle"
        if mmg and self._combo_n_channels.currentIndex() != 0:
            self._combo_n_channels.setCurrentIndex(0)  # 1 channel
        self._combo_n_channels.setEnabled(
            self._channel_controls_enabled and not mmg
        )

    def _reset_buffers(self) -> None:
        """Clear every per-channel ring buffer back to silence."""
        for bufs in (self._buf_raw, self._buf_env):
            for buf in bufs:
                buf.clear()
                buf.extend([0.0] * MAX_POINTS)
        self._buf_acc.clear()
        self._buf_acc.extend([0.0] * MAX_POINTS)
        self._plot_acc.setYRange(-1.0, 1.0, padding=0)

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
            # Empty is allowed: BitalinoDevice autodetects the device. A MAC or
            # an explicit COM port are also accepted and resolved on open().
            desc = self._edit_mac.text().strip()
            self._settings.setValue("adquisicion/port", desc)
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
        self._update_fv_button()
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
        self._update_fv_button()
        self._log(tr("Device disconnected."))

    @Slot()
    def _toggle_grabacion(self) -> None:
        if self._btn_grabar.isChecked():
            self._iniciar_grabacion()
        else:
            self._detener_grabacion()

    def _iniciar_grabacion(self) -> None:
        # Ask where and under what name to save the EDF (same UX as the
        # "Save figure" dialogs), pre-filled with the destination folder and a
        # timestamped default name. Cancelling aborts the recording start.
        save_dir = self._edit_dir.text().strip() or "."
        default_name = f"emg_{datetime.now():%Y-%m-%d_%H-%M}.edf"
        ruta, _ = QFileDialog.getSaveFileName(
            self, tr("Save EDF recording as…"),
            str(Path(save_dir) / default_name),
            tr("EDF files (*.edf *.EDF)"),
        )
        if not ruta:
            self._btn_grabar.setChecked(False)
            return
        if not ruta.lower().endswith(".edf"):
            ruta += ".edf"
        save_path = ruta
        save_dir = str(Path(ruta).parent)
        self._edit_dir.setText(save_dir)
        self._settings.setValue("adquisicion/save_dir", save_dir)

        self._reset_buffers()
        self._marker_events.clear()
        self._list_markers.clear()
        self._total_samples = 0
        for pool in self._marker_lines:
            for line in pool:
                line.hide()
        self._reset_y_scales()

        n = self._n_channels
        labels = self._active_labels()
        for i, lbl in enumerate(labels):
            self._settings.setValue(f"adquisicion/label_{i}", lbl)

        # The accelerometer is BITalino-only; when on, the device appends an ACC
        # channel and the worker needs a matching trailing "ACC" label.
        use_acc = self._acc_enabled and self._combo_device_type.currentIndex() == 0
        # Encode the placement in the ACC channel label (ASCII, ≤16 chars) so
        # the Analysis tab can pick the right ACC analysis on load.
        acc_label = (
            "ACC (limb)"
            if self._combo_acc_place.currentData() == "limb"
            else "ACC (muscle)"
        )
        worker_labels = [*labels, acc_label] if use_acc else list(labels)

        if self._combo_device_type.currentIndex() == 0:
            # The EMG channels take the first analogue inputs, skipping the one
            # the accelerometer is on (they must not collide). So with the ACC
            # on A1, a single EMG channel lands on A2, etc.
            acc_ch = self._combo_acc_channel.currentData()
            if use_acc:
                emg_channels = [c for c in range(6) if c != acc_ch][:n]
            else:
                emg_channels = list(range(n))
            if use_acc:
                emg_ports = ", ".join(f"A{c + 1}" for c in emg_channels)
                self._log(tr(
                    "Channels: EMG on {emg}, accelerometer on A{acc}."
                ).format(emg=emg_ports, acc=acc_ch + 1))
            device = create_device(
                BACKEND_BITALINO,
                port=self._edit_mac.text().strip(),
                fs=FS,
                channels=emg_channels,
                acc=use_acc,
                acc_channel=acc_ch,
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
        metadata = RecordingMetadata(
            # Both fields carry the code: EDF+ writes 'X' into an empty
            # patientname, and a file whose patient block is 'X' with a
            # code beside it says less than one that says the code twice.
            student_name=self._edit_student_code.text().strip(),
            student_code=self._edit_student_code.text().strip(),
            protocol=mode_protocol(self._mode),
            equipment=device.name,
        )
        # Live quality check against the device's true physical rails.
        self._quality_monitor = LiveQualityMonitor(
            device.physical_min, device.physical_max
        )
        self._lbl_calidad.setVisible(True)
        self._worker = AcquisitionWorker(
            device=device,
            save_dir=save_dir,
            save_path=save_path,
            sensor_labels=worker_labels,
            auto_detect=self._chk_auto.isChecked(),
            onset_k=self._spin_k.value(),
            metadata=metadata,
        )
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.log.connect(self._log)
        self._worker.error.connect(self._on_error)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.marker_added.connect(self._on_marker_added)
        self._worker.start()
        self._write_pending_mvc_ref_markers()
        self._salir_revision()
        self._render_timer.start()
        # The watchdog starts in _on_data_ready after the first sample is read;
        # not here, so it does not fire during device.open() (can take ~3 s).

        self._btn_grabar.setText(tr("Stop recording"))
        self._btn_conectar.setEnabled(False)
        self._lbl_estado.setText(tr("Status: recording…"))
        self._bcast_status(True)
        self._set_auto_controls_enabled(False)
        # Live muscle-load monitor: ready to calibrate while recording.
        self._reset_load_monitor()
        self._update_fv_button()
        self._load_timer.start()

        # Armed here and fired on the first block of data: the device can take
        # seconds to open, and a countdown that starts before the samples do
        # measures no resting level to judge the calibration against.
        self._mvc_flow_pending = self._flow_needs_calibration()
        self._mvc_flow_tries = 0
        self._btn_calibrar.setEnabled(not self._mvc_flow_pending)
        # Said out loud, with the three things the answer depends on. Three
        # bench sessions came back with no calibration and no way to tell,
        # from the file alone, whether the flow had declined to arm or armed
        # and failed to start. One line here separates them.
        self._log(tr(
            "Session flow: practical={mode}, {n} channel(s), references={refs} "
            "→ calibrate first: {yes}."
        ).format(
            mode=self._mode, n=self._n_channels,
            refs=sum(1 for r in self._mvc_ref[: self._n_channels] if r),
            yes=self._mvc_flow_pending,
        ))
        if self._mvc_flow_pending:
            # Those seconds are the whole reason the button used to be
            # pressed by hand: say what is happening in them.
            self._mvc_info(tr(
                "Starting the session — the calibration begins as soon as the "
                "signal arrives."
            ))
            self._log(tr(
                "This practical calibrates first: waiting for the signal to "
                "start the session."
            ))

    def _detener_grabacion(self) -> None:
        # A session stopped in the middle of its own flow leaves a CAL span
        # with no end, which the reader drops: half a maximal effort is not
        # a maximal effort.
        self._mvc_flow_pending = False
        self._mvc_flow_tries = 0
        # Calibrating needs a recording in progress, so the button follows
        # the recording rather than being left wherever the flow put it.
        self._btn_calibrar.setEnabled(False)
        self._prep_timer.stop()
        self._watchdog_timer.stop()
        self._render_timer.stop()
        self._stop_load_monitor()
        self._bcast_status(False)
        if self._worker:
            self._worker.stop()
        self._btn_grabar.setText(tr("Start recording"))
        self._btn_grabar.setChecked(False)
        self._btn_conectar.setEnabled(True)
        self._lbl_estado.setText(tr("Status: connected (ready to record)"))
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
        # Samples are flowing, so the session's opening phase can begin. Armed
        # in _iniciar_grabacion; fired here so the wizard's first countdown has
        # a real resting level to measure.
        #
        # The flag is cleared by _iniciar_calibracion once it is past its
        # guards, not here. Clearing it before the call spends the session's
        # one chance on an attempt that may bounce — and when it did, the
        # recording came back with no calibration at all and the button left
        # disabled, which is a worse state than either outcome. Retrying on
        # the next block costs nothing: this runs ten times a second.
        if self._mvc_flow_pending and not self._mvc_active:
            self._iniciar_calibracion(auto_flow=True)
            if self._mvc_flow_pending:
                # It bounced. Retrying is nearly free, but not for ever: an
                # armed flow that never starts used to leave the Calibrate
                # button disabled with no calibration and no way to ask for
                # one, which is a worse outcome than either.
                self._mvc_flow_tries += 1
                if self._mvc_flow_tries >= MVC_FLOW_MAX_TRIES:
                    self._mvc_flow_pending = False
                    self._btn_calibrar.setEnabled(True)
                    self._mvc_info("")
                    self._log(tr(
                        "The session could not start the calibration on its "
                        "own. Press «Calibrate MVC» when you are ready — the "
                        "phases will be written just the same."
                    ))
        # data_ready carries one array per channel; append each to its buffer.
        # The filtered trace is still emitted by the worker (it feeds the
        # envelope) but is no longer displayed, so it is not buffered here.
        raw = data["raw_mv"]
        env = data["envelope"]
        # Fill the EMG channel buffers (bounded by the active EMG count, so the
        # trailing ACC column is never mistaken for a second muscle).
        for c in range(min(len(raw), self._n_channels, MAX_CHANNELS)):
            self._buf_raw[c].extend(raw[c].tolist())
            self._buf_env[c].extend(env[c].tolist())
        # The accelerometer, when present, is the column right after the EMG
        # channels; it feeds its own buffer/plot.
        if self._acc_enabled and len(raw) > self._n_channels:
            self._buf_acc.extend(raw[self._n_channels].tolist())
        # During the wizard's contraction window, track the raw peak so the
        # plots can auto-scale to this subject once calibration finishes.
        if self._mvc_active and self._mvc_phase == "contract":
            for c in range(min(len(raw), self._n_channels, MAX_CHANNELS)):
                if raw[c].size:
                    self._mvc_raw_peak[c] = max(
                        self._mvc_raw_peak[c], float(np.max(np.abs(raw[c])))
                    )
        if raw:
            self._total_samples += len(raw[0])
        self._new_data = True
        # Live signal-quality indicator (worst status across channels).
        if self._quality_monitor is not None and raw:
            self._update_quality(raw)
        # Live muscle-load monitor (calibration or per-block load update).
        self._process_load(env)
        # Re-broadcast to classroom followers (no-op if not running).
        self._bcast_live(env)
        # Green LED: there is traffic. The timer will set it back to yellow if
        # no new block arrives within LED_IDLE_MS ms.
        self._set_led("ok")
        self._led_idle_timer.start()

    def _update_quality(self, raw: list) -> None:
        """Show the worst per-channel quality status of the latest block."""
        assert self._quality_monitor is not None
        status = None
        for c in range(min(len(raw), self._n_channels)):
            s = self._quality_monitor.update(raw[c])
            # Prefer a problem status over "ok"; first problem wins.
            if s.code != "ok":
                status = s
                break
            status = s
        if status is None:
            return
        self._lbl_calidad.setText(status.message)
        self._lbl_calidad.setStyleSheet(_QUALITY_STYLES.get(status.code, ""))

    def _refresh_plots(self, force: bool = False) -> None:
        """Called every 33 ms by _render_timer. Draws only if there is new data
        (or if `force`, e.g. when changing the stacking gain)."""
        if self._revisando:
            # A finished recording is on the plots. The ring buffer holds
            # its last 30 seconds and would quietly replace it.
            return
        if not self._new_data and not force:
            return
        self._new_data = False

        if self._total_samples == 0:
            # Nothing has been acquired since the last clear, so there is
            # nothing to draw — and drawing anyway is not harmless. The ring
            # buffers are *filled* with zeros rather than emptied, so a redraw
            # here lays a flat line across the envelope plot and, stacked, one
            # along each lane's baseline. On a fresh start nobody sees them,
            # because no redraw is forced before the first samples arrive; on
            # «New session» one is, and the tab came back with lines across it.
            for curva in (*self._curves_raw, *self._curves_env, self._curve_acc):
                if curva is not None:
                    curva.setData([], [])
            # And the axis, said rather than implied. Coming out of the session
            # review the X range is the session's — forty seconds, ninety, as
            # long as it was — and what used to bring it back was auto-range
            # refitting itself around those phantom zeros. With nothing drawn
            # there is nothing to fit, so the empty tab would have kept the
            # last session's axis: the same "advancing over an empty canvas"
            # reported from the bench, arriving by the other door.
            #
            # And auto-range straight back on afterwards: setXRange turns it
            # off, which is the very thing that stranded the live view inside
            # the session's axis in the first place. The explicit range is only
            # what the empty tab shows; the first samples to arrive refit it.
            ventana = min(self._n_visible, MAX_POINTS) / FS
            for pw in (self._plot_raw, self._plot_env):
                pw.setXRange(0.0, ventana, padding=0)
                pw.enableAutoRange(axis="x")
            return

        n = min(self._n_visible, MAX_POINTS)
        # X axis in seconds relative to the start of the visible window (all
        # buffers have the same length, so it is computed only once).
        t = np.arange(n) / FS

        # In stacked mode (2 channels) the raw plot is drawn shifted to each
        # lane and scaled by the gain: displayed = baseline + gain·signal.
        stacked_raw = self._is_stacked(0)

        for c in range(self._n_channels):
            arr_raw = np.array(list(self._buf_raw[c]))[-n:]
            arr_env = np.array(list(self._buf_env[c]))[-n:]
            if stacked_raw:
                arr_raw = self._lane_baseline(0, c) + self._y_gain[0] * arr_raw
            self._curves_raw[c].setData(t, arr_raw)
            self._curves_env[c].setData(t, arr_env)

        if self._acc_enabled:
            arr_acc = np.array(list(self._buf_acc))[-n:]
            self._curve_acc.setData(t, arr_acc)

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
    # Review: the finished recording, on the plots that recorded it
    # ------------------------------------------------------------------

    #: One colour per kind of stretch. Muted on purpose — these sit *behind*
    #: the trace, and a shading that competes with the signal defeats the
    #: point of showing the signal.
    _COLORES_FASE: ClassVar[dict[str, tuple[int, int, int, int]]] = {
        WARMUP: (150, 150, 150, 45),
        CALIBRATION: (230, 126, 34, 55),
        PREPARATION: (120, 160, 200, 40),
        RECORDING: (60, 160, 90, 40),
    }

    def _mostrar_registro(self, edf_path: str) -> None:
        """Put the recording that has just finished on the plots, whole.

        Asked for from the bench: after stopping, being able to scroll back
        over what was just recorded without leaving the tab. The live plots
        show a thirty-second ring buffer, so the session is read back from the
        EDF rather than kept in memory — the file is the record of truth, it
        is already written and closed, and what is reviewed is then exactly
        what was saved, annotations included, instead of a parallel copy that
        could disagree with it.

        A failure here loses the review and nothing else: the recording is on
        disk and the analysis tab is untouched.
        """
        try:
            nombres = list_edf_emg_channels(edf_path)
            if not nombres:
                return
            señales = [read_edf_mne(edf_path, n) for n in nombres[:MAX_CHANNELS]]
            fs = float(señales[0]["sfreq"])
            if fs <= 0:
                return
        except Exception as exc:
            self._log(tr("The recording could not be shown for review: {err}")
                      .format(err=exc))
            return

        self._salir_revision()
        self._revisando = True

        n = len(señales[0]["emg_raw"])
        t = np.arange(n) / fs
        duracion = n / fs
        apilado = self._is_stacked(0)
        pico_raw = 0.0
        pico_env = 0.0
        for c, datos in enumerate(señales):
            crudo = np.asarray(datos["emg_raw"], dtype=np.float64)
            try:
                sobre = process_offline(crudo, fs)["emg_envelope"]
            except Exception:
                sobre = np.abs(crudo)
            pico_raw = max(pico_raw, float(np.max(np.abs(crudo))) if crudo.size else 0.0)
            pico_env = max(pico_env, float(np.max(sobre)) if sobre.size else 0.0)
            if apilado:
                crudo = self._lane_baseline(0, c) + self._y_gain[0] * crudo
            self._curves_raw[c].setData(t, crudo)
            self._curves_env[c].setData(t, sobre)
        for c in range(len(señales), MAX_CHANNELS):
            self._curves_raw[c].setData([], [])
            self._curves_env[c].setData([], [])
        # The lanes are named after the file being reviewed, not after the
        # label boxes: those still said «EMG1 / EMG2» while the shading beside
        # them read «FCR 1 … ECR 3», two names for the same muscle on one
        # screen. Restored from the boxes on the way back to live.
        for c, nombre in enumerate(nombres[:MAX_CHANNELS]):
            self._lane_labels[0][c].setText(f" {nombre}")

        # The accelerometer, when the session recorded one. Read by index
        # because it is not an EMG channel and carries its own units.
        if self._acc_enabled:
            try:
                todos = list_edf_channels(edf_path)
                acc = next((c for c in todos if c not in nombres), None)
                if acc is not None:
                    from emgteach.io import read_edf_pyedflib
                    # «emg_raw» is the reader's name for whatever channel it
                    # was asked for; under «signal» there was nothing, and
                    # the accelerometer's panel of the review stayed blank.
                    self._curve_acc.setData(
                        t, np.asarray(read_edf_pyedflib(
                            edf_path, todos.index(acc))["emg_raw"],
                            dtype=np.float64)[:n])
            except Exception:
                self._curve_acc.setData([], [])

        # A whole session is far more points than a live window; let pyqtgraph
        # decimate it for drawing, keeping the peaks, or panning crawls.
        for pw in (self._plot_raw, self._plot_env):
            pw.setDownsampling(auto=True, mode="peak")
            pw.setClipToView(True)
            pw.setXRange(0.0, duracion, padding=0.01)
        if not apilado and pico_raw > 0:
            self._plot_raw.setYRange(-1.15 * pico_raw, 1.15 * pico_raw, padding=0)
        if pico_env > 0:
            self._plot_env.setYRange(0.0, 1.15 * pico_env, padding=0)

        for pool in self._marker_lines:
            for line in pool:
                line.hide()

        tramos = phase_spans(
            parse_phase_markers(señales[0].get("markers", [])),
            duracion, channel_names=dict(enumerate(nombres)),
        )
        alto = 1.15 * pico_env if pico_env > 0 else 1.0
        for tramo in tramos:
            for pw in (self._plot_raw, self._plot_env):
                region = pg.LinearRegionItem(
                    values=(tramo.start_s, tramo.end_s), movable=False,
                    brush=pg.mkBrush(self._COLORES_FASE.get(
                        tramo.kind, (150, 150, 150, 40))),
                    pen=pg.mkPen(None),
                )
                region.setZValue(-10)      # behind the trace, always
                pw.addItem(region, ignoreBounds=True)
                self._revision_items.append((pw, region))
            texto = tramo.label or self._nombre_fase(tramo.kind)
            etiqueta = pg.TextItem(texto, anchor=(0, 0), color=(90, 90, 90))
            etiqueta.setPos(tramo.start_s, alto)
            self._plot_env.addItem(etiqueta, ignoreBounds=True)
            self._revision_items.append((self._plot_env, etiqueta))

        self._plot_raw.setTitle(tr("Recording just finished (review)"))
        self._plot_env.setTitle(tr("Envelope of the recording (review)"))
        self._log(tr(
            "Reviewing the recording: {dur:.1f} s. Drag to scroll, wheel to "
            "zoom. It goes back to live on the next recording."
        ).format(dur=duracion))

    def _nombre_fase(self, kind: str) -> str:
        """The word for a stretch of the session, for its label on the plot."""
        return {
            WARMUP: tr("warm-up"),
            CALIBRATION: tr("calibration"),
            PREPARATION: tr("get ready"),
            RECORDING: tr("recording"),
        }.get(kind, "")

    def _salir_revision(self) -> None:
        """Back to the live view: take the session and its shading off."""
        for pw, item in self._revision_items:
            try:
                pw.removeItem(item)
            except Exception:      # the plot was already torn down
                pass
        self._revision_items.clear()
        if not self._revisando:
            return
        self._revisando = False
        for pw in (self._plot_raw, self._plot_env):
            pw.setDownsampling(auto=False)
            pw.setClipToView(False)
            # Setting an explicit X range to show the session *turns auto-range
            # off*, and the live view has no range of its own — it relies on
            # auto-range to follow the sliding window. Left off, the next
            # recording drew its five seconds inside the ninety-two of the
            # session before it: a sliver of signal creeping across an empty
            # canvas. Reported from the bench in exactly those words.
            pw.enableAutoRange(axis="x")
        self._plot_raw.setTitle(tr("Raw EMG signal (mV)"))
        self._plot_env.setTitle(
            tr("Envelope (5 Hz low-pass filter, causal with continuous state)")
        )
        self._reset_all_scales()
        self._refresh_lane_label_texts()   # back to the label boxes' names
        self._new_data = True
        self._refresh_plots(force=True)
        # Re-enabling auto-range only says the axis *may* refit; pyqtgraph
        # queues the recomputation and, coming out of an explicit range, it
        # never arrives on its own. Without this the view stayed at the
        # session's ninety-two seconds however much live data went in.
        for pw in (self._plot_raw, self._plot_env):
            pw.getViewBox().updateAutoRange()

    def _apply_acc_range(self) -> None:
        """Set the live ACC plot's Y range: the full ±1 g by default, or — when
        magnified with ▲ — a smaller window centred on the trace's current
        level (so zooming in keeps the gravity-offset signal in view).

        The range is set only here (on zoom and on record start), never per
        frame, so the plot is stable: at rest it shows a flat line, and it
        deflects when the sensor moves — no auto-range flicker or drift.
        """
        if self._acc_zoom <= 1.0:
            self._plot_acc.setYRange(-1.0, 1.0, padding=0)
            return
        n = min(self._n_visible, MAX_POINTS)
        arr = np.array(list(self._buf_acc))[-n:]
        centre = float(np.mean(arr)) if arr.size else 0.0
        half = 1.0 / self._acc_zoom
        self._plot_acc.setYRange(centre - half, centre + half, padding=0)

    def _acc_zoom_step(self, zoom_in: bool) -> None:
        """Magnify (▲) or widen (▼) the live ACC plot via its sidebar buttons."""
        factor = 1.25 if zoom_in else 1 / 1.25
        self._acc_zoom = min(50.0, max(1.0, self._acc_zoom * factor))
        self._apply_acc_range()

    # ------------------------------------------------------------------
    # Muscle-load monitor (live MVC — Jonsson APDA)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Classroom broadcast (followers watch on their phone browser)
    # ------------------------------------------------------------------

    @Slot(bool)
    def _on_toggle_broadcast(self, checked: bool) -> None:
        if checked:
            if self._broadcast.start():
                url = self._broadcast.follower_url()
                self._lbl_aula.setText(tr("Students open:  {url}").format(url=url))
                self._btn_copy_url.setVisible(True)
                self._log(
                    tr("Classroom mode on — students can follow at {url}").format(url=url)
                )
                self._btn_aula_qr.setEnabled(True)
                self._bcast_config()
            else:
                self._chk_aula.setChecked(False)
                self._err(tr("Could not start classroom mode (port busy?)."))
        else:
            self._broadcast.stop()
            self._lbl_aula.setText("")
            self._btn_copy_url.setVisible(False)
            self._btn_aula_qr.setEnabled(False)
            self._log(tr("Classroom mode off — previous follower links are now invalid."))

    @Slot()
    def _copy_broadcast_url(self) -> None:
        if not self._broadcast.is_running():
            return
        QGuiApplication.clipboard().setText(self._broadcast.follower_url())
        self._log(tr("Follower link copied to the clipboard."))
        self._btn_copy_url.setText(tr("Copied ✓"))
        QTimer.singleShot(
            1500, lambda: self._btn_copy_url.setText(tr("Copy link"))
        )

    @Slot()
    def _on_aula_qr(self) -> None:
        """Show a scannable QR code of the follower URL in a small dialog."""
        if not self._broadcast.is_running():
            return
        url = self._broadcast.follower_url()
        pix = self._make_qr_pixmap(url)
        if pix is None:
            self._err(tr("QR code unavailable (the 'segno' library is missing)."))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Scan to follow the session"))
        lay = QVBoxLayout(dlg)
        img = QLabel()
        img.setPixmap(pix)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(img)
        cap = QLabel(url)
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cap.setStyleSheet("font-weight: bold; color: #1F4E79;")
        lay.addWidget(cap)
        hint = QLabel(tr("Point the phone camera at the code (same Wi-Fi network)."))
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        dlg.exec()

    @staticmethod
    def _make_qr_pixmap(url: str, scale: int = 8) -> QPixmap | None:
        """Render *url* as a QR-code QPixmap, or None if segno is unavailable."""
        try:
            import io

            import segno
        except ImportError:
            return None
        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="png", scale=scale, border=2)
        pix = QPixmap()
        pix.loadFromData(buf.getvalue(), "PNG")
        return pix

    @Slot(int)
    def _on_broadcast_clients(self, n: int) -> None:
        if self._broadcast.is_running():
            url = self._broadcast.follower_url()
            self._lbl_aula.setText(
                tr("Students open:  {url}   ·   {n} following").format(url=url, n=n)
            )

    def _bcast_config(self) -> None:
        self._broadcast.broadcast({
            "t": "config", "n": self._n_channels,
            "labels": self._active_labels(), "recording": self.is_recording(),
        })

    def _bcast_status(self, recording: bool) -> None:
        self._broadcast.broadcast({"t": "status", "recording": recording})

    def _bcast_live(self, env: list) -> None:
        """Push a downsampled envelope + the live %MVC load to followers."""
        if not self._broadcast.is_running():
            return
        env_out = []
        for c in range(self._n_channels):
            a = env[c] if c < len(env) else None
            if a is None or not len(a):
                env_out.append([])
                continue
            step = max(1, len(a) // 8)
            env_out.append([round(float(x), 4) for x in a[::step][:8]])
        self._broadcast.broadcast({"t": "data", "env": env_out})
        ch = []
        for c in range(self._n_channels):
            ol = self._online[c]
            active = bool(self._mvc_ref[c])
            ch.append({
                "active": active,
                "pct": round(ol.current, 1) if active else 0.0,
                "static": round(ol.static, 0), "median": round(ol.median, 0),
                "peak": round(ol.peak, 0), "zone": ol.status,
            })
        self._broadcast.broadcast({
            "t": "load", "warn": self._load_warning,
            "danger": self._load_danger, "ch": ch,
        })

    def _bcast_calib(self, active: bool, phase: str = "", title: str = "",
                     sub: str = "", count=None, secs=None,
                     progress=None, effort=None) -> None:
        if not self._broadcast.is_running():
            return
        self._broadcast.broadcast({
            "t": "calib", "active": active, "phase": phase, "title": title,
            "sub": sub, "count": count, "secs": secs,
            "progress": progress, "effort": effort,
        })

    def _build_load_panel(self) -> QGroupBox:
        """Live muscle-load box (sits between Control and Markers in the actions
        row): on a single line, the Calibrate button and — per active channel,
        side by side — a load bar (tiredness / fatigue zones) and its P10/P50/P90
        readout, with a status label at the end."""
        grp = QGroupBox(tr("Muscle load (live MVC)"))
        add_help(grp, "acq.load")
        row = QHBoxLayout(grp)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(8)

        # Left column: the MVC-calibration controls and, stacked below them, the
        # guided force-velocity controls — so the two guided flows read the same
        # way (a button plus its selection to the right).
        left_col = QVBoxLayout()
        left_col.setSpacing(2)

        mvc_row = QHBoxLayout()
        mvc_row.setSpacing(6)
        self._btn_calibrar = QPushButton(tr("Calibrate MVC"))
        self._btn_calibrar.setEnabled(False)
        self._btn_calibrar.setToolTip(
            tr("Guided MVC calibration: contract each muscle in turn at maximum "
               "when prompted; sets the reference for the live load monitor.")
        )
        self._btn_calibrar.clicked.connect(self._on_calibrar)
        mvc_row.addWidget(self._btn_calibrar)
        # «Best of 3» used to be a checkbox here, off by default. Repeating
        # the maximum and keeping the strongest is not an option: it is how a
        # maximum is measured at all — the first maximal effort of a session
        # is genuinely submaximal, and a single attempt has nothing to fall
        # back on. The protocol said to tick it; the application now does.
        mvc_row.addStretch()
        left_col.addLayout(mvc_row)

        # Its own box, with its own «?». The guided flow is the kinematics
        # practical's whole procedure, not a detail of the load monitor, and
        # the button's tooltip was the only place that said what it does —
        # every other thing on this tab is explained from a corner «?», and a
        # student who has learnt to look there found nothing here. The
        # kinematics practical shows the box; the other two hide it whole.
        self._box_fv_guided = QGroupBox(tr("Guided force-velocity acquisition"))
        add_help(self._box_fv_guided, "acq.fv")
        fv_row = QHBoxLayout(self._box_fv_guided)
        fv_row.setContentsMargins(6, 3, 6, 3)
        fv_row.setSpacing(6)
        self._btn_fv_guided = QPushButton(tr("Guided F-V…"))
        self._btn_fv_guided.setEnabled(False)
        self._btn_fv_guided.setToolTip(
            tr("Guided force-velocity acquisition: an MVC maximum first (no "
               "load), then a discrete 'contract with this load' prompt for "
               "every repetition of every load. Starts the recording for you "
               "and marks each contraction with its load so the force-velocity "
               "study reads them directly. Enable the accelerometer and connect "
               "the BITalino first.")
        )
        self._btn_fv_guided.clicked.connect(self._on_fv_guided)
        fv_row.addWidget(self._btn_fv_guided)

        # Deliberately never disabled: rehearsing is what you do *before* the
        # device is connected and the subject is holding a weight, so gating it
        # on the hardware would put it out of reach exactly when it is useful.
        self._btn_fv_rehearse = QPushButton(tr("Rehearse…"))
        self._btn_fv_rehearse.setToolTip(
            tr("It emulates the entire guided procedure with the same "
               "warnings, in the same order, with a synthetic record. Each "
               "step is explained and ends with the simulated "
               "force-velocity study.")
        )
        self._btn_fv_rehearse.clicked.connect(self._on_fv_rehearse)
        fv_row.addWidget(self._btn_fv_rehearse)

        # Shows the chosen reps and loads, mirroring "Best of 3" next to MVC.
        self._lbl_fv_config = QLabel("")
        self._lbl_fv_config.setStyleSheet("font-size: 9px; color: #555555;")
        self._refresh_fv_config_label()
        fv_row.addWidget(self._lbl_fv_config)
        fv_row.addStretch()
        left_col.addWidget(self._box_fv_guided)

        row.addLayout(left_col)

        # Adjustable warning / danger thresholds (% MVC). Disabled until an MVC
        # is calibrated; changing them updates the bars and the monitor live.
        self._box_thr = QWidget()
        thr_l = QHBoxLayout(self._box_thr)
        thr_l.setContentsMargins(0, 0, 0, 0)
        thr_l.setSpacing(2)
        lbl_thr_w = QLabel(tr("Warning"))
        lbl_thr_w.setStyleSheet("font-size: 9px; color: #E67E22;")
        thr_l.addWidget(lbl_thr_w)
        self._spin_warning = QSpinBox()
        self._spin_warning.setRange(1, 99)
        # Apply only when the edit is committed (Enter / focus-out / arrows),
        # not on every keystroke — otherwise the warning<danger auto-correction
        # makes the two boxes fight while you are still typing a number.
        self._spin_warning.setKeyboardTracking(False)
        self._spin_warning.setSuffix(" %")
        self._spin_warning.setFixedWidth(58)
        self._spin_warning.setValue(round(self._load_warning))
        self._spin_warning.setEnabled(False)
        self._spin_warning.setToolTip(
            tr("Load (% MVC) where the warning (tiredness) zone starts.")
        )
        self._spin_warning.valueChanged.connect(self._on_thresholds_changed)
        thr_l.addWidget(self._spin_warning)
        lbl_thr_d = QLabel(tr("Danger"))
        lbl_thr_d.setStyleSheet("font-size: 9px; color: #cc0000;")
        thr_l.addWidget(lbl_thr_d)
        self._spin_danger = QSpinBox()
        self._spin_danger.setRange(2, 100)
        self._spin_danger.setKeyboardTracking(False)
        self._spin_danger.setSuffix(" %")
        self._spin_danger.setFixedWidth(58)
        self._spin_danger.setValue(round(self._load_danger))
        self._spin_danger.setEnabled(False)
        self._spin_danger.setToolTip(
            tr("Load (% MVC) where the danger (fatigue) zone starts.")
        )
        self._spin_danger.valueChanged.connect(self._on_thresholds_changed)
        thr_l.addWidget(self._spin_danger)
        row.addWidget(self._box_thr)

        self._load_rows: list[QWidget] = []
        self._load_name_labels: list[QLabel] = []
        self._load_bars: list[LoadBar] = []
        self._load_readouts: list[QLabel] = []
        for c in range(MAX_CHANNELS):
            roww = QWidget()
            rr = QHBoxLayout(roww)
            rr.setContentsMargins(0, 0, 0, 0)
            rr.setSpacing(4)
            name = QLabel()
            name.setStyleSheet(
                f"font-size: 9px; font-weight: bold; color: {_CHANNEL_COLOR_HEX[c]};"
            )
            bar = LoadBar()
            bar.set_zones(self._load_warning, self._load_danger)
            bar.setMinimumWidth(120)
            readout = QLabel("")
            readout.setStyleSheet("font-size: 9px;")
            rr.addWidget(name)
            rr.addWidget(bar, stretch=1)
            rr.addWidget(readout)
            self._load_rows.append(roww)
            self._load_name_labels.append(name)
            self._load_bars.append(bar)
            self._load_readouts.append(readout)
            row.addWidget(roww, stretch=1)

        self._lbl_load_info = QLabel("")
        self._lbl_load_info.setStyleSheet("font-size: 9px; color: #555555;")
        row.addWidget(self._lbl_load_info)
        return grp

    @Slot()
    def _on_calibrar(self) -> None:
        """The «Calibrate MVC» button: a calibration asked for on its own."""
        self._iniciar_calibracion(auto_flow=False)

    def _iniciar_calibracion(self, *, auto_flow: bool = False) -> None:
        """Launch the guided, per-muscle MVC-calibration wizard.

        ``auto_flow`` marks the calibration as the opening phase of a session
        started from the record button. Only then do the preparation pause and
        the ``REC start`` annotation follow it: a calibration run in the middle
        of a recording sits in the middle of the file, and saying the recording
        starts *there* would throw away everything before it.
        """
        if not (self._worker and self._worker.isRunning()):
            if not auto_flow:
                self._log(tr(
                    "The calibration needs a recording in progress."
                ))
            return
        if self._mvc_active or self._fv_active:
            if not auto_flow:
                self._log(tr("Another guided procedure is already running."))
            return
        self._mvc_active = True
        self._btn_cancelar_guia.setVisible(True)
        # Pressing «Calibrate MVC» while the session flow is armed is the
        # same calibration the flow was about to run, so it adopts the flow
        # rather than replacing it. Without this the button wins the race —
        # the device takes seconds to open and nothing visible happens in
        # the meantime, so pressing it is the natural thing to do — and the
        # file comes back with its calibration marked and no recording
        # phase, which is exactly what the flow exists to write.
        self._mvc_flow_auto = auto_flow or self._mvc_flow_pending
        self._mvc_flow_pending = False
        # Always three: the first maximal effort of a session is genuinely
        # submaximal, and with one attempt there is nothing to fall back on.
        self._mvc_reps = 3
        # And then three brief maximal squeezes. A held maximum peaks at its
        # start and settles on a plateau; the task's brief efforts reach the
        # peak, and on the bench they came out at 135 % of a plateau-based
        # reference. A squeeze reaches the peak alone, and the reference is
        # the best 0.2 s across all six, so it is a maximum the task cannot
        # exceed. Reps 1–3 are the held ones, 4–6 the squeezes.
        self._mvc_bursts = self._profile.mvc_bursts
        self._mvc_muscle = 0
        self._mvc_rep = 0
        self._mvc_capture = [[] for _ in range(MAX_CHANNELS)]
        self._mvc_cross = [{} for _ in range(MAX_CHANNELS)]
        self._mvc_no_maximas = []
        self._mvc_raw_peak = [0.0] * MAX_CHANNELS   # for post-calibration autoscale
        self._mvc_ref = [None] * MAX_CHANNELS
        self._set_thresholds_enabled(False)
        self._btn_calibrar.setEnabled(False)
        self._btn_grabar.setEnabled(False)
        self._update_fv_button()          # disabled while the MVC wizard runs
        for bar in self._load_bars:
            bar.reset()
        self._log(
            tr("Calibration started as the session's opening phase.")
            if self._mvc_flow_auto
            else tr("Calibration started on its own.")
        )
        self._reposition_mvc_overlay()
        self._mvc_enter_warmup()
        self._mvc_timer.start()

    def _set_thresholds_enabled(self, enabled: bool) -> None:
        """Enable/disable the warning/danger spin-boxes (active only once an
        MVC is calibrated)."""
        self._spin_warning.setEnabled(enabled)
        self._spin_danger.setEnabled(enabled)

    @Slot()
    def _on_thresholds_changed(self) -> None:
        """Apply the warning/danger spin-boxes to the bars and the monitor.

        Keeps ``warning < danger`` (nudging the danger value up if needed),
        persists both to QSettings and refreshes the readout colours."""
        self._spin_warning.blockSignals(True)
        self._spin_danger.blockSignals(True)
        w = self._spin_warning.value()
        d = self._spin_danger.value()
        if d <= w:
            d = min(100, w + 1)
            self._spin_danger.setValue(d)
            if d <= w:                       # warning was at the top (99/100)
                w = d - 1
                self._spin_warning.setValue(w)
        self._spin_warning.blockSignals(False)
        self._spin_danger.blockSignals(False)

        self._load_warning, self._load_danger = float(w), float(d)
        self._settings.setValue("adquisicion/load_warning", self._load_warning)
        self._settings.setValue("adquisicion/load_danger", self._load_danger)
        for c in range(MAX_CHANNELS):
            self._online[c].warning_limit = self._load_warning
            self._online[c].danger_limit = self._load_danger
            self._load_bars[c].set_zones(self._load_warning, self._load_danger)
            self._load_bars[c].set_value(self._online[c].current,
                                         active=bool(self._mvc_ref[c]))
        self._update_load_readout()

    def _process_load(self, env: list) -> None:
        """Per-block hook from _on_data_ready: feed the MVC wizard during a
        contraction window, otherwise update the live %MVC monitor."""
        n_ch = min(len(env), self._n_channels)
        if self._mvc_active:
            if self._mvc_phase == "contract":
                self._mvc_feed(env)
            elif self._mvc_phase == "ready":
                # The countdown is rest by construction, so it costs nothing to
                # measure what this muscle looks like when it is doing nothing.
                # Without that there is no way to tell a maximal contraction
                # from a distracted one: both are just a number of millivolts.
                self._mvc_rest_feed(env)
            return
        if self._fv_active:
            if self._fv_phase == "mvc_contract":
                self._fv_mvc_feed(env)
            return
        if all(r is None for r in self._mvc_ref[:n_ch]):
            return
        for c in range(n_ch):
            ref = self._mvc_ref[c]
            if not ref:
                continue
            pct = env[c] / ref * 100.0
            self._online[c].add(pct)
            # The bar tracks the instantaneous load (this block ~100 ms) so it
            # follows the contraction force; the P10/P50/P90 readout below uses
            # the running OnlineLoad statistics.
            inst = float(np.mean(pct)) if pct.size else 0.0
            self._load_bars[c].set_value(inst, active=True)

    # -- Guided MVC-calibration wizard ---------------------------------------

    def _mvc_info(self, text: str) -> None:
        """Show the wizard's current instruction (small info label)."""
        self._lbl_load_info.setText(text)

    def _mvc_label(self) -> str:
        """Label of the muscle being calibrated (channel label, never a name)."""
        labels = self._active_labels()
        c = self._mvc_muscle
        return labels[c] if c < len(labels) else tr("Muscle {n}").format(n=c + 1)

    def _mvc_enter_warmup(self) -> None:
        """A few easy contractions before the first maximal one.

        The first maximal effort of a session is genuinely submaximal, and
        best-of-three cannot rescue it: on the bench the three flexor
        repetitions came out at 57 %, 68 % and 100 % of each other, still
        rising at the third, so the best of them was still not a maximum.
        Recorded and marked rather than waited out off the clock — the
        acquisition never stops, and the file stays continuous.
        """
        self._mvc_phase = "warmup"
        self._mvc_elapsed = 0.0
        self._write_phase_marker(warmup_start_marker())

    def _mvc_enter_ready(self) -> None:
        self._mvc_phase = "ready"
        self._mvc_elapsed = 0.0
        self._mvc_cur_buf = []
        self._mvc_cross_buf = {}
        self._mvc_peak = 0.0

    @Slot()
    def _mvc_tick(self) -> None:
        self._mvc_elapsed += MVC_TICK_MS / 1000.0
        label = self._mvc_label()
        # Reps 1..n are the held maxima; the ones after are the brief
        # squeezes, counted on their own so the subject knows which they are
        # doing.
        breve = self._mvc_rep >= self._mvc_reps
        if breve:
            rep = tr(" (brief {i}/{n})").format(
                i=self._mvc_rep - self._mvc_reps + 1, n=self._mvc_bursts)
        elif self._mvc_reps > 1:
            rep = tr(" (rep {i}/{n})").format(i=self._mvc_rep + 1, n=self._mvc_reps)
        else:
            rep = ""
        if self._mvc_phase == "warmup":
            total = self._profile.warmup_s
            cuenta = max(1, int(np.ceil(total - self._mvc_elapsed)))
            titulo = tr("Warm up first")
            detalle = tr(
                "Two or three easy contractions of each muscle. The first "
                "maximal effort of a session is never the strongest one."
            )
            self._mvc_overlay.show_ready(titulo, cuenta, detalle)
            self._mvc_info(tr("Warming up: {n}").format(n=cuenta))
            self._bcast_calib(True, "warmup", titulo, detalle, count=cuenta)
            if self._mvc_elapsed >= total:
                self._mvc_enter_ready()
            return

        if self._mvc_phase == "ready":
            if self._mvc_elapsed <= MVC_TICK_MS / 1000.0:
                self._mvc_rest_buf = []      # one baseline per repetition
            count = max(1, int(np.ceil(MVC_READY_S - self._mvc_elapsed)))
            detalle = (
                tr("Make a single, brief muscle contraction (a twitch) with "
                   "the greatest force you can.")
                if breve else
                tr("Push as hard as you can when the count reaches 0 — against s"
                   "omething that cannot move, such as the underside of the table, not against a hand")
            )
            self._mvc_overlay.show_ready(
                tr("Get ready — {label}{rep}").format(label=label, rep=rep),
                count,
                detalle,
            )
            self._mvc_info(
                tr("Get ready — {label}{rep}: {n}").format(label=label, rep=rep, n=count)
            )
            self._bcast_calib(
                True, "ready",
                tr("Get ready — {label}{rep}").format(label=label, rep=rep),
                detalle, count=count,
            )
            if self._mvc_elapsed >= MVC_READY_S:
                self._mvc_phase = "contract"
                self._mvc_elapsed = 0.0
                self._mvc_cur_buf = []
                self._mvc_cross_buf = {}
                self._mvc_peak = 0.0
                self._mvc_cur = 0.0
                # The span opens here and closes in _mvc_finish_rep. Between
                # the two is the effort itself, which is what the analysis has
                # to be able to recompute the reference from.
                self._write_phase_marker(
                    cal_start_marker(self._mvc_muscle, self._mvc_rep + 1)
                )
        elif self._mvc_phase == "contract":
            # A held maximum lasts the calibration time; a squeeze, a second
            # and a half: long enough to reach the peak, too short for the
            # plateau.
            dur = self._profile.mvc_burst_s if breve else self._profile.apda_calib_s
            secs_left = max(0.0, dur - self._mvc_elapsed)
            progress = min(1.0, self._mvc_elapsed / dur)
            effort = (self._mvc_cur / self._mvc_peak) if self._mvc_peak > 0 else 0.0
            titulo = (
                tr("Make a single, brief contraction of {label} with the "
                   "greatest force you can{rep}")
                if breve else tr("Contract {label} at maximum!{rep}")
            ).format(label=label, rep=rep)
            self._mvc_overlay.show_contract(titulo, secs_left, progress, effort)
            self._mvc_info(
                tr(
                    "Contract {label} as hard as you can!  ({s:.0f} s)  "
                    "peak {pk:.2f} mV"
                ).format(label=label, s=secs_left, pk=self._mvc_peak)
            )
            self._bcast_calib(
                True, "contract", titulo,
                secs=secs_left, progress=progress, effort=effort,
            )
            if self._mvc_elapsed >= dur:
                self._mvc_finish_rep()
        elif self._mvc_phase == "rest":
            sub = (
                tr("Get ready for the next repetition")
                if self._mvc_rep > 0
                else tr("Next muscle: {label}").format(label=label)
            )
            self._mvc_overlay.show_relax(sub)
            self._mvc_info(tr("Relax…"))
            self._bcast_calib(True, "rest", tr("Relax"), sub)
            if self._mvc_elapsed >= MVC_REST_S:
                self._mvc_enter_ready()

    def _mvc_rest_feed(self, env: list) -> None:
        """Accumulate the active muscle's envelope while it is at rest."""
        c = self._mvc_muscle
        if c < len(env) and env[c].size:
            self._mvc_rest_buf.extend(env[c].tolist())

    def _mvc_check_is_a_maximum(self, c: int, ref: float) -> None:
        """Say so when the calibration did not capture a maximal contraction.

        A reference only a little above the muscle's own resting level is not a
        maximum, and it is not a harmless one: every later % MVC is wrong by
        the same factor, the live load bars sit in the red from the first
        contraction, and the analysis reports several hundred per cent. The
        wizard cannot know whether the subject pushed, but it can compare what
        it captured against what the same muscle looked like doing nothing a
        few seconds earlier.
        """
        rest = np.asarray(self._mvc_rest_buf, dtype=float)
        if not rest.size or ref <= 0:
            return
        nivel = float(np.percentile(rest, 95))
        ratio = ref / nivel if nivel > 0 else float("inf")
        if ratio >= self._profile.mvc_min_rest_ratio:
            return
        labels = self._active_labels()
        name = labels[c] if c < len(labels) else str(c + 1)
        self._mvc_no_maximas.append(name)
        self._log(tr(
            "⚠ «{muscle}»: the calibration reached {ref:.3f} mV, only {ratio:.1f}× "
            "its resting level. That is not a maximal contraction — every % MVC "
            "from now on will be too high by that factor. Calibrate again."
        ).format(muscle=name, ref=ref, ratio=ratio))

    def _mvc_feed(self, env: list) -> None:
        """Accumulate the active muscle's envelope during its contraction.

        And the other channels' at the same time: what they read while this
        muscle is at its maximum is the only measurement the session makes of
        whether the montage is separating two muscles at all.
        """
        c = self._mvc_muscle
        if c < len(env) and env[c].size:
            self._mvc_cur_buf.extend(env[c].tolist())
            self._mvc_cur = float(np.mean(env[c]))
            self._mvc_peak = max(self._mvc_peak, float(np.max(env[c])))
        for k in range(min(len(env), self._n_channels)):
            if k != c and env[k].size:
                self._mvc_cross_buf.setdefault(k, []).extend(env[k].tolist())

    def _mvc_finish_rep(self) -> None:
        # Closed before anything else: a span with no end is dropped when the
        # file is read back, which is exactly right for a recording stopped
        # mid-effort but would be wrong for one that finished.
        self._write_phase_marker(
            cal_end_marker(self._mvc_muscle, self._mvc_rep + 1)
        )
        self._mvc_capture[self._mvc_muscle].append(
            np.asarray(self._mvc_cur_buf, dtype=float)
        )
        for k, muestras in self._mvc_cross_buf.items():
            self._mvc_cross[self._mvc_muscle].setdefault(k, []).append(
                np.asarray(muestras, dtype=float)
            )
        self._mvc_rep += 1
        if self._mvc_rep < self._mvc_reps + self._mvc_bursts:
            self._mvc_phase = "rest"          # rest, then repeat this muscle
            self._mvc_elapsed = 0.0
            return
        self._mvc_compute_muscle(self._mvc_muscle)
        self._mvc_rep = 0
        if self._mvc_muscle + 1 < self._n_channels:
            self._mvc_muscle += 1             # rest, then next muscle
            self._mvc_phase = "rest"
            self._mvc_elapsed = 0.0
        else:
            self._mvc_finish_all()

    def _mvc_compute_muscle(self, c: int) -> None:
        window = max(1, round(self._profile.mvc_peak_window_s * FS))
        ref = mvc_from_reps(
            self._mvc_capture[c], self._profile.mvc_percentile,
            window_samples=window,
        )
        self._mvc_ref[c] = ref if ref > 0 else None
        self._mvc_check_is_a_maximum(c, ref)
        self._online[c].reset()
        self._load_bars[c].set_value(0.0, active=bool(self._mvc_ref[c]))
        self._write_mvc_ref_marker(c)

    def _flow_needs_calibration(self) -> bool:
        """Whether pressing record has to run the calibration first.

        A practical that compares two muscles has nothing to compare without
        both references, so the record button runs the whole session rather
        than leaving the calibration to be remembered. Already calibrated in
        this session and it does not run again: the references are still good
        and a second one would only cost the subject three more maximal
        efforts, which is the fastest way to make the next contraction weaker.
        """
        return (
            mode_requires_calibration(self._mode)
            and not any(self._mvc_ref[: self._n_channels])
        )

    def _write_phase_marker(self, label: str) -> None:
        """Write a phase annotation, if there is an open recording to write to.

        Calibrating without recording is still allowed — the reference lands
        in the next file as a cached ``MVC ref`` — and then there is no span
        to mark. Silently doing nothing is the right answer: the phases
        describe a file, and in that case there is no file yet.
        """
        if self._worker and self._worker.isRunning():
            self._worker.add_marker(label)

    def _mvc_enter_prep(self) -> None:
        """Between the two phases: a countdown, recorded but not analysed.

        The acquisition is deliberately not stopped here. Stopping would force
        the file to represent a gap — which EDF+ handles badly — or two
        files to be written and then merged. A few seconds of signal nobody
        looks at costs some kilobytes and saves all of that.
        """
        if not (self._worker and self._worker.isRunning()):
            self._log(tr(
                "The recording ended before the preparation phase could "
                "start, so this file has no recording phase marked."
            ))
            self._mvc_overlay.hide_overlay()
            self._bcast_calib(False)
            return
        self._worker.add_marker(prep_start_marker())
        self._prep_elapsed = 0.0
        self._prep_timer.start()

    @Slot()
    def _prep_tick(self) -> None:
        total = self._profile.prep_countdown_s
        self._prep_elapsed += MVC_TICK_MS / 1000.0
        cuenta = max(1, int(np.ceil(total - self._prep_elapsed)))
        titulo = tr("Get ready to record")
        detalle = self._prep_aviso or tr(
            "The recording starts when the count reaches 0. "
            "The calibration is already saved."
        )
        self._mvc_overlay.show_ready(titulo, cuenta, detalle)
        self._mvc_info(tr("Get ready to record: {n}").format(n=cuenta))
        self._bcast_calib(True, "prep", titulo, detalle, count=cuenta)
        if self._prep_elapsed < total:
            return

        self._prep_timer.stop()
        self._worker.add_marker(rec_start_marker())
        self._mvc_overlay.hide_overlay()
        self._bcast_calib(False)
        self._mvc_info(tr("Recording — the calibration is behind you."))
        self._log(tr(
            "Recording phase started. Everything before this point — the "
            "calibration and this pause — stays out of the analysis."
        ))

    def _write_mvc_ref_marker(self, c: int) -> None:
        """Carry this channel's MVC reference into the EDF as an annotation.

        Without it the reference lives only in memory and dies with the
        session, so the offline analysis — which starts from the file — has no
        way of knowing what each muscle's maximum was, and can only fall back
        to millivolts. Same device as the guided force-velocity wizard uses for
        its loads.
        """
        ref = self._mvc_ref[c]
        if ref and self._worker and self._worker.isRunning():
            self._worker.add_marker(mvc_ref_marker(c, float(ref)))

    def _write_pending_mvc_ref_markers(self) -> None:
        """Write every reference calibrated *before* the recording started.

        Calibrating first and recording afterwards is a normal order of work —
        the wizard even enables the record button when it finishes — and in
        that order there was no open file to annotate. Dumping the known
        references as the recording opens is what keeps that path from
        producing a file the analysis cannot read in % MVC.
        """
        for c in range(self._n_channels):
            self._write_mvc_ref_marker(c)

    def _mvc_crosstalk(self) -> list[tuple[str, str, float]]:
        """How much each channel read while a *different* muscle was calibrated.

        One entry per ordered pair, ``(muscle calibrated, other channel,
        % of that other channel's own reference)``, measured exactly the way
        the reference itself was: strongest sustained window, best of the
        repetitions. Comparing an instantaneous peak against a sustained
        reference would inflate the number by itself.

        The figure answers the question the two live bars cannot: whether the
        second channel is following its own muscle or the first one's. It is
        never zero — a maximal effort recruits the antagonist to hold the joint
        — so it is reported as a measurement and only warned about above
        ``mvc_crosstalk_pct``.
        """
        window = max(1, round(self._profile.mvc_peak_window_s * FS))
        labels = self._active_labels()

        def name(i: int) -> str:
            return labels[i] if i < len(labels) else str(i + 1)

        out: list[tuple[str, str, float]] = []
        for c in range(self._n_channels):
            for k, reps in sorted(self._mvc_cross[c].items()):
                ref_k = self._mvc_ref[k]
                if not ref_k or k >= self._n_channels:
                    continue
                nivel = mvc_from_reps(
                    reps, self._profile.mvc_percentile, window_samples=window,
                )
                if nivel > 0:
                    out.append((name(c), name(k), 100.0 * nivel / ref_k))
        return out

    def _mvc_finish_all(self) -> None:
        self._mvc_timer.stop()
        self._mvc_active = False
        self._mvc_phase = "done"
        self._btn_cancelar_guia.setVisible(False)
        ok = [c for c in range(self._n_channels) if self._mvc_ref[c]]
        self._prep_aviso = ""
        self._btn_calibrar.setEnabled(True)
        self._update_fv_button()          # re-enabled once the MVC wizard ends
        if self._worker and self._worker.isRunning():
            self._btn_grabar.setEnabled(True)
        self._set_thresholds_enabled(bool(ok))
        if ok:
            self._autoscale_after_calibration(ok)
            summary = " · ".join(
                f"{self._active_labels()[c]}: {self._mvc_ref[c]:.2f} mV" for c in ok
            )
            self._mvc_info(
                tr("MVC ready — {summary}. You can start recording.").format(
                    summary=summary
                )
            )
            self._log(tr("MVC calibrated: {summary}").format(summary=summary))

            cruce = self._mvc_crosstalk()
            for activo, otro, pct in cruce:
                self._log(tr(
                    "Channel separation — while «{muscle}» was at maximum, "
                    "«{other}» reached {pct:.0f} % of its own reference."
                ).format(muscle=activo, other=otro, pct=pct))
            juntos = [
                tr("{other} at {pct:.0f} % during {muscle}").format(
                    other=otro, muscle=activo, pct=pct)
                for activo, otro, pct in cruce
                if pct >= self._profile.mvc_crosstalk_pct
            ]

            weak = [name for name in self._mvc_no_maximas if name]
            if weak:
                # The one result nobody must scroll past. A reference that is
                # not a maximum makes every later percentage wrong by the same
                # factor, and the event log moves on within seconds — so it
                # ends on the panel the operator is already looking at.
                warning = tr(
                    "{muscles}: this is not a maximum. Calibrate again against "
                    "a resistance the joint cannot move."
                ).format(muscles=" · ".join(weak))
                self._prep_aviso = warning
                self._mvc_overlay.show_done(tr("Calibration too weak"), warning)
                self._bcast_calib(
                    True, "done", tr("Calibration too weak"), warning
                )
            elif juntos:
                # Both references are maximal, so the calibration is not the
                # problem — the montage is. Two channels this alike measure one
                # muscle twice, and every later comparison between them, the
                # co-activation index included, is built on that.
                warning = tr(
                    "{pairs}. Move the electrode pairs further apart, over the "
                    "belly of each muscle, and support the forearm."
                ).format(pairs=" · ".join(juntos))
                self._prep_aviso = warning
                self._mvc_overlay.show_done(tr("Channels not separated"), warning)
                self._bcast_calib(
                    True, "done", tr("Channels not separated"), warning
                )
            else:
                self._mvc_overlay.show_done(
                    tr("MVC ready"),
                    tr("{summary}\nYou can start recording.").format(
                        summary=summary),
                )
                self._bcast_calib(True, "done", tr("MVC ready"), summary)
        else:
            self._mvc_info(tr("Calibration failed (no signal)."))
            self._mvc_overlay.show_done(
                tr("Calibration failed"), tr("No signal — check the electrodes.")
            )
            self._bcast_calib(
                True, "done", tr("Calibration failed"),
                tr("No signal — check the electrodes."),
            )
        if self._mvc_flow_auto and self._worker and self._worker.isRunning():
            # The session continues into its second phase, and it does so
            # here rather than on a timer two seconds from now. A deferred
            # hand-over is one more thing that can fail to happen — on the
            # bench it did, leaving a file with its calibration marked and no
            # recording phase at all — and it bought nothing: the verdict is
            # carried into the countdown, which is on screen far longer than
            # the two seconds it used to get on its own.
            self._mvc_flow_auto = False
            self._mvc_enter_prep()
            return

        QTimer.singleShot(5000, self._mvc_overlay.hide_overlay)
        QTimer.singleShot(5000, lambda: self._bcast_calib(False))

    def _mvc_cancel(self) -> None:
        """Abort the wizard (e.g. on stop/disconnect)."""
        self._mvc_timer.stop()
        self._prep_timer.stop()
        self._mvc_active = False
        self._mvc_flow_auto = False
        self._mvc_flow_pending = False
        self._mvc_phase = ""
        self._mvc_overlay.hide_overlay()
        self._btn_cancelar_guia.setVisible(False)
        self._update_fv_button()
        self._bcast_calib(False)

    @Slot()
    def _cancelar_guiado(self) -> None:
        """Out of whichever guided procedure is running, now.

        The button beside the record button and Esc both land here. The
        recording itself goes on: what the operator wanted to stop was the
        guide, and stopping the file with it would throw away the take.
        A calibration cut short leaves no reference — the closed repetitions
        stay in the file, and the analysis reads them back as it does for a
        recording stopped mid-calibration.
        """
        if self._mvc_active:
            self._mvc_cancel()
            self._prep_aviso = ""
            if self._worker and self._worker.isRunning():
                self._btn_calibrar.setEnabled(True)
                self._btn_grabar.setEnabled(True)
            self._set_thresholds_enabled(any(bool(r) for r in self._mvc_ref[:self._n_channels]))
            self._log(tr("Calibration cancelled; the recording goes on."))
        elif self._fv_active:
            self._fv_cancel()
            if self._worker and self._worker.isRunning():
                self._btn_calibrar.setEnabled(True)
                self._btn_grabar.setEnabled(True)
            self._update_fv_button()
            self._log(tr("Force-velocity acquisition cancelled; the recording goes on."))
        self._btn_cancelar_guia.setVisible(False)

    # -- Guided force-velocity acquisition wizard ----------------------------

    @Slot()
    def _on_fv_guided(self) -> None:
        """Launch the guided force-velocity acquisition wizard.

        Asks for the list of known loads first (this is the load dialog the
        operator sees), then — starting the recording itself if one is not
        already running — guides an MVC maximum (no load) followed by a discrete
        'contract with this load' prompt for every repetition of every load,
        marking each contraction in the EDF so the Analysis-tab force-velocity
        study reads the loads directly instead of the operator typing them.
        """
        if self._mvc_active or self._fv_active:
            return
        from emgteach.gui.widgets.force_velocity_plan_dialog import (
            ForceVelocityPlanDialog,
        )

        placement = self._combo_acc_place.currentData()
        dlg = ForceVelocityPlanDialog(self, placement=placement)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        loads = dlg.loads()
        reps, prep_s, window_s = (
            dlg.reps(), dlg.prep_seconds(), dlg.window_seconds()
        )
        if len(loads) < 2:
            return
        # Remember the plan and show it next to the button (like "Best of 3").
        self._settings.setValue(
            "adquisicion/fv_loads", ", ".join(f"{v:g}" for v in loads)
        )
        self._settings.setValue("adquisicion/fv_reps", int(reps))
        self._refresh_fv_config_label()
        # Start recording ourselves if the operator has not already — the
        # wizard needs an active worker to mark the contractions in the EDF.
        if not (self._worker and self._worker.isRunning()):
            self._btn_grabar.setChecked(True)
            self._iniciar_grabacion()
            if not (self._worker and self._worker.isRunning()):
                # The operator cancelled the save-path dialog (or start failed).
                self._btn_grabar.setChecked(False)
                return
        self._fv_start(loads, reps, prep_s, window_s)

    @Slot()
    def _on_fv_rehearse(self) -> None:
        """Rehearse the guided procedure — no device, no subject, no recording."""
        from emgteach.gui.widgets.fv_rehearsal_dialog import (
            ForceVelocityRehearsalDialog,
        )

        dlg = ForceVelocityRehearsalDialog.run(self)
        if dlg is not None:
            # Modeless and kept alive: the point is to leave it open beside the
            # real controls while following it.
            self._fv_rehearsal = dlg

    def _fv_start(
        self,
        loads: list[float],
        reps: int,
        prep_s: float,
        window_s: float,
    ) -> None:
        """Start the guided F-V state machine for a validated load plan."""
        if len(loads) < 2 or self._mvc_active or self._fv_active:
            return
        self._fv_loads = list(loads)
        self._fv_reps = max(1, int(reps))
        self._fv_prep_s = float(prep_s)
        self._fv_window_s = float(window_s)
        self._fv_active = True
        self._btn_cancelar_guia.setVisible(True)
        self._fv_idx = 0
        self._fv_rep = 0
        self._fv_mvc_buf = []
        self._fv_mvc_peak = 0.0
        self._fv_mvc_cur = 0.0
        self._btn_calibrar.setEnabled(False)
        self._btn_grabar.setEnabled(False)
        self._update_fv_button()          # disabled while the wizard runs
        self._reposition_mvc_overlay()
        self._fv_phase = "mvc_ready"       # an MVC maximum (no load) comes first
        self._fv_elapsed = 0.0
        self._fv_timer.start()

    def _fv_current_load(self) -> float:
        if 0 <= self._fv_idx < len(self._fv_loads):
            return self._fv_loads[self._fv_idx]
        return 0.0

    def _fv_progress(self) -> str:
        return tr(" (load {i}/{n}, rep {r}/{rn})").format(
            i=self._fv_idx + 1, n=len(self._fv_loads),
            r=self._fv_rep + 1, rn=self._fv_reps,
        )

    def _fv_info(self, text: str) -> None:
        self._lbl_load_info.setText(text)

    def _fv_mvc_feed(self, env: list) -> None:
        """Accumulate the muscle's envelope during the MVC-maximum window."""
        if env and env[0].size:
            self._fv_mvc_buf.extend(env[0].tolist())
            self._fv_mvc_cur = float(np.mean(env[0]))
            self._fv_mvc_peak = max(self._fv_mvc_peak, float(np.max(env[0])))

    @Slot()
    def _fv_tick(self) -> None:
        self._fv_elapsed += MVC_TICK_MS / 1000.0
        kg = self._fv_current_load()
        prep_s = self._fv_prep_s
        mvc_hold_s = FV_MVC_HOLD_S       # sustained maximum
        lift_s = self._fv_window_s       # quick loaded lift

        if self._fv_phase == "mvc_ready":
            count = max(1, int(np.ceil(MVC_READY_S - self._fv_elapsed)))
            self._mvc_overlay.show_ready(
                tr("Get ready — maximum contraction (no load)"),
                count,
                tr("Contract at maximum when the count reaches 0"),
            )
            self._fv_info(
                tr("Get ready — maximum (no load): {n}").format(n=count)
            )
            if self._fv_elapsed >= MVC_READY_S:
                self._fv_phase = "mvc_contract"
                self._fv_elapsed = 0.0
                self._fv_mvc_buf = []
                self._fv_mvc_peak = 0.0
                self._fv_mvc_cur = 0.0
        elif self._fv_phase == "mvc_contract":
            secs_left = max(0.0, mvc_hold_s - self._fv_elapsed)
            progress = min(1.0, self._fv_elapsed / mvc_hold_s)
            effort = (
                self._fv_mvc_cur / self._fv_mvc_peak
                if self._fv_mvc_peak > 0 else 0.0
            )
            self._mvc_overlay.show_contract(
                tr("Contract at maximum! (no load)"),
                secs_left, progress, effort,
            )
            self._fv_info(tr("Contract at maximum! ({s:.0f} s)").format(
                s=secs_left))
            if self._fv_elapsed >= mvc_hold_s:
                self._fv_compute_mvc()
                self._fv_phase = "mvc_rest"
                self._fv_elapsed = 0.0
        elif self._fv_phase == "mvc_rest":
            self._mvc_overlay.show_relax(
                tr("Relax — now the loads, lightest first")
            )
            self._fv_info(tr("Relax — the loads come next…"))
            if self._fv_elapsed >= FV_MVC_TO_LOADS_REST_S:
                self._fv_phase = "ready"
                self._fv_elapsed = 0.0
        elif self._fv_phase == "ready":
            count = max(1, int(np.ceil(prep_s - self._fv_elapsed)))
            self._mvc_overlay.show_ready(
                tr("Prepare {kg:g} kg{prog}").format(kg=kg, prog=self._fv_progress()),
                count,
                tr("Lift {kg:g} kg when the count reaches 0").format(kg=kg),
            )
            self._fv_info(tr("Prepare {kg:g} kg{prog}: {n}").format(
                kg=kg, prog=self._fv_progress(), n=count))
            if self._fv_elapsed >= prep_s:
                self._fv_begin_contract(kg)
        elif self._fv_phase == "contract":
            # A quick concentric lift — no hold. Show only the big "Lift!" cue
            # (no hold timer or effort bar) and move straight to relax, so the
            # accelerometer captures the shortening velocity rather than a flat
            # isometric hold.
            self._mvc_overlay.show_action(
                tr("Lift {kg:g} kg!").format(kg=kg),
                self._fv_progress().strip(),
            )
            self._fv_info(tr("Lift {kg:g} kg — then relax").format(kg=kg))
            if self._fv_elapsed >= lift_s:
                self._fv_finish_contract()
        elif self._fv_phase == "rest":
            more_reps = self._fv_rep < self._fv_reps
            if more_reps:
                sub = tr("Relax — another rep of {kg:g} kg").format(kg=kg)
            else:
                nxt = (
                    self._fv_loads[self._fv_idx]
                    if self._fv_idx < len(self._fv_loads) else kg
                )
                sub = tr("Relax — change to {kg:g} kg").format(kg=nxt)
            self._mvc_overlay.show_relax(sub)
            self._fv_info(tr("Relax…"))
            if self._fv_elapsed >= MVC_REST_S:
                self._fv_phase = "ready"
                self._fv_elapsed = 0.0

    def _fv_compute_mvc(self) -> None:
        """Set the MVC reference from the guided maximum contraction."""
        if not self._fv_mvc_buf:
            return
        window = max(1, round(self._profile.mvc_peak_window_s * FS))
        ref = mvc_from_reps(
            [np.asarray(self._fv_mvc_buf, dtype=float)],
            self._profile.mvc_percentile, window_samples=window,
        )
        if ref > 0:
            self._mvc_ref[0] = ref
            self._online[0].reset()
            self._load_bars[0].set_value(0.0, active=True)
            self._set_thresholds_enabled(True)
            self._autoscale_after_calibration([0])
            self._log(tr("F-V: MVC reference {ref:.2f} mV.").format(ref=ref))

    def _fv_begin_contract(self, kg: float) -> None:
        """Enter a contraction window and mark it in the EDF with its load."""
        self._fv_phase = "contract"
        self._fv_elapsed = 0.0
        from emgteach.force_velocity import fv_load_marker

        if self._worker and self._worker.isRunning():
            self._worker.add_marker(fv_load_marker(kg))
        self._log(tr("Force-velocity: contraction with {kg:g} kg.").format(kg=kg))

    def _fv_finish_contract(self) -> None:
        """Advance to the next rep, next load, or finish."""
        self._fv_rep += 1
        if self._fv_rep < self._fv_reps:
            self._fv_phase = "rest"           # rest, then another rep, same load
            self._fv_elapsed = 0.0
            return
        self._fv_rep = 0
        self._fv_idx += 1
        if self._fv_idx < len(self._fv_loads):
            self._fv_phase = "rest"           # rest, then the next load
            self._fv_elapsed = 0.0
        else:
            self._fv_finish_all()

    def _fv_finish_all(self) -> None:
        self._fv_timer.stop()
        self._fv_active = False
        self._fv_phase = "done"
        self._btn_cancelar_guia.setVisible(False)
        if self._worker and self._worker.isRunning():
            self._btn_grabar.setEnabled(True)
            self._btn_calibrar.setEnabled(True)
        self._update_fv_button()          # re-enabled once the wizard ends
        n = len(self._fv_loads)
        self._fv_info(
            tr(
                "Force-velocity: {n} loads recorded. Stop recording, then open "
                "the Force-velocity study in the Analysis tab."
            ).format(n=n)
        )
        self._mvc_overlay.show_done(
            tr("Loads recorded"),
            tr(
                "{n} loads marked.\nStop recording, then open the "
                "Force-velocity study."
            ).format(n=n),
        )
        self._log(
            tr("Force-velocity acquisition finished: {n} loads.").format(n=n)
        )
        QTimer.singleShot(5000, self._mvc_overlay.hide_overlay)

    def _fv_cancel(self) -> None:
        """Abort the guided F-V wizard (e.g. on stop/disconnect)."""
        self._fv_timer.stop()
        self._fv_active = False
        self._fv_phase = ""
        self._btn_cancelar_guia.setVisible(False)
        if not self._mvc_active:
            self._mvc_overlay.hide_overlay()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_mvc_overlay()

    def _reposition_mvc_overlay(self) -> None:
        """Centre the floating MVC guide near the top of the plot area."""
        ov = self._mvc_overlay
        x = max(0, (self.width() - ov.width()) // 2)
        y = 72
        if hasattr(self, "_grp_plots"):
            y = max(72, self._grp_plots.geometry().top() + 8)
        ov.move(x, y)

    @Slot()
    def _update_load_readout(self) -> None:
        if all(r is None for r in self._mvc_ref[: self._n_channels]):
            return
        colours = {"normal": "#1a7a1a", "warning": "#E67E22", "danger": "#cc0000"}
        for c in range(self._n_channels):
            if not self._mvc_ref[c]:
                continue
            ol = self._online[c]
            self._load_readouts[c].setText(
                f"P10 {ol.static:.0f} · P50 {ol.median:.0f} · P90 {ol.peak:.0f} %"
            )
            self._load_readouts[c].setStyleSheet(
                f"font-size: 9px; color: {colours[ol.status]};"
            )

    def _reset_load_monitor(self) -> None:
        self._mvc_cancel()
        self._fv_cancel()
        self._mvc_ref = [None] * MAX_CHANNELS
        self._mvc_capture = [[] for _ in range(MAX_CHANNELS)]
        self._mvc_cross = [{} for _ in range(MAX_CHANNELS)]
        self._mvc_no_maximas = []
        for c in range(MAX_CHANNELS):
            self._online[c].reset()
            self._load_bars[c].reset()
            self._load_readouts[c].setText("")
        self._lbl_load_info.setText("")
        self._set_thresholds_enabled(False)

    def _stop_load_monitor(self) -> None:
        self._load_timer.stop()
        self._mvc_cancel()
        self._fv_cancel()
        self._btn_calibrar.setEnabled(False)
        self._update_fv_button()
        self._set_thresholds_enabled(False)
        for bar in self._load_bars:
            bar.set_value(0.0, active=False)

    # ------------------------------------------------------------------
    # Markers
    # ------------------------------------------------------------------



    @Slot(float, str)
    def _on_marker_added(self, tiempo: float, etiqueta: str) -> None:
        # The marker is reflected in the "Event log" (log).
        self._log(tr("Marker added: t={t:.1f} s — {label}").format(t=tiempo, label=etiqueta))
        # Record the event to draw it live over the plots.
        self._marker_events.append((tiempo, etiqueta))
        if self._broadcast.is_running():
            self._broadcast.broadcast(
                {"t": "marker", "time": round(tiempo, 1), "label": etiqueta}
            )
        # Add it to the editable marker list (data carries the exact key).
        item = QListWidgetItem(f"t={tiempo:.1f} s — {etiqueta}")
        item.setData(Qt.ItemDataRole.UserRole, (float(tiempo), etiqueta))
        self._list_markers.addItem(item)
        # Two lines, so the oldest goes as the newest arrives. A list that
        # grows all recording long is a table nobody reads while recording,
        # and it was pushing the plots down the window to say it.
        while self._list_markers.count() > 2:
            self._list_markers.takeItem(0)



    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._err(msg)
        self._restaurar_controles()

    @Slot(str)
    def _on_finished(self, edf_path: str) -> None:
        self._restaurar_controles()
        if edf_path:
            self._log(tr("Recording finished. File: {path}").format(path=edf_path))
            self.recording_saved.emit(edf_path)
            self._mostrar_registro(edf_path)

    def _restaurar_controles(self) -> None:
        self._btn_grabar.setChecked(False)
        self._btn_grabar.setText(tr("Start recording"))
        self._btn_conectar.setEnabled(True)
        self._lbl_estado.setText(tr("Status: connected (ready to record)"))
        self._set_auto_controls_enabled(True)
        self._stop_load_monitor()
        self._quality_monitor = None
        self._lbl_calidad.setVisible(False)
        self._lbl_calidad.setText("")

    # ------------------------------------------------------------------
    # Vertical scale (▲▼ per plot)
    # ------------------------------------------------------------------

    def _y_zoom(self, idx: int, zoom_in: bool) -> None:
        """Adjust the vertical scale of plot `idx` by a factor of 1.5.

        In stacked mode (raw plot with 2 channels) it scales the data gain
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
        """Restore the vertical scale of the two plots to their initial state."""
        self._y_accum = [1.0, 1.0]
        self._y_gain = [1.0, 1.0]
        # Envelope: never stacked, direct initial range.
        self._plot_env.setYRange(*self._y_ranges_init[1], padding=0)
        # Raw: the mode (stacked or overlaid) sets range and annotations.
        self._apply_stacking_mode()
        # ACC: drop the manual zoom back to the full ±1 g.
        self._acc_zoom = 1.0
        self._plot_acc.setYRange(-1.0, 1.0, padding=0)

    def _autoscale_after_calibration(self, channels: list[int]) -> None:
        """Fit the live plots to this subject once the MVC is known.

        Sets the *initial* Y ranges (so the ▲▼ reset returns to this
        calibrated scale) from the calibration itself: the envelope top is a
        headroom multiple of the largest MVC reference (leaving room for
        >100 %MVC phasic bursts and a small margin below 0), and the raw plot
        spans ±(largest raw peak × factor). Falls back to the profile
        defaults when a measure is missing, and never shrinks below them so a
        weak calibration cannot hide the signal.
        """
        refs = [self._mvc_ref[c] for c in channels if self._mvc_ref[c]]
        raw_peaks = [self._mvc_raw_peak[c] for c in channels
                     if self._mvc_raw_peak[c] > 0]

        # Envelope (plot 1): 0-based, with headroom above and a little below.
        if refs:
            top = max(refs) * AUTOSCALE_ENV_FACTOR
            top = max(top, self._profile.ylim_envelope[1])   # never shrink
            self._y_ranges_init[1] = (-0.05 * top, top)

        # Raw (plot 0): symmetric around 0. In stacked mode this half becomes
        # each lane's half-height (see _apply_stacking_mode).
        if raw_peaks:
            amp = max(raw_peaks) * AUTOSCALE_RAW_FACTOR
            amp = max(amp, self._profile.ylim_raw[1])        # never shrink
            self._y_ranges_init[0] = (-amp, amp)

        self._reset_y_scales()

    # ------------------------------------------------------------------
    # Time scale (sliding window)
    # ------------------------------------------------------------------

    # Every one of these ends in a forced repaint, and that is the whole
    # point of the line. Without it the window only changed on the *next*
    # frame that carried new samples — so while recording it worked with a
    # thirty-millisecond delay nobody could notice, and standing idle it did
    # nothing at all: the caption said "5 s visible" and the plot went on
    # showing thirty. Reported from the bench as "I click and the time scale
    # does not change", which is exactly what happened.
    #
    # The vertical ▲▼ buttons beside each plot had always forced it. Two
    # controls in the same corner, one working and one not.

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        """◀▶ — double the visible window (less detail, more context)."""
        nueva = min(self._n_visible * 2, MAX_POINTS)
        nueva = max(nueva, int(0.5 * FS))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()
        self._refresh_plots(force=True)

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        """▶◀ — halve the visible window (more detail)."""
        nueva = max(self._n_visible // 2, int(0.5 * FS))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()
        self._refresh_plots(force=True)

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva = MAX_POINTS // factor
        nueva = max(nueva, int(0.5 * FS))
        self._n_visible = nueva
        self._update_ventana_label()
        self._refresh_plots(force=True)

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
    # New-session reset (clear the live view for a new student)
    # ------------------------------------------------------------------

    def is_recording(self) -> bool:
        """True while a recording worker is running."""
        return bool(self._worker and self._worker.isRunning())

    def reset(self) -> None:
        """Clear the live acquisition view to its just-opened state.

        Wipes the plot buffers, event markers, local log and the muscle-load
        calibration, and restores the scales/time window. Keeps the device
        connection and the saved configuration (MAC, folder, labels). The EDF
        files already written to disk are NOT touched. No effect while
        recording (the caller guards with :meth:`is_recording`).
        """
        if self.is_recording():
            return
        self._salir_revision()
        self._reset_buffers()
        self._marker_events.clear()
        self._list_markers.clear()
        self._total_samples = 0
        for pool in self._marker_lines:
            for line in pool:
                line.hide()
        self._reset_load_monitor()
        self._reset_all_scales()
        self._local_log.clear()
        self._new_data = True
        self._refresh_plots(force=True)

    # ------------------------------------------------------------------
    # Cleanup on window close
    # ------------------------------------------------------------------

    def apply_mode(self, mode: str, advanced: bool) -> None:
        """Set the tab up for one practical, optionally with the fine controls.

        Whole containers are hidden, never the individual widgets: most of
        these controls sit beside plain QLabels that are not kept as
        attributes, so hiding the widget alone would leave its caption behind.

        The mode *drives* the channel count and the accelerometer rather than
        merely hiding their selectors. Hiding them alone was a bug: a
        two-muscle set-up chosen in one mode survived into another that had no
        way to show or change it, so the labels and load bars claimed two
        muscles while the rest of the tab behaved as if there were one.
        """
        # Kept, not merely acted on: the session flow asks which practical is
        # running on every press of the record button, long after this call.
        # It was read and never stored, so _flow_needs_calibration raised
        # AttributeError inside a Qt slot — which prints to stderr and is
        # invisible in the running app — and aborted the rest of
        # _iniciar_grabacion in silence. Four bench recordings came back with
        # no calibration because of this one missing assignment.
        self._mode = normalise_mode(mode)
        self._apply_mode_channels(mode)

        # Which device, and where it is plugged in, is offered in every
        # practical. It used to be a fine control, on the reasoning that a
        # laboratory is set up once — but the practicals are where the app is
        # actually used, and sending someone to a different mode to change a
        # COM port is sending them away from the exercise to fix the tool.
        port = str(self._settings.value("adquisicion/port", "") or "").strip()
        first_setup = not port
        self._box_device.setVisible(True)
        self._lbl_first_setup.setVisible(first_setup)
        # Only the single-muscle practical can be done with the Arduino +
        # MyoWare board; the other two need the BITalino (two channels, the
        # accelerometer). So the device choice is offered there and nowhere
        # else, and a practical that needs the BITalino gets it — the port
        # or address stays editable, since that differs from board to board.
        solo_un_musculo = self._mode == MODE_SINGLE
        self._combo_device_type.setVisible(solo_un_musculo)
        self._lbl_device_fixed.setVisible(not solo_un_musculo)
        if not solo_un_musculo and self._combo_device_type.currentIndex() != 0:
            self._combo_device_type.setCurrentIndex(0)

        # Channel names the practical imposes: the row goes, and the names
        # come from _active_labels(). The boxes are left exactly as the
        # operator had them, so their own names survive a visit to a practical
        # that does not use them.
        self._box_labels.setVisible(not mode_fixed_labels(mode))
        # The hint in the first box names what the practical records: one
        # muscle, or the agonist of a pair.
        self._edit_labels[0].setPlaceholderText(
            tr("Muscle — e.g. biceps") if mode_channels(mode) == 1 else _LABEL_HINTS[0]())

        # Belongs to the kinematics practical, not to the fine controls.
        uses_acc = mode_uses_acc(mode)
        self._box_acc.setVisible(uses_acc)
        self._box_fv_guided.setVisible(uses_acc)
        # Which analogue input the sensor is wired to is a convention the
        # block states — muscle on A1, accelerometer on A2 — not a selector:
        # the selector and its «find it» diagnostic stay built (the recording
        # code reads the combo) but never shown, and the practical sets it.
        self._box_acc_wiring.setVisible(False)
        if uses_acc:
            fijo = self._combo_acc_channel.findData(_ACC_INPUT)
            if fijo >= 0:
                self._combo_acc_channel.setCurrentIndex(fijo)

        # The channel count is now decided by the mode, so its selector never
        # appears — it would be a control that cannot disagree with the mode.
        self._box_nchan.setVisible(False)

        # Following the class on their own phones is what the practical is
        # for, not a fine adjustment, so it is offered at every level.
        self._box_aula.setVisible(True)

        # Offered at every level, and not as a fine adjustment: it is the only
        # thing left in the Event markers box now that marking by hand is
        # gone, and hiding it in the practicals would leave an empty box and a
        # recording with no marks in it at all. Marks are not a refinement —
        # the analysis finds each effort by them.
        self._box_autoonset.setVisible(True)
        # Fine controls: the warning/danger thresholds, the onset sensitivity
        # k, and the four ways of moving the view by hand (Reset scales and
        # the ▲▼ sidebar). None of them is a decision a student should be
        # making in the middle of a physiology exercise; the advanced
        # practical, where the reader is past that point, shows them all.
        # The legend and the lane labels are painted while the tab is built,
        # before any mode has been applied, so they carried the names of the
        # default practical: with the channel count already at two nothing
        # changed and the first lane stayed «Muscle» beside an «ECR».
        self._update_legend()

        self._box_thr.setVisible(advanced)
        # k stays on screen in every practical, with its one-line meaning
        # beside it: the box's help explains it, and a control that is
        # explained and hidden is a puzzle. Its default is right for all
        # three practicals; the label says so.
        self._box_k.setVisible(True)
        self._btn_reset_escala.setVisible(advanced)
        self._sidebar.setVisible(advanced)

    def _apply_mode_channels(self, mode: str) -> None:
        """Make the recording match the mode: channel count and accelerometer.

        Driven through the existing widgets so their slots run and the plots,
        legend, load bars and broadcast configuration all follow.
        """
        # Every practical does this, including the kinematics one. The
        # channel selector is hidden in every mode on purpose, so "whatever
        # the user set stays set" would mean a channel count that nothing on
        # screen could show or change. That is the state this
        # module exists to make unreachable.
        #
        # Imposing is not locking: this *sets* the widgets when the practical
        # is chosen and leaves them editable, and the accelerometer's own
        # checkbox stays on screen. Choosing the kinematics practical arrives
        # with the accelerometer on, which is what makes it kinematics, and
        # unticking it afterwards is still the operator's to do.
        wanted = mode_channels(mode)
        if self._combo_n_channels.currentIndex() != wanted - 1:
            self._combo_n_channels.setCurrentIndex(wanted - 1)

        uses_acc = mode_uses_acc(mode)
        if self._chk_acc.isChecked() != uses_acc:
            self._chk_acc.setChecked(uses_acc)

    def cleanup(self) -> None:
        """
        Called by MainWindow.closeEvent before destroying the window.
        Stops timers, stops the worker (forced if necessary) and waits for it
        to finish to ensure the EDF is closed correctly.
        """
        self._watchdog_timer.stop()
        self._render_timer.stop()
        self._load_timer.stop()
        self._broadcast.stop()
        if self._worker and self._worker.isRunning():
            self._worker.stop_forced()
            self._worker.wait(5000)
