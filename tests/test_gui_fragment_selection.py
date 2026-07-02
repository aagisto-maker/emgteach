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


def test_default_detection_params_match_core(qapp: QCoreApplication) -> None:
    import inspect

    from emgteach.selection import suggest_significant_segments

    params = inspect.signature(suggest_significant_segments).parameters
    dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
    assert dlg._spin_k.value() == params["k"].default
    assert dlg._spin_min_dur.value() == params["min_duration_s"].default
    assert dlg._spin_merge_gap.value() == params["merge_gap_s"].default
    dlg.deleteLater()


def test_min_duration_param_filters_short_fragments(qapp: QCoreApplication) -> None:
    # Two 1.5 s bursts survive a 1 s minimum but not a 2 s minimum.
    dlg = FragmentSelectionDialog(_burst_signal(), FS, FILTER_KWARGS)
    dlg._spin_min_dur.setValue(1.0)
    dlg._auto_suggest()
    assert dlg._table.rowCount() == 2
    dlg._spin_min_dur.setValue(2.0)
    dlg._auto_suggest()
    # No burst is 2 s long -> falls back to the whole-recording proposal.
    assert dlg._table.rowCount() == 1
    dlg.deleteLater()
