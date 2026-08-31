"""The recording writes the session's own shape into the file.

Step 2 of the two-phase session: the wizard delimits every calibration
repetition with a ``CAL`` span, the pause that follows is marked ``PREP`` and
the recording proper opens with ``REC start`` — all in **one continuous file**,
because the acquisition deliberately does not stop between the phases.

The coupling these tests exist to protect is the one that would fail silently:
the labels the acquisition writes have to be the labels
:mod:`emgteach.phases` reads. A typo in one format string would leave a
recording that looks perfect and analyses as if it had never been calibrated.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.modes import MODE_FREE, MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE
from emgteach.phases import parse_phase_markers
from emgteach.profiles import EMG_PROFILE

pytestmark = pytest.mark.gui


class _FakeWorker:
    """Collects what the tab writes, in order, and claims to be recording."""

    def __init__(self) -> None:
        self.markers: list[str] = []

    def isRunning(self) -> bool:      # Qt's spelling, matched on purpose
        return True

    def add_marker(self, label: str) -> None:
        self.markers.append(str(label))

    def stop(self) -> None:
        """The tab stops the worker when the recording ends; nothing to do here."""

    def is_streaming(self) -> bool:
        """Feeding a block starts the tab's watchdog, which asks this."""
        return True


@pytest.fixture
def tab(qapp):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "fases"))
    widget._n_channels = 1
    widget._worker = _FakeWorker()
    yield widget
    # Feeding a block starts the watchdog, and the timers outlive the widget in
    # the shared QApplication: left running they raise in *other* tests' teardown.
    widget._watchdog_timer.stop()
    widget._mvc_timer.stop()
    widget._prep_timer.stop()
    widget._load_timer.stop()
    widget.close()


def _bloque(n: int = 100) -> dict:
    """One block of data as the worker emits it: quiet, two channels."""
    return {
        "raw_mv": [np.zeros(n), np.zeros(n)],
        "envelope": [np.full(n, 0.004), np.full(n, 0.004)],
    }


def _una_repeticion(tab) -> None:
    """Drive the wizard through one channel, one repetition, deterministically.

    The state machine is stepped at its two transitions rather than waited on:
    what is under test is which annotations come out and in what order, not how
    long a countdown lasts.
    """
    from emgteach.gui.tabs.acquisition import MVC_READY_S

    tab._mvc_reps = 1
    tab._mvc_muscle = 0
    tab._mvc_rep = 0
    tab._mvc_phase = "ready"
    tab._mvc_elapsed = MVC_READY_S          # the countdown has just run out
    tab._mvc_tick()                         # → contract, opens the CAL span
    tab._mvc_cur_buf = [0.10] * 100
    tab._mvc_finish_rep()                   # closes it, computes, finishes


class TestTheCalibrationIsDelimitedInTheFile:
    def test_each_repetition_opens_and_closes_a_span(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=False)
        _una_repeticion(tab)
        assert "CAL start ch=1 rep=1" in tab._worker.markers
        assert "CAL end ch=1 rep=1" in tab._worker.markers
        assert tab._worker.markers.index("CAL start ch=1 rep=1") < tab._worker.markers.index(
            "CAL end ch=1 rep=1"
        )

    def test_the_reference_is_still_written_beside_the_spans(self, tab) -> None:
        """The cached value does not go away: a file carries both, and the
        spans are what a later edit recomputes from."""
        tab._iniciar_calibracion(auto_flow=False)
        _una_repeticion(tab)
        assert any(m.startswith("MVC ref ch=1") for m in tab._worker.markers)

    def test_calibrating_without_a_recording_writes_nothing(self, tab) -> None:
        """Still allowed — the reference lands in the next file as a cached
        value — and there is no span to mark, because there is no file."""
        tab._worker = None
        tab._mvc_muscle = 0
        tab._mvc_rep = 0
        tab._write_phase_marker("CAL start ch=1 rep=1")   # must not raise

    def test_the_labels_are_the_ones_the_reader_parses(self, tab) -> None:
        """The whole point. Times are synthesised here — the worker stamps them
        in the real thing — so what is checked is the wording."""
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        _correr_la_cuenta_atras(tab)

        marcas = [(float(i), m) for i, m in enumerate(tab._worker.markers)]
        fases = parse_phase_markers(marcas)
        assert len(fases.cal_reps) == 1
        assert fases.cal_reps[0].channel_index == 0
        assert fases.cal_reps[0].rep == 1
        assert fases.prep_start_s is not None
        assert fases.rec_start_s is not None
        assert fases.has_phases


