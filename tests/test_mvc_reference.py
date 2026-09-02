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
class TestThereIsNoThirdWay:
    """"Use this recording itself" is gone, and with it its whole dialogue.

    It existed so that someone who had already recorded without a maximal
    effort could still get *something*. What they got was a number for every
    panel, each wrong in the same direction: dividing a recording by its own
    95th percentile makes its loudest moment 100 % whatever the muscle can do,
    so the Jonsson limits reported an overloaded subject regardless. A failure
    mode that has to be sign-posted in five places is a failure mode to
    delete.

    What is *not* deleted is panel 2's "normalised to its own maximum": the
    same arithmetic under an honest name, correct for the time course of one
    channel. What went is its use as a reference for muscle load.
    """

    def test_the_offer_and_its_dialogue_are_gone(self) -> None:
        from emgteach.gui.tabs.mvc import MvcTab

        for nombre in ("_ofrecer_auto_normalizacion", "_confirmar_sin_referencia",
                       "_seleccionar_edf_cvm", "_limpiar_cvm",
                       "_reference_required"):
            assert not hasattr(MvcTab, nombre), nombre

    def test_the_worker_takes_no_second_file(self) -> None:
        """The reference comes out of the session. There is nowhere else to
        look, so there is no parameter to pass."""
        import inspect

        from emgteach.workers.mvc import MvcWorker

        assert "mvc_path" not in inspect.signature(MvcWorker.__init__).parameters



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


@pytest.mark.gui
class TestBestOfThreeAndTheFinalPanel:
    """Two things the third bench session exposed.

    The flexor calibration came out right that day — 38 times its resting
    level, with the recording's strongest half-second reaching 111 % of it,
    which is what a correct MVC looks like. The extensor did not: its
    reference landed *below* its own resting level. One attempt per muscle
    leaves nothing to fall back on when that happens, and the warning that
    said so scrolled out of the event log unseen.
    """

    @pytest.fixture
    def tab(self, qapp):
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.acquisition import AcquisitionTab
        from emgteach.gui.widgets.logger import LoggerWidget

        widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "b3"))
        yield widget
        widget.close()

    def test_best_of_three_is_the_behaviour_not_a_box(self, tab) -> None:
        """It was a checkbox, off by default, in every practical — and the
        protocol document told the operator to tick it. Repeating the maximum
        and keeping the strongest is not an option: it is how a maximum is
        measured at all, so there is no box, and a calibration always asks for
        three efforts per muscle."""
        assert not hasattr(tab, "_chk_mvc_best3")

        class Corriendo:
            def isRunning(self) -> bool:
                return True

            def add_marker(self, *_a) -> None:
                pass

        tab._worker = Corriendo()
        try:
            tab._iniciar_calibracion(auto_flow=False)
            assert tab._mvc_reps == 3
        finally:
            tab._mvc_cancel()
            tab._worker = None

    def test_a_weak_calibration_ends_on_the_panel_not_only_in_the_log(
        self, tab
    ) -> None:
        """The real extensor figures: a reference of 0.0286 mV over a resting
        level of about 0.031 — the "maximum" was weaker than rest."""
        tab._mvc_rest_buf = list(_envelope(0.031, 3000))
        tab._mvc_check_is_a_maximum(0, 0.0286)
        tab._mvc_ref[0] = 0.0286
        tab._mvc_finish_all()
        assert "weak" in tab._mvc_overlay._title.lower() or (
            "floja" in tab._mvc_overlay._title.lower()
        )
        assert tab._mvc_overlay._subtitle

    def test_a_good_calibration_still_ends_on_ready(self, tab) -> None:
        """It must not shout at a session that went well: the flexor of that
        same recording reached 20 times its resting level."""
        tab._mvc_rest_buf = list(_envelope(0.005, 3000))
        tab._mvc_check_is_a_maximum(0, 0.0999)
        tab._mvc_ref[0] = 0.0999
        tab._mvc_finish_all()
        assert "weak" not in tab._mvc_overlay._title.lower()
        assert "floja" not in tab._mvc_overlay._title.lower()

    def test_the_verdict_is_cleared_between_calibrations(self, tab) -> None:
        """A second attempt must not inherit the first one's complaint."""
        tab._mvc_rest_buf = list(_envelope(0.031, 3000))
        tab._mvc_check_is_a_maximum(0, 0.0286)
        assert tab._mvc_no_maximas
        tab.reset()
        assert not tab._mvc_no_maximas


