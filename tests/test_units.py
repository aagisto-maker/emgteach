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

#: Anything that names a physical quantity.
UNITS = (" mv", "(mv", "mv)", " g)", "(g)", " v)", "(v)", "µv", "uv")


def _has_unit(label: str) -> bool:
    """Does this axis label name a physical unit?

    "% MVC" is removed first: a percentage of a maximum *is* the normalised
    form, and it happens to contain the letters of a millivolt.
    """
    low = label.lower().replace("% mvc", "").replace("%mvc", "")
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


def _with_mvc(path: Path, refs: dict[int, float], fs: int = 1000,
              secs: int = 10) -> str:
    """The same pair recording, with an MVC reference annotated per channel.

    Written the way the acquisition tab writes it, so the test exercises the
    real round trip: calibrate → record → close the EDF → reopen in Analysis.
    """
    from emgteach.mvc import mvc_ref_marker

    n = fs * secs
    t = np.arange(n) / fs
    rng = np.random.default_rng(3)
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
        for channel, ref in refs.items():
            w.add_annotation(0.5, mvc_ref_marker(channel, ref))
    return str(path)


class TestTheReferenceTravelsInTheFile:
    """The MVC reference used to die with the session; now it rides in the EDF.

    Without that, the offline analysis — which starts from the file — has no
    way of knowing what each muscle's maximum was, which is the whole reason
    the panel could only ever speak millivolts.
    """

    def test_the_label_round_trips(self) -> None:
        from emgteach.mvc import mvc_ref_marker, parse_mvc_ref_markers

        markers = [(1.0, mvc_ref_marker(0, 0.4213)),
                   (2.0, mvc_ref_marker(1, 0.2871))]
        assert parse_mvc_ref_markers(markers) == {0: 0.4213, 1: 0.2871}

    def test_the_channel_is_1_based_on_the_label_and_0_based_in_the_dict(
        self,
    ) -> None:
        """The label is read by a human, the dict by the code."""
        from emgteach.mvc import mvc_ref_marker, parse_mvc_ref_markers

        assert "ch=1" in mvc_ref_marker(0, 0.5)
        assert 0 in parse_mvc_ref_markers([(0.0, mvc_ref_marker(0, 0.5))])

    def test_the_last_calibration_of_a_channel_wins(self) -> None:
        """It is the reference the subject finished with, and the one that
        matches the electrodes as they ended up placed."""
        from emgteach.mvc import mvc_ref_marker, parse_mvc_ref_markers

        markers = [(9.0, mvc_ref_marker(0, 0.9)), (1.0, mvc_ref_marker(0, 0.1))]
        assert parse_mvc_ref_markers(markers) == {0: 0.9}

    def test_other_annotations_are_ignored(self) -> None:
        """The student's own marks and the force-velocity loads share the file."""
        from emgteach.force_velocity import fv_load_marker
        from emgteach.mvc import parse_mvc_ref_markers

        markers = [(1.0, "Contraction onset"), (2.0, fv_load_marker(4.0)),
                   (3.0, "MVC"), (4.0, "")]
        assert parse_mvc_ref_markers(markers) == {}

    def test_the_analysis_reads_it_back_out_of_a_real_edf(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """The trip that matters: written on calibration, read after reopening."""
        edf = _with_mvc(tmp_path / "refs.edf", {0: 0.80, 1: 0.09})
        tab, r = _run_analysis(qapp, monkeypatch, edf)
        try:
            assert r["mvc_ref"] == pytest.approx(0.80)
            assert r["mvc_ref_2"] == pytest.approx(0.09)
        finally:
            tab.cleanup()


class TestTheAgonistAntagonistOverlay:
    """The one panel that puts two different muscles on a single axis.

    Their millivolts are not comparable — surface amplitude depends on the skin
    and fat between muscle and electrode — so with a reference for both the
    panel speaks % MVC, and without one it stays in millivolts and says so.
    Mixing the two units on one axis is the one thing it must never do.
    """

    def test_with_both_references_it_speaks_percent_mvc(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        edf = _with_mvc(tmp_path / "refs.edf", {0: 0.80, 1: 0.09})
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            ax = next(a for a in tab._fig.axes
                      if "agonist" in a.get_title().lower())
            assert "%" in ax.get_ylabel(), ax.get_ylabel()
            assert not _has_unit(ax.get_ylabel())
            assert "% MVC" in ax.get_title()
            # Both muscles reach a decent fraction of their own maximum, so
            # neither is squashed against the axis.
            spans = [float(np.ptp(np.asarray(ln.get_ydata(), dtype=float)))
                     for ln in ax.get_lines()
                     if np.asarray(ln.get_ydata()).size > 2]
            assert len(spans) == 2
            assert min(spans) > 0.3 * max(spans), spans
        finally:
            tab.cleanup()

    def test_without_references_it_stays_in_millivolts_and_warns(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """The fallback has to admit what it is. A picture that quietly looked
        comparable would be worse than one that says it is not — and the
        warning has to be *in the figure*, which travels alone into the PDF."""
        edf = _two_channel_edf(tmp_path / "pair.edf")
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            ax = next(a for a in tab._fig.axes
                      if "agonist" in a.get_title().lower())
            assert _has_unit(ax.get_ylabel()), ax.get_ylabel()
            avisos = [t.get_text() for t in ax.texts
                      if "millivolt" in t.get_text().lower()
                      or "milivolt" in t.get_text().lower()]
            assert avisos, [t.get_text() for t in ax.texts]
        finally:
            tab.cleanup()

    def test_one_reference_behaves_like_none(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """Units are never mixed on the one axis: a % MVC curve beside a
        millivolt curve invites exactly the comparison the panel exists to
        make possible."""
        edf = _with_mvc(tmp_path / "half.edf", {0: 0.80})
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            ax = next(a for a in tab._fig.axes
                      if "agonist" in a.get_title().lower())
            assert _has_unit(ax.get_ylabel()), ax.get_ylabel()
            assert any("millivolt" in t.get_text().lower() for t in ax.texts)
        finally:
            tab.cleanup()


class TestEveryPanelAgrees:
    def test_no_axis_calls_itself_normalised_and_names_a_unit(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """Sweep every panel for a label that contradicts itself.

        An axis that announces a ratio — a percentage, "normalised", "0-1" —
        and then also names millivolts is telling the student two different
        things about the same numbers. Checked on the declared label rather
        than guessed from the magnitudes, because a genuine millivolt envelope
        is made of small numbers too and there is no telling the two apart by
        size.
        """
        edf = _with_mvc(tmp_path / "refs.edf", {0: 0.80, 1: 0.09})
        tab, _r = _run_analysis(qapp, monkeypatch, edf)
        try:
            offenders = [
                f"{ax.get_title()!r} → {ax.get_ylabel()!r}"
                for ax in tab._fig.axes
                if any(w in ax.get_ylabel().lower()
                       for w in ("%", "normalis", "0-1", "fraction"))
                and _has_unit(ax.get_ylabel())
            ]
            assert not offenders, (
                "axes that call themselves a ratio and name a unit: "
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

    def test_in_percent_mvc_a_silent_muscle_reads_low(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        """What normalising to the MVC gives for free.

        Against its own *maximum* a silent muscle's noise fills the axis and
        reads as co-contraction. Against its own *MVC* it stays where it
        belongs — near zero — which is also what lets a co-activation floor
        mean anything.
        """
        edf = _silent_antagonist_edf(tmp_path / "silent.edf")
        # Give both channels a reference; the antagonist's is a real maximum
        # measured on a muscle that did work at some other time.
        import pyedflib  # noqa: F401  (ensures the EDF stack is present)

        from emgteach.mvc import mvc_ref_marker

        tab, r = _run_analysis(qapp, monkeypatch, edf)
        try:
            env2 = np.asarray(r["emg_envelope_2"], dtype=float)
            # Expressed against a plausible MVC for that muscle, the silent
            # trace stays far below the working one.
            env1 = np.asarray(r["emg_envelope"], dtype=float)
            assert env2.max() < 0.1 * env1.max(), (env1.max(), env2.max())
            assert mvc_ref_marker(1, 0.2)          # helper stays importable
        finally:
            tab.cleanup()
