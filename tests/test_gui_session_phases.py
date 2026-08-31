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


@pytest.fixture
def tab(qapp):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "fases"))
    widget._n_channels = 1
    widget._worker = _FakeWorker()
    yield widget
    widget.close()


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
        for mode, espera in (
            (MODE_PAIR, True), (MODE_SINGLE, False),
            (MODE_KINEMATICS, False), (MODE_FREE, False),
        ):
            tab._mode = mode
            tab._mvc_ref = [None] * 8
            assert tab._flow_needs_calibration() is espera, mode

    def test_an_already_calibrated_session_is_not_asked_to_do_it_again(
        self, tab
    ) -> None:
        """Three more maximal efforts is the fastest way to make the next
        contraction weaker."""
        tab._mode = MODE_PAIR
        tab._mvc_ref = [None] * 8
        assert tab._flow_needs_calibration()
        tab._mvc_ref[0] = 0.12
        assert not tab._flow_needs_calibration()

    def test_a_reference_on_a_channel_this_practical_does_not_use_does_not_count(
        self, tab
    ) -> None:
        tab._mode = MODE_PAIR
        tab._n_channels = 2
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


class TestAMovementIsNotAMaximalContraction:
    """The check the rest-ratio one cannot make."""

    @staticmethod
    def _calibrar_con(tab, envolvente) -> None:
        """Through the real path, not straight to the check.

        Calling _mvc_check_was_held() directly would keep passing on an
        application that had stopped calling it — which is the failure that
        matters, since the check is silent when it is happy.
        """
        tab._iniciar_calibracion(auto_flow=False)
        tab._mvc_capture[0] = [np.asarray(envolvente, dtype=float)]
        tab._mvc_compute_muscle(0)

    def test_a_movement_is_called_out(self, tab) -> None:
        import numpy as np

        e = np.full(4000, 0.004)
        e[1750:2250] = 0.12                    # one brief burst
        self._calibrar_con(tab, e)
        assert tab._mvc_no_sostenidas

    def test_a_held_effort_passes_in_silence(self, tab) -> None:
        import numpy as np

        e = np.full(4000, 0.12)
        e[:400] = np.linspace(0.0, 0.12, 400)
        e[-400:] = np.linspace(0.12, 0.0, 400)
        self._calibrar_con(tab, e)
        assert not tab._mvc_no_sostenidas

    def test_it_ends_on_the_panel_not_only_in_the_log(self, tab) -> None:
        import numpy as np

        e = np.full(4000, 0.004)
        e[1750:2250] = 0.12
        self._calibrar_con(tab, e)
        tab._mvc_ref[0] = 0.12
        tab._mvc_finish_all()
        titulo = tab._mvc_overlay._title.lower()
        assert "not held" in titulo or "no se mantuvo" in titulo

    def test_a_reference_below_rest_still_wins_the_panel(self, tab) -> None:
        """Both faults at once. A reference under the muscle's own resting
        level corrupts every percentage by a larger factor, so it is the one
        the operator has to read."""
        import numpy as np

        e = np.full(4000, 0.004)
        e[1750:2250] = 0.0286
        tab._mvc_rest_buf = list(_envelope_ruidosa(0.031, 3000))
        self._calibrar_con(tab, e)        # both checks run in here
        assert tab._mvc_no_maximas and tab._mvc_no_sostenidas
        tab._mvc_finish_all()
        titulo = tab._mvc_overlay._title.lower()
        assert "weak" in titulo or "floja" in titulo


def _envelope_ruidosa(mean: float, n: int, seed: int = 0):
    import numpy as np

    rng = np.random.default_rng(seed)
    return np.abs(rng.normal(mean, mean * 0.25, n)) + mean * 0.5
