"""GUI tests for channel selection in the Analysis and MVC tabs.

Lock the "one or two EMG channels" behaviour: with a single channel the compare
option (Analysis) and the channel picker (MVC) are disabled; with two channels
the user picks EMG1/EMG2 and the analysis uses only that channel; the
accelerometer channel is never offered; and the overlaid-envelopes panel is only
usable while comparing. Marked ``gui`` (needs a QApplication).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.gui


def _write_edf(path: Path, channels: list[tuple[str, float, float, str]]) -> None:
    from pyedflib import highlevel

    fs, n = 1000, 4000
    headers = [
        highlevel.make_signal_header(
            label, sample_frequency=fs, physical_min=pmin,
            physical_max=pmax, dimension=dim,
        )
        for (label, pmin, pmax, dim) in channels
    ]
    signals = [np.random.default_rng(1).standard_normal(n) * 0.2 for _ in channels]
    highlevel.write_edf(str(path), signals, headers, highlevel.make_header())


_TWO_CH_ACC = [
    ("EMG1", -1.65, 1.65, "mV"),
    ("EMG2", -1.65, 1.65, "mV"),
    ("ACC", -1.0, 1.0, "g"),
]
_ONE_CH = [("EMG1", -1.65, 1.65, "mV")]


def _analysis_tab(qapp):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget

    return AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "an-chan"))


def _overlay_pos(tab) -> int:
    from emgteach.gui.tabs.analysis import _OVERLAY_PID

    return tab._panel_pids.index(_OVERLAY_PID)


def test_analysis_two_channels_compare_off_and_partner_auto(
    qapp, tmp_path: Path
) -> None:
    edf = tmp_path / "two.edf"
    _write_edf(edf, _TWO_CH_ACC)
    tab = _analysis_tab(qapp)
    tab._populate_channels(str(edf))

    # ACC is excluded; only the two EMG channels are offered.
    labels = [tab._combo_canal.itemText(i) for i in range(tab._combo_canal.count())]
    assert labels == ["EMG1", "EMG2"]

    pos = _overlay_pos(tab)
    # Comparing is possible but off by default; the overlay panel is locked.
    assert tab._chk_compare2.isEnabled()
    assert not tab._chk_compare2.isChecked()
    assert not tab._chk_paneles[pos].isEnabled()
    assert not tab._chk_paneles[pos].isChecked()

    # Turning comparison on picks the partner automatically and unlocks panel 9.
    tab._chk_compare2.setChecked(True)
    assert tab._combo_canal2.currentText() == "EMG2"
    assert tab._chk_paneles[pos].isEnabled()
    assert tab._chk_paneles[pos].isChecked()

    # Selecting EMG2 flips the partner to EMG1.
    tab._combo_canal.setCurrentIndex(1)
    assert tab._combo_canal2.currentText() == "EMG1"

    # Turning it off re-locks the overlay panel.
    tab._chk_compare2.setChecked(False)
    assert not tab._chk_paneles[pos].isEnabled()
    assert not tab._chk_paneles[pos].isChecked()


def test_analysis_single_channel_disables_compare_and_overlay(
    qapp, tmp_path: Path
) -> None:
    edf = tmp_path / "one.edf"
    _write_edf(edf, _ONE_CH)
    tab = _analysis_tab(qapp)
    tab._populate_channels(str(edf))

    labels = [tab._combo_canal.itemText(i) for i in range(tab._combo_canal.count())]
    assert labels == ["EMG1"]
    assert not tab._chk_compare2.isEnabled()
    assert not tab._chk_paneles[_overlay_pos(tab)].isEnabled()


def test_mvc_channel_picker_enabled_only_for_two_channels(
    qapp, tmp_path: Path
) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.mvc import MvcTab
    from emgteach.gui.widgets.logger import LoggerWidget

    tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "mvc-chan"))

    two = tmp_path / "m2.edf"
    _write_edf(two, _TWO_CH_ACC)
    tab._populate_channels(str(two))
    labels = [tab._combo_canal.itemText(i) for i in range(tab._combo_canal.count())]
    assert labels == ["EMG1", "EMG2"]     # ACC excluded
    assert tab._combo_canal.isEnabled()

    one = tmp_path / "m1.edf"
    _write_edf(one, _ONE_CH)
    tab._populate_channels(str(one))
    assert [tab._combo_canal.itemText(i) for i in range(tab._combo_canal.count())] == [
        "EMG1"
    ]
    assert not tab._combo_canal.isEnabled()
