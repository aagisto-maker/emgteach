"""The guided sessions' marks and scripts, without Qt.

A guided session writes ASCII marks in the idiom of the phase marks — the
family first, in capitals, then what opens or closes — and the analysis reads
the file back from them alone. What is tested here is that round trip: the
marks are written as documented, read back into closed stretches, never
confused with a student's marks or the calibration's, and dropped where the
phase marks are dropped.
"""

from __future__ import annotations

import itertools

import pytest

from emgteach.manual_marks import MANUAL_MARK_LABELS
from emgteach.phases import cal_start_marker, is_phase_marker, strip_phase_markers
from emgteach.sessions import (
    EFFORT,
    FAMILIES,
    READY,
    REST,
    SessionPhase,
    SessionScript,
    end_marker,
    header_marker,
    is_session_marker,
    parse_session_markers,
    span_end_marker,
    span_start_marker,
)

# ── Writing ────────────────────────────────────────────────────────────────


def test_the_marks_are_written_as_documented() -> None:
    assert header_marker("GRAD", steps=5) == "GRAD start steps=5 v=1"
    assert header_marker("HOLD", 2, mode="sustained", secs=30) == (
        "HOLD start mode=sustained secs=30 v=2")
    assert span_start_marker("GRAD", "step", k=1, pct=20) == "GRAD step start k=1 pct=20"
    assert span_end_marker("GRAD", "step", k=1) == "GRAD step end k=1"
    assert end_marker("GRAD") == "GRAD end"
    assert end_marker("GRAD", stopped=True) == "GRAD end stopped"


def test_a_decimal_parameter_keeps_its_point() -> None:
    assert span_start_marker("HOLD", "rep", n=1, on=1.5) == "HOLD rep start n=1 on=1.5"


def test_every_mark_is_ascii() -> None:
    for marca in (header_marker("GRAD", steps=5), span_start_marker("GRAD", "step", k=1),
                  end_marker("HOLD", stopped=True)):
        assert marca.isascii(), marca


# ── Reading ────────────────────────────────────────────────────────────────


def _gradacion(fin: bool = True, parada: bool = False) -> list[tuple[float, str]]:
    marcas = [(10.0, "GRAD start steps=2 v=1"),
              (15.0, "GRAD step start k=1 pct=20"), (19.0, "GRAD step end k=1"),
              (25.0, "GRAD step start k=2 pct=40"), (29.0, "GRAD step end k=2")]
    if fin:
        marcas.append((34.0, end_marker("GRAD", stopped=parada)))
    return marcas


def test_a_whole_session_reads_back() -> None:
    s = parse_session_markers(_gradacion())
    assert s is not None
    assert s.family == "GRAD" and s.version == 1 and s.completed
    assert s.start_s == 10.0 and s.end_s == 34.0
    assert s.params["steps"] == "2"
    assert [(t.name, t.start_s, t.end_s) for t in s.spans] == [
        ("step", 15.0, 19.0), ("step", 25.0, 29.0)]
    assert [t.number("pct") for t in s.spans] == [20.0, 40.0]
    assert s.spans[0].duration_s == 4.0


def test_a_file_without_a_session_has_none() -> None:
    assert parse_session_markers([(1.0, "REC start"), (3.0, "Onset (auto)")]) is None
    assert parse_session_markers([]) is None


def test_a_stopped_session_is_not_complete() -> None:
    s = parse_session_markers(_gradacion(parada=True))
    assert s is not None and not s.completed and s.end_s == 34.0
    assert len(s.spans) == 2


def test_a_session_cut_by_the_end_of_the_recording_is_not_complete() -> None:
    s = parse_session_markers(_gradacion(fin=False))
    assert s is not None and not s.completed and s.end_s is None


def test_an_effort_cut_short_is_dropped() -> None:
    """Half a step is not a step, as half a maximal effort is not one."""
    marcas = [*_gradacion(fin=False), (35.0, "GRAD step start k=3 pct=60"), (37.0, "GRAD end stopped")]
    s = parse_session_markers(marcas)
    assert s is not None and [t.params["k"] for t in s.spans] == ["1", "2"]


def test_an_end_with_nothing_open_is_ignored() -> None:
    s = parse_session_markers([(0.0, "GRAD start v=1"), (1.0, "GRAD step end k=1"),
                               (2.0, "GRAD end")])
    assert s is not None and s.spans == ()


