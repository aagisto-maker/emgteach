"""Units on the axes: a normalised quantity never carries a physical unit.

The application's central teaching point is that a millivolt does not measure
the muscle — it also measures where the electrodes sat and how much skin and
fat lay between them and the fibres, which is why everything is expressed
against a maximum. A plot that plots a ratio and then labels the axis "mV"
contradicts, in the one place the student is actually looking, what the whole
practical is for.

These tests read the axis labels off real, rendered figures rather than the
source, so they see what the student sees.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QElapsedTimer

from emgteach.io import BufferedEdfWriter, ChannelInfo

pytestmark = pytest.mark.gui

#: Anything that names a physical quantity. A normalised axis may not contain
#: one; "% MVC" is deliberately absent, since a percentage of a maximum *is*
#: the normalised form.
UNITS = (" mv", "(mv", "mv)", " g)", "(g)", " v)", "(v)", "µv", "uv")


def _has_unit(label: str) -> bool:
    low = label.lower()
    return any(u in low for u in UNITS)


def _two_channel_edf(path: Path, fs: int = 1000, secs: int = 10) -> str:
    """Two muscles of deliberately different size.

    The second is a tenth of the first, as an antagonist under more tissue
    would be. In millivolts that difference swamps the picture; normalised,
    the timing that the practical is about survives.
    """
    n = fs * secs
    t = np.arange(n) / fs
    rng = np.random.default_rng(7)
    # A quiet lead-in: the onset detector takes its baseline from the first
    # second, and a recording that starts mid-contraction has no baseline to
    # take — which is also true of a real one.
    quiet = (t >= 1.5).astype(float)
    burst = (np.sin(2 * np.pi * 0.25 * (t - 1.5)) ** 2) * quiet
    agonist = rng.normal(0.0, 0.60, n) * burst
    antagonist = rng.normal(0.0, 0.06, n) * (1.0 - burst) * quiet
    chans = [
        ChannelInfo("Biceps", dimension="mV", sample_frequency=fs),
        ChannelInfo("Triceps", dimension="mV", sample_frequency=fs),
    ]
    with BufferedEdfWriter(str(path), channels=chans) as w:
        for i in range(0, n, fs):
            w.add_samples(agonist[i:i + fs], antagonist[i:i + fs])
    return str(path)


def _run_analysis(qapp, monkeypatch, edf: str):
    """Open the EDF in the analysis tab with both channels and let it draw."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QMessageBox

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget
    from emgteach.modes import MODE_PAIR

    # A two-channel file makes the tab ask which muscle; left to itself the
    # modal would stall the run.
    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: QMessageBox.StandardButton.NoButton
    )
    tab = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "units"))
    tab.apply_mode(MODE_PAIR, False)
    tab.adopt_recording(edf)
    idx = tab._combo_canal.findText("Biceps")
    if idx >= 0:
        tab._combo_canal.setCurrentIndex(idx)
    tab._chk_compare2.setChecked(True)
    idx2 = tab._combo_canal2.findText("Triceps")
    if idx2 >= 0:
        tab._combo_canal2.setCurrentIndex(idx2)

    done: list = []
    original = tab._on_result
    tab._on_result = lambda r: (original(r), done.append(r))
    tab._iniciar_analisis()

    timer = QElapsedTimer()
    timer.start()
    while not done and timer.elapsed() < 30000:
        qapp.processEvents()
    assert done, "the analysis worker produced no result"
    return tab, done[0]


