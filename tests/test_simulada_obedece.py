"""The simulated board obeys the calibration, so a rehearsal teaches the right thing.

Its subject repeats a fixed twelve-second cycle that starts when the board is
connected and never reaches full activation: 0.50 for the flexion, 0.50 for the
extension, 0.40 for the grip. The calibration span fell wherever that cycle
happened to be — often at rest, or on an edge — so the reference came out
small and the task then read above 100 % of the maximal voluntary contraction.
A session rehearsed without hardware showed the opposite of what the practical
is about.

The application already knows when it is asking for a maximum: the wizard opens
a ``CAL`` span and closes it. It now says so to the device as well
(:meth:`AcquisitionDevice.instruct`). A board ignores it. The simulated one
gives the maximum being asked, and the task reads the share of it the cycle
says: about a half for the alternating gestures, about 0.40 for the grip, with
the grip co-activating and the others not.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.coactivation import coactivation_index
from emgteach.devices.base import AcquisitionDevice
from emgteach.devices.bitalino import BitalinoDevice
from emgteach.devices.bitalino_sim import (
    _MAX_MV,
    _REST_MV,
    CYCLE_S,
    SimulatedBitalinoPort,
    _SyntheticSubject,
)
from emgteach.dsp import process_offline

FS = 1000.0
#: mV of one ADC count, to undo :func:`mv_to_adc` without copying its arithmetic.
_VCC, _GAIN, _ADC_MAX = 3.3, 1009.0, 1023


def _a_mv(cuentas: list[int]) -> float:
    """One ADC count back to millivolts, as the application converts it."""
    return (cuentas[0] / _ADC_MAX - 0.5) * (_VCC * 1000.0) / _GAIN


def _tramo(sujeto: _SyntheticSubject, t0: float, dur: float) -> np.ndarray:
    """``dur`` seconds of both muscles from *t0*, in millivolts."""
    n = int(dur * FS)
    salida = np.empty((n, 2), dtype=float)
    for i in range(n):
        cuentas = sujeto.sample(t0 + i / FS, FS, [0, 1])
        salida[i, 0] = _a_mv([cuentas[0]])
        salida[i, 1] = _a_mv([cuentas[1]])
    return salida


def _envolvente(mv: np.ndarray) -> np.ndarray:
    return process_offline(mv, FS)["emg_envelope"]


class TestTheSubjectDoesWhatItIsAsked:
    def test_while_asked_the_muscle_is_at_its_maximum_and_the_other_at_rest(self) -> None:
        s = _SyntheticSubject(acc_channel=None, seed=1)
        for muscle in (0, 1):
            s.instruct(muscle, 1.0)
            for t in (0.0, 3.0, 9.0, 11.9):      # anywhere in the cycle
                a = s.activation(t)
                assert a[muscle] == pytest.approx(1.0)
                assert a[1 - muscle] == pytest.approx(0.0)

    def test_the_cycle_is_where_it_was_when_the_asking_stops(self) -> None:
        """Nothing in the instruction touches the clock."""
        s = _SyntheticSubject(acc_channel=None, seed=1)
        antes = [s.activation(t) for t in (1.5, 5.5, 9.5)]
        s.instruct(0, 1.0)
        s.activation(2.0)
        s.instruct(0, None)
        assert [s.activation(t) for t in (1.5, 5.5, 9.5)] == antes

    def test_the_amplitude_follows_the_level_asked(self) -> None:
        s = _SyntheticSubject(acc_channel=None, seed=7)
        s.instruct(0, 1.0)
        mv = _tramo(s, 0.0, 1.0)
        assert np.std(mv[:, 0]) == pytest.approx(_MAX_MV[0], rel=0.15)
        assert np.std(mv[:, 1]) == pytest.approx(_REST_MV, rel=0.25)


class TestTheTaskThenReadsUnderTheMaximum:
    """What the fault was about: the % MVC a rehearsal shows."""

    @staticmethod
    def _referencia(muscle: int) -> float:
        """The peak of the envelope over a 1.5 s span asked of *muscle*."""
        s = _SyntheticSubject(acc_channel=None, seed=11)
        s.instruct(muscle, 1.0)
        return float(np.max(_envolvente(_tramo(s, 0.0, 1.5)[:, muscle])))

    @pytest.mark.parametrize("muscle", [0, 1])
    def test_no_sample_of_the_task_passes_100_pct_of_the_reference(self, muscle: int) -> None:
        """Measured: the reference is 0.67 and 0.69 of each muscle's maximum
        — the envelope of Gaussian noise of standard deviation s averages
        s·sqrt(2/pi) once rectified and less once low-passed, so it is not
        the standard deviation itself — and the task then reads 53 % and
        54 % of it, which is the half the cycle asks for."""
        ref = self._referencia(muscle)
        assert 0.6 < ref / _MAX_MV[muscle] < 0.8, ref
        s = _SyntheticSubject(acc_channel=None, seed=11)
        tarea = _tramo(s, 0.0, CYCLE_S)          # the whole cycle: the three gestures
        pct = 100.0 * _envolvente(tarea[:, muscle]) / ref
        assert pct.max() < 100.0, pct.max()
        # And about the half of the cycle, not a floor: the gesture is seen.
        assert 40.0 < pct.max() < 70.0, pct.max()

    def test_without_the_instruction_the_task_passed_the_reference(self) -> None:
        """The fault, kept as a test so it cannot come back unnoticed.

        A span taken while the cycle is at rest — half of it is — measures a
        reference of noise, and every gesture then reads far above 100 %.
        """
        s = _SyntheticSubject(acc_channel=None, seed=11)
        ref_quieta = float(np.max(_envolvente(_tramo(s, 2.8, 1.5)[:, 0])))
        tarea = _tramo(s, 0.0, CYCLE_S)
        assert 100.0 * _envolvente(tarea[:, 0]).max() / ref_quieta > 200.0


class TestTheGripCoActivates:
    def test_the_grip_reads_higher_than_the_alternating_gestures(self) -> None:
        """Qualitatively the finding of the practical, which is the point of a
        rehearsal: both muscles at once in the grip, one at a time in the rest."""
        s = _SyntheticSubject(acc_channel=None, seed=3)
        ventanas = {"flexión": (0.6, 1.8), "extensión": (4.6, 1.8), "presa": (8.6, 1.8)}
        indices = {}
        for nombre, (t0, dur) in ventanas.items():
            mv = _tramo(s, t0, dur)
            e1, e2 = _envolvente(mv[:, 0]), _envolvente(mv[:, 1])
            res = coactivation_index(e1, e2, FS, floor_pct=0.0,
                                     rest_1=0.0, rest_2=0.0,
                                     name_1="1", name_2="2")
            indices[nombre] = res.index
        # Measured: 19.5 % the flexion, 33.1 % the extension, 80.7 % the
        # grip — the shape of the bank's own figures for the practical.
        assert indices["presa"] > 60.0, indices
        assert indices["presa"] > 2.0 * max(indices["flexión"], indices["extensión"]), indices


class TestItReachesTheSubjectFromTheApplication:
    def test_the_port_passes_it_on(self) -> None:
        port = SimulatedBitalinoPort(seed=2)
        port.instruct(1, 1.0)
        assert port._subject.activation(0.0) == (0.0, 1.0)
        port.instruct(1, None)
        assert port._subject.activation(0.0) != (0.0, 1.0)

    def test_the_simulated_device_forwards_it_and_a_real_one_does_not(self) -> None:
        simulada = BitalinoDevice("simulada", fs=1000, channels=[0, 1])
        simulada.open()
        try:
            simulada.instruct(0, 1.0)
            assert simulada._serial._subject.activation(0.0) == (1.0, 0.0)
        finally:
            simulada.close()
        # A board: the address is a COM port, so nothing is forwarded and
        # nothing raises — there is not even a connection here.
        BitalinoDevice("COM9", fs=1000, channels=[0]).instruct(0, 1.0)

    def test_a_device_that_cannot_act_on_it_ignores_it(self) -> None:
        """The default of the interface, which every other backend inherits."""

        class _Mudo(AcquisitionDevice):
            fs = 1000.0
            name = "mudo"

            def open(self) -> None: ...
            def read(self, n_samples: int):
                return np.zeros((n_samples, 1))
            def close(self) -> None: ...
            def force_close(self) -> None: ...

        assert _Mudo().instruct(0, 1.0) is None

class _WorkerDeMentira:
    """The worker as the tab uses it here: the two calls it makes to it."""

    def __init__(self) -> None:
        self.markers: list[str] = []
        self.instructions: list[tuple[int, float | None]] = []

    def isRunning(self) -> bool:
        return True

    def is_streaming(self) -> bool:
        return True

    def add_marker(self, label: str) -> None:
        self.markers.append(str(label))

    def instruct(self, channel_index: int, level: float | None) -> None:
        self.instructions.append((channel_index, level))

    def stop(self) -> None:
        pass


@pytest.fixture
def adquisicion(qapp):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    tab = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "simulada-obedece"))
    tab._n_channels = 1
    tab._worker = _WorkerDeMentira()
    yield tab
    tab._watchdog_timer.stop()
    tab._mvc_timer.stop()
    tab._prep_timer.stop()
    tab._load_timer.stop()
    tab.close()


class TestTheWizardSaysItToTheDevice:
    """Where the instruction comes from: the span the wizard already marks."""

    def test_the_effort_opens_with_the_instruction_and_closes_without_it(
        self, adquisicion
    ) -> None:
        from emgteach.gui.tabs.acquisition import MVC_READY_S
        from emgteach.profiles import EMG_PROFILE

        tab = adquisicion
        tab._iniciar_calibracion(auto_flow=False)
        try:
            tab._mvc_muscle = 0
            tab._mvc_rep = 0
            tab._mvc_phase = "ready"
            tab._mvc_elapsed = MVC_READY_S
            tab._mvc_tick()                       # the countdown reaches 0
            assert tab._mvc_phase == "contract"
            assert "CAL start ch=1 rep=1" in tab._worker.markers
            assert tab._worker.instructions == [(0, 1.0)]

            tab._mvc_cur_buf = [0.0] * 10
            tab._mvc_elapsed = EMG_PROFILE.mvc_burst_s
            tab._mvc_tick()                       # the effort is over
            assert "CAL end ch=1 rep=1" in tab._worker.markers
            assert tab._worker.instructions[-1] == (0, None)
        finally:
            if tab._mvc_active:
                tab._mvc_cancel()
