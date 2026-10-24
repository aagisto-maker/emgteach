"""The guided session's clock, against a clock the test moves by hand.

The runner reads a monotonic clock at every tick and moves on to whatever
phase that instant falls in. With the clock in the test's hands the marks,
the phases and the end can be checked to the tick, and a tick that comes late
can be made to come late.
"""

from __future__ import annotations

import pytest

from emgteach.gui.session_runner import SessionRunner
from emgteach.sessions import (
    EFFORT,
    READY,
    REST,
    SessionPhase,
    SessionScript,
    end_marker,
    header_marker,
    span_end_marker,
    span_start_marker,
)


def _script() -> SessionScript:
    def paso(k: int) -> SessionPhase:
        return SessionPhase(
            f"step{k}", EFFORT, 2.0, "Squeeze", level=0.2 * k,
            opens=span_start_marker("GRAD", "step", k=k),
            closes=span_end_marker("GRAD", "step", k=k))

    return SessionScript(
        key="prueba", family="GRAD", title="Test", slug="prueba",
        header=header_marker("GRAD", steps=2),
        phases=(SessionPhase("ready", READY, 1.0, "Get ready"), paso(1),
                SessionPhase("rest", REST, 1.0, "Rest"), paso(2),
                SessionPhase("end", REST, 1.0, "Rest", cue=False)),
    )


class _Reloj:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def run(qapp):
    reloj = _Reloj()
    runner = SessionRunner(_script(), clock=reloj)
    ocurrido: dict[str, list] = {"marcas": [], "fases": [], "ticks": [], "fin": []}
    runner.marker.connect(lambda m: ocurrido["marcas"].append((reloj.t - 100.0, m)))
    runner.phase_started.connect(lambda f, i: ocurrido["fases"].append((f.key, i)))
    runner.tick.connect(lambda f, rest, hecho: ocurrido["ticks"].append((f.key, rest, hecho)))
    runner.finished.connect(lambda ok: ocurrido["fin"].append(ok))

    def a(t: float) -> None:
        reloj.t = 100.0 + t
        runner._on_tick()

    yield runner, ocurrido, a
    runner.cancel()


def test_start_writes_the_header_and_begins_the_first_phase(run) -> None:
    runner, ocurrido, _a = run
    runner.start()
    assert ocurrido["marcas"] == [(0.0, "GRAD start steps=2 v=1")]
    assert ocurrido["fases"] == [("ready", 0)]
    assert ocurrido["ticks"] == [("ready", 1.0, 0.0)]
    assert runner.is_running and runner.current_phase is not None


def test_each_phase_writes_its_marks_at_its_time_and_the_end(run) -> None:
    runner, ocurrido, a = run
    runner.start()
    for t in (0.5, 1.0, 2.0, 3.0, 3.5, 4.0, 6.0, 6.5, 7.0):
        a(t)
    assert ocurrido["marcas"] == [
        (0.0, "GRAD start steps=2 v=1"),
        (1.0, "GRAD step start k=1"), (3.0, "GRAD step end k=1"),
        (4.0, "GRAD step start k=2"), (6.0, "GRAD step end k=2"),
        (7.0, end_marker("GRAD")),
    ]
    assert [k for k, _i in ocurrido["fases"]] == ["ready", "step1", "rest", "step2", "end"]
    assert ocurrido["fin"] == [True]
    assert not runner.is_running and runner.current_phase is None


def test_a_late_tick_crosses_every_phase_in_order(run) -> None:
    """A busy interface thread delays a tick; it must not skip a mark."""
    runner, ocurrido, a = run
    runner.start()
    a(4.5)
    assert [m for _t, m in ocurrido["marcas"]] == [
        "GRAD start steps=2 v=1", "GRAD step start k=1", "GRAD step end k=1",
        "GRAD step start k=2"]
    assert [k for k, _i in ocurrido["fases"]] == ["ready", "step1", "rest", "step2"]
    clave, resto, hecho = ocurrido["ticks"][-1]
    assert clave == "step2" and resto == pytest.approx(1.5) and hecho == pytest.approx(0.25)


def test_the_ticks_count_down(run) -> None:
    runner, ocurrido, a = run
    runner.start()
    a(1.5)
    assert ocurrido["ticks"][-1] == ("step1", pytest.approx(1.5), pytest.approx(0.25))


def test_cancelling_says_stopped_and_leaves_the_effort_open(run) -> None:
    runner, ocurrido, a = run
    runner.start()
    a(2.0)
    runner.cancel()
    assert [m for _t, m in ocurrido["marcas"]][-2:] == [
        "GRAD step start k=1", "GRAD end stopped"]
    assert ocurrido["fin"] == [False]
    a(10.0)                                  # a tick after the end does nothing
    assert ocurrido["fin"] == [False]
    assert [m for _t, m in ocurrido["marcas"]][-1] == "GRAD end stopped"


def test_cancelling_twice_or_before_starting_does_nothing(run) -> None:
    runner, ocurrido, _a = run
    runner.cancel()
    assert ocurrido["marcas"] == [] and ocurrido["fin"] == []
    runner.start()
    runner.cancel()
    runner.cancel()
    assert ocurrido["fin"] == [False]


def test_a_listener_may_stop_the_session_when_a_phase_starts(run) -> None:
    """The tab stops the session from inside a signal (the recording ended):
    nothing more is said after that."""
    runner, ocurrido, a = run
    runner.phase_started.connect(lambda f, _i: f.key == "step1" and runner.cancel())
    runner.start()
    a(1.0)
    assert ocurrido["fin"] == [False]
    assert ocurrido["ticks"][-1][0] == "ready"


def test_the_timer_runs_while_the_session_does(run) -> None:
    runner, _ocurrido, a = run
    runner.start()
    assert runner._timer.isActive()
    a(7.0)
    assert not runner._timer.isActive()
