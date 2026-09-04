"""Headless tests for the fragment-selection dialog."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QCoreApplication

from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

FS = 1000
FILTER_KWARGS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


def _burst_signal() -> np.ndarray:
    rng = np.random.default_rng(0)
    n = 10 * FS
    sig = rng.normal(0.0, 0.01, size=n)
    for a, b in ((2.0, 3.5), (6.0, 7.5)):
        i0, i1 = int(a * FS), int(b * FS)
        t = np.arange(i1 - i0) / FS
        sig[i0:i1] += 0.5 * np.sin(2 * np.pi * 90.0 * t)
    return sig


def test_auto_suggest_populates_two_fragments(qapp: QCoreApplication) -> None:
    dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
    # Opened with no initial selection -> auto-suggest ran and found 2 bursts.
    assert dlg._table.rowCount() == 2
    segs = dlg.selected_segments()
    assert len(segs) == 2
    assert segs[0][0] < segs[1][0]
    dlg.deleteLater()


def test_unchecking_a_fragment_drops_it(qapp: QCoreApplication) -> None:
    dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
    # Uncheck the first fragment's keep box.
    holder = dlg._table.cellWidget(0, 0)
    checkbox = holder.findChild(type(dlg._row_widgets[0]["keep"]))
    checkbox.setChecked(False)
    assert len(dlg.selected_segments()) == 1
    dlg.deleteLater()


def test_whole_recording_returns_empty(qapp: QCoreApplication) -> None:
    dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
    dlg._use_whole()  # clears the table
    assert dlg.selected_segments() == []
    dlg.deleteLater()


def test_add_fragment_appends_row(qapp: QCoreApplication) -> None:
    dlg = FragmentSelectionDialog(
        _burst_signal(), FS, FILTER_KWARGS, segments=[(1.0, 2.0)]
    )
    assert dlg._table.rowCount() == 1
    dlg._add_fragment()
    assert dlg._table.rowCount() == 2
    dlg.deleteLater()


def test_preloaded_segments_are_used(qapp: QCoreApplication) -> None:
    dlg = FragmentSelectionDialog(
        _burst_signal(), FS, FILTER_KWARGS, segments=[(1.0, 3.0), (5.0, 6.0)]
    )
    segs = dlg.selected_segments()
    assert segs == [(1.0, 3.0), (5.0, 6.0)]
    dlg.deleteLater()


class TestTheStudentCannotChangeTheAnalysisFromHere:
    """The eight settings this dialogue once carried are not back.

    It is opened by students, to throw away a repetition that went wrong. It
    used to greet them with a band-pass, a notch, an envelope cut-off and three
    detection parameters — concepts none of which can be set by someone who
    does not already know what they do, and two of which had a second copy in
    the tab behind. What it offers now is two sliders whose effect is drawn
    as they move, and a fine row that stays folded until asked for; the
    filters stay with the tab behind.
    """

    def test_no_filter_settings_are_offered(self, qapp: QCoreApplication) -> None:
        from PySide6.QtWidgets import QDoubleSpinBox

        dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
        # The only spin boxes on view are the two per row, which are the start
        # and end of a fragment — the part he liked. The fine row's two are
        # folded away.
        fuera_de_la_tabla = [
            w for w in dlg.findChildren(QDoubleSpinBox)
            if not any(w is r["start"] or w is r["end"] for r in dlg._row_widgets)
            and w.isVisibleTo(dlg)
        ]
        assert fuera_de_la_tabla == []
        assert not dlg._box_fino.isVisibleTo(dlg)
        dlg.deleteLater()

    def test_the_cut_offs_pass_straight_through(
        self, qapp: QCoreApplication
    ) -> None:
        """What comes back is what went in. The tab behind owns the filters."""
        dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
        assert dlg.filter_kwargs() == FILTER_KWARGS
        dlg.deleteLater()

    def test_the_proposal_still_uses_the_core_defaults(
        self, qapp: QCoreApplication
    ) -> None:
        """Removing the controls must not have changed what is proposed."""
        dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
        dlg._auto_suggest()
        assert dlg._table.rowCount() == 2  # the two bursts of _burst_signal
        dlg.deleteLater()


class TestTheEditorStaysInsideTheRecordingPhase:
    """A two-phase session is mostly *not* the task.

    Run over the whole file, the automatic suggestion proposed the six maximal
    efforts of the calibration as fragments of the work: they are the most
    active signal in the recording, so they win every activity test there is.
    On the bench session of 1 September, nine of the ten fragments it offered
    were the warm-up and the calibration.

    Which is the one decision this application exists to take out of the
    operator's hands — it knows exactly where the calibration was — arriving
    back as a suggestion.
    """

    SPAN = (6.0, 10.0)

    def _dlg(self, **kw):
        return FragmentSelectionDialog(
            _burst_signal(), FS, FILTER_KWARGS, span=self.SPAN, **kw)

    def test_nothing_is_suggested_outside_it(self, qapp) -> None:
        """The signal has two bursts, at 2-3.5 s and at 6-7.5 s, and the span
        holds the second. One row, not two.

        Counted on the table rather than on ``selected_segments()``: the spin
        boxes clamp to the span, so a fragment proposed at 2 s comes back
        reading 6 s and the check passes over a suggestion that never should
        have been made.
        """
        dlg = self._dlg()
        assert dlg._table.rowCount() == 1, [
            (dlg._row_widgets[i]["start"].value(),
             dlg._row_widgets[i]["end"].value())
            for i in range(dlg._table.rowCount())
        ]
        a, b = self.SPAN
        for ini, fin in dlg.selected_segments():
            assert ini >= a - 1e-6 and fin <= b + 1e-6, (ini, fin)
        dlg.deleteLater()

    def test_the_bounds_cannot_be_dragged_out_of_it(self, qapp) -> None:
        """The suggestion is a starting point; the operator edits it, and the
        edit has the same limits the suggestion had."""
        dlg = self._dlg(segments=[(7.0, 8.0)])
        spin = dlg._row_widgets[0]["start"]
        spin.setValue(0.0)
        assert spin.value() >= self.SPAN[0]
        dlg.deleteLater()

    def test_a_new_fragment_lands_inside_it(self, qapp) -> None:
        """It used to be centred on the file, which in a two-phase session
        puts it in the middle of the calibration."""
        dlg = self._dlg(segments=[(7.0, 8.0)])
        dlg._add_fragment()
        ini, fin = dlg.selected_segments()[-1]
        assert ini >= self.SPAN[0] and fin <= self.SPAN[1]
        dlg.deleteLater()

    def test_without_a_span_the_whole_file_is_offered(self, qapp) -> None:
        """Every recording made before the guided flow has no phases to
        restrict to, and its whole length is the task."""
        dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
        assert any(ini < self.SPAN[0] for ini, _fin in dlg.selected_segments())
        dlg.deleteLater()
