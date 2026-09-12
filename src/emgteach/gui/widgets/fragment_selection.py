"""Interactive editor to select the significant fragments of a recording.

This is the GUI half of the assisted-selection feature: it proposes the
informative fragments automatically (via
:func:`emgteach.selection.suggest_significant_segments`) and lets the user
accept, tweak, add or drop them before the analysis runs. The core logic
lives in :mod:`emgteach.selection`; this dialog only edits a list of
``(start_s, end_s)`` windows and shows a preview.

**Two levels of adjustment, both live.** The first version of this dialogue
carried eight spin boxes nobody could set without already knowing what they
did; the second carried none, and the recourse when the proposal was wrong
was to drag seconds row by row. What was asked for is the thing in between:
a couple of settings a student can move *while looking at the result*. So
the basic level is two sliders — how sensitive the detector is, and from
what share of the stronger muscle the weaker one counts as co-activating —
and every move of them redraws the shaded stretches and the rows at once.
The fine level, folded away until asked for, adds the minimum duration, the
gap that joins two pieces, and how readily a run is split into separate
contractions. The threshold the sensitivity sets is drawn as a dashed line
over the envelope, so it is set by eye, which is the only way a number of
that kind ever gets set.

**Three steps, and the screen holds still.** The sensitivity comes first,
above the plot, with a counter beside it: how many contractions of each kind
are marked against how many the protocol asks for, so a missing flexion is
seen without anyone having to look for it. Then each contraction is taken in
turn — with ◀ ▶, or by clicking it on the plot — and three buttons keep it,
drop it, or split it in two where a row turns out to hold two contractions;
one button per muscle confirms or corrects who led it. Going through them
moves a highlight; the axes do not move.

**Correcting never places a mark by hand.** Dropping a wrong mark that sits
beside a contraction the detector missed left that contraction unrepresented,
and dragging the mark onto it measures whatever window the hand let go of.
Instead, the stretches that clear the line half the sensitivity would draw,
and that no row covers, are drawn dotted, and a click makes one a row. A mark
therefore always sits on activity the threshold located — much what lowering
k would do, applied to one contraction instead of the whole recording. A
split, likewise, goes to the valley the envelopes show between the two peaks
(see :func:`emgteach.selection.split_fragment`), not to where a hand would
put it, and the cut is drawn before it is made.

The dialog is constructible directly from signal arrays (so it can be unit
tested headless) or from an EDF file via :meth:`FragmentSelectionDialog.from_edf`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.charts import COLOUR_1, COLOUR_2
from emgteach.coactivation import _DOMINANCE, propose_labels
from emgteach.dsp import process_offline
from emgteach.i18n import tr
from emgteach.selection import (
    DEFAULT_DETECTION,
    Segment,
    _find_runs,
    activity_threshold,
    normalise_segments,
    split_fragment,
    suggest_significant_segments,
    total_duration_s,
)

#: The shading of a kept fragment, by who led it: the first muscle, the
#: second, both, or nobody in particular (one muscle, or no name).
_SHADE_1 = COLOUR_1
_SHADE_2 = COLOUR_2
_SHADE_BOTH = "#8E44AD"
_SHADE_PLAIN = "#4CAF50"
_SHADE_DROPPED = "#9E9E9E"
#: The dotted outline of a candidate, and the outline of the row under review.
_EDGE_CANDIDATE = "#6B7580"
_EDGE_CURRENT = "#1A2A3A"
#: The counter, when the count matches the protocol and when it does not.
_COUNT_OK = "#2E7D32"
_COUNT_OFF = "#B9770E"

#: Candidates are looked for at this share of the sensitivity, and never
#: below the floor, under which the resting noise itself clears the line.
_K_CANDIDATE = 0.5
_K_CANDIDATE_MIN = 1.0

#: How long after the last slider move the proposal is rebuilt. Long enough
#: that dragging does not rebuild at every pixel, short enough to feel live.
_DEBOUNCE_MS = 150


def default_detection(k: float | None = None) -> dict[str, float]:
    """The detection settings the dialogue opens on, co-activation rule included.

    ``k`` is the practical's own sensitivity (see
    :func:`emgteach.modes.mode_detection_k`); without it, the core default.
    """
    d = dict(DEFAULT_DETECTION)
    d["both_ratio"] = float(_DOMINANCE)
    if k is not None:
        d["k"] = float(k)
    return d


class FragmentSelectionDialog(QDialog):
    """Modal editor returning the fragments to analyse.

    Parameters
    ----------
    raw : ndarray
        Raw signal (mV).
    fs : float
        Sampling frequency (Hz).
    filter_kwargs : dict
        ``f_low``/``f_high``/``f_notch``/``f_env`` used both for the
        envelope preview and for the automatic suggestion.
    segments : list of (float, float), optional
        Pre-existing selection to load. When ``None`` the dialog runs the
        automatic suggestion on open.
    detection : dict, optional
        The settings to open the sliders on — what the editor was left on
        last time — so a second visit starts where the first ended.
    default_k : float, optional
        The sensitivity this practical opens on, and the one «Reset» goes
        back to. ``detection`` wins over it when both are given.
    expected : sequence of int, optional
        How many contractions the protocol asks for: led by the first
        muscle, by the second and by both — or one total, with one muscle.
    parent : QWidget, optional
        Parent widget.
    """

    def __init__(
        self,
        raw: np.ndarray,
        fs: float,
        filter_kwargs: dict[str, float],
        segments: list[tuple[float, float]] | None = None,
        labels: list[str] | None = None,
        span: tuple[float, float] | None = None,
        naming: bool = True,
        raw_2: np.ndarray | None = None,
        name_1: str = '',
        name_2: str = '',
        mvc_ref: float | None = None,
        mvc_ref_2: float | None = None,
        detection: dict[str, float] | None = None,
        default_k: float | None = None,
        expected: Sequence[int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Select analysis fragments"))
        # Bigger than it was: the plot is now the control, and a plot in
        # which a twelve-second series occupies six hundred pixels is one in
        # which the stretches can be told apart and clicked.
        self.setMinimumSize(960, 640)
        self.resize(1120, 780)

        self._raw = np.asarray(raw, dtype=np.float64).ravel()
        self._fs = float(fs)
        self._f_low = float(filter_kwargs.get("f_low", 20.0))
        self._f_high = float(filter_kwargs.get("f_high", 450.0))
        self._f_notch = float(filter_kwargs.get("f_notch", 50.0))
        self._f_env = float(filter_kwargs.get("f_env", 5.0))
        self._full_duration = len(self._raw) / self._fs
        # The stretch this editor is allowed to work in. In a two-phase
        # session that is the recording phase: the calibration is signal
        # too, and the automatic suggestion found its six maximal efforts
        # and offered them as fragments of the task — which is the one
        # decision the application exists to take out of the operator's
        # hands, arriving back as a suggestion.
        self._span = (
            (max(0.0, float(span[0])), min(self._full_duration, float(span[1])))
            if span else (0.0, self._full_duration)
        )
        # Whether naming a fragment does anything here. A name is only read
        # by the co-activation table, which needs an agonist and an
        # antagonist; with a single muscle on screen there is no such table
        # and the column asked for something no part of the program would
        # ever look at.
        self._naming = bool(naming)
        # The antagonist, when there is one. Only used to work out which
        # muscle led each contraction, which is the one part of the naming
        # a measurement can settle: see coactivation.propose_labels.
        self._raw_2 = (
            np.asarray(raw_2, dtype=np.float64).ravel()
            if raw_2 is not None else None
        )
        self._name_1 = name_1 or tr('Muscle {n}').format(n=1)
        self._name_2 = name_2 or tr('Muscle {n}').format(n=2)
        #: Each muscle's own maximum, when the recording carries one: the
        #: only footing on which two different muscles compare.
        self._mvc_ref = mvc_ref
        self._mvc_ref_2 = mvc_ref_2
        self._row_widgets: list[dict[str, Any]] = []
        #: The practical's sensitivity: where the slider opens and where
        #: «Reset» takes it back to.
        self._k_defecto = (
            float(default_k) if default_k is not None
            else float(DEFAULT_DETECTION["k"])
        )
        #: The detection settings, as the sliders have them.
        self._det = default_detection(self._k_defecto)
        if detection:
            self._det.update({k: float(v) for k, v in detection.items()
                              if k in self._det})
        self._both_label = tr("Co-activation")
        #: Each envelope over the span and where it clears the lower line
        #: (see _buscar_candidatos), for the candidates a click can promote.
        self._bajo: list[tuple[np.ndarray, np.ndarray]] = []
        #: The row being gone through, or -1 when none is.
        self._fila_actual = -1
        self._esperadas_iniciales = tuple(int(n) for n in (expected or ()))

        # Envelope for the preview (downsampled when drawing).
        self._env = self._envolvente(self._raw)
        self._t = np.arange(len(self._env)) / self._fs
        self._env_2 = self._envolvente(self._raw_2)
        self._techo = self._techo_de_la_senal()
        # What a split needs: each envelope and its resting baseline, which
        # does not move with the sensitivity.
        i0, i1 = round(self._span[0] * self._fs), round(self._span[1] * self._fs)
        self._envs = [e for e in (self._env, self._env_2) if e is not None]
        self._bases = [activity_threshold(e[i0:i1], 1.0)[0] for e in self._envs]

        # Rebuilding the proposal is a filter pass over the whole span; a
        # slider being dragged asks for it at every pixel. One timer, armed
        # on every move, fires once the hand has stopped.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_DEBOUNCE_MS)
        self._timer.timeout.connect(self._auto_suggest)

        self._build_ui()

        if segments:
            nombres = labels or []
            self._buscar_candidatos()
            self._set_rows([
                Segment(a, b, reason="manual",
                        label=nombres[i] if i < len(nombres) else "")
                for i, (a, b) in enumerate(segments)
            ])
        else:
            self._auto_suggest()

    def _envolvente(self, raw: np.ndarray | None):
        """The envelope of a channel, or None when there is no channel."""
        if raw is None:
            return None
        try:
            return process_offline(
                raw,
                self._fs,
                f_low=self._f_low,
                f_high=self._f_high,
                f_notch=self._f_notch,
                f_env=self._f_env,
            )["emg_envelope"]
        except Exception:  # pragma: no cover — very short/degenerate signal
            return np.abs(raw)

    def _techo_de_la_senal(self) -> float:
        """The top of the preview, fixed for the life of the dialogue.

        Going through the rows must move the highlight and nothing else; an
        axis that rescaled itself at every redraw shifted the whole trace
        under the eye of whoever was reading it.
        """
        a, b = self._span
        i0, i1 = round(a * self._fs), round(b * self._fs)
        picos = [
            float(np.nanmax(e[i0:i1]))
            for e in (self._env, self._env_2)
            if e is not None and e[i0:i1].size
        ]
        alto = max(picos) if picos else 0.0
        return 1.08 * alto if np.isfinite(alto) and alto > 0 else 1.0

    def _nombres_propuestos(self, segs: list[Segment]) -> list[str]:
        """Which muscle led each proposal, where that can be measured.

        The operator was being asked to name every contraction by hand, and
        for a series of a dozen that is a dozen decisions, all of them the
        same one. The part of it that is a measurement — which of the two
        muscles worked harder — the program can make itself; what it cannot
        do is say that FCR leading means the subject was asked to flex,
        because it only knows these muscles as the names that were typed.
        So it fills in the muscle, and the reading is left where it was.
        """
        if self._env_2 is None or self._env is None:
            return [s.label for s in segs]
        return propose_labels(
            self._env, self._env_2, self._fs,
            [(s.start_s, s.end_s) for s in segs],
            name_1=self._name_1, name_2=self._name_2,
            both_label=self._both_label,
            ref_1=self._mvc_ref, ref_2=self._mvc_ref_2,
            both_ratio=self._det["both_ratio"],
        )

    def _categorias(self) -> list[str | None]:
        """What the counter counts: each name the app proposes, or every row."""
        if self._naming and self._env_2 is not None:
            return [self._name_1, self._name_2, self._both_label]
        return [None]

    # -- construction --------------------------------------------------------

    @classmethod
    def from_edf(
        cls,
        edf_path: str,
        channel_name: str,
        filter_kwargs: dict[str, float],
        segments: list[tuple[float, float]] | None = None,
        labels: list[str] | None = None,
        span: tuple[float, float] | None = None,
        naming: bool = True,
        channel_name_2: str | None = None,
        mvc_ref: float | None = None,
        mvc_ref_2: float | None = None,
        detection: dict[str, float] | None = None,
        default_k: float | None = None,
        expected: Sequence[int] | None = None,
        parent: QWidget | None = None,
    ) -> FragmentSelectionDialog:
        """Build the dialog by loading one or two channels from an EDF."""
        from emgteach.io import read_edf_mne

        edf = read_edf_mne(edf_path, channel_name)
        raw_2 = None
        if channel_name_2:
            try:
                raw_2 = read_edf_mne(edf_path, channel_name_2)["emg_raw"]
            except Exception:  # pragma: no cover — channel gone from the file
                raw_2 = None
        return cls(
            edf["emg_raw"],
            float(edf["sfreq"]),
            filter_kwargs,
            segments=segments,
            labels=labels,
            span=span,
            naming=naming,
            raw_2=raw_2,
            name_1=channel_name,
            name_2=channel_name_2 or '',
            mvc_ref=mvc_ref,
            mvc_ref_2=mvc_ref_2,
            detection=detection,
            default_k=default_k,
            expected=expected,
            parent=parent,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # What it is for, in the words a student would use, in the order the
        # screen is used: the sensitivity, the clicks, the walk through.
        texto = tr(
            "Each row is one contraction found in the recording. Set the "
            "sensitivity until the count beside it matches what was done. "
            "Then go through the contractions with ◀ ▶, or click one on the "
            "plot, and keep it, drop it or split it in two; a click on a "
            "dotted stretch adds it. Only the kept rows are analysed, joined "
            "up as if recorded in one go. Press «Use these fragments» even if "
            "you change nothing: that is what applies them."
        )
        if self._naming:
            texto += " " + tr(
                "The «Muscle» column says which of the two led each "
                "contraction; the app fills it in by comparing them. Change it "
                "if you disagree. Consecutive rows with the same name become a "
                "single window of the co-activation table, so a run of "
                "flexions is measured as one."
            )
        info = QLabel(texto)
        info.setWordWrap(True)
        root.addWidget(info)

        # The sensitivity before the plot: it decides what is marked, and it
        # is set looking at the whole recording and at the count.
        root.addWidget(self._build_adjustments())

        # Preview plot — the control, not a decoration: the shaded stretches
        # are the rows, the dotted ones are what a click can add, the dashed
        # line is the sensitivity.
        self._fig = Figure(figsize=(9.0, 3.0), constrained_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(220)
        self._ax = self._fig.add_subplot(111)
        self._canvas.mpl_connect("button_press_event", self._on_click)
        root.addWidget(self._canvas, stretch=3)

        root.addLayout(self._build_navigation())

        # Fragment table.
        # No «Reason» column: it said «activity» / «manual» / «whole
        # recording», which is where a row came from, not anything the
        # student can act on.
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            tr("Keep"), tr("Start (s)"), tr("End (s)"), tr("Duration (s)"),
            # «Muscle», not «Manoeuvre»: what the column holds is which of the
            # two led the contraction, which is what the app can measure.
            tr("Muscle"),
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.currentCellChanged.connect(self._al_cambiar_fila)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        if not self._naming:
            # Hidden rather than removed: the column indices are wired into the
            # row builder and the readers, and one practical having a column
            # the others do not is not worth two sets of indices.
            self._table.setColumnHidden(4, True)
        root.addWidget(self._table, stretch=2)

        # Action buttons.
        btn_row = QHBoxLayout()
        self._btn_auto = QPushButton(tr("Start over"))
        self._btn_auto.setToolTip(
            tr("Discard the changes and go back to what the app proposed.")
        )
        self._btn_auto.clicked.connect(self._auto_suggest)
        btn_row.addWidget(self._btn_auto)
        self._btn_add = QPushButton(tr("Add fragment"))
        self._btn_add.setToolTip(
            tr("Add a row for a contraction the app did not find.")
        )
        self._btn_add.clicked.connect(self._add_fragment)
        btn_row.addWidget(self._btn_add)
        self._btn_remove = QPushButton(tr("Remove selected"))
        self._btn_remove.setToolTip(tr("Delete the selected row."))
        self._btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(self._btn_remove)
        self._btn_whole = QPushButton(tr("Whole recording"))
        self._btn_whole.setToolTip(tr("Clear the selection and analyse everything."))
        self._btn_whole.clicked.connect(self._use_whole)
        btn_row.addWidget(self._btn_whole)
        btn_row.addStretch()
        self._lbl_total = QLabel("")
        btn_row.addWidget(self._lbl_total)
        root.addLayout(btn_row)

        # OK / Cancel.
        ok_row = QHBoxLayout()
        ok_row.addStretch()
        self._btn_cancel = QPushButton(tr("Cancel"))
        self._btn_cancel.clicked.connect(self.reject)
        ok_row.addWidget(self._btn_cancel)
        self._btn_ok = QPushButton(tr("Use these fragments"))
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self.accept)
        ok_row.addWidget(self._btn_ok)
        root.addLayout(ok_row)

    def _build_adjustments(self) -> QGroupBox:
        """The two levels of adjustment: two sliders, and a folded fine row."""
        grp = QGroupBox(tr("Adjust the proposal"))
        lay = QGridLayout(grp)
        lay.setContentsMargins(8, 4, 8, 6)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(4)

        # Basic 1: sensitivity. The slider holds k × 10 (a QSlider is integer).
        lay.addWidget(QLabel(tr("Sensitivity")), 0, 0)
        self._sld_k = QSlider(Qt.Orientation.Horizontal)
        self._sld_k.setRange(10, 60)
        self._sld_k.setValue(round(self._det["k"] * 10))
        self._sld_k.setToolTip(tr("lower finds more contractions; higher, fewer"))
        self._sld_k.valueChanged.connect(self._on_k)
        lay.addWidget(self._sld_k, 0, 1)
        self._lbl_k = QLabel()
        self._lbl_k.setMinimumWidth(52)
        lay.addWidget(self._lbl_k, 0, 2)
        pista_k = QLabel(tr("lower finds more contractions; higher, fewer"))
        pista_k.setStyleSheet("color:#6B7580; font-size:10px;")
        lay.addWidget(pista_k, 0, 3)

        # The count, beside the setting that moves it: how many of each kind
        # are marked, over how many the protocol asks for.
        cabecera = QLabel(tr("Marked / expected"))
        cabecera.setToolTip(tr(
            "Kept rows of each kind, over how many the protocol asks for."
        ))
        lay.addWidget(cabecera, 1, 0)
        cuenta = QHBoxLayout()
        cuenta.setSpacing(6)
        self._contadores: list[tuple[str | None, QLabel, QSpinBox]] = []
        for i, categoria in enumerate(self._categorias()):
            etiqueta = QLabel()
            spin = QSpinBox()
            spin.setRange(0, 99)
            spin.setSpecialValueText("—")
            if i < len(self._esperadas_iniciales):
                spin.setValue(self._esperadas_iniciales[i])
            spin.setToolTip(tr(
                "How many the protocol asks for. Change it if a series was "
                "repeated; «—» counts without a target."
            ))
            spin.valueChanged.connect(self._refrescar_contador)
            cuenta.addWidget(etiqueta)
            cuenta.addWidget(spin)
            cuenta.addSpacing(12)
            self._contadores.append((categoria, etiqueta, spin))
        cuenta.addStretch()
        lay.addLayout(cuenta, 1, 1, 1, 3)

        # Basic 2, only with two muscles: the co-activation rule. Holds the
        # ratio in percent.
        self._sld_ratio = QSlider(Qt.Orientation.Horizontal)
        self._sld_ratio.setRange(20, 90)
        self._sld_ratio.setValue(round(self._det["both_ratio"] * 100))
        self._sld_ratio.valueChanged.connect(self._on_ratio)
        self._lbl_ratio = QLabel()
        self._lbl_ratio.setMinimumWidth(52)
        self._fila_ratio = [
            QLabel(tr("Co-activation when the weaker muscle exceeds")),
            self._sld_ratio, self._lbl_ratio, QLabel(tr("% of the stronger")),
        ]
        for col, w in enumerate(self._fila_ratio):
            lay.addWidget(w, 2, col)
            w.setVisible(self._naming and self._env_2 is not None)

        # The fine level, folded. A toggle button rather than a checkbox,
        # because it reveals controls rather than setting anything.
        self._btn_fino = QToolButton()
        self._btn_fino.setCheckable(True)
        self._btn_fino.setAutoRaise(True)
        self._btn_fino.setText("▸ " + tr("Fine adjustment"))
        self._btn_fino.toggled.connect(self._toggle_fino)
        lay.addWidget(self._btn_fino, 3, 0, 1, 2)
        self._btn_reset = QPushButton(tr("Reset"))
        self._btn_reset.setToolTip(tr(
            "Moving a setting rebuilds the proposal; rows edited by hand are "
            "replaced."
        ))
        self._btn_reset.clicked.connect(self._reset_detection)
        lay.addWidget(self._btn_reset, 3, 2)
        pista = QLabel(tr("Click a stretch to select it; a dotted one, to add it."))
        pista.setStyleSheet("color:#6B7580; font-size:10px;")
        lay.addWidget(pista, 3, 3)

        self._box_fino = QWidget()
        fino = QGridLayout(self._box_fino)
        fino.setContentsMargins(0, 0, 0, 0)
        fino.setHorizontalSpacing(8)
        fino.setVerticalSpacing(4)
        fino.addWidget(QLabel(tr("Minimum duration (s)")), 0, 0)
        self._spin_min = QDoubleSpinBox()
        self._spin_min.setRange(0.1, 3.0)
        self._spin_min.setSingleStep(0.1)
        self._spin_min.setDecimals(1)
        self._spin_min.setValue(self._det["min_duration_s"])
        self._spin_min.valueChanged.connect(self._on_fine)
        fino.addWidget(self._spin_min, 0, 1)
        fino.addWidget(QLabel(tr("Join gaps shorter than (s)")), 0, 2)
        self._spin_gap = QDoubleSpinBox()
        self._spin_gap.setRange(0.0, 2.0)
        self._spin_gap.setSingleStep(0.1)
        self._spin_gap.setDecimals(1)
        self._spin_gap.setValue(self._det["merge_gap_s"])
        self._spin_gap.valueChanged.connect(self._on_fine)
        fino.addWidget(self._spin_gap, 0, 3)
        fino.addWidget(QLabel(tr("Split between contractions")), 1, 0)
        self._sld_prom = QSlider(Qt.Orientation.Horizontal)
        self._sld_prom.setRange(5, 60)
        self._sld_prom.setValue(round(self._det["prominence"] * 100))
        self._sld_prom.setToolTip(tr(
            "lower splits a series more readily; higher keeps it together"
        ))
        self._sld_prom.valueChanged.connect(self._on_prom)
        fino.addWidget(self._sld_prom, 1, 1)
        self._lbl_prom = QLabel()
        self._lbl_prom.setMinimumWidth(52)
        fino.addWidget(self._lbl_prom, 1, 2)
        pista_p = QLabel(tr("lower splits a series more readily; higher keeps it together"))
        pista_p.setStyleSheet("color:#6B7580; font-size:10px;")
        fino.addWidget(pista_p, 1, 3)
        self._box_fino.setVisible(False)
        lay.addWidget(self._box_fino, 4, 0, 1, 4)
        lay.setColumnStretch(1, 1)
        lay.setColumnStretch(3, 1)

        self._refresh_setting_labels()
        return grp

    def _build_navigation(self) -> QHBoxLayout:
        """◀ ▶ through the rows, and one button per name to confirm who led."""
        nav = QHBoxLayout()
        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedWidth(40)
        self._btn_prev.setToolTip(tr("Previous contraction"))
        self._btn_prev.clicked.connect(self._anterior)
        nav.addWidget(self._btn_prev)
        self._lbl_nav = QLabel()
        self._lbl_nav.setMinimumWidth(240)
        self._lbl_nav.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self._lbl_nav)
        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedWidth(40)
        self._btn_next.setToolTip(tr("Next contraction"))
        self._btn_next.clicked.connect(self._siguiente)
        nav.addWidget(self._btn_next)
        # What is done with the contraction under review, one click each.
        # Keep and drop move on to the next, like the names; a split stays on
        # the first half, whose name is the next thing to check.
        nav.addSpacing(16)
        self._btn_mantener = QPushButton(tr("Keep it"))
        self._btn_mantener.setCheckable(True)
        self._btn_mantener.setToolTip(
            tr("Keep this contraction in the analysis and go on to the next.")
        )
        self._btn_mantener.clicked.connect(self._mantener)
        nav.addWidget(self._btn_mantener)
        self._btn_eliminar = QPushButton(tr("Drop it"))
        self._btn_eliminar.setCheckable(True)
        self._btn_eliminar.setToolTip(tr(
            "Leave this contraction out of the analysis and go on to the next. "
            "It stays on the plot, hatched, and «Keep it» brings it back."
        ))
        self._btn_eliminar.clicked.connect(self._eliminar)
        nav.addWidget(self._btn_eliminar)
        self._btn_dividir = QPushButton(tr("Split it"))
        self._btn_dividir.clicked.connect(self._dividir)
        nav.addWidget(self._btn_dividir)
        # Confirming is choosing, not typing: the three things the column can
        # say, one click each, and the click moves on to the next row.
        self._btns_nombre: dict[str, QPushButton] = {}
        if self._naming and self._env_2 is not None:
            nav.addSpacing(16)
            nav.addWidget(QLabel(tr("Led by:")))
            for nombre, color in ((self._name_1, _SHADE_1),
                                  (self._name_2, _SHADE_2),
                                  (self._both_label, _SHADE_BOTH)):
                b = QPushButton(nombre)
                b.setCheckable(True)
                # Colour and weight only: a border in a style sheet takes the
                # button's native look away and shrinks it to its text.
                b.setStyleSheet(
                    f"QPushButton:checked {{ color: {color}; font-weight: bold; }}"
                )
                b.setToolTip(tr("Name this contraction and go on to the next."))
                b.clicked.connect(lambda _c=False, n=nombre: self._etiquetar(n))
                nav.addWidget(b)
                self._btns_nombre[nombre] = b
        nav.addStretch()
        return nav

    # -- the settings --------------------------------------------------------

    def _refresh_setting_labels(self) -> None:
        self._lbl_k.setText(f"k = {self._det['k']:.1f}")
        self._lbl_ratio.setText(f"{self._det['both_ratio'] * 100:.0f} %")
        self._lbl_prom.setText(f"{self._det['prominence']:.2f}")

    def _on_k(self, value: int) -> None:
        self._det["k"] = value / 10.0
        self._refresh_setting_labels()
        self._timer.start()

    def _on_prom(self, value: int) -> None:
        self._det["prominence"] = value / 100.0
        self._refresh_setting_labels()
        self._timer.start()

    def _on_fine(self, _value: float) -> None:
        self._det["min_duration_s"] = float(self._spin_min.value())
        self._det["merge_gap_s"] = float(self._spin_gap.value())
        self._timer.start()

    def _on_ratio(self, value: int) -> None:
        """The co-activation rule moves the names, not the rows: no rebuild."""
        self._det["both_ratio"] = value / 100.0
        self._refresh_setting_labels()
        self._relabel_rows()

    def _toggle_fino(self, on: bool) -> None:
        self._box_fino.setVisible(on)
        self._btn_fino.setText(("▾ " if on else "▸ ") + tr("Fine adjustment"))

    def _reset_detection(self) -> None:
        self._det = default_detection(self._k_defecto)
        for w in (self._sld_k, self._sld_ratio, self._sld_prom,
                  self._spin_min, self._spin_gap):
            w.blockSignals(True)
        self._sld_k.setValue(round(self._det["k"] * 10))
        self._sld_ratio.setValue(round(self._det["both_ratio"] * 100))
        self._sld_prom.setValue(round(self._det["prominence"] * 100))
        self._spin_min.setValue(self._det["min_duration_s"])
        self._spin_gap.setValue(self._det["merge_gap_s"])
        for w in (self._sld_k, self._sld_ratio, self._sld_prom,
                  self._spin_min, self._spin_gap):
            w.blockSignals(False)
        self._refresh_setting_labels()
        self._auto_suggest()

    def detection_kwargs(self) -> dict[str, float]:
        """The settings the editor was left on, for the analysis to reuse."""
        return dict(self._det)

    def expected_counts(self) -> tuple[int, ...]:
        """The targets the counter was left on, for the next visit."""
        return tuple(spin.value() for _c, _l, spin in self._contadores)

    # -- row management ------------------------------------------------------

    def _set_rows(self, segments: list[Segment]) -> None:
        """Replace the table contents with ``segments``."""
        self._reconstruir([(seg, True) for seg in segments])

    def _reconstruir(self, filas: list[tuple[Segment, bool]]) -> None:
        """Replace the table contents; no row is under review afterwards."""
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        self._row_widgets = []
        for seg, keep in filas:
            self._append_row(seg, keep=keep)
        self._table.blockSignals(False)
        self._fila_actual = -1
        self._refresh_derived()

    def _append_row(self, seg: Segment, keep: bool) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        chk = QCheckBox()
        chk.setChecked(keep)
        chk.stateChanged.connect(self._refresh_derived)
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(chk)
        self._table.setCellWidget(row, 0, holder)

        spin_start = self._make_spin(seg.start_s)
        spin_end = self._make_spin(seg.end_s)
        spin_start.valueChanged.connect(self._refresh_derived)
        spin_end.valueChanged.connect(self._refresh_derived)
        self._table.setCellWidget(row, 1, spin_start)
        self._table.setCellWidget(row, 2, spin_end)

        dur_item = QTableWidgetItem(f"{seg.duration_s:.2f}")
        dur_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._table.setItem(row, 3, dur_item)

        # The three things this column can say, which are the three the app
        # itself puts there.
        combo_nombre = QComboBox()
        combo_nombre.setEditable(True)
        for opcion in ("", self._name_1, self._name_2, self._both_label):
            if opcion not in {combo_nombre.itemText(i)
                              for i in range(combo_nombre.count())}:
                combo_nombre.addItem(opcion)
        combo_nombre.setCurrentText(seg.label)
        combo_nombre.setToolTip(tr(
            "Which muscle led this contraction. The app works it out by "
            "comparing the two; change it if you disagree, or empty it to "
            "leave the contraction out of the co-activation table."
        ))
        combo_nombre.currentTextChanged.connect(self._refresh_derived)
        self._table.setCellWidget(row, 4, combo_nombre)

        self._row_widgets.append({
            "keep": chk, "start": spin_start, "end": spin_end,
            "dur": dur_item, "label": combo_nombre,
        })

    def _make_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(self._span[0], max(self._span[1], value))
        spin.setDecimals(2)
        spin.setSingleStep(0.1)
        spin.setValue(value)
        return spin

    def _current_segments(self, only_kept: bool) -> list[Segment]:
        segs: list[Segment] = []
        for w in self._row_widgets:
            keep = w["keep"].isChecked()  # type: ignore[attr-defined]
            if only_kept and not keep:
                continue
            a = w["start"].value()  # type: ignore[attr-defined]
            b = w["end"].value()  # type: ignore[attr-defined]
            if b > a:
                nombre = w["label"].currentText().strip()  # type: ignore[attr-defined]
                segs.append(Segment(a, b, label=nombre))
        return segs

    def _filas_con_estado(self) -> list[tuple[Segment, bool]]:
        """Every row as it stands, kept or not, for a rebuild that keeps them."""
        return [
            (Segment(w["start"].value(), w["end"].value(), reason="manual",
                     label=w["label"].currentText().strip()),
             w["keep"].isChecked())
            for w in self._row_widgets
        ]

    def _relabel_rows(self) -> None:
        """Name every row again under the current co-activation rule."""
        if not self._naming or self._env_2 is None:
            return
        segs = self._current_segments(only_kept=False)
        if len(segs) != len(self._row_widgets):
            return
        for w, nombre in zip(self._row_widgets, self._nombres_propuestos(segs),
                             strict=True):
            combo = w["label"]
            combo.blockSignals(True)
            combo.setCurrentText(nombre)
            combo.blockSignals(False)
        self._refresh_derived()

    # -- actions -------------------------------------------------------------

    def _detectar(self, k: float) -> list[Segment]:
        """What the detector finds at sensitivity ``k``, in the file's clock."""
        a, b = self._span
        i0, i1 = round(a * self._fs), round(b * self._fs)

        def detecta(raw):
            return suggest_significant_segments(
                raw[i0:i1],
                self._fs,
                f_low=self._f_low,
                f_high=self._f_high,
                f_notch=self._f_notch,
                f_env=self._f_env,
                k=k,
                min_duration_s=self._det["min_duration_s"],
                merge_gap_s=self._det["merge_gap_s"],
                prominence=self._det["prominence"],
            )

        # Back into the file's own clock: the worker crops by these numbers.
        filas = [
            Segment(a + x.start_s, a + x.end_s, x.score, x.reason, x.label)
            for x in detecta(self._raw)
        ]
        if self._raw_2 is not None:
            # Both muscles, not just the one on display. The selection crops
            # *both* channels, so proposing only the contractions of the
            # channel that happens to be selected quietly decided which half
            # of the session got analysed.
            filas += [
                Segment(a + x.start_s, a + x.end_s, x.score, x.reason, x.label)
                for x in detecta(self._raw_2)
            ]
            filas = normalise_segments(filas, self._full_duration)
        return filas

    def _buscar_candidatos(self) -> None:
        """Where each envelope clears the line half the sensitivity draws.

        Not the detector run again at a lower k: its splitting step weighs a
        peak against the tallest one in the same run, so a weak contraction
        between two strong ones, found at one k, was lost again at a lower
        one once the three had merged into a single run. The line alone has
        no such step. None when k is already at the floor.
        """
        self._bajo = []
        k = max(_K_CANDIDATE_MIN, self._det["k"] * _K_CANDIDATE)
        if k >= self._det["k"]:
            return
        a, b = self._span
        i0, i1 = round(a * self._fs), round(b * self._fs)
        for env in (self._env, self._env_2):
            if env is None:
                continue
            tramo = np.asarray(env[i0:i1], dtype=np.float64)
            _base, umbral = activity_threshold(tramo, k)
            self._bajo.append((tramo, tramo > umbral))

    def _candidatos_libres(self) -> list[Segment]:
        """The stretches over the lower line that no row covers.

        Worked out at every call because the rows move. What is left of a
        row's own contraction once the row is taken out — the rise into it,
        the fall out of it — is not a candidate: it peaks where it touches
        the row. A stretch that rises again before falling is another
        contraction, and stays even when it touches one.
        """
        if not self._bajo:
            return []
        a = self._span[0]
        filas = [
            (w["start"].value(), w["end"].value())  # type: ignore[attr-defined]
            for w in self._row_widgets
        ]
        min_n = max(1, round(self._det["min_duration_s"] * self._fs))
        hallados: list[Segment] = []
        for tramo, activo in self._bajo:
            libre = activo.copy()
            for ini, fin in filas:
                j0 = max(0, int(np.floor((ini - a) * self._fs)))
                j1 = min(len(libre), int(np.ceil((fin - a) * self._fs)) + 1)
                if j1 > j0:
                    libre[j0:j1] = False
            for s, e in _find_runs(libre):  # inclusive ends
                if e - s + 1 < min_n:
                    continue
                pico = s + int(np.argmax(tramo[s:e + 1]))
                margen = max(1, (e - s) // 20)
                ladera = (
                    (s > 0 and activo[s - 1] and pico - s <= margen)
                    or (e + 1 < len(activo) and activo[e + 1] and e - pico <= margen)
                )
                if not ladera:
                    hallados.append(Segment(a + s / self._fs,
                                            a + (e + 1) / self._fs,
                                            reason="candidate"))
        return normalise_segments(hallados, self._full_duration)

    def _auto_suggest(self) -> None:
        """Propose the active stretches — inside the span, and only there.

        Run over the whole file it proposed the calibration's maximal efforts
        as fragments of the task: they are the most active signal in the
        recording, so they win every activity test there is. Which is exactly
        the decision this application takes out of the operator's hands, and
        it was arriving back as a suggestion.
        """
        self._timer.stop()
        self._buscar_candidatos()
        filas = self._detectar(self._det["k"])
        if self._naming:
            filas = [
                Segment(f.start_s, f.end_s, f.score, f.reason, nombre)
                for f, nombre in zip(
                    filas, self._nombres_propuestos(filas), strict=True
                )
            ]
        self._set_rows(filas)

    def _promover(self, candidato: Segment) -> None:
        """Make a candidate a row, named like the rest, in its place in time."""
        nombre = (self._nombres_propuestos([candidato])[0]
                  if self._naming else "")
        nueva = Segment(candidato.start_s, candidato.end_s, candidato.score,
                        "candidate", nombre)
        filas = sorted([*self._filas_con_estado(), (nueva, True)],
                       key=lambda f: f[0].start_s)
        self._reconstruir(filas)
        self._ir_a(next(i for i, (s, _k) in enumerate(filas) if s is nueva))

    def _add_fragment(self) -> None:
        # A 1 s fragment centred on the span, ready to be dragged. Centred on
        # the *file* it landed in the calibration, which is not a place the
        # editor is allowed to reach any more.
        mid = (self._span[0] + self._span[1]) / 2.0
        a = max(self._span[0], mid - 0.5)
        b = min(self._span[1], a + 1.0)
        self._append_row(Segment(a, b, reason="manual"), keep=True)
        self._refresh_derived()

    def _remove_selected(self) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._row_widgets):
            # Quiet while the row goes: the table announces its new current
            # row before the row's widgets have left the list.
            self._table.blockSignals(True)
            self._table.removeRow(row)
            self._table.blockSignals(False)
            del self._row_widgets[row]
            self._fila_actual = -1
            self._refresh_derived()

    def _use_whole(self) -> None:
        self._set_rows([])

    def _on_click(self, event) -> None:
        if event.inaxes is not self._ax or event.xdata is None:
            return
        self._clic_en(float(event.xdata))

    def _clic_en(self, x: float) -> None:
        """A click at ``x`` seconds: a row's stretch is selected, for the
        buttons under the plot to keep, drop or split; a dotted candidate
        becomes a row; anywhere else does nothing.

        The click used to drop the row outright, which made the plot a switch
        rather than a way to pick a contraction and look at it. And a mark
        still never lands where the detector found nothing."""
        for i, w in enumerate(self._row_widgets):
            a = w["start"].value()  # type: ignore[attr-defined]
            b = w["end"].value()  # type: ignore[attr-defined]
            if a <= x <= b:
                self._ir_a(i)
                return
        for c in self._candidatos_libres():
            if c.start_s <= x <= c.end_s:
                self._promover(c)
                return

    # -- going through the rows ----------------------------------------------

    def _ir_a(self, fila: int) -> None:
        """Put row ``fila`` under review: highlighted, selected, in view."""
        n = len(self._row_widgets)
        self._fila_actual = max(0, min(n - 1, fila)) if n else -1
        if self._fila_actual >= 0:
            self._table.blockSignals(True)
            self._table.setCurrentCell(self._fila_actual, 3)
            self._table.blockSignals(False)
            item = self._table.item(self._fila_actual, 3)
            if item is not None:
                self._table.scrollToItem(item)
        self._refrescar_navegacion()
        self._redraw_preview()

    def _siguiente(self) -> None:
        self._ir_a(self._fila_actual + 1 if self._fila_actual >= 0 else 0)

    def _anterior(self) -> None:
        self._ir_a(max(0, self._fila_actual - 1))

    def _al_cambiar_fila(self, fila: int, _col: int, _fila_ant: int,
                         _col_ant: int) -> None:
        """A row picked in the table is the one under review too."""
        if fila != self._fila_actual and 0 <= fila < len(self._row_widgets):
            self._fila_actual = fila
            self._refrescar_navegacion()
            self._redraw_preview()

    def _etiquetar(self, nombre: str) -> None:
        """Name the row under review and go on: confirming is one click."""
        i = self._fila_actual
        if not 0 <= i < len(self._row_widgets):
            return
        self._row_widgets[i]["label"].setCurrentText(nombre)  # type: ignore[attr-defined]
        self._siguiente()

    def _mantener(self) -> None:
        self._decidir(True)

    def _eliminar(self) -> None:
        self._decidir(False)

    def _decidir(self, conservar: bool) -> None:
        """Keep or drop the row under review and go on: one click per row.

        Dropped, not deleted: it stays on the plot, hatched, and «Keep it»
        brings it back.
        """
        i = self._fila_actual
        if not 0 <= i < len(self._row_widgets):
            return
        self._row_widgets[i]["keep"].setChecked(conservar)  # type: ignore[attr-defined]
        self._siguiente()

    def _corte(
        self, fila: int
    ) -> tuple[tuple[float, float], tuple[float, float]] | None:
        """Where row ``fila`` would be split, or None when it holds one
        contraction."""
        if not 0 <= fila < len(self._row_widgets) or not self._envs:
            return None
        w = self._row_widgets[fila]
        return split_fragment(
            self._envs, self._bases, self._fs,
            w["start"].value(), w["end"].value(),  # type: ignore[attr-defined]
        )

    def _dividir(self) -> None:
        """Split the row under review at the valley between its two
        contractions. Both halves keep the row's state and are named anew;
        the first stays under review."""
        i = self._fila_actual
        corte = self._corte(i)
        if corte is None:
            return
        (a0, a1), (b0, b1) = corte
        # The table holds hundredths of a second, and pieces a sample apart
        # would round onto each other there and be joined again downstream.
        a1 = float(np.floor(a1 * 100.0)) / 100.0
        b0 = max(float(np.ceil(b0 * 100.0)) / 100.0, a1 + 0.01)
        filas = self._filas_con_estado()
        fila, conservar = filas[i]
        mitades = [Segment(a0, a1, reason="split", label=fila.label),
                   Segment(b0, b1, reason="split", label=fila.label)]
        if self._naming and self._env_2 is not None:
            mitades = [
                Segment(m.start_s, m.end_s, m.score, m.reason, nombre)
                for m, nombre in zip(mitades, self._nombres_propuestos(mitades),
                                     strict=True)
            ]
        filas[i:i + 1] = [(m, conservar) for m in mitades]
        self._reconstruir(filas)
        self._ir_a(i)

    # -- derived state (duration cells, total label, preview) ----------------

    def _refresh_derived(self) -> None:
        for w in self._row_widgets:
            a = w["start"].value()  # type: ignore[attr-defined]
            b = w["end"].value()  # type: ignore[attr-defined]
            w["dur"].setText(f"{max(0.0, b - a):.2f}")  # type: ignore[attr-defined]
        kept = normalise_segments(
            self._current_segments(only_kept=True), self._full_duration
        )
        total = total_duration_s(kept)
        if not kept:
            self._lbl_total.setText(tr("Whole recording will be analysed."))
        else:
            self._lbl_total.setText(
                tr("{n} fragment(s) — {d:.2f} s of {full:.1f} s").format(
                    n=len(kept), d=total, full=self._full_duration
                )
            )
        self._refrescar_contador()
        self._refrescar_navegacion()
        self._redraw_preview()

    def _cuenta(self) -> list[int]:
        """Kept rows of each kind, in the counter's order."""
        filas = self._current_segments(only_kept=True)
        categorias = self._categorias()
        if categorias == [None]:
            return [len(filas)]
        return [sum(1 for s in filas if s.label == c) for c in categorias]

    def _refrescar_contador(self) -> None:
        for (categoria, etiqueta, spin), n in zip(
            self._contadores, self._cuenta(), strict=True
        ):
            nombre = categoria if categoria is not None else tr("Contractions")
            etiqueta.setText(f"{nombre}: {n} /")
            esperadas = spin.value()
            if esperadas == 0:
                color, aviso = "", ""
            elif n == esperadas:
                color, aviso = _COUNT_OK, ""
            else:
                color = _COUNT_OFF
                aviso = tr(
                    "{n} marked and {m} expected: look for the missing one "
                    "among the dotted stretches, or drop the extra one."
                ).format(n=n, m=esperadas)
            etiqueta.setStyleSheet(
                f"color:{color}; font-weight:600;" if color else ""
            )
            etiqueta.setToolTip(aviso)

    def _refrescar_navegacion(self) -> None:
        n = len(self._row_widgets)
        i = self._fila_actual
        if n == 0:
            texto = tr("No contraction marked.")
        elif i < 0:
            texto = tr("▶ goes through the contractions one by one.")
        else:
            texto = tr("Contraction {i} of {n}").format(i=i + 1, n=n)
            if not self._row_widgets[i]["keep"].isChecked():  # type: ignore[attr-defined]
                texto += " · " + tr("dropped")
        self._lbl_nav.setText(texto)
        self._btn_prev.setEnabled(n > 0 and i > 0)
        self._btn_next.setEnabled(n > 0 and i < n - 1)
        actual = (
            self._row_widgets[i]["label"].currentText().strip()  # type: ignore[attr-defined]
            if 0 <= i < n else None
        )
        for nombre, b in self._btns_nombre.items():
            b.setEnabled(0 <= i < n)
            b.setChecked(nombre == actual)
        hay = 0 <= i < n
        conservada = hay and self._row_widgets[i]["keep"].isChecked()  # type: ignore[attr-defined]
        self._btn_mantener.setEnabled(hay)
        self._btn_mantener.setChecked(conservada)
        self._btn_eliminar.setEnabled(hay)
        self._btn_eliminar.setChecked(hay and not conservada)
        divisible = hay and self._corte(i) is not None
        self._btn_dividir.setEnabled(divisible)
        self._btn_dividir.setToolTip(
            tr("This row has a single peak: there is nothing to split.")
            if hay and not divisible
            else tr("Cut this row in two at the deepest valley between its peaks.")
        )

    def _shade_colour(self, label: str) -> str:
        if not self._naming or self._env_2 is None:
            return _SHADE_PLAIN
        if label == self._name_1:
            return _SHADE_1
        if label == self._name_2:
            return _SHADE_2
        if label == self._both_label:
            return _SHADE_BOTH
        return _SHADE_PLAIN

    def _redraw_preview(self) -> None:
        self._ax.clear()
        # Downsample the envelope for a light preview (cap ~4000 points).
        step = max(1, len(self._env) // 4000)
        a, b = self._span
        i0, i1 = round(a * self._fs), round(b * self._fs)
        self._ax.plot(
            self._t[::step], self._env[::step], color=COLOUR_1, linewidth=0.8,
            label=self._name_1 if self._env_2 is not None else None,
        )
        # The threshold the sensitivity sets, over the span the detector
        # sees, so a slider move is a line move before it is a row change.
        _base, umbral = activity_threshold(self._env[i0:i1], self._det["k"])
        umbrales = [umbral]
        self._ax.axhline(umbral, color=COLOUR_1, lw=0.8, ls="--", alpha=0.7,
                         label=tr("activity threshold"))
        if self._env_2 is not None:
            n2 = min(len(self._t), len(self._env_2))
            self._ax.plot(
                self._t[:n2:step], self._env_2[:n2:step], color=COLOUR_2,
                linewidth=0.8, label=self._name_2,
            )
            _b2, umbral2 = activity_threshold(self._env_2[i0:i1], self._det["k"])
            umbrales.append(umbral2)
            self._ax.axhline(umbral2, color=COLOUR_2, lw=0.8, ls="--", alpha=0.7)
        # Every row, kept or not: the dropped ones in grey, so the click
        # that dropped one can bring it back.
        for w in self._row_widgets:
            ini = w["start"].value()  # type: ignore[attr-defined]
            fin = w["end"].value()  # type: ignore[attr-defined]
            if fin <= ini:
                continue
            if w["keep"].isChecked():  # type: ignore[attr-defined]
                nombre = w["label"].currentText().strip()  # type: ignore[attr-defined]
                # A white edge, so two rows that touch — the halves of a
                # split — still read as two.
                self._ax.axvspan(
                    ini, fin, facecolor=to_rgba(self._shade_colour(nombre), 0.25),
                    edgecolor="white", lw=1.2,
                )
            else:
                self._ax.axvspan(ini, fin, color=_SHADE_DROPPED, alpha=0.15,
                                 hatch="//", lw=0)
        # What a click can add: outlined, not filled, so they never read as
        # marks.
        for j, c in enumerate(self._candidatos_libres()):
            self._ax.axvspan(
                c.start_s, c.end_s, fill=False, edgecolor=_EDGE_CANDIDATE,
                lw=1.0, ls=":",
                label=tr("below the threshold: click to add") if j == 0 else None,
            )
        i = self._fila_actual
        if 0 <= i < len(self._row_widgets):
            ini = self._row_widgets[i]["start"].value()  # type: ignore[attr-defined]
            fin = self._row_widgets[i]["end"].value()  # type: ignore[attr-defined]
            if fin > ini:
                self._ax.axvspan(ini, fin, fill=False, edgecolor=_EDGE_CURRENT,
                                 lw=2.0)
            corte = self._corte(i)
            if corte is not None:
                # Where «Split it» would cut, before it does.
                self._ax.axvline((corte[0][1] + corte[1][0]) / 2.0,
                                 color=_EDGE_CURRENT, lw=1.0, ls="-.")
        self._ax.legend(loc="upper right", fontsize=8, frameon=False)
        # Fixed axes: the span across, the signal's own top upwards — raised
        # only when the threshold line would otherwise leave the plot.
        techo = max([self._techo] + [1.05 * u for u in umbrales])
        self._ax.set_xlim(a, max(b, a + 1e-6))
        self._ax.set_ylim(-0.02 * techo, techo)
        self._ax.set_xlabel(tr("Time (s)"))
        self._ax.set_ylabel(tr("Envelope (mV)"))
        self._canvas.draw_idle()

    # -- result --------------------------------------------------------------

    def filter_kwargs(self) -> dict[str, float]:
        """Return the filter cut-offs currently set in the dialog.

        The tab behind owns them; they pass through unchanged so the analysis
        matches what was previewed here.
        """
        return {
            "f_low": self._f_low,
            "f_high": self._f_high,
            "f_notch": self._f_notch,
            "f_env": self._f_env,
        }

    def named_segments(self) -> list[tuple[float, float, str]]:
        """The kept fragments with their names, in order.

        The companion of :meth:`selected_segments`, which stays as it was: the
        analysis crops by the pairs and reads the co-activation windows off the
        names, and most callers only care about one of the two.
        """
        kept = normalise_segments(
            self._current_segments(only_kept=True), self._full_duration
        )
        return [(s.start_s, s.end_s, s.label) for s in kept]

    def labels(self) -> list[str]:
        """Just the names, aligned with :meth:`selected_segments`."""
        pares = self.selected_segments()
        nombrados = self.named_segments()
        if len(pares) != len(nombrados):
            # selected_segments() collapses "the whole recording" to an empty
            # list; there is then nothing to align names to.
            return []
        return [n for _a, _b, n in nombrados]

    def selected_segments(self) -> list[tuple[float, float]]:
        """Return the checked fragments as normalised ``(start, end)`` tuples.

        An empty list means "analyse the whole recording".
        """
        kept = normalise_segments(
            self._current_segments(only_kept=True), self._full_duration
        )
        # If the single kept fragment is essentially the whole recording,
        # treat it as "whole" (empty selection) so the worker skips cropping.
        if (
            len(kept) == 1
            and kept[0].start_s <= 1e-6
            and kept[0].end_s >= self._full_duration - 1e-6
        ):
            return []
        return [(s.start_s, s.end_s) for s in kept]
