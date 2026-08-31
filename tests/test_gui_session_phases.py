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
        tab._iniciar_calibracion(auto_flow=False)
        _una_repeticion(tab)
        tab._mvc_enter_prep()
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
        # _mvc_finish_all defers the pause by two seconds so the verdict panel
        # can be read; the test does not wait for the clock.
        tab._mvc_enter_prep()
        assert "PREP start" in tab._worker.markers
        assert "REC start" not in tab._worker.markers   # not yet
        _correr_la_cuenta_atras(tab)
        assert "REC start" in tab._worker.markers

    def test_the_pause_comes_after_every_calibration_span(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        tab._mvc_enter_prep()
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

        The hand-over is deferred a couple of seconds so the verdict panel can
        be read, so what is checked is the decision — ``_prep_pending`` — and
        not whether a timer has fired yet."""
        tab._iniciar_calibracion(auto_flow=False)
        _una_repeticion(tab)
        assert not tab._prep_pending
        assert "PREP start" not in tab._worker.markers
        assert "REC start" not in tab._worker.markers

    def test_the_flow_does_hand_over(self, tab) -> None:
        """The other half of the same decision: without this, the test above
        would pass on an application that never starts the second phase."""
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        assert tab._prep_pending
        tab._mvc_enter_prep()
        assert not tab._prep_pending

    def test_the_countdown_lasts_what_the_profile_says(self, tab) -> None:
        assert EMG_PROFILE.prep_countdown_s == 5.0

    def test_stopping_mid_pause_writes_no_start(self, tab) -> None:
        tab._iniciar_calibracion(auto_flow=True)
        _una_repeticion(tab)
        tab._mvc_enter_prep()
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
        assert not tab._prep_pending
        assert not tab._prep_timer.isActive()
