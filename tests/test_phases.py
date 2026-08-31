"""The session as one file with two phases, and the rule that picks a reference.

Everything here is about one decision: **the ``CAL`` spans are the source and
the ``MVC ref`` annotation is a cached result**. Get the precedence wrong and
discarding a bad repetition in the analysis tab changes nothing, which is worse
than not offering the choice at all.

The fixtures build a session shaped like a real one — three calibration
repetitions per channel of deliberately unequal strength, a preparation pause,
then the work — so "best of three" and "discard the weak one" are testable
against numbers chosen on purpose rather than whatever the noise gave.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.mvc import mvc_ref_marker, parse_mvc_ref_markers
from emgteach.phases import (
    FROM_CACHE,
    FROM_REPS,
    NO_CALIBRATION,
    CalRep,
    SessionPhases,
    cal_end_marker,
    cal_start_marker,
    is_phase_marker,
    mvc_reference,
    parse_phase_markers,
    prep_start_marker,
    rec_start_marker,
    reference_source_text,
    slice_reps,
    strip_phase_markers,
)

FS = 1000.0
DURACION = 30.0

#: (start, end, envelope amplitude) per repetition of channel 0. The second is
#: the strongest and the first the weakest, so "best of three" and "discard the
#: weak one" have different, checkable answers.
REPS_CH0 = [(2.0, 6.0, 0.080), (10.0, 14.0, 0.120), (18.0, 22.0, 0.100)]
REPOSO = 0.005


def _envelope() -> np.ndarray:
    """A flat envelope per repetition, so the reference is exact, not noisy.

    ``mvc_peak_hold`` returns the strongest window mean, which over a constant
    stretch is that constant — the assertions below can therefore name the
    number instead of bracketing it.
    """
    env = np.full(int(DURACION * FS), REPOSO)
    for a, b, amp in REPS_CH0:
        env[int(a * FS) : int(b * FS)] = amp
    return env


def _markers() -> list[tuple[float, str]]:
    """The annotations a two-phase session writes, plus a student's own mark."""
    m: list[tuple[float, str]] = []
    for i, (a, b, _amp) in enumerate(REPS_CH0, start=1):
        m.append((a, cal_start_marker(0, i)))
        m.append((b, cal_end_marker(0, i)))
    m.append((22.5, mvc_ref_marker(0, 0.120)))
    m.append((24.0, prep_start_marker()))
    m.append((26.0, rec_start_marker()))
    m.append((27.0, "Grip"))
    return m


class TestReadingThePhasesBack:
    """Round trip, and the shapes a real session leaves behind."""

    def test_the_repetitions_survive_a_write_and_a_read(self) -> None:
        p = parse_phase_markers(_markers())
        assert len(p.cal_reps) == 3
        assert [r.rep for r in p.reps_for(0)] == [1, 2, 3]
        assert p.reps_for(0)[0].start_s == pytest.approx(2.0)
        assert p.reps_for(0)[0].end_s == pytest.approx(6.0)
        assert p.reps_for(0)[0].duration_s == pytest.approx(4.0)

    def test_the_label_counts_channels_from_one_and_the_object_from_zero(
        self,
    ) -> None:
        """As ``mvc_ref_marker`` does: 1-based on screen, 0-based in the code."""
        assert cal_start_marker(0, 1) == "CAL start ch=1 rep=1"
        assert cal_end_marker(1, 3) == "CAL end ch=2 rep=3"
        assert parse_phase_markers([(0.0, cal_start_marker(1, 1)),
                                    (1.0, cal_end_marker(1, 1))]).channels() == (1,)

    def test_the_two_phase_boundaries_are_read(self) -> None:
        p = parse_phase_markers(_markers())
        assert p.prep_start_s == pytest.approx(24.0)
        assert p.rec_start_s == pytest.approx(26.0)
        assert p.has_phases

    def test_a_file_from_before_this_change_has_no_phases(self) -> None:
        p = parse_phase_markers([(1.0, "Grip"), (2.0, mvc_ref_marker(0, 0.1))])
        assert not p.has_phases
        assert p.cal_reps == ()
        assert p.rec_span(DURACION) is None

    def test_two_channels_are_kept_apart(self) -> None:
        m = [(0.0, cal_start_marker(0, 1)), (4.0, cal_end_marker(0, 1)),
             (8.0, cal_start_marker(1, 1)), (12.0, cal_end_marker(1, 1))]
        p = parse_phase_markers(m)
        assert p.channels() == (0, 1)
        assert len(p.reps_for(0)) == 1
        assert p.reps_for(1)[0].start_s == pytest.approx(8.0)


