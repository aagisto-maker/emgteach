"""Interactive editor to select the significant fragments of a recording.

This is the GUI half of the assisted-selection feature: it proposes the
informative fragments automatically (via
:func:`emgteach.selection.suggest_significant_segments`) and lets the user
accept, tweak, add or drop them before the analysis runs. The core logic
lives in :mod:`emgteach.selection`; this dialog only edits a list of
``(start_s, end_s)`` windows and shows a preview.

The dialog is constructible directly from signal arrays (so it can be unit
tested headless) or from an EDF file via :meth:`FragmentSelectionDialog.from_edf`.
"""

from __future__ import annotations

import inspect
from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from emgteach.dsp import process_offline
from emgteach.i18n import tr
from emgteach.profiles import EMG_PROFILE
from emgteach.selection import (
    Segment,
    normalise_segments,
    suggest_significant_segments,
    total_duration_s,
)

# Detection parameters, read straight from the core function so the two never
# drift apart. They are no longer editable here: see _build_ui.
_suggest_defaults = inspect.signature(suggest_significant_segments).parameters
_DEFAULT_K = float(_suggest_defaults["k"].default)
_DEFAULT_MIN_DURATION_S = float(_suggest_defaults["min_duration_s"].default)
_DEFAULT_MERGE_GAP_S = float(_suggest_defaults["merge_gap_s"].default)


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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Select analysis fragments"))
        self.setMinimumSize(720, 520)

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
        self._row_widgets: list[dict[str, Any]] = []

        # Envelope for the preview (downsampled when drawing).
        try:
            self._env = process_offline(
                self._raw,
                self._fs,
                f_low=self._f_low,
                f_high=self._f_high,
                f_notch=self._f_notch,
                f_env=self._f_env,
            )["emg_envelope"]
        except Exception:  # pragma: no cover — very short/degenerate signal
            self._env = np.abs(self._raw)
        self._t = np.arange(len(self._env)) / self._fs

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
        parent: QWidget | None = None,
    ) -> FragmentSelectionDialog:
        """Build the dialog by loading one channel from an EDF file."""
        from emgteach.io import read_edf_mne

        edf = read_edf_mne(edf_path, channel_name)
        return cls(
            edf["emg_raw"],
            float(edf["sfreq"]),
            filter_kwargs,
            segments=segments,
            labels=labels,
            span=span,
            naming=naming,
            parent=parent,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # What it is for, in the words a student would use, and when not to
        # bother. This dialogue is used by students and most sessions never
        # open it: it earns two short paragraphs, not a lecture.
        texto = tr(
            "Each row is one contraction found in the recording. Uncheck the "
            "ones not worth analysing — a movement done wrong, a tug on the "
            "cable, an effort that never got going — and only the rest is "
            "analysed, joined up as if it had been recorded in one go.\n\n"
            "If they are all good there is nothing to do here: cancel, and "
            "the whole recording is analysed. To move where one begins or "
            "ends, change its seconds with the mouse wheel, the arrows, or by "
            "typing."
        )
        if self._naming:
            texto += "\n\n" + tr(
                "With two muscles each row can also be named with the "
                "manoeuvre — «Flexion», «Grip». The name says which movement "
                "was being made, not which muscle contracted, and it is what "
                "tells the co-activation table which of the two is the "
                "agonist. Consecutive rows with the same name count as one."
            )
        info = QLabel(texto)
        info.setWordWrap(True)
        root.addWidget(info)

        # Preview plot.
        self._fig = Figure(figsize=(7.0, 2.2), constrained_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax = self._fig.add_subplot(111)
        root.addWidget(self._canvas, stretch=1)

        # Fragment table.
        # No «Reason» column: it said «activity» / «manual» / «whole
        # recording», which is where a row came from, not anything the
        # student can act on.
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            tr("Keep"), tr("Start (s)"), tr("End (s)"), tr("Duration (s)"),
            tr("Manoeuvre"),
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
        root.addWidget(self._table, stretch=1)

        # The envelope cut-offs and the detection parameters used to live
        # here, eight spin boxes of them. They are gone. Band and notch are
        # the profile's and are not set anywhere else in the program; the
        # envelope smoothing belongs to the tab that opened this dialogue,
        # and having a second copy meant a student who came in to delete a
        # row could change the analysis without knowing it. The three
        # detection numbers — sensitivity, minimum duration, merge gap —
        # cannot be set by anyone who does not already know what they do,
        # and the recourse when the proposal is wrong is the one that needs
        # no explanation: drag the seconds, add a row, delete a row.

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

        # Editable, with the practical's own vocabulary already in it. The
        # presets are the ones the MARK button used to offer: they stopped
        # being live labels and became suggestions here, which is where the
        # naming moved to.
        combo_nombre = QComboBox()
        combo_nombre.setEditable(True)
        combo_nombre.addItem("")
        for preset in EMG_PROFILE.marker_presets:
            if preset != "Other…":
                combo_nombre.addItem(tr(preset))
        combo_nombre.setCurrentText(seg.label)
        combo_nombre.setToolTip(tr(
            "The manoeuvre performed, not the muscle contracting. Leave it "
            "empty for a fragment that is only signal worth keeping. "
            "Consecutive fragments with the same name form a single window of "
            "the co-activation table."
        ))
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

    # -- actions -------------------------------------------------------------

    def _auto_suggest(self) -> None:
        """Propose the active stretches — inside the span, and only there.

        Run over the whole file it proposed the calibration's maximal efforts
        as fragments of the task: they are the most active signal in the
        recording, so they win every activity test there is. Which is exactly
        the decision this application takes out of the operator's hands, and
        it was arriving back as a suggestion.
        """
        a, b = self._span
        i0, i1 = round(a * self._fs), round(b * self._fs)
        segs = suggest_significant_segments(
            self._raw[i0:i1],
            self._fs,
            f_low=self._f_low,
            f_high=self._f_high,
            f_notch=self._f_notch,
            f_env=self._f_env,
            k=_DEFAULT_K,
            min_duration_s=_DEFAULT_MIN_DURATION_S,
            merge_gap_s=_DEFAULT_MERGE_GAP_S,
        )
        # Back into the file's own clock: the worker crops by these numbers.
        self._set_rows([
            Segment(a + x.start_s, a + x.end_s, x.score, x.reason, x.label)
            for x in segs
        ])

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
        self._redraw_preview(kept)

    def _redraw_preview(self, kept: list[Segment]) -> None:
        self._ax.clear()
        # Downsample the envelope for a light preview (cap ~4000 points).
        step = max(1, len(self._env) // 4000)
        self._ax.plot(
            self._t[::step], self._env[::step], color="#1F4E79", linewidth=0.8
        )
        for seg in kept:
            self._ax.axvspan(seg.start_s, seg.end_s, color="#4CAF50", alpha=0.25)
        self._ax.set_xlim(self._span[0], max(self._span[1], self._span[0] + 1e-6))
        self._ax.set_xlabel(tr("Time (s)"))
        self._ax.set_ylabel(tr("Envelope (mV)"))
        self._canvas.draw_idle()

    # -- result --------------------------------------------------------------

    def filter_kwargs(self) -> dict[str, float]:
        """Return the filter cut-offs currently set in the dialog.

        These are the band-pass / notch / envelope cut-offs the user tuned
        for the preview and detection; the caller can reuse them for the
        actual analysis so it matches what was seen here.
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
