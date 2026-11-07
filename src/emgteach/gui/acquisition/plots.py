"""The live plots, their scales and the review, as a piece of the acquisition
tab (step 3 of docs/PLAN-partir-AcquisitionTab.md).

The raw EMG, the envelope and the accelerometer, drawn from ring buffers
thirty seconds long at about thirty frames a second; the time window
(◀▶, the zoom combo, ▶◀) and the vertical scales (the ▲▼ sidebar, «Reset
scales»); two channels stacked in lanes on the raw plot with reference
ticks; the live envelope following its own peak; the scale the device
itself reaches, and the one a calibration gives; and, once a recording
ends, the whole file read back on the same plots with its phases shaded.

Communication, the rule of the plan: the tab hands the piece what it needs
to know — the sampling rate, the channels' colours and the profile's ranges
when it is built; the channel count, the names, the accelerometer, each
block of samples and each event as they come — and calls its methods;
the piece says what goes to the event log through :attr:`logged`, and keeps
no reference to the tab. In the review it asks the tab, through the function
it is given, how to name each stretch a guided session marked.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Sequence
from typing import ClassVar, cast

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.devices import BACKEND_ARDUINO, BACKEND_BITALINO, device_class
from emgteach.dsp import process_offline
from emgteach.gui.widgets.help_button import add_help
from emgteach.i18n import tr
from emgteach.io import list_edf_channels, list_edf_emg_channels, read_edf_mne
from emgteach.phases import (
    CALIBRATION,
    PREPARATION,
    RECORDING,
    WARMUP,
    PhaseSpan,
    parse_phase_markers,
    phase_spans,
)
from emgteach.profiles import SignalProfile
from emgteach.sessions import MeasuredSpan, parse_session_markers

__all__ = [
    "AUTOSCALE_ENV_FACTOR",
    "AUTOSCALE_RAW_FACTOR",
    "ENV_SIGUE_CAIDA",
    "ENV_SIGUE_MARGEN",
    "GUIDED",
    "MAX_MARKER_LINES",
    "MAX_POINTS",
    "LivePlots",
]

# Number of samples in the ring buffer (= 30 s at 1000 Hz)
# The visible window can be smaller thanks to the time-zoom control.
MAX_POINTS = 30_000
# Maximum number of event markers drawn live at once (a reusable pool of
# lines per plot; more than enough for a 30 s window).
MAX_MARKER_LINES = 40

# Headroom applied to the live plots when they auto-scale after calibration:
# the envelope top is this multiple of the MVC reference (so >100 %MVC phasic
# bursts stay visible), the raw plot spans ±(peak × factor).
AUTOSCALE_ENV_FACTOR = 1.5
AUTOSCALE_RAW_FACTOR = 1.25

#: How the live envelope's vertical scale follows the signal. The top rises at
#: once to keep the highest point of the visible window in view with this
#: margin above it, and once that peak has scrolled away falls back towards the
#: base scale by this factor per redraw (about thirty a second).
ENV_SIGUE_MARGEN = 1.15
ENV_SIGUE_CAIDA = 0.97

# With 2 channels the raw plot stacks (one lane per channel) instead of
# overlapping. The mV axis is no longer absolute, so each lane shows reference
# ticks at 0/±_CALIB_MV·gain (an honest calibration that does not hide the
# signal). Real signal mV per stacking plot (0=raw); the envelope (1) never
# stacks.
_CALIB_MV = {0: 1.0}

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

#: A stretch a guided session marked, as the review shades it.
GUIDED = "guided"

#: The bar the review draws under each contraction, as a share of the
#: plot's height, and its colour.
_BARRA_ALTO = 0.07
_BARRA_COLOR = (0, 137, 123, 170)

#: The stretch a number was read on, inside its bar (Ángel, 7 November
#: 2026): light green, taller than the bar, with a fine dark edge, so it
#: stands out on the light green of the «recording» phase, on a projector
#: and in black and white.
_MEDIDO_ALTO = 0.12
_MEDIDO_COLOR = (190, 235, 160, 240)
_MEDIDO_BORDE = (20, 70, 30)
_MEDIDO_FILO = 0.006


def _muestra(color: tuple[int, ...], borde: tuple[int, int, int] | None) -> QLabel:
    """A small swatch of *color* for the legend, with an edge when given."""
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    mapa = QPixmap(22, 10)
    mapa.fill(QColor(0, 0, 0, 0))
    pintor = QPainter(mapa)
    pintor.setBrush(QColor(*color))
    pintor.setPen(QPen(QColor(*borde), 1.2) if borde else QPen(QColor(0, 0, 0, 0)))
    pintor.drawRect(0, 0, 21, 9)
    pintor.end()
    etiqueta = QLabel()
    etiqueta.setPixmap(mapa)
    return etiqueta


def _misma_ruta(a: str, b: str) -> bool:
    """Whether two paths name the same file."""
    import os

    def norma(p: str) -> str:
        return os.path.normcase(os.path.abspath(p))

    return bool(a) and bool(b) and norma(a) == norma(b)


class LivePlots(QGroupBox):
    """The «Real-time EMG signal» box: the plots, their scales and the review."""

    #: A line for the event log.
    logged = Signal(str)

    def __init__(
        self,
        *,
        fs: int,
        colours: list[tuple[int, int, int]],
        colour_hex: list[str],
        profile: Callable[[], SignalProfile],
        n_channels: Callable[[], int],
        acc_enabled: Callable[[], bool],
        labels: Callable[[], list[str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(tr("Real-time EMG signal"), parent)
        self._fs = fs
        #: One colour per channel the interface offers, the same in every
        #: plot (blue = channel 1, red = channel 2); as many curves as colours.
        self._colours = colours
        self._colour_hex = colour_hex
        self._n_max = len(colours)
        #: How many channels are active, asked each time it matters (the
        #: tab's count, as the plots always read it).
        self._channel_count = n_channels
        #: Whether the accelerometer is on, asked each time it matters.
        self._acc_on = acc_enabled
        #: The names of the active channels, asked for each time they are
        #: drawn (the colour key, the lanes): the practical's, or the boxes'.
        self._labels = labels
        #: The signal profile: its ranges are the starting scales, and the
        #: floor a calibrated scale never shrinks below (read when used).
        self._profile = profile

        # Per-channel ring buffers for the three signals (30 s at 1000 Hz).
        # Every channel the interface offers is allocated; only the active
        # ones are filled.
        self._buf_raw = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(self._n_max)
        ]
        self._buf_env = [
            deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS) for _ in range(self._n_max)
        ]
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
        #: The measured stretches drawn now, a subset of _revision_items.
        self._medidos: list = []
        #: The recording on review, "" when none, and whether it has bars.
        self._revision_ruta = ""
        self._con_barra = False

        # Events for drawing live lines: (time_s, label). The total number of
        # acquired samples places each marker within the sliding window.
        self._marker_events: list[tuple[float, str]] = []
        self._total_samples = 0

        # ---- Vertical-scale state (per plot: 0=raw, 1=env) ----
        # Initial Y ranges taken from the signal profile (restored in
        # reset_y_scales).
        self._y_ranges_init: list[tuple[float, float]] = [
            profile().ylim_raw,       # raw
            profile().ylim_envelope,  # envelope
        ]
        self._y_accum: list[float] = [1.0, 1.0]  # accumulated factor per plot
        # Per-plot data gain, used ONLY in stacked mode (2 channels) on the raw
        # plot: the ▲▼ zoom multiplies the signal while keeping the lanes fixed,
        # instead of scaling the ViewBox. Unused in 1-channel mode.
        self._y_gain: list[float] = [1.0, 1.0]
        #: The live envelope's current top, while it follows the signal
        #: (see _escala_envolvente_en_vivo); None until the first redraw.
        self._env_techo: float | None = None
        self._ultimo_pico_env = 0.0

        # ---- Time-scale state ----
        # Number of visible samples in each plot. Starts showing 5 s.
        self._n_visible: int = 5 * self._fs   # visible samples (adjustable with zoom)

        # Independent render timer — decouples data reception from redrawing.
        # 33 ms ≈ 30 FPS max, regardless of the worker's speed.
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self._refresh_plots)

        # ── Plots + scale controls ──────────────────────────────
        add_help(self, "acq.plots")
        self.setObjectName("plotsBox")  # stays white (see the application's style sheet)
        plots_root = QVBoxLayout(self)
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
        self._btn_reset_escala.clicked.connect(self.reset_all_scales)
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

        # One curve per channel in each plot (colour = channel). self._n_max
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
        # With numbers that no longer start at zero, the unit has to be said.
        self._plot_raw.setLabel("bottom", "s")
        self._plot_raw.showGrid(x=True, y=True, alpha=0.3)
        for c in range(self._n_max):
            self._curves_raw.append(
                self._plot_raw.plot(pen=pg.mkPen(color=self._colours[c], width=1))
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
        self._plot_env.setLabel("bottom", "s")
        self._plot_env.showGrid(x=True, y=True, alpha=0.3)
        for c in range(self._n_max):
            self._curves_env.append(
                self._plot_env.plot(pen=pg.mkPen(color=self._colours[c], width=2))
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
        self._plot_acc.setLabel("bottom", "s")
        self._plot_acc.showGrid(x=True, y=True, alpha=0.3)
        self._plot_acc.setYRange(-1.0, 1.0, padding=0)
        self._curve_acc = self._plot_acc.plot(
            pen=pg.mkPen(color="#2ca02c", width=1)
        )
        self._plot_acc.setVisible(bool(self._acc_enabled))
        self._plot_acc.setMinimumHeight(70)
        plots_col_vbox.addWidget(self._plot_acc, stretch=1)

        # What the bar and the stretch inside it are, under the plots, in
        # the review only.
        self._leyenda = QWidget()
        fila_leyenda = QHBoxLayout(self._leyenda)
        fila_leyenda.setContentsMargins(4, 0, 4, 0)
        self._leyenda_barra = _muestra(_BARRA_COLOR, None)
        fila_leyenda.addWidget(self._leyenda_barra)
        self._leyenda_barra_txt = QLabel(tr("contraction the fragment editor proposes"))
        fila_leyenda.addWidget(self._leyenda_barra_txt)
        fila_leyenda.addSpacing(18)
        self._leyenda_medido = _muestra(_MEDIDO_COLOR, _MEDIDO_BORDE)
        fila_leyenda.addWidget(self._leyenda_medido)
        self._leyenda_medido_txt = QLabel(tr("stretch the measured value is obtained from"))
        fila_leyenda.addWidget(self._leyenda_medido_txt)
        fila_leyenda.addStretch(1)
        self._leyenda.setVisible(False)
        plots_col_vbox.addWidget(self._leyenda)

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
            for c in range(self._n_max):
                bl = pg.InfiniteLine(
                    angle=0,
                    movable=False,
                    pen=pg.mkPen(color=self._colours[c], width=1,
                                 style=Qt.PenStyle.DotLine),
                )
                bl.hide()
                pw.addItem(bl, ignoreBounds=True)
                base_lines.append(bl)

                txt = pg.TextItem(anchor=(0, 0.5), fill=(255, 255, 255, 200))
                txt.setColor(self._colours[c])
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

        slot_labels = [tr("R"), tr("E")]   # button per plot: raw / envelope
        for i, lbl_txt in enumerate(slot_labels):
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



        # Update the combo so it reflects the initial n_visible
        self._sync_combo_zoom()

    # ------------------------------------------------------------------
    # What the tab tells the plots
    # ------------------------------------------------------------------

    @property
    def _n_channels(self) -> int:
        return self._channel_count()

    @property
    def _acc_enabled(self) -> bool:
        return bool(self._acc_on())

    def set_channels(self, n_channels: int) -> None:
        """How many channels are active: their curves are shown, the rest hidden."""
        for c in range(self._n_max):
            visible = c < n_channels
            self._curves_raw[c].setVisible(visible)
            self._curves_env[c].setVisible(visible)

    def restack(self) -> None:
        """The channel count changed: overlaid or stacked again, at gain 1."""
        self._y_gain = [1.0, 1.0]
        self._apply_stacking_mode()

    def show_accelerometer(self, visible: bool) -> None:
        """Show or hide the accelerometer's plot with its ▲▼ slot.

        The slot follows its plot so the raw/envelope buttons stay aligned
        with their own plots. Whether the accelerometer is drawn and fed is
        asked of the tab each time; this is only what is on screen.
        """
        self._plot_acc.setVisible(bool(visible))
        self._acc_sidebar_slot.setVisible(bool(visible))

    def set_scale_controls_visible(self, visible: bool) -> None:
        """The ▲▼ sidebar and «Reset scales»: the fine controls of the tab."""
        self._btn_reset_escala.setVisible(visible)
        self._sidebar.setVisible(visible)

    def append(self, raw: list, env: list) -> None:
        """One block from the worker: one array per channel for each signal.

        Bounded by the active EMG count, so the trailing ACC column is never
        mistaken for a second muscle; the accelerometer, when present, is the
        column right after the EMG channels. The filtered trace is still
        emitted by the worker (it feeds the envelope) but is not displayed,
        so it is not buffered here.
        """
        for c in range(min(len(raw), self._n_channels, self._n_max)):
            self._buf_raw[c].extend(raw[c].tolist())
            self._buf_env[c].extend(env[c].tolist())
        if self._acc_enabled and len(raw) > self._n_channels:
            self._buf_acc.extend(raw[self._n_channels].tolist())
        if raw:
            self._total_samples += len(raw[0])
        self._new_data = True

    def add_marker(self, time_s: float, label: str) -> None:
        """An event to draw as a line over the live plots, at its second."""
        self._marker_events.append((time_s, label))

    def clear(self) -> None:
        """Silence in the buffers, no events and no samples: a fresh start."""
        self._reset_buffers()
        self._marker_events.clear()
        self._total_samples = 0
        for pool in self._marker_lines:
            for line in pool:
                line.hide()

    def plot_widgets(self) -> list[pg.PlotWidget]:
        """The three plots: raw, envelope and accelerometer."""
        return [self._plot_raw, self._plot_env, self._plot_acc]

    def start_live(self) -> None:
        self._render_timer.start()

    def stop_live(self) -> None:
        self._render_timer.stop()

    def redraw(self) -> None:
        """Draw now, whether or not new samples arrived."""
        self._new_data = True
        self._refresh_plots(force=True)

    def follow_device(self, index: int, *, recording: bool) -> None:
        """Draw the raw plot to the device's own full scale.

        The profile's ±3.3 mV predates the gain correction: a BITalino cannot
        exceed ±1.635 mV, so the trace lived in the middle half of the panel
        with dead space above and below it; the Arduino front end reaches
        ±12.5 mV and was clipped by the same number. The full scale is a
        property of the device, so it is asked of the device class
        (``full_scale_mv``, the same number the EDF header carries) rather
        than kept as a second copy here; and of the class, not an instance,
        because no device exists yet when the type is chosen.
        """
        backend = BACKEND_BITALINO if index == 0 else BACKEND_ARDUINO
        try:
            amp = device_class(backend).full_scale_mv()
        except Exception:  # pragma: no cover — a backend registered as a function
            amp = self._profile().ylim_raw[1]
        self._y_ranges_init[0] = (-amp, amp)
        if not recording:
            self._apply_stacking_mode()

    def update_legend(self) -> None:
        """The colour key, offered only where there are two curves to tell apart.

        With one channel it named the only trace on screen, in the colour that
        trace already is. With two it earns its place — but only because of the
        envelope plot: the raw plot writes each muscle's name inside its own
        lane, and the envelope overlays both curves with nothing naming them.
        """
        labels = self._labels()
        parts = [
            f'<span style="color:{self._colour_hex[i]}">&#9679; {lbl}</span>'
            for i, lbl in enumerate(labels)
        ]
        self._lbl_legend.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        self._lbl_legend.setVisible(len(labels) > 1)
        # Keep the stacked-mode lane labels in sync.
        if hasattr(self, "_lane_labels"):
            self._refresh_lane_label_texts()

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
        labels = self._labels()
        for idx in (0,):
            a = self._lane_half(idx)
            for c in range(self._n_max):
                txt = self._lane_labels[idx][c]
                if self._is_stacked(idx) and c < self._n_channels:
                    txt.setText(f" {labels[c]}")
                    txt.setColor(self._colours[c])
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
                for c in range(self._n_max):
                    bl = self._baselines[idx][c]
                    if c < self._n_channels:
                        bl.setPos(self._lane_baseline(idx, c))
                        bl.show()
                    else:
                        bl.hide()
            else:
                pw.setYRange(*self._y_ranges_init[idx], padding=0)
                axis.setTicks(None)  # restore automatic ticks (absolute mV)
                for c in range(self._n_max):
                    self._baselines[idx][c].hide()
        self._refresh_lane_label_texts()

    def _reset_buffers(self) -> None:
        """Clear every per-channel ring buffer back to silence."""
        for bufs in (self._buf_raw, self._buf_env):
            for buf in bufs:
                buf.clear()
                buf.extend([0.0] * MAX_POINTS)
        self._buf_acc.clear()
        self._buf_acc.extend([0.0] * MAX_POINTS)
        self._plot_acc.setYRange(-1.0, 1.0, padding=0)

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
            # last session's axis: the same "advancing over an empty canvas",
            # arriving by the other door.
            #
            # And auto-range straight back on afterwards: setXRange turns it
            # off, which is the very thing that stranded the live view inside
            # the session's axis in the first place. The explicit range is only
            # what the empty tab shows; the first samples to arrive refit it.
            ventana = min(self._n_visible, MAX_POINTS) / self._fs
            for pw in (self._plot_raw, self._plot_env):
                pw.setXRange(0.0, ventana, padding=0)
                pw.enableAutoRange(axis="x")
            return

        n = min(self._n_visible, MAX_POINTS)
        # X axis in seconds of the recording, not of the window: the
        # numbers advance with it. Drawn from zero, a recording two
        # minutes long read 0…5 s for as long as it lasted, and the
        # student had no way of saying when something happened — nor of
        # telling a live screen from a stopped one. All the buffers have
        # the same length, so it is computed once.
        t = (self._total_samples - n + np.arange(n)) / self._fs

        # In stacked mode (2 channels) the raw plot is drawn shifted to each
        # lane and scaled by the gain: displayed = baseline + gain·signal.
        stacked_raw = self._is_stacked(0)

        pico_env = 0.0
        for c in range(self._n_channels):
            arr_raw = np.array(list(self._buf_raw[c]))[-n:]
            arr_env = np.array(list(self._buf_env[c]))[-n:]
            if stacked_raw:
                arr_raw = self._lane_baseline(0, c) + self._y_gain[0] * arr_raw
            self._curves_raw[c].setData(t, arr_raw)
            self._curves_env[c].setData(t, arr_env)
            if arr_env.size:
                pico_env = max(pico_env, float(np.nanmax(arr_env)))
        self._ultimo_pico_env = pico_env
        self._escala_envolvente_en_vivo(pico_env)

        if self._acc_enabled:
            arr_acc = np.array(list(self._buf_acc))[-n:]
            self._curve_acc.setData(t, arr_acc)

        self._seguir_la_senal(float(t[-1]))

        # Reposition the marker lines. Each event already carries the
        # second of the recording it happened at, which is now the axis's
        # own unit: it is drawn there, and the filter of what is on screen
        # is the one of always.
        visible = [
            tiempo
            for tiempo, _label in self._marker_events
            if 0 <= self._total_samples - tiempo * self._fs <= n
        ]
        visible = visible[-MAX_MARKER_LINES:]
        for pool in self._marker_lines:
            for i, line in enumerate(pool):
                if i < len(visible):
                    line.setPos(visible[i])
                    line.show()
                elif line.isVisible():
                    line.hide()

    def _seguir_la_senal(self, fin: float) -> None:
        """Slide a zoomed live plot so that its right edge is the last sample.

        The live view has no X range of its own: it relies on pyqtgraph's
        auto-range to follow the sliding window. A wheel zoom turns that
        auto-range off (``scaleBy`` ends in ``setXRange``), and until 3.9.0
        the axis then stayed where it was while the signal, whose seconds
        advance, ran out of sight to the right, until «A» was pressed. The
        width the wheel chose is kept — it is how many seconds are on
        screen — and the window slides with the last sample, as an
        oscilloscope's does; «A» gives the whole window back. A plot still
        on auto-range is left to it.
        """
        plots = [self._plot_raw, self._plot_env]
        if self._acc_enabled:
            plots.append(self._plot_acc)
        for pw in plots:
            vb = pw.getViewBox()
            if vb.autoRangeEnabled()[0]:
                continue
            x0, x1 = vb.viewRange()[0]
            ancho = x1 - x0
            if ancho <= 0 or abs(x1 - fin) < 0.5 / self._fs:
                continue
            vb.setXRange(fin - ancho, fin, padding=0)

    #: One colour per kind of stretch. Muted on purpose — these sit *behind*
    #: the trace, and a shading that competes with the signal defeats the
    #: point of showing the signal.
    _COLORES_FASE: ClassVar[dict[str, tuple[int, int, int, int]]] = {
        WARMUP: (150, 150, 150, 45),
        CALIBRATION: (230, 126, 34, 55),
        PREPARATION: (120, 160, 200, 40),
        RECORDING: (60, 160, 90, 40),
        GUIDED: (142, 68, 173, 45),
    }

    def show_recording(self, edf_path: str,
                       label_for: Callable[[MeasuredSpan], str],
                       contractions: Sequence[tuple[float, float]] = ()) -> str | None:
        """Put the recording that has just finished on the plots, whole.

        *contractions* are drawn as a bar along the bottom of both plots,
        each from where it starts to where the muscle is back at rest:
        the rows the fragment editor will propose
        (:func:`emgteach.fragments.recording_proposal`). The shading behind
        is the session's phases, what the application asked; the bar is
        what the muscle did, the letting go after the cue included
        (Ángel's gradation of 6 November 2026).

        After stopping, the operator can scroll back over what was just
        recorded without leaving the tab. The live plots
        show a thirty-second ring buffer, so the session is read back from the
        EDF rather than kept in memory — the file is the record of truth, it
        is already written and closed, and what is reviewed is then exactly
        what was saved, annotations included, instead of a parallel copy that
        could disagree with it.

        A failure here loses the review and nothing else: the recording is on
        disk and the analysis tab is untouched. It is not silent: what is
        returned is ``None`` when the review is on screen, and otherwise why
        it is not, for the tab to say in the event log. An error nobody
        expected is written to the error log too, and leaves the plots as
        they were rather than half drawn (the bench of 6 November 2026: a
        recording ended, sometimes, with no review and no word why).
        """
        try:
            nombres = list_edf_emg_channels(edf_path)
            if not nombres:
                return tr("the file has no EMG channel")
            señales = [read_edf_mne(edf_path, n) for n in nombres[:self._n_max]]
            fs = float(señales[0]["sfreq"])
            if fs <= 0:
                return tr("the file has no valid sampling rate")
        except Exception as exc:
            return tr("the file could not be read ({err})").format(err=exc)
        try:
            self._dibujar_revision(edf_path, label_for, contractions, nombres, señales, fs)
        except Exception as exc:
            from emgteach.crash import log_path, record_exception

            record_exception(type(exc), exc, exc.__traceback__)
            self.leave_review()
            return tr("an unexpected error ({err}); its details are in {path}").format(
                err=f"{type(exc).__name__}: {exc}", path=log_path())
        return None

    def _dibujar_revision(self, edf_path: str,
                          label_for: Callable[[MeasuredSpan], str],
                          contractions: Sequence[tuple[float, float]],
                          nombres: list[str], señales: list, fs: float) -> None:
        """The review itself, once the file is read (show_recording)."""
        self.leave_review()
        self._revisando = True
        self._revision_ruta = edf_path

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
        for c in range(len(señales), self._n_max):
            self._curves_raw[c].setData([], [])
            self._curves_env[c].setData([], [])
        # The lanes are named after the file being reviewed, not after the
        # label boxes: those still said «EMG1 / EMG2» while the shading beside
        # them read «FCR 1 … ECR 3», two names for the same muscle on one
        # screen. Restored from the boxes on the way back to live.
        for c, nombre in enumerate(nombres[:self._n_max]):
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

        marcas = señales[0].get("markers", [])
        tramos = phase_spans(
            parse_phase_markers(marcas),
            duracion, channel_names=dict(enumerate(nombres)),
        )
        # And what a guided session measured: each effort it marked.
        guiada = parse_session_markers(marcas)
        if guiada is not None:
            tramos = tuple(sorted(
                (*tramos, *(
                    PhaseSpan(max(0.0, t.start_s), min(duracion, t.end_s),
                              GUIDED, label_for(t))
                    for t in guiada.spans if t.end_s > 0 and t.start_s < duracion)),
                key=lambda sp: sp.start_s))
        alto = 1.15 * pico_env if pico_env > 0 else 1.0
        # Two rows for the names, and a name is dropped rather than written
        # over its neighbour. A short stretch beside a long one — «get ready»
        # between the last calibration rep and the recording — printed the
        # three words on top of each other and none of them could be read.
        px_por_s = self._px_por_segundo(duracion)
        ocupado = [-1e9, -1e9]             # right edge of each row, in pixels
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
            if not texto:
                continue
            etiqueta = pg.TextItem(texto, anchor=(0, 0), color=(90, 90, 90))
            inicio_px = tramo.start_s * px_por_s
            ancho_px = etiqueta.boundingRect().width()
            fila = next(
                (i for i, fin in enumerate(ocupado) if inicio_px > fin + 4),
                None,
            )
            if fila is None:               # both rows taken: leave it out
                continue
            ocupado[fila] = inicio_px + ancho_px
            etiqueta.setPos(tramo.start_s, alto * (1.0 - 0.10 * fila))
            self._plot_env.addItem(etiqueta, ignoreBounds=True)
            self._revision_items.append((self._plot_env, etiqueta))

        for a, b in contractions:
            for pw in (self._plot_raw, self._plot_env):
                barra = pg.LinearRegionItem(
                    values=(float(a), float(b)), movable=False,
                    span=(0.0, _BARRA_ALTO), brush=pg.mkBrush(*_BARRA_COLOR),
                    pen=pg.mkPen(None),
                )
                barra.setZValue(-5)        # over the phases, behind the trace
                pw.addItem(barra, ignoreBounds=True)
                self._revision_items.append((pw, barra))

        self._plot_raw.setTitle(tr("Recording just finished (review)"))
        self._plot_env.setTitle(tr("Envelope of the recording (review)"))
        self.logged.emit(tr(
            "Reviewing the recording: {dur:.1f} s. Drag to scroll, wheel to "
            "zoom. It goes back to live on the next recording."
        ).format(dur=duracion))
        if contractions:
            self.logged.emit(tr(
                "The bar under the traces marks each contraction the fragment "
                "editor will propose, from where it starts to where the muscle "
                "is back at rest."))
        self._con_barra = bool(contractions)

    def reviewing(self, edf_path: str) -> bool:
        """Whether *edf_path* is the recording on review now."""
        return self._revisando and bool(edf_path) and _misma_ruta(
            edf_path, self._revision_ruta)

    def show_measured(self, stretches: Sequence[tuple[float, float]]) -> None:
        """Draw, inside the bars, the stretches the analysis read its numbers
        on (:func:`emgteach.guided.measured_in_file`), in file time; those of
        a previous analysis of the same recording go. Nothing outside the
        review."""
        if not self._revisando:
            return
        for pw, item in self._medidos:
            try:
                pw.removeItem(item)
            except Exception:      # the plot was already torn down
                pass
            if (pw, item) in self._revision_items:
                self._revision_items.remove((pw, item))
        self._medidos = []
        for a, b in stretches:
            for pw in (self._plot_raw, self._plot_env):
                franja = pg.LinearRegionItem(
                    values=(float(a), float(b)), movable=False,
                    span=(0.0, _MEDIDO_ALTO), brush=pg.mkBrush(*_MEDIDO_COLOR),
                    pen=pg.mkPen(_MEDIDO_BORDE, width=1.2),
                )
                franja.setZValue(-4)       # over its bar, behind the trace
                # The pen draws its sides; its top, a fine dark edge too.
                filo = pg.LinearRegionItem(
                    values=(float(a), float(b)), movable=False,
                    span=(_MEDIDO_ALTO - _MEDIDO_FILO, _MEDIDO_ALTO),
                    brush=pg.mkBrush(*_MEDIDO_BORDE), pen=pg.mkPen(None),
                )
                filo.setZValue(-4)
                for item in (franja, filo):
                    pw.addItem(item, ignoreBounds=True)
                    self._medidos.append((pw, item))
                    self._revision_items.append((pw, item))
        self._mostrar_leyenda(self._con_barra, bool(stretches))

    def _mostrar_leyenda(self, barra: bool, medido: bool) -> None:
        """The line under the plots, with the measured stretches only: the
        bar, and the stretch inside it. Where nothing measured is drawn —
        the pair, kinematics, the quick contractions — the review is as it
        was."""
        self._leyenda_barra.setVisible(barra)
        self._leyenda_barra_txt.setVisible(barra)
        self._leyenda_medido.setVisible(medido)
        self._leyenda_medido_txt.setVisible(medido)
        self._leyenda.setVisible(medido)

    def _px_por_segundo(self, duracion: float) -> float:
        """Pixels one second of the review takes on screen, as first drawn.

        Only used to decide which phase names fit beside each other. Zooming
        afterwards does not re-run the decision: what matters is that the
        first view, the one the operator actually reads, is legible.
        """
        if duracion <= 0:
            return 0.0
        ancho = 0
        try:
            ancho = int(self._plot_env.getViewBox().width())
        except Exception:                  # not laid out yet
            ancho = 0
        if ancho <= 1:
            ancho = max(self._plot_env.width(), 900)
        return ancho / duracion

    def _nombre_fase(self, kind: str) -> str:
        """The word for a stretch of the session, for its label on the plot."""
        return {
            WARMUP: tr("warm-up"),
            CALIBRATION: tr("calibration"),
            PREPARATION: tr("get ready"),
            RECORDING: tr("recording"),
        }.get(kind, "")

    def leave_review(self) -> None:
        """Back to the live view: take the session and its shading off."""
        for pw, item in self._revision_items:
            try:
                pw.removeItem(item)
            except Exception:      # the plot was already torn down
                pass
        self._revision_items.clear()
        self._medidos = []
        self._revision_ruta = ""
        self._leyenda.setVisible(False)
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
            # canvas.
            pw.enableAutoRange(axis="x")
        self._plot_raw.setTitle(tr("Raw EMG signal (mV)"))
        self._plot_env.setTitle(tr("Envelope (mV)"))
        self.reset_all_scales()
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

        if idx == 1 and not self._revisando:
            # The live envelope follows its own peak; ▲▼ move the base scale
            # that following starts from, so the signal stays in view either
            # way. The finished recording under review keeps the plain zoom.
            nuevo = self._y_accum[1] / factor if zoom_in else self._y_accum[1] * factor
            if not 0.01 <= nuevo <= 100.0:
                return
            self._y_accum[1] = nuevo
            self._env_techo = None
            self._escala_envolvente_en_vivo(self._ultimo_pico_env)
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

    def reset_y_scales(self) -> None:
        """Restore the vertical scale of the two plots to their initial state."""
        self._y_accum = [1.0, 1.0]
        self._y_gain = [1.0, 1.0]
        # Envelope: never stacked, direct initial range.
        self._env_techo = None
        self._plot_env.setYRange(*self._y_ranges_init[1], padding=0)
        # Raw: the mode (stacked or overlaid) sets range and annotations.
        self._apply_stacking_mode()
        # ACC: drop the manual zoom back to the full ±1 g.
        self._acc_zoom = 1.0
        self._plot_acc.setYRange(-1.0, 1.0, padding=0)

    def _escala_envolvente_en_vivo(self, pico: float) -> None:
        """Keep the live envelope inside its axes, as the phones' view does.

        The scale used to be fixed — from the profile, or from the calibration
        — and a contraction above it was drawn off the top of the plot. That is
        the plot the student watches to know whether the effort is right, and
        the one the figures are taken from. The follower view on the phones
        never had the problem because it follows the peak, and so does this
        now: the top rises at once to keep the highest point of the visible
        window in view, and falls back gradually once that peak has scrolled
        away, never below the base scale (the calibrated one, times the ▲▼
        zoom).
        """
        ini_bajo, ini_alto = self._y_ranges_init[1]
        base = ini_alto * self._y_accum[1]
        objetivo = max(base, float(pico) * ENV_SIGUE_MARGEN)
        previo = self._env_techo
        if previo is None or objetivo >= previo:
            techo = objetivo
        else:
            techo = max(objetivo, previo * ENV_SIGUE_CAIDA)
        if previo is not None and abs(techo - previo) <= 1e-9 * max(1.0, techo):
            return
        self._env_techo = techo
        suelo = (ini_bajo / ini_alto) * techo if ini_alto > 0 else 0.0
        self._plot_env.setYRange(suelo, techo, padding=0)

    def autoscale(self, refs: list[float], raw_peaks: list[float]) -> None:
        """Fit the live plots to this subject once the MVC is known.

        Sets the *initial* Y ranges (so the ▲▼ reset returns to this
        calibrated scale) from the calibration itself: the envelope top is a
        headroom multiple of the largest MVC reference (leaving room for
        >100 %MVC phasic bursts and a small margin below 0), and the raw plot
        spans ±(largest raw peak × factor). Falls back to the profile
        defaults when a measure is missing, and never shrinks below them so a
        weak calibration cannot hide the signal.
        """
        # Envelope (plot 1): 0-based, with headroom above and a little below.
        if refs:
            top = max(refs) * AUTOSCALE_ENV_FACTOR
            top = max(top, self._profile().ylim_envelope[1])   # never shrink
            self._y_ranges_init[1] = (-0.05 * top, top)

        # Raw (plot 0): symmetric around 0. In stacked mode this half becomes
        # each lane's half-height (see _apply_stacking_mode).
        if raw_peaks:
            amp = max(raw_peaks) * AUTOSCALE_RAW_FACTOR
            amp = max(amp, self._profile().ylim_raw[1])        # never shrink
            self._y_ranges_init[0] = (-amp, amp)

        self.reset_y_scales()

    @Slot()
    def _on_tiempo_ampliar(self) -> None:
        """◀▶ — double the visible window (less detail, more context)."""
        nueva = min(self._n_visible * 2, MAX_POINTS)
        nueva = max(nueva, int(0.5 * self._fs))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()
        self._refresh_plots(force=True)

    @Slot()
    def _on_tiempo_reducir(self) -> None:
        """▶◀ — halve the visible window (more detail)."""
        nueva = max(self._n_visible // 2, int(0.5 * self._fs))
        self._n_visible = nueva
        self._sync_combo_zoom()
        self._update_ventana_label()
        self._refresh_plots(force=True)

    @Slot(int)
    def _on_combo_zoom_changed(self, index: int) -> None:
        factor = _ZOOM_FACTORS[index]
        nueva = MAX_POINTS // factor
        nueva = max(nueva, int(0.5 * self._fs))
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
        model = cast(QStandardItemModel, self._combo_zoom.model())
        for i, f in enumerate(_ZOOM_FACTORS):
            n = MAX_POINTS // f
            item = model.item(i)
            if item:
                enabled = n >= int(0.5 * self._fs)
                item.setEnabled(enabled)

    def _update_ventana_label(self) -> None:
        segundos = self._n_visible / self._fs
        if segundos >= 1.0:
            self._lbl_ventana_info.setText(f"{segundos:.1f} {tr('s visible')}")
        else:
            self._lbl_ventana_info.setText(f"{segundos * 1000:.0f} {tr('ms visible')}")

    def reset_all_scales(self) -> None:
        """Full reset: Y ranges + time window back to the initial state."""
        self.reset_y_scales()
        self._n_visible = 5 * self._fs
        self._sync_combo_zoom()
        self._update_ventana_label()