class TestTheSpansThatDoNotClose:
    """A recording stopped mid-calibration, and other half-written sessions."""

    def test_an_unclosed_repetition_is_dropped(self) -> None:
        """What stopping the recording in the middle of a rep leaves behind.
        A span with no end has no duration, and half a maximal effort is not a
        maximal effort."""
        m = [(2.0, cal_start_marker(0, 1)), (6.0, cal_end_marker(0, 1)),
             (10.0, cal_start_marker(0, 2))]           # stopped here
        p = parse_phase_markers(m)
        assert [r.rep for r in p.reps_for(0)] == [1]

    def test_an_end_with_nothing_open_is_ignored(self) -> None:
        p = parse_phase_markers([(6.0, cal_end_marker(0, 1))])
        assert p.cal_reps == ()

    def test_a_restarted_repetition_takes_the_second_start(self) -> None:
        m = [(2.0, cal_start_marker(0, 1)),
             (3.0, cal_start_marker(0, 1)),            # the wizard restarted it
             (7.0, cal_end_marker(0, 1))]
        p = parse_phase_markers(m)
        assert len(p.cal_reps) == 1
        assert p.cal_reps[0].start_s == pytest.approx(3.0)

    def test_a_zero_length_span_is_not_a_repetition(self) -> None:
        m = [(2.0, cal_start_marker(0, 1)), (2.0, cal_end_marker(0, 1))]
        assert parse_phase_markers(m).cal_reps == ()

    def test_the_last_rec_start_wins(self) -> None:
        """Same reasoning as the MVC references: the one the session finished
        with is the one that describes the file."""
        p = parse_phase_markers([(5.0, rec_start_marker()),
                                 (9.0, rec_start_marker())])
        assert p.rec_start_s == pytest.approx(9.0)


class TestPhasesAreNotEventsInTheRecording:
    """They are facts about the session, and must not reach the panels."""

    def test_the_students_marks_survive_and_the_phase_ones_do_not(self) -> None:
        limpios = strip_phase_markers(_markers())
        etiquetas = [d for _t, d in limpios]
        assert "Grip" in etiquetas
        assert not any(is_phase_marker(d) for d in etiquetas)

    def test_it_does_not_reach_past_its_own_annotations(self) -> None:
        """The MVC reference is stripped by the analysis worker, with its own
        parser. Two strippers that overlap would each look correct alone and
        drop the other's marks together."""
        limpios = strip_phase_markers(_markers())
        assert parse_mvc_ref_markers(limpios)      # still there to be read

    def test_a_recording_with_no_phase_markers_is_returned_whole(self) -> None:
        m = [(1.0, "Flexion"), (2.0, "Grip")]
        assert strip_phase_markers(m) == m


class TestTheAnalysedSpanStartsAtRec:
    """Which is how the preparation pause stays out of everything."""

    def test_calibration_and_preparation_fall_outside(self) -> None:
        span = parse_phase_markers(_markers()).rec_span(DURACION)
        assert span is not None
        inicio, fin = span
        assert inicio == pytest.approx(26.0)
        assert fin == pytest.approx(DURACION)
        # every calibration repetition, and the pause, are before it
        for r in parse_phase_markers(_markers()).cal_reps:
            assert r.end_s < inicio
        assert parse_phase_markers(_markers()).prep_start_s < inicio

    def test_a_rec_start_past_the_end_is_clamped(self) -> None:
        p = parse_phase_markers([(99.0, rec_start_marker())])
        assert p.rec_span(30.0) == (30.0, 30.0)


class TestSlicingTheRepetitions:
    def test_each_repetition_comes_back_at_its_own_amplitude(self) -> None:
        p = parse_phase_markers(_markers())
        trozos = slice_reps(_envelope(), FS, p.reps_for(0))
        assert [round(float(t.mean()), 3) for t in trozos] == [0.080, 0.120, 0.100]

    def test_keep_selects_by_the_number_the_wizard_counted(self) -> None:
        p = parse_phase_markers(_markers())
        trozos = slice_reps(_envelope(), FS, p.reps_for(0), keep={1, 3})
        assert [round(float(t.mean()), 3) for t in trozos] == [0.080, 0.100]

    def test_a_span_outside_the_signal_is_skipped_not_zero_length(self) -> None:
        reps = [CalRep(0, 1, 100.0, 104.0)]
        assert slice_reps(_envelope(), FS, reps) == []