class TestAreTheTwoChannelsSeeingTwoMuscles:
    """«Es difícil separar ECR de FCR en la calibración» — the fourth session.

    Both references came out maximal that day (47 and 28 times their resting
    levels), so the difficulty was not a weak contraction: it was that the two
    channels rose and fell together. Measured on that recording, the resting
    channel reached 20-26 % of its own reference while the other muscle was at
    its maximum, and the two envelopes correlated at r = +0.79 throughout the
    calibration — against r = +0.07 over the working recording that followed.

    So the antagonist is never silent during a maximal effort: it holds the
    joint, and part of what its electrodes read is the other muscle's signal
    conducted through the tissue. Neither is separable from two bipolar
    channels, and neither is a fault. What the wizard can do is measure how
    far above that floor the pair goes, and say so when the two channels stop
    telling two muscles apart.
    """

    @pytest.fixture
    def tab(self, qapp):
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.acquisition import AcquisitionTab
        from emgteach.gui.widgets.logger import LoggerWidget

        widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "xt"))
        widget._n_channels = 2
        yield widget
        widget.close()

    @staticmethod
    def _cross(tab, level: float) -> None:
        """Channel 1 held at *level* while channel 0 was being calibrated."""
        tab._mvc_cross[0][1] = [np.full(4000, level)]

    def test_the_other_channel_is_recorded_during_the_contraction(
        self, tab
    ) -> None:
        """Nothing can be measured that was not kept: the wizard used to
        accumulate only the muscle it was calibrating."""
        tab._mvc_muscle = 0
        tab._mvc_reps = 2          # so finishing rep 1 does not end the wizard
        env = [np.full(100, 0.10), np.full(100, 0.02)]
        tab._mvc_feed(env)
        tab._mvc_feed(env)
        tab._mvc_finish_rep()
        assert tab._mvc_cross[0][1][0].size == 200
        assert float(tab._mvc_cross[0][1][0].mean()) == pytest.approx(0.02)

    def test_the_figure_is_a_share_of_the_other_muscles_own_reference(
        self, tab
    ) -> None:
        """The bench pair: 0.036 mV on the extensor against its own 0.171."""
        tab._mvc_ref[0], tab._mvc_ref[1] = 0.0979, 0.1712
        self._cross(tab, 0.036)
        cruce = tab._mvc_crosstalk()
        assert len(cruce) == 1
        _, _, pct = cruce[0]
        assert pct == pytest.approx(21.0, abs=1.0)

    def test_a_normal_montage_ends_on_ready(self, tab) -> None:
        """21 % is what a correctly placed pair does. It must not be
        an alarm, or the alarm means nothing when it matters."""
        tab._mvc_ref[0], tab._mvc_ref[1] = 0.0979, 0.1712
        self._cross(tab, 0.036)
        tab._mvc_finish_all()
        assert "not separated" not in tab._mvc_overlay._title.lower()
        assert "sin separar" not in tab._mvc_overlay._title.lower()

    def test_two_pairs_on_one_muscle_end_on_the_panel(self, tab) -> None:
        """Both electrode pairs over the flexor: the second channel follows
        the first one to within a tenth, and every later comparison between
        them — the co-activation index above all — measures nothing."""
        tab._mvc_ref[0], tab._mvc_ref[1] = 0.0979, 0.1712
        self._cross(tab, 0.15)                     # 88 % of the other reference
        tab._mvc_finish_all()
        assert (
            "not separated" in tab._mvc_overlay._title.lower()
            or "sin separar" in tab._mvc_overlay._title.lower()
        )
        assert tab._mvc_overlay._subtitle

    def test_a_reference_that_is_not_a_maximum_still_wins_the_panel(
        self, tab
    ) -> None:
        """Both faults at once. The weak reference is the one that corrupts
        every later percentage, so it is the one the operator must read."""
        tab._mvc_ref[0], tab._mvc_ref[1] = 0.0979, 0.1712
        self._cross(tab, 0.15)
        tab._mvc_rest_buf = list(_envelope(0.031, 3000))
        tab._mvc_check_is_a_maximum(0, 0.0286)
        tab._mvc_finish_all()
        assert (
            "weak" in tab._mvc_overlay._title.lower()
            or "floja" in tab._mvc_overlay._title.lower()
        )

    def test_one_channel_measures_nothing(self, tab) -> None:
        """A single sensor has no other channel to compare against."""
        tab._n_channels = 1
        tab._mvc_ref[0] = 0.0979
        assert tab._mvc_crosstalk() == []

    def test_the_threshold_lives_in_the_profile(self) -> None:
        assert EMG_PROFILE.mvc_crosstalk_pct == 50.0


