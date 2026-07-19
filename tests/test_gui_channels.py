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


def test_accelerometer_panels_gated_on_acc_channel(qapp, tmp_path: Path) -> None:
    from emgteach.gui.tabs.analysis import (
        _MMG_PID,
        _MOVEMENT_PID,
        _TREMOR_PID,
    )

    # File with an ACC channel placed on the limb -> movement panel default-on.
    with_acc = tmp_path / "with_acc.edf"
    _write_edf(with_acc, [
        ("EMG1", -1.65, 1.65, "mV"),
        ("ACC (limb)", -1.0, 1.0, "g"),
    ])
    tab = _analysis_tab(qapp)
    tab._populate_channels(str(with_acc))
    # ACC excluded from the EMG channel picker.
    assert [tab._combo_canal.itemText(i) for i in range(tab._combo_canal.count())] == [
        "EMG1"
    ]
    assert tab._acc_channel_name == "ACC (limb)" and tab._acc_placement == "limb"
    pm = tab._panel_pids.index(_MMG_PID)
    pt = tab._panel_pids.index(_TREMOR_PID)
    pv = tab._panel_pids.index(_MOVEMENT_PID)
    assert (
        tab._chk_paneles[pm].isEnabled()
        and tab._chk_paneles[pt].isEnabled()
        and tab._chk_paneles[pv].isEnabled()
    )
    assert tab._chk_paneles[pv].isChecked()        # movement default for "limb"
    assert not tab._chk_paneles[pm].isChecked()
    assert not tab._chk_paneles[pt].isChecked()

    # File without an ACC channel -> all ACC panels locked.
    no_acc = tmp_path / "no_acc.edf"
    _write_edf(no_acc, [("EMG1", -1.65, 1.65, "mV")])
    tab._populate_channels(str(no_acc))
    assert tab._acc_channel_name is None
    assert not tab._chk_paneles[pm].isEnabled()
    assert not tab._chk_paneles[pt].isEnabled()
    assert not tab._chk_paneles[pv].isEnabled()


def test_force_velocity_dialog_detects_reps_and_draws(qapp, tmp_path: Path) -> None:
    from pyedflib import highlevel

    from emgteach.gui.widgets.force_velocity_dialog import ForceVelocityDialog

    fs, n = 1000, 12000
    t = np.arange(n) / fs
    rng = np.random.default_rng(0)
    emg = np.full(n, 0.01) + 0.003 * rng.standard_normal(n)
    acc = 0.01 * rng.standard_normal(n)
    for start, amp, freq in [(2.0, 0.15, 6.0), (5.0, 0.30, 4.0), (8.0, 0.5, 3.0)]:
        i0 = int(start * fs)
        i1 = i0 + int(0.8 * fs)
        emg[i0:i1] += amp * np.abs(np.sin(2 * np.pi * 40 * t[i0:i1]))
        acc[i0:i1] += 0.4 * np.sin(2 * np.pi * freq * t[i0:i1])
    edf = tmp_path / "fv.edf"
    headers = [
        highlevel.make_signal_header(
            "EMG1", sample_frequency=fs, physical_min=-1.65,
            physical_max=1.65, dimension="mV",
        ),
        highlevel.make_signal_header(
            "ACC (limb)", sample_frequency=fs, physical_min=-1.0,
            physical_max=1.0, dimension="g",
        ),
    ]
    highlevel.write_edf(str(edf), [emg, acc], headers, highlevel.make_header())

    dlg = ForceVelocityDialog(str(edf), "EMG1", "ACC (limb)")
    assert dlg._table.rowCount() == 3            # three lifts detected
    # No guided markers -> the load column (col 2) starts blank (manual entry).
    assert all(dlg._table.item(i, 2).text() == "" for i in range(3))
    # Every contraction starts ticked as valid (col 0 checkbox).
    from PySide6.QtCore import Qt
    assert all(
        dlg._table.item(i, 0).checkState() == Qt.CheckState.Checked
        for i in range(3)
    )
    # EMG amplitude rises with the (heavier) later reps — recruitment.
    assert dlg._emg_amp[0] < dlg._emg_amp[2]
    dlg._redraw()                                # four curves, no crash
    assert len(dlg._fig.get_axes()) == 4


