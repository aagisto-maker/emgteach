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
that kind ever gets set. A click on a shaded stretch keeps or drops it.

The dialog is constructible directly from signal arrays (so it can be unit
tested headless) or from an EDF file via :meth:`FragmentSelectionDialog.from_edf`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
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
    activity_threshold,
    normalise_segments,
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

#: How long after the last slider move the proposal is rebuilt. Long enough
#: that dragging does not rebuild at every pixel, short enough to feel live.
_DEBOUNCE_MS = 150


def default_detection() -> dict[str, float]:
    """The detection settings the dialogue opens on, co-activation rule included."""
    d = dict(DEFAULT_DETECTION)
    d["both_ratio"] = float(_DOMINANCE)
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Select analysis fragments"))
        # Bigger than it was: the plot is now the control, and a plot in
        # which a twelve-second series occupies six hundred pixels is one in
        # which the stretches can be told apart and clicked.
        self.setMinimumSize(960, 640)
        self.resize(1120, 740)

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
        #: The detection settings, as the sliders have them.
        self._det = default_detection()
        if detection:
            self._det.update({k: float(v) for k, v in detection.items()
                              if k in self._det})
        self._both_label = tr("Co-activation")

        # Envelope for the preview (downsampled when drawing).
        self._env = self._envolvente(self._raw)
        self._t = np.arange(len(self._env)) / self._fs
        self._env_2 = self._envolvente(self._raw_2)

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
            parent=parent,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # What it is for, in the words a student would use. Two sentences:
        # this dialogue is used by students and most sessions never open it.
        texto = tr(
            "Each row is one contraction found in the recording. Uncheck the "
            "ones not worth analysing — a movement done wrong, a tug on the "
            "cable — and only the rest is analysed, joined up as if recorded "
            "in one go. Press «Use these fragments» even if you change "
            "nothing: that is what applies them."
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

        # Preview plot — the control, not a decoration: the shaded stretches
        # are the rows, the dashed line is the sensitivity, and a click on a
        # stretch keeps or drops it.
        self._fig = Figure(figsize=(9.0, 3.0), constrained_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(220)
        self._ax = self._fig.add_subplot(111)
        self._canvas.mpl_connect("button_press_event", self._on_click)
        root.addWidget(self._canvas, stretch=3)

        root.addWidget(self._build_adjustments())

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
            lay.addWidget(w, 1, col)
            w.setVisible(self._naming and self._env_2 is not None)

        # The fine level, folded. A toggle button rather than a checkbox,
        # because it reveals controls rather than setting anything.
        self._btn_fino = QToolButton()
        self._btn_fino.setCheckable(True)
        self._btn_fino.setAutoRaise(True)
        self._btn_fino.setText("▸ " + tr("Fine adjustment"))
        self._btn_fino.toggled.connect(self._toggle_fino)
        lay.addWidget(self._btn_fino, 2, 0, 1, 2)
        self._btn_reset = QPushButton(tr("Reset"))
        self._btn_reset.setToolTip(tr(
            "Moving a setting rebuilds the proposal; rows edited by hand are "
            "replaced."
        ))
        self._btn_reset.clicked.connect(self._reset_detection)
        lay.addWidget(self._btn_reset, 2, 2)
        pista = QLabel(tr("Click a shaded stretch to keep or drop it."))
        pista.setStyleSheet("color:#6B7580; font-size:10px;")
        lay.addWidget(pista, 2, 3)

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
        lay.addWidget(self._box_fino, 3, 0, 1, 4)
        lay.setColumnStretch(1, 1)
        lay.setColumnStretch(3, 1)

        self._refresh_setting_labels()
        return grp

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
        self._det = default_detection()
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

    # -- row management ------------------------------------------------------

    def _set_rows(self, segments: list[Segment]) -> None:
        """Replace the table contents with ``segments``."""
        self._table.setRowCount(0)
        self._row_widgets = []
        for seg in segments:
            self._append_row(seg, keep=True)
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
        dur_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
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

    def _auto_suggest(self) -> None:
        """Propose the active stretches — inside the span, and only there.

        Run over the whole file it proposed the calibration's maximal efforts
        as fragments of the task: they are the most active signal in the
        recording, so they win every activity test there is. Which is exactly
        the decision this application takes out of the operator's hands, and
        it was arriving back as a suggestion.
        """
        self._timer.stop()
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
                k=self._det["k"],
                min_duration_s=self._det["min_duration_s"],
                merge_gap_s=self._det["merge_gap_s"],
                prominence=self._det["prominence"],
            )

        # Back into the file's own clock: the worker crops by these numbers.
        segs = detecta(self._raw)
        filas = [
            Segment(a + x.start_s, a + x.end_s, x.score, x.reason, x.label)
            for x in segs
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
        if self._naming:
            filas = [
                Segment(f.start_s, f.end_s, f.score, f.reason, nombre)
                for f, nombre in zip(
                    filas, self._nombres_propuestos(filas), strict=True
                )
            ]
        self._set_rows(filas)

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
            self._table.removeRow(row)
            del self._row_widgets[row]
            self._refresh_derived()

    def _use_whole(self) -> None:
        self._set_rows([])

    def _on_click(self, event) -> None:
        if event.inaxes is not self._ax or event.xdata is None:
            return
        self._toggle_at(float(event.xdata))

    def _toggle_at(self, x: float) -> None:
        """Keep or drop the row whose stretch contains ``x`` seconds."""
        for w in self._row_widgets:
            a = w["start"].value()  # type: ignore[attr-defined]
            b = w["end"].value()  # type: ignore[attr-defined]
            if a <= x <= b:
                chk = w["keep"]
                chk.setChecked(not chk.isChecked())  # type: ignore[attr-defined]
                return

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
        self._redraw_preview()

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
        self._ax.axhline(umbral, color=COLOUR_1, lw=0.8, ls="--", alpha=0.7,
                         label=tr("activity threshold"))
        if self._env_2 is not None:
            n2 = min(len(self._t), len(self._env_2))
            self._ax.plot(
                self._t[:n2:step], self._env_2[:n2:step], color=COLOUR_2,
                linewidth=0.8, label=self._name_2,
            )
            _b2, umbral2 = activity_threshold(self._env_2[i0:i1], self._det["k"])
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
                self._ax.axvspan(ini, fin, color=self._shade_colour(nombre),
                                 alpha=0.25, lw=0)
            else:
                self._ax.axvspan(ini, fin, color=_SHADE_DROPPED, alpha=0.15,
                                 hatch="//", lw=0)
        if self._env_2 is not None or True:
            self._ax.legend(loc="upper right", fontsize=8, frameon=False)
        self._ax.set_xlim(a, max(b, a + 1e-6))
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