def test_an_end_is_matched_to_its_own_start() -> None:
    marcas = [(0.0, "HOLD start v=1"), (1.0, "HOLD rep start n=1"),
              (2.0, "HOLD rep end n=2"), (3.0, "HOLD rep end n=1"), (4.0, "HOLD end")]
    s = parse_session_markers(marcas)
    assert s is not None and [(t.start_s, t.end_s) for t in s.spans] == [(1.0, 3.0)]


def test_the_marks_are_read_in_time_order() -> None:
    s = parse_session_markers(list(reversed(_gradacion())))
    assert s is not None and len(s.spans) == 2 and s.completed


def test_the_last_session_of_a_file_is_the_one_read() -> None:
    marcas = [(0.0, "HOLD start v=1"), (1.0, "HOLD end stopped"), *_gradacion()]
    s = parse_session_markers(marcas)
    assert s is not None and s.family == "GRAD"


def test_another_familys_stretch_does_not_join_the_session() -> None:
    marcas = [(0.0, "GRAD start v=1"), (1.0, "HOLD rep start n=1"),
              (2.0, "HOLD rep end n=1"), (3.0, "GRAD end")]
    s = parse_session_markers(marcas)
    assert s is not None and s.spans == ()


def test_a_later_version_reads_with_its_number() -> None:
    s = parse_session_markers([(0.0, "GRAD start steps=5 v=2"), (1.0, "GRAD end")])
    assert s is not None and s.version == 2


# ── Never a student's mark, never the calibration's ─────────────────────────


@pytest.mark.parametrize("marca", [m for _t, m in _gradacion()] + ["GRAD end stopped"])
def test_every_session_mark_is_recognised(marca: str) -> None:
    assert is_session_marker(marca)


@pytest.mark.parametrize("marca", [
    *MANUAL_MARK_LABELS, "Inicio contracción", "Fatiga", "Otro",
    cal_start_marker(0, 1), "REC start", "PREP start", "Onset (auto)",
    "MVC ref ch=1 value=0.4 mV", "FV load=2 kg", "Gradación", "grad start",
])
def test_nothing_else_is_a_session_mark(marca: str) -> None:
    assert not is_session_marker(marca)


def test_the_session_marks_are_dropped_with_the_phase_marks() -> None:
    """They describe the session: a line across every panel and a window in
    the co-activation table are what the phase marks are stripped to avoid."""
    marcas = [*_gradacion(), (12.0, "Fatigue"), (13.0, "REC start")]
    assert all(is_phase_marker(m) for _t, m in _gradacion())
    assert strip_phase_markers(marcas) == [(12.0, "Fatigue")]


def test_the_families_are_the_sessions() -> None:
    """One family of marks per kind of session: graded contractions, fatigue,
    quick contractions."""
    assert FAMILIES == ("GRAD", "HOLD", "FAST")


# ── The script ────────────────────────────────────────────────────────────


def _script() -> SessionScript:
    return SessionScript(
        key="prueba", family="GRAD", title="Test", slug="prueba",
        header=header_marker("GRAD", steps=1),
        phases=(
            SessionPhase("ready", READY, 3.0, "Get ready"),
            SessionPhase("step", EFFORT, 4.0, "Squeeze", level=0.5,
                         opens=span_start_marker("GRAD", "step", k=1),
                         closes=span_end_marker("GRAD", "step", k=1)),
            SessionPhase("rest", REST, 5.0, "Rest"),
        ),
    )


def test_the_phases_tile_the_session_without_gaps() -> None:
    fases = _script().timed()
    assert [f.start for f in fases] == [0.0, 3.0, 7.0]
    for a, b in itertools.pairwise(fases):
        assert a.end == b.start
    assert _script().total_seconds == 12.0 == fases[-1].end


def test_a_script_can_be_shortened_for_a_test() -> None:
    corta = _script().with_seconds(0.5)
    assert corta.total_seconds == 1.5
    assert corta.phases[1].opens == _script().phases[1].opens


def test_a_phase_must_have_a_known_kind_and_a_duration() -> None:
    with pytest.raises(ValueError):
        SessionPhase("x", "squeeze", 1.0, "X")
    with pytest.raises(ValueError):
        SessionPhase("x", REST, 0.0, "X")


def test_a_script_needs_a_known_family_and_phases() -> None:
    with pytest.raises(ValueError):
        SessionScript("x", "RHYTHM", "X", "x", "RHYTHM start v=1",
                      (SessionPhase("r", REST, 1.0, "R"),))
    with pytest.raises(ValueError):
        SessionScript("x", "GRAD", "X", "x", "GRAD start v=1", ())
