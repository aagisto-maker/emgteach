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
        soltando = np.linspace(0.075, 0.0, int(FS * 1.0))
        env[: soltando.size] += soltando
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

    @staticmethod
    def _tab(qapp):
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.acquisition import AcquisitionTab
        from emgteach.gui.widgets.logger import LoggerWidget

        return AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "mvcref"))

    @pytest.mark.gui
    def test_a_reference_close_to_rest_is_called_out(self, qapp) -> None:
        """The real numbers: a reference of 0.015 mV over a resting level of
        0.005 is three times rest, not a maximal contraction."""
        tab = self._tab(qapp)
        try:
            tab._mvc_rest_buf = list(_envelope(0.005, 3000))
            antes = tab._logger.toPlainText()
            tab._mvc_check_is_a_maximum(0, 0.015)
            nuevo = tab._logger.toPlainText()[len(antes):]
            assert "⚠" in nuevo
            assert "0.015" in nuevo or "0,015" in nuevo
        finally:
            tab.close()

    @pytest.mark.gui
    def test_a_genuine_maximum_passes_in_silence(self, qapp) -> None:
        """It must not cry wolf: a real MVC is many times the resting level."""
        tab = self._tab(qapp)
        try:
            tab._mvc_rest_buf = list(_envelope(0.005, 3000))
            antes = tab._logger.toPlainText()
            tab._mvc_check_is_a_maximum(0, 0.40)
            assert tab._logger.toPlainText() == antes
        finally:
            tab.close()

    @pytest.mark.gui
    def test_with_no_baseline_captured_it_says_nothing(self, qapp) -> None:
        """Better silent than guessing: without a rest sample there is nothing
        to compare against."""
        tab = self._tab(qapp)
        try:
            tab._mvc_rest_buf = []
            antes = tab._logger.toPlainText()
            tab._mvc_check_is_a_maximum(0, 0.015)
            assert tab._logger.toPlainText() == antes
        finally:
            tab.close()

    def test_the_ratio_lives_in_the_profile(self) -> None:
        """Tunable against real forearm data, like the co-activation floor."""
        assert EMG_PROFILE.mvc_min_rest_ratio == pytest.approx(5.0)
        assert EMG_PROFILE.mvc_implausible_pct == pytest.approx(150.0)


@pytest.mark.gui
class TestAcceptingTheThirdWay:
    """Saying yes to "use this recording itself" has to *do* it.

    Reported from the bench as "I tell it yes and it does not do it": the flag
    was set and the button enabled, but the result stayed behind a second press
    of Compute, and the load distribution was withheld entirely. Agreeing to a
    known-imperfect option is a decision, not a request for another dialogue.
    """

    @staticmethod
    def _tab(qapp, edf):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QMessageBox

        from emgteach.gui.tabs.mvc import MvcTab
        from emgteach.gui.widgets.logger import LoggerWidget
        from emgteach.modes import MODE_PAIR

        def click_destructive(self):
            for b in self.buttons():
                if self.buttonRole(b) == QMessageBox.ButtonRole.DestructiveRole:
                    b.click()
                    return 0
            return 0

        QMessageBox.exec = click_destructive
        tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "third"))
        tab.apply_mode(MODE_PAIR, False)
        tab.adopt_recording(str(edf))
        return tab

    @staticmethod
    def _edf(path):
        from emgteach.io import BufferedEdfWriter, ChannelInfo

        fs, secs = 1000, 12
        n = fs * secs
        t = np.arange(n) / fs
        rng = np.random.default_rng(2)
        burst = ((t > 3) & (t < 6)).astype(float) + 0.05
        sig = rng.normal(0, 0.3, n) * burst
        with BufferedEdfWriter(
            str(path),
            channels=[ChannelInfo("EMG", dimension="mV", sample_frequency=fs)],
        ) as w:
            for i in range(0, n, fs):
                w.add_samples(sig[i:i + fs])
        return str(path)

    def test_accepting_computes_without_a_second_press(
        self, qapp, tmp_path
    ) -> None:
        from PySide6.QtCore import QElapsedTimer

        tab = self._tab(qapp, self._edf(tmp_path / "solo.edf"))
        try:
            done: list = []
            original = tab._on_result
            tab._on_result = lambda r: (original(r), done.append(r))
            tab._ofrecer_auto_normalizacion()
            timer = QElapsedTimer()
            timer.start()
            while not done and timer.elapsed() < 30000:
                qapp.processEvents()
            assert done, "accepting produced no result"
            assert done[0]["mvc_is_auto"] is True
        finally:
            tab.cleanup()

    def test_the_distribution_is_drawn_but_the_limits_are_not(
        self, qapp, tmp_path
    ) -> None:
        """The shape is a fair description of the recording; the Jonsson
        comparison is not, and drawing it painted everything red."""
        from PySide6.QtCore import QElapsedTimer

        tab = self._tab(qapp, self._edf(tmp_path / "solo.edf"))
        try:
            done: list = []
            original = tab._on_result
            tab._on_result = lambda r: (original(r), done.append(r))
            tab._ofrecer_auto_normalizacion()
            timer = QElapsedTimer()
            timer.start()
            while not done and timer.elapsed() < 30000:
                qapp.processEvents()
            assert done
            ax = tab._apdf_fig.axes[0]
            assert ax.get_lines(), "the distribution was not drawn"
            # Its own maximum, not % MVC, and no limit markers.
            assert "%" in ax.get_xlabel()
            assert "MVC" not in ax.get_xlabel()
            assert "Jonsson" not in ax.get_title()
        finally:
            tab.cleanup()