class TestTheAgonistAntagonistOverlay:
    """The one panel that puts two different muscles on a single axis.

    Their millivolts are not comparable, so reading co-contraction off a
    shared millivolt axis measures electrode placement: a thicker biceps
    would look like co-activation. This is the panel where getting the unit
    wrong teaches the opposite of the lesson.
    """

    def test_it_plots_a_ratio_and_says_so(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        edf = _two_channel_edf(tmp_path / "pair.edf")
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            overlay = [
                ax for ax in tab._fig.axes
                if "agonist" in ax.get_title().lower()
            ]
            assert overlay, "the overlay panel was not drawn"
            ax = overlay[0]
            assert not _has_unit(ax.get_ylabel()), (
                f"the overlay names a physical unit: {ax.get_ylabel()!r}"
            )
            # A ratio against each channel's own maximum: both curves must
            # reach ~1 and neither may exceed it.
            for line in ax.get_lines():
                y = np.asarray(line.get_ydata(), dtype=float)
                if y.size > 2:
                    assert y.max() <= 1.001, "not normalised: exceeds its maximum"
        finally:
            tab.cleanup()

    def test_the_weaker_muscle_is_not_flattened(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """The antagonist is a tenth of the agonist in millivolts. On a shared
        millivolt axis it would be a flat line at the bottom and its timing
        unreadable — which is the practical's actual question."""
        edf = _two_channel_edf(tmp_path / "pair.edf")
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            ax = next(ax for ax in tab._fig.axes
                      if "agonist" in ax.get_title().lower())
            spans = [
                float(np.ptp(np.asarray(ln.get_ydata(), dtype=float)))
                for ln in ax.get_lines()
                if np.asarray(ln.get_ydata()).size > 2
            ]
            assert len(spans) == 2, "both muscles should be drawn"
            # Neither curve may be squashed into a fraction of the other's
            # range; normalised, both use most of the axis.
            assert min(spans) > 0.5 * max(spans), spans
        finally:
            tab.cleanup()


class TestEveryPanelAgrees:
    def test_no_rendered_axis_labels_a_ratio_with_a_unit(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """Sweep every panel the analysis tab drew.

        A panel whose data never leaves 0-1.15 while its axis says millivolts
        is either mislabelled or plotting something it should not; either way
        a student reads a ratio as an amplitude.
        """
        edf = _two_channel_edf(tmp_path / "pair.edf")
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            offenders = []
            for ax in tab._fig.axes:
                label = ax.get_ylabel()
                if not _has_unit(label):
                    continue
                ys = [
                    np.asarray(ln.get_ydata(), dtype=float)
                    for ln in ax.get_lines()
                ]
                ys = [y for y in ys if y.size > 2 and np.isfinite(y).any()]
                if ys and all(np.nanmax(np.abs(y)) <= 1.15 for y in ys):
                    offenders.append(f"{ax.get_title()!r} → {label!r}")
            assert not offenders, (
                "axes that look like a ratio but name a unit: "
                + "; ".join(offenders)
            )
        finally:
            tab.cleanup()


def _silent_antagonist_edf(path: Path, fs: int = 1000, secs: int = 10) -> str:
    """One muscle working, the other genuinely silent.

    What a clean single-direction movement produces, and the case that breaks
    normalisation: the silent channel has no maximum, so dividing by its
    largest noise peak sends baseline noise to full height.
    """
    n = fs * secs
    t = np.arange(n) / fs
    rng = np.random.default_rng(11)
    quiet = (t >= 1.5).astype(float)
    burst = (np.sin(2 * np.pi * 0.25 * (t - 1.5)) ** 2) * quiet
    agonist = rng.normal(0.0, 0.60, n) * burst
    antagonist = rng.normal(0.0, 0.004, n)          # baseline only
    chans = [
        ChannelInfo("Flexor", dimension="mV", sample_frequency=fs),
        ChannelInfo("Extensor", dimension="mV", sample_frequency=fs),
    ]
    with BufferedEdfWriter(str(path), channels=chans) as w:
        for i in range(0, n, fs):
            w.add_samples(agonist[i:i + fs], antagonist[i:i + fs])
    return str(path)


class TestASilentMuscleIsNotDrawnAsActive:
    """Normalising to a channel's own maximum assumes it *has* one.

    A muscle that never contracted has only noise, and dividing by its largest
    noise peak magnifies that noise to full scale — which reads as
    co-contraction, the exact opposite of the finding. The panel has to say
    "silent", not draw a full-height wiggle.
    """

    def test_the_worker_reports_which_channels_contracted(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        edf = _silent_antagonist_edf(tmp_path / "silent.edf")
        tab, r = _run_analysis(qapp, monkeypatch, edf)
        try:
            assert r["emg_contracted"] is True
            assert r["emg_contracted_2"] is False
        finally:
            tab.cleanup()

    def test_both_are_reported_active_when_both_work(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """The guard must not fire on the normal alternating protocol."""
        edf = _two_channel_edf(tmp_path / "pair.edf")
        tab, r = _run_analysis(qapp, monkeypatch, edf)
        try:
            assert r["emg_contracted"] is True
            assert r["emg_contracted_2"] is True
        finally:
            tab.cleanup()

    def test_the_silent_muscle_is_drawn_as_silent(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        edf = _silent_antagonist_edf(tmp_path / "silent.edf")
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            ax = next(ax for ax in tab._fig.axes
                      if "agonist" in ax.get_title().lower())
            etiquetas = [ln.get_label() for ln in ax.get_lines()]
            dicho = [e for e in etiquetas if "Extensor" in str(e)]
            assert dicho, f"the silent channel is not named: {etiquetas}"
            assert "contraction" in str(dicho[0]) or "contracc" in str(dicho[0]), (
                f"the legend does not say it stayed silent: {dicho[0]!r}"
            )
            # Dashed, so it does not read as a signal at a glance.
            silenciosa = next(
                ln for ln in ax.get_lines() if "Extensor" in str(ln.get_label())
            )
            assert silenciosa.get_linestyle() not in ("-", "solid")
        finally:
            tab.cleanup()