class TestThePrecedenceRule:
    """The rule the whole change rests on."""

    def test_the_spans_beat_a_stale_annotation(self) -> None:
        """Spec §3.3 / test 11.2. The expected value is computed here from the
        spans themselves — asserting only "different from the annotation"
        would pass for a reference that was wrong in some other way."""
        markers = [
            *[(a, cal_start_marker(0, i)) for i, (a, _b, _amp)
              in enumerate(REPS_CH0, start=1)],
            *[(b, cal_end_marker(0, i)) for i, (_a, b, _amp)
              in enumerate(REPS_CH0, start=1)],
            (23.0, mvc_ref_marker(0, 0.055)),        # stale: an old calibration
        ]
        p = parse_phase_markers(markers)
        valor, fuente = mvc_reference(
            0, phases=p, envelope=_envelope(), fs=FS,
            cached=parse_mvc_ref_markers(markers),
        )
        esperado = max(amp for _a, _b, amp in REPS_CH0)   # best of three
        assert fuente == FROM_REPS
        assert valor == pytest.approx(esperado, abs=1e-6)

    def test_without_spans_the_cached_value_is_used(self) -> None:
        """A file recorded before this change: the number is right, the
        repetitions are simply not there to inspect."""
        markers = [(23.0, mvc_ref_marker(0, 0.0978971))]
        valor, fuente = mvc_reference(
            0, phases=parse_phase_markers(markers), envelope=_envelope(), fs=FS,
            cached=parse_mvc_ref_markers(markers),
        )
        assert fuente == FROM_CACHE
        assert valor == pytest.approx(0.0978971)

    def test_with_neither_there_is_no_reference(self) -> None:
        valor, fuente = mvc_reference(0, phases=SessionPhases(), cached={})
        assert valor is None
        assert fuente == NO_CALIBRATION

    def test_a_channel_that_was_not_calibrated_falls_through(self) -> None:
        """One muscle calibrated and the other not is a real montage, not an
        error: the second channel simply has no reference."""
        p = parse_phase_markers(_markers())
        valor, fuente = mvc_reference(1, phases=p, envelope=_envelope(), fs=FS)
        assert valor is None
        assert fuente == NO_CALIBRATION

    def test_the_spans_are_skipped_without_a_signal_to_measure(self) -> None:
        """The parse alone cannot produce a number, so it must not claim to."""
        p = parse_phase_markers(_markers())
        valor, fuente = mvc_reference(0, phases=p, cached={0: 0.09})
        assert fuente == FROM_CACHE
        assert valor == pytest.approx(0.09)


class TestDiscardingARepetitionMovesTheReference:
    """Spec test 3: the choice has to change the vara de medir, visibly."""

    @staticmethod
    def _ref(keep=None) -> float:
        valor, _ = mvc_reference(
            0, phases=parse_phase_markers(_markers()),
            envelope=_envelope(), fs=FS, keep=keep,
        )
        assert valor is not None
        return valor

    def test_discarding_the_weakest_barely_moves_it(self) -> None:
        """Best of three ignores the weak one anyway — which is the point of
        best-of-three, and worth showing the student."""
        assert self._ref(keep={2, 3}) == pytest.approx(self._ref(), abs=1e-6)

    def test_discarding_the_strongest_lowers_it_visibly(self) -> None:
        con_todas = self._ref()
        sin_la_mejor = self._ref(keep={1, 3})
        assert sin_la_mejor < con_todas
        assert sin_la_mejor == pytest.approx(0.100, abs=1e-6)
        # and every %MVC computed from it rises by the same factor
        assert con_todas / sin_la_mejor == pytest.approx(0.120 / 0.100, rel=1e-6)

    def test_a_channel_cannot_be_left_with_no_repetition(self) -> None:
        """Spec test 3b. Emptying the list is not a calibration with a smaller
        reference — it is no calibration, and that is done by not calibrating.
        Silently falling back to the cached value would answer a question
        nobody asked."""
        with pytest.raises(ValueError, match="at least one"):
            self._ref(keep=set())

    def test_keeping_repetitions_that_do_not_exist_is_the_same_error(self) -> None:
        with pytest.raises(ValueError):
            self._ref(keep={7, 8})


class TestTheProvenanceIsShownNotInferred:
    def test_the_three_sources_read_differently(self) -> None:
        textos = {
            reference_source_text(FROM_REPS),
            reference_source_text(FROM_CACHE),
            reference_source_text(NO_CALIBRATION),
        }
        assert len(textos) == 3
        assert all(t.strip() for t in textos)

    def test_the_count_of_repetitions_can_travel_with_it(self) -> None:
        assert "3" in reference_source_text(FROM_REPS, n_reps=3)

    def test_the_token_is_not_the_sentence(self) -> None:
        """``mvc_is_auto`` exists as a flag beside the translated ``mvc_source``
        for exactly this reason: the interface must branch on the token, so it
        keeps working in Spanish."""
        assert FROM_REPS != reference_source_text(FROM_REPS)
