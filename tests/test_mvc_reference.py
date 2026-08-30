"""When the "maximum" was not a maximum, and when there was no baseline.

Both were found on the first real forearm session, and neither was a bug in
the maths: the application recorded faithfully what the subject did and then
reported it without comment. A calibration that captured a tenth of the true
maximum produced an analysis running to 1509 % MVC, live load bars in the red
from the first contraction, and a co-activation index computed on numbers that
were wrong by a factor of ten.

The application cannot know whether someone pushed hard. It can compare what
it captured against what the same muscle looked like doing nothing a few
seconds earlier, and it can notice afterwards that a recording spends a third
of its time above 100 % of its own maximum.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.profiles import EMG_PROFILE
from emgteach.workers.analysis import _baseline_is_usable

FS = 1000.0


def _envelope(mean: float, n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.abs(rng.normal(mean, mean * 0.25, n)) + mean * 0.5


class TestWasThereABaselineAtAll:
    """Telling "the muscle stayed silent" from "the recording has no rest".

    They look identical to the onset detector — nothing is detected either way
    — but only one of them is a statement about the subject. Saying the wrong
    one is telling the student something false about their own arm.
    """

    def test_a_clean_opening_second_gives_a_usable_baseline(self) -> None:
        n = int(FS * 20)
        env = _envelope(0.003, n)
        env[int(FS * 5):int(FS * 8)] += 0.08          # a contraction, later
        assert _baseline_is_usable(env, FS, EMG_PROFILE) is True

    def test_starting_mid_contraction_leaves_no_baseline(self) -> None:
        """The shape of the real failure, reproduced.

        The subject was still letting go when the recording began, so the
        opening second holds the *transition* from active to rest. Its mean is
        high and its spread higher still, and baseline + 3 SD lands above
        everything that follows: nothing is ever detected, on a channel that
        plainly contracted. In the session that found this the threshold came
        out at 0.0804 mV on a recording whose maximum was 0.0707.
        """
        n = int(FS * 20)
        env = _envelope(0.003, n)
        letting_go = np.linspace(0.075, 0.0, int(FS * 1.0))
        env[: letting_go.size] += letting_go
        env[int(FS * 6):int(FS * 9)] += 0.035         # a real contraction
        assert _baseline_is_usable(env, FS, EMG_PROFILE) is False

    def test_the_same_recording_with_two_quiet_seconds_first_is_fine(
        self,
    ) -> None:
        """And the fix the message asks for: start with the muscle at rest."""
        n = int(FS * 20)
        env = _envelope(0.003, n)
        env[int(FS * 6):int(FS * 9)] += 0.035
        assert _baseline_is_usable(env, FS, EMG_PROFILE) is True

    def test_the_threshold_test_is_what_separates_them(self) -> None:
        """A resting threshold above the recording's own maximum cannot be a
        resting threshold — that is the whole test, and it needs no tuning."""
        n = int(FS * 20)
        flat = _envelope(0.003, n)
        assert _baseline_is_usable(flat, FS, EMG_PROFILE) is True

    def test_a_recording_too_short_to_hold_a_baseline(self) -> None:
        assert _baseline_is_usable(_envelope(0.003, 50), FS, EMG_PROFILE) is False


class TestTheCalibrationIsComparedWithRest:
    """The prevention half: said at the bench, while it can still be redone."""

    @pytest.fixture
    def tab(self, qapp):
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.acquisition import AcquisitionTab
        from emgteach.gui.widgets.logger import LoggerWidget

        widget = AcquisitionTab(
            LoggerWidget(), QSettings("emgteach-test", "mvcref")
        )
        yield widget
        widget.close()

    @pytest.mark.gui
    def test_a_reference_close_to_rest_is_called_out(self, tab) -> None:
        """The real numbers from the first session: a reference of 0.015 mV
        over a resting level of 0.005 is three times rest, not a maximum."""
        tab._mvc_rest_buf = list(_envelope(0.005, 3000))
        before = tab._logger.toPlainText()
        tab._mvc_check_is_a_maximum(0, 0.015)
        added = tab._logger.toPlainText()[len(before):]
        assert "⚠" in added
        assert "0.015" in added or "0,015" in added

    @pytest.mark.gui
    def test_a_genuine_maximum_passes_in_silence(self, tab) -> None:
        """It must not cry wolf. In the second session, with the calibration
        made against a resistance, the reference came out 19 times the resting
        level — and nothing was said, correctly."""
        tab._mvc_rest_buf = list(_envelope(0.005, 3000))
        before = tab._logger.toPlainText()
        tab._mvc_check_is_a_maximum(0, 0.40)
        assert tab._logger.toPlainText() == before

    @pytest.mark.gui
    def test_with_no_baseline_captured_it_says_nothing(self, tab) -> None:
        """Better silent than guessing: without a rest sample there is nothing
        to compare against."""
        tab._mvc_rest_buf = []
        before = tab._logger.toPlainText()
        tab._mvc_check_is_a_maximum(0, 0.015)
        assert tab._logger.toPlainText() == before

    def test_the_thresholds_live_in_the_profile(self) -> None:
        """Tunable against real forearm data, like the co-activation floor."""
        assert EMG_PROFILE.mvc_min_rest_ratio == pytest.approx(5.0)
        assert EMG_PROFILE.mvc_implausible_pct == pytest.approx(150.0)
        assert EMG_PROFILE.mvc_peak_window_s == pytest.approx(0.5)


@pytest.mark.gui
class TestAcceptingTheThirdWay:
    """Saying yes to "use this recording itself" has to *do* it.

    Reported from the bench as "I tell it yes and it does not do it": the flag
    was set and the button enabled, but the result stayed behind a second press
    of Compute, and the load distribution was withheld entirely. Agreeing to a
    known-imperfect option is a decision, not a request for another dialogue.
    """

    @staticmethod
    def _edf(path):
        from emgteach.io import BufferedEdfWriter, ChannelInfo

        fs, secs = 1000, 12
        n = fs * secs
        t = np.arange(n) / fs
        rng = np.random.default_rng(2)
        burst = ((t > 3) & (t < 6)).astype(float) + 0.05
        signal = rng.normal(0, 0.3, n) * burst
        with BufferedEdfWriter(
            str(path),
            channels=[ChannelInfo("EMG", dimension="mV", sample_frequency=fs)],
        ) as writer:
            for i in range(0, n, fs):
                writer.add_samples(signal[i:i + fs])
        return str(path)

    @pytest.fixture
    def accepted(self, qapp, tmp_path):
        """A tab that has been told "use this recording", and its result."""
        from PySide6.QtCore import QElapsedTimer, QSettings
        from PySide6.QtWidgets import QMessageBox

        from emgteach.gui.tabs.mvc import MvcTab
        from emgteach.gui.widgets.logger import LoggerWidget
        from emgteach.modes import MODE_PAIR

        def click_destructive(self):
            for button in self.buttons():
                role = self.buttonRole(button)
                if role == QMessageBox.ButtonRole.DestructiveRole:
                    button.click()
                    return 0
            return 0

        QMessageBox.exec = click_destructive
        tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "third"))
        tab.apply_mode(MODE_PAIR, False)
        tab.adopt_recording(self._edf(tmp_path / "solo.edf"))

        done: list = []
        original = tab._on_result
        tab._on_result = lambda r: (original(r), done.append(r))
        tab._ofrecer_auto_normalizacion()
        timer = QElapsedTimer()
        timer.start()
        while not done and timer.elapsed() < 30000:
            qapp.processEvents()

        yield tab, done
        qapp.processEvents()
        tab.cleanup()

    def test_accepting_computes_without_a_second_press(self, accepted) -> None:
        _tab, done = accepted
        assert done, "accepting produced no result"
        assert done[0]["mvc_is_auto"] is True

    def test_the_distribution_is_drawn_but_the_limits_are_not(
        self, accepted
    ) -> None:
        """The shape is a fair description of the recording; the Jonsson
        comparison is not, and drawing it painted everything red."""
        tab, done = accepted
        assert done
        ax = tab._apdf_fig.axes[0]
        assert ax.get_lines(), "the distribution was not drawn"
        assert "%" in ax.get_xlabel()
        assert "MVC" not in ax.get_xlabel()
        assert "Jonsson" not in ax.get_title()


class TestTheAmplitudeArrows:
    """The ▲▼ sidebar changes the amplitude; it does not pan.

    Reported from the bench: in the MVC tab the arrows moved the trace up and
    down instead of making it taller. The zoom held the *midpoint* of the view
    fixed, and panels 2 and 3 carry non-negative signals drawn from zero — so
    halving the range about its midpoint lifted the floor off zero and slid the
    trace upwards. The analysis tab had always scaled about zero.
    """

    @pytest.fixture
    def zoom(self, qapp):
        """A tab and a bare axes to zoom.

        The backend is left alone: switching it here would invalidate the Qt
        canvas of any tab already built in this session, and a plain Figure
        needs no backend to hold an axes.

        ``_y_zoom`` ends in ``draw_idle()``, which schedules the redraw on the
        event loop; tearing the tab down with that still pending fires it on a
        canvas that has just been deleted, so the queue is drained first.
        """
        from matplotlib.figure import Figure
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.mvc import MvcTab
        from emgteach.gui.widgets.logger import LoggerWidget

        tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "zoom"))
        yield tab, Figure().subplots()
        qapp.processEvents()
        tab.cleanup()

    @pytest.mark.gui
    def test_a_non_negative_axis_keeps_its_floor_at_zero(self, zoom) -> None:
        """The envelope and the % MVC start at zero and cannot go below it."""
        tab, ax = zoom
        for limits in ((0.0, 0.10), (0.0, 150.0)):
            ax.set_ylim(*limits)
            tab._y_accum = {}
            tab._y_zoom(0, ax, True)
            bottom, top = ax.get_ylim()
            assert bottom == pytest.approx(0.0), limits
            assert top == pytest.approx(limits[1] / 1.5), limits

    @pytest.mark.gui
    def test_zooming_out_also_keeps_the_floor(self, zoom) -> None:
        tab, ax = zoom
        ax.set_ylim(0.0, 0.10)
        tab._y_accum = {}
        tab._y_zoom(0, ax, False)
        bottom, top = ax.get_ylim()
        assert bottom == pytest.approx(0.0)
        assert top == pytest.approx(0.15)

    @pytest.mark.gui
    def test_a_bipolar_axis_scales_symmetrically(self, zoom) -> None:
        """The raw and filtered traces swing either side of zero, and zero is
        still the anchor — there it happens to be the midpoint too."""
        tab, ax = zoom
        ax.set_ylim(-0.5, 0.5)
        tab._y_accum = {}
        tab._y_zoom(0, ax, True)
        bottom, top = ax.get_ylim()
        assert bottom == pytest.approx(-1 / 3, abs=1e-3)
        assert top == pytest.approx(1 / 3, abs=1e-3)

    @pytest.mark.gui
    def test_the_trace_grows_rather_than_moves(self, zoom) -> None:
        """Stated as the symptom rather than the mechanism: a fixed value sits
        at a *higher fraction* of the axis after zooming in, and the bottom of
        the view does not move."""
        tab, ax = zoom
        ax.set_ylim(0.0, 0.10)
        value = 0.03
        before = (value - 0.0) / 0.10
        tab._y_accum = {}
        tab._y_zoom(0, ax, True)
        bottom, top = ax.get_ylim()
        assert (value - bottom) / (top - bottom) > before
        assert bottom == pytest.approx(0.0)


class TestJudgingAReferenceFairly:
    """What is compared against the reference is measured the same way."""

    def test_the_running_mean_matches_the_reference_statistic(self) -> None:
        """The reference is the strongest 0.5 s the subject held, so a
        recording is judged by its own strongest 0.5 s and not by an
        instantaneous peak. On the second bench recording that difference
        alone turned an honest 234 % into an alarming 384 %.
        """
        from emgteach.mvc import mvc_peak_hold
        from emgteach.workers.analysis import _sustained

        rng = np.random.default_rng(9)
        n = int(FS * 10)
        env = np.abs(rng.normal(0.02, 0.004, n))
        env[int(FS * 4):int(FS * 4.2)] += 0.4          # a brief spike
        sustained = _sustained(env, FS, 0.5)
        assert sustained.max() < env.max() / 2, "the spike survived the mean"
        assert sustained.max() == pytest.approx(
            mvc_peak_hold(env, int(0.5 * FS)), rel=1e-9
        ), "the two ways of measuring the same thing disagree"

    def test_a_short_recording_is_returned_untouched(self) -> None:
        from emgteach.workers.analysis import _sustained

        short = _envelope(0.02, 100)
        assert np.array_equal(_sustained(short, FS, 0.5), short)