def test_force_velocity_dialog_prefills_guided_loads(qapp, tmp_path: Path) -> None:
    """A recording made by the guided wizard carries FV load annotations; the
    dialog pre-fills the load column from them instead of leaving it blank."""
    from pyedflib import highlevel

    from emgteach.force_velocity import fv_load_marker
    from emgteach.gui.widgets.force_velocity_dialog import ForceVelocityDialog

    fs, n = 1000, 12000
    t = np.arange(n) / fs
    rng = np.random.default_rng(1)
    emg = np.full(n, 0.01) + 0.003 * rng.standard_normal(n)
    acc = 0.01 * rng.standard_normal(n)
    plan = [(2.0, 4.0), (5.0, 6.0), (8.0, 8.0)]   # (start_s, load_kg)
    for start, _kg in plan:
        i0 = int(start * fs)
        i1 = i0 + int(0.8 * fs)
        emg[i0:i1] += 0.3 * np.abs(np.sin(2 * np.pi * 40 * t[i0:i1]))
        acc[i0:i1] += 0.4 * np.sin(2 * np.pi * 4.0 * t[i0:i1])
    edf = tmp_path / "fv_guided.edf"
    headers = [
        highlevel.make_signal_header(
            "EMG1", sample_frequency=fs, physical_min=-1.65,
            physical_max=1.65, dimension="mV",
        ),
        highlevel.make_signal_header(
            "ACC (limb)", sample_frequency=fs, physical_min=-1.0,
            physical_max=1.0, dimension="g",
        ),
    ]
    header = highlevel.make_header()
    # The wizard marks each load a moment before its lift window.
    header["annotations"] = [
        [start - 0.2, -1, fv_load_marker(kg)] for start, kg in plan
    ]
    highlevel.write_edf(str(edf), [emg, acc], headers, header)

    dlg = ForceVelocityDialog(str(edf), "EMG1", "ACC (limb)")
    assert dlg._table.rowCount() == 3
    prefilled = [dlg._table.item(i, 2).text() for i in range(3)]
    assert prefilled == ["4", "6", "8"]          # loads read from the markers
    dlg._redraw()                                # draws directly, no typing
    assert len(dlg._fig.get_axes()) == 4


def test_channel_diagnostic_picks_the_responding_channel() -> None:
    """The diagnostic flags a channel only when its range clearly stands out."""
    from emgteach.gui.widgets.channel_diagnostic_dialog import (
        ChannelDiagnosticDialog,
    )

    pick = ChannelDiagnosticDialog._pick_channel
    # A4 (index 3) swings widely, the rest are noise -> index 3 wins.
    assert pick([4.0, 3.0, 5.0, 220.0, 2.0, 1.0]) == 3
    # Only noise everywhere -> no winner.
    assert pick([4.0, 3.0, 5.0, 6.0, 2.0, 1.0]) is None
    # Two channels swing similarly -> ambiguous, no false positive.
    assert pick([200.0, 3.0, 180.0, 5.0]) is None
    assert pick([]) is None


def test_force_velocity_averages_reps_and_excludes_unticked() -> None:
    """Repetitions at the same load are averaged; dropping one changes it."""
    import numpy as np

    from emgteach.gui.widgets.force_velocity_dialog import ForceVelocityDialog

    loads = np.array([2.0, 2.0, 4.0, 4.0])
    vel = np.array([1.0, 3.0, 0.5, 0.5])
    emg = np.array([0.1, 0.3, 0.2, 0.2])

    ul, uv, ue = ForceVelocityDialog._average_by_load(loads, vel, emg)
    np.testing.assert_allclose(ul, [2.0, 4.0])
    np.testing.assert_allclose(uv, [2.0, 0.5])       # (1+3)/2, (0.5+0.5)/2
    np.testing.assert_allclose(ue, [0.2, 0.2])

    # Drop the high-velocity outlier of the 2 kg load -> its mean changes.
    keep = np.array([True, False, True, True])
    ul2, uv2, _ = ForceVelocityDialog._average_by_load(
        loads[keep], vel[keep], emg[keep]
    )
    np.testing.assert_allclose(ul2, [2.0, 4.0])
    np.testing.assert_allclose(uv2, [1.0, 0.5])      # only the 1.0 rep remains


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