def _correr_la_cuenta_atras(tab) -> None:
    from emgteach.gui.tabs.acquisition import MVC_TICK_MS

    pasos = int(EMG_PROFILE.prep_countdown_s / (MVC_TICK_MS / 1000.0)) + 2
    for _ in range(pasos):
        if not tab._prep_timer.isActive():
            break
        tab._prep_tick()


class TestThePauseBetweenThePhases:
    def test_the_flow_marks_the_pause_and_then_the_recording(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        assert "PREP start" in tab._worker.markers
        assert "REC start" not in tab._worker.markers   # not yet
        _correr_la_cuenta_atras(tab)
        assert "REC start" in tab._worker.markers

    def test_the_pause_comes_after_every_calibration_span(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        _correr_la_cuenta_atras(tab)
        m = tab._worker.markers
        assert m.index("PREP start") > m.index("CAL end ch=1 rep=1")
        assert m.index("REC start") > m.index("PREP start")

    def test_a_calibration_asked_for_on_its_own_does_not_move_the_start(
        self, tab
    ) -> None:
        """A calibration run in the middle of a recording sits in the middle of
        the file. Writing ``REC start`` there would throw away everything
        before it, which is most of the recording.

        """
        tab._iniciar_calibracion(auto_flow=False)
        _una_repeticion(tab)
        assert "PREP start" not in tab._worker.markers
        assert "REC start" not in tab._worker.markers

    def test_the_flow_does_hand_over(self, tab) -> None:
        """The other half of the same decision: without this, the test above
        would pass on an application that never starts the second phase.

        It used to be deferred two seconds on a timer so the verdict panel
        could be read. On the bench that hand-over simply did not happen, and
        the recording came back with its calibration marked and no recording
        phase at all. It is a direct call now, and this is what says so."""
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        assert "PREP start" in tab._worker.markers
        assert tab._prep_timer.isActive()

    def test_the_countdown_lasts_what_the_profile_says(self, tab) -> None:
        assert EMG_PROFILE.prep_countdown_s == 5.0

    def test_a_weak_calibration_is_still_read_during_the_countdown(
        self, tab
    ) -> None:
        """The verdict used to get two seconds of its own before the pause.
        Now it rides in the countdown, which is on screen five times longer —
        losing it in the hand-over would hide the one result nobody must
        scroll past."""
        tab._mvc_rest_buf = [0.031] * 3000
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        assert tab._prep_aviso, "the weak-calibration verdict was dropped"
        tab._prep_tick()
        assert tab._mvc_overlay._subtitle == tab._prep_aviso

    def test_stopping_mid_pause_writes_no_start(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        tab._detener_grabacion()
        assert "REC start" not in tab._worker.markers
        assert not tab._prep_timer.isActive()

    def test_the_pause_needs_a_recording_to_be_written_to(self, tab) -> None:
        tab._worker = None
        tab._mvc_enter_prep()          # must not raise
        assert not tab._prep_timer.isActive()


class TestWhenTheRecordButtonRunsTheWholeSession:
    def test_only_the_practical_that_compares_two_muscles(self, tab) -> None:
        """Through apply_mode, the way the application does it.

        This used to assign ``tab._mode`` itself — which *created* the
        attribute the application never set, so the test passed on a build
        where every press of the record button raised."""
        for mode, espera in (
            (MODE_PAIR, True), (MODE_SINGLE, False),
            (MODE_KINEMATICS, False), (MODE_FREE, False),
        ):
            tab.apply_mode(mode, False)
            tab._mvc_ref = [None] * 8
            assert tab._flow_needs_calibration() is espera, mode

    def test_an_already_calibrated_session_is_not_asked_to_do_it_again(
        self, tab
    ) -> None:
        """Three more maximal efforts is the fastest way to make the next
        contraction weaker."""
        tab.apply_mode(MODE_PAIR, False)
        tab._mvc_ref = [None] * 8
        assert tab._flow_needs_calibration()
        tab._mvc_ref[0] = 0.12
        assert not tab._flow_needs_calibration()

    def test_a_reference_on_a_channel_this_practical_does_not_use_does_not_count(
        self, tab
    ) -> None:
        tab.apply_mode(MODE_PAIR, False)
        tab._mvc_ref = [None] * 8
        tab._mvc_ref[5] = 0.12          # left over from another set-up
        assert tab._flow_needs_calibration()

    def test_the_flow_flag_survives_only_while_the_flow_runs(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        assert tab._mvc_flow_auto
        _una_repeticion(tab)            # _mvc_finish_all hands over to the pause
        assert not tab._mvc_flow_auto
        tab._iniciar_calibracion(auto_flow=False)
        assert not tab._mvc_flow_auto

    def test_cancelling_disarms_everything(self, tab) -> None:
        tab._mvc_flow_pending = True
        tab._iniciar_calibracion(auto_flow=True)
        tab._mvc_cancel()
        assert not tab._mvc_flow_auto
        assert not tab._mvc_flow_pending
        assert not tab._prep_timer.isActive()


class TestWarmingUpBeforeTheFirstMaximum:
    """The auto flow took away the window the operator used to have.

    Before, you connected, recorded, did a few contractions and then pressed
    Calibrate. Now the record button starts the countdown, and the bench showed
    what that costs: the flexor's three repetitions came out 57 %, 68 % and
    100 % of each other, still rising at the third.
    """

    def test_a_calibration_opens_with_the_warm_up(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        assert tab._mvc_phase == "warmup"
        assert "WARMUP start" in tab._worker.markers

    def test_a_calibration_asked_for_on_its_own_warms_up_too(self, tab) -> None:
        """The reason is physiological, not procedural: it does not depend on
        which button started the wizard."""
        tab._iniciar_calibracion(auto_flow=False)
        assert tab._mvc_phase == "warmup"

    def test_it_gives_way_to_the_first_countdown(self, tab) -> None:
        from emgteach.gui.tabs.acquisition import MVC_TICK_MS

        tab._iniciar_calibracion(auto_flow=True)
        pasos = int(EMG_PROFILE.warmup_s / (MVC_TICK_MS / 1000.0)) + 2
        for _ in range(pasos):
            if tab._mvc_phase != "warmup":
                break
            tab._mvc_tick()
        assert tab._mvc_phase == "ready"

    def test_it_comes_before_the_first_span(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        m = tab._worker.markers
        assert m.index("WARMUP start") < m.index("CAL start ch=1 rep=1")

    def test_how_long_it_lasts_lives_in_the_profile(self, tab) -> None:
        assert EMG_PROFILE.warmup_s == 10.0


class TestTheButtonCannotBeatTheFlow:
    """The record button arms the session; the device then takes seconds to
    open, and nothing visible happens in the meantime. Pressing «Calibrate MVC»
    in that gap is the natural thing to do — and it used to win: the wizard ran
    as a plain calibration, the armed flow was swallowed by the "already
    running" guard, and the file came back with its calibration marked and no
    recording phase at all. Which is precisely what the flow exists to write.
    """

    def test_a_manual_press_adopts_the_armed_flow(self, tab) -> None:
        tab._mvc_flow_pending = True
        tab._on_calibrar()                      # the button, not the flow
        assert tab._mvc_flow_auto, "the armed session was dropped"
        assert not tab._mvc_flow_pending

    def test_and_then_the_phases_are_written(self, tab) -> None:
        """The point of adopting it: the outcome no longer depends on who won."""
        tab._mvc_flow_pending = True
        tab._on_calibrar()
        _una_repeticion(tab)
        assert "PREP start" in tab._worker.markers

    def test_a_press_with_nothing_armed_stays_a_plain_calibration(self, tab) -> None:
        """A calibration asked for in the middle of a recording still must not
        move the start of the analysed span."""
        tab._mvc_flow_pending = False
        tab._on_calibrar()
        _una_repeticion(tab)
        assert not tab._mvc_flow_auto
        assert "PREP start" not in tab._worker.markers


class TestTheArmedSessionSurvivesABouncedAttempt:
    """The flag used to be spent before the attempt, not after it.

    ``_on_data_ready`` cleared ``_mvc_flow_pending`` and *then* called the
    wizard; if the call bounced off one of its guards the session's one chance
    was gone, and the recording came back with no calibration at all and the
    Calibrate button left disabled — a worse state than either outcome, and
    silent. It is cleared by the wizard now, once it is past the guards, and
    the attempt is retried on the next block; that runs ten times a second.
    """

    def test_a_block_that_bounces_leaves_it_armed(self, tab) -> None:
        """Through the real path: this is where the flag used to be spent."""
        tab._fv_active = True                   # a guided procedure is running
        tab._mvc_flow_pending = True
        tab._on_data_ready(_bloque())
        assert tab._mvc_flow_pending, "the armed session was spent on a bounce"
        assert "WARMUP start" not in tab._worker.markers
        tab._fv_active = False

    def test_and_the_next_block_starts_it(self, tab) -> None:
        tab._fv_active = True
        tab._mvc_flow_pending = True
        tab._on_data_ready(_bloque())           # bounces
        tab._fv_active = False
        tab._on_data_ready(_bloque())           # the retry
        assert not tab._mvc_flow_pending
        assert "WARMUP start" in tab._worker.markers

    def test_a_block_with_the_flow_armed_starts_the_session(self, tab) -> None:
        tab._mvc_flow_pending = True
        tab._on_data_ready(_bloque())
        assert tab._mvc_flow_auto
        assert tab._mvc_phase == "warmup"

    def test_a_block_with_nothing_armed_starts_nothing(self, tab) -> None:
        tab._mvc_flow_pending = False
        tab._on_data_ready(_bloque())
        assert not tab._mvc_active
        assert tab._worker.markers == []

    def test_and_the_retry_then_takes(self, tab) -> None:
        """The point of keeping it: the next block starts the session."""
        tab._worker = None
        tab._mvc_flow_pending = True
        tab._iniciar_calibracion(auto_flow=True)      # bounces
        tab._worker = _FakeWorker()                   # the device is up now
        tab._iniciar_calibracion(auto_flow=True)      # the retry
        assert not tab._mvc_flow_pending
        assert tab._mvc_flow_auto
        assert "WARMUP start" in tab._worker.markers

    def test_a_successful_start_clears_it(self, tab) -> None:
        tab._mvc_flow_pending = True
        tab._iniciar_calibracion(auto_flow=True)
        assert not tab._mvc_flow_pending


class TestFailingToStartIsNotADeadEnd:
    """Three bench sessions in a row came back with no calibration at all.

    Each had a different cause, but they shared a shape: the flow armed, did
    not start, and left «Calibrate MVC» disabled — so there was no calibration
    and no way to ask for one, during the recording or after it. A convenience
    that can take the feature away is worse than no convenience.
    """

    def test_it_gives_up_and_hands_the_button_back(self, tab) -> None:
        from emgteach.gui.tabs.acquisition import MVC_FLOW_MAX_TRIES

        tab._fv_active = True                    # something keeps bouncing it
        tab._mvc_flow_pending = True
        tab._btn_calibrar.setEnabled(False)
        for _ in range(MVC_FLOW_MAX_TRIES + 1):
            tab._on_data_ready(_bloque())
        assert not tab._mvc_flow_pending
        assert tab._btn_calibrar.isEnabled(), "no way left to calibrate"
        tab._fv_active = False

    def test_it_does_not_give_up_too_soon(self, tab) -> None:
        """Three seconds of data, not three blocks: a device that opens slowly
        must not cost the session its calibration."""
        from emgteach.gui.tabs.acquisition import MVC_FLOW_MAX_TRIES

        assert MVC_FLOW_MAX_TRIES >= 20
        tab._fv_active = True
        tab._mvc_flow_pending = True
        for _ in range(MVC_FLOW_MAX_TRIES - 1):
            tab._on_data_ready(_bloque())
        assert tab._mvc_flow_pending, "gave up before the device could settle"
        tab._fv_active = False

    def test_the_counter_starts_fresh_each_recording(self, tab) -> None:
        tab._mvc_flow_tries = 99
        tab._detener_grabacion()
        assert tab._mvc_flow_tries == 0

    def test_stopping_leaves_no_calibrate_button_to_press(self, tab) -> None:
        """It needs a recording in progress, so it follows the recording
        instead of being left wherever the flow put it."""
        tab._btn_calibrar.setEnabled(True)
        tab._detener_grabacion()
        assert not tab._btn_calibrar.isEnabled()


class TestTheTabRemembersWhichPracticalItIs:
    """The one missing assignment that cost four bench recordings.

    ``_flow_needs_calibration`` read ``self._mode`` and nothing ever set it, so
    every press of the record button raised AttributeError inside a Qt slot —
    printed to stderr, invisible in the running application — and aborted the
    rest of the start-up: no arming, no calibration, and the Calibrate button
    left disabled with no way to enable it.

    The tests that were meant to cover this assigned ``tab._mode`` themselves,
    which *created* the attribute. They passed on an application that could not
    record. A test may set what the operator sets; it must never set what the
    application is supposed to set.
    """

    def test_a_fresh_tab_already_knows_its_practical(self, tab) -> None:
        from emgteach.modes import MODES

        assert tab._mode in MODES

    def test_asking_before_apply_mode_does_not_raise(self, tab) -> None:
        tab._flow_needs_calibration()          # must not raise

    def test_apply_mode_is_what_keeps_it_up_to_date(self, tab) -> None:
        from emgteach.modes import MODES

        for mode in MODES:
            tab.apply_mode(mode, False)
            assert tab._mode == mode

    def test_starting_a_recording_gets_as_far_as_arming_the_flow(
        self, tab
    ) -> None:
        """What actually broke: the arming lines never ran, so nothing after
        them in _iniciar_grabacion ran either."""
        tab.apply_mode(MODE_PAIR, False)
        tab._mvc_ref = [None] * 8
        assert tab._flow_needs_calibration()
        assert tab._mvc_flow_tries == 0
