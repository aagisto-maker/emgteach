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
    """The eight settings this dialogue used to carry are gone.

    It is opened by students, to throw away a repetition that went wrong. It
    used to greet them with a band-pass, a notch, an envelope cut-off and three
    detection parameters — concepts none of which can be set by someone who
    does not already know what they do, and two of which had a second copy in
    the tab behind. A student who came in to delete a row could change the
    analysis without knowing it.
    """

    def test_no_settings_are_offered(self, qapp: QCoreApplication) -> None:
        from PySide6.QtWidgets import QDoubleSpinBox

        dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
        # The only spin boxes left are the two per row, which are the start and
        # end of a fragment — the part he liked.
        fuera_de_la_tabla = [
            w for w in dlg.findChildren(QDoubleSpinBox)
            if not any(w is r["start"] or w is r["end"] for r in dlg._row_widgets)
        ]
        assert fuera_de_la_tabla == []
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


class TestItSaysContractionEverywhere:
    """One object, one name, in everything the student reads.

    The dialogue's title, buttons and counter said «fragment» while its first
    line said «contraction» — the same rows under two names, and the reader
    with no way to know they were the same. The code still says fragment: the
    word is in the tuned file, in the tabs and in the core, and it is a wider
    thing there (a stretch of signal, which a contraction usually is but the
    whole recording also is). Only the surface is unified.
    """

    def test_no_visible_string_says_fragment(self) -> None:
        import ast
        import pathlib

        from emgteach.gui.widgets import fragment_selection

        fuente = pathlib.Path(fragment_selection.__file__).read_text(
            encoding="utf-8"
        )
        malas = [
            (n.lineno, a.value)
            for n in ast.walk(ast.parse(fuente))
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "tr"
            for a in n.args
            if isinstance(a, ast.Constant)
            and isinstance(a.value, str)
            and "fragment" in a.value.lower()
        ]
        assert not malas, f"dicen «fragment» y deberían decir contracción: {malas}"

    def test_the_spanish_says_contraccion_too(self, qapp: QCoreApplication) -> None:
        """A key renamed in English but left with the old Spanish value is the
        classic half-done rename, and only shows in the language nobody
        develops in."""
        from emgteach import i18n

        anterior = i18n.get_language()
        try:
            i18n.set_language("es")
            dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
            visible = [dlg.windowTitle(), dlg._btn_add.text(),
                       dlg._btn_remove.text(), dlg._btn_ok.text()]
            assert not [t for t in visible if "fragment" in t.lower()], visible
            assert sum("contracci" in t.lower() for t in visible) >= 3, visible
            dlg.deleteLater()
        finally:
            i18n.set_language(anterior)