class TestTheRestingBaselineComesFromThePause:
    """The two-phase flow created the very problem the baseline check warns of.

    The analysed span starts at ``REC start``, and the countdown that precedes
    it tells the subject the recording is beginning — so they begin. On the
    first complete session the extensor's opening second measured 41 µV against
    17 µV during the preparation pause, and the threshold it gave (171 µV) sat
    above the recording's own maximum (130 µV): nothing was ever detected, and
    the application told the student to "record a couple of quiet seconds
    before the first contraction" — which the application itself had just made
    impossible by deciding where the recording starts.

    The pause is the answer, and it is already in the file: quiet by design,
    outside the analysed span, and the same length every time.
    """

    @staticmethod
    def _tramo(inicio_activo: bool) -> np.ndarray:
        """The analysed span, shaped like the real one.

        Resting level 30 µV and a contraction reaching about 130 µV — the
        extensor's own figures. When the subject starts at the countdown the
        opening second holds the *ramp* into the first contraction, which is
        what makes its spread, and therefore the threshold, so large.
        """
        env = _envelope(0.0295, int(FS * 20), seed=4)
        env[int(FS * 4):int(FS * 7)] += 0.10
        if inicio_activo:
            arranque = np.linspace(0.0, 0.10, int(FS * 1.0))
            env[: arranque.size] += arranque
        return env

    def test_an_active_opening_second_defeats_the_old_test(self) -> None:
        """The fixture has to reproduce the failure, or the next test proves
        nothing."""
        assert _baseline_is_usable(self._tramo(True), FS, EMG_PROFILE) is False

    def test_the_pause_rescues_it(self) -> None:
        pausa = _envelope(0.0165, int(FS * 5), seed=5)
        assert _baseline_is_usable(
            self._tramo(True), FS, EMG_PROFILE, baseline=pausa
        ) is True

    def test_a_pause_that_was_not_quiet_is_not_rescued(self) -> None:
        """It must not paper over a subject who kept working through the
        countdown: then there really is no baseline in the file."""
        pausa = _envelope(0.09, int(FS * 5), seed=6)
        assert _baseline_is_usable(
            self._tramo(True), FS, EMG_PROFILE, baseline=pausa
        ) is False

    def test_without_a_pause_nothing_changes(self) -> None:
        """Every recording made before the two-phase flow still takes its
        baseline from the opening second."""
        assert _baseline_is_usable(self._tramo(False), FS, EMG_PROFILE) is True
        assert _baseline_is_usable(
            self._tramo(False), FS, EMG_PROFILE, baseline=None
        ) is True

    def test_a_pause_too_short_to_measure_is_ignored(self) -> None:
        assert _baseline_is_usable(
            self._tramo(False), FS, EMG_PROFILE, baseline=np.array([0.01])
        ) is True
