"""Tests for the assisted fragment-selection core (:mod:`emgteach.selection`)."""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.selection import (
    Segment,
    normalise_segments,
    suggest_significant_segments,
    total_duration_s,
)

FS = 1000


def _burst_signal() -> np.ndarray:
    """10 s of rest with two 1.5 s active bursts (at 2-3.5 s and 6-7.5 s)."""
    rng = np.random.default_rng(0)
    n = 10 * FS
    sig = rng.normal(0.0, 0.01, size=n)  # quiet baseline
    for a, b in ((2.0, 3.5), (6.0, 7.5)):
        i0, i1 = int(a * FS), int(b * FS)
        t = np.arange(i1 - i0) / FS
        sig[i0:i1] += 0.5 * np.sin(2 * np.pi * 90.0 * t)  # in-band burst
    return sig


class TestSuggest:
    def test_finds_two_bursts(self) -> None:
        segs = suggest_significant_segments(_burst_signal(), FS)
        assert len(segs) == 2
        # Envelope smoothing widens the detected bursts, so assert each
        # proposal overlaps its true burst (2-3.5 s and 6-7.5 s) rather than
        # pinning exact edges.
        def overlaps(seg, a: float, b: float) -> bool:
            return seg.start_s < b and seg.end_s > a

        assert overlaps(segs[0], 2.0, 3.5)
        assert overlaps(segs[1], 6.0, 7.5)
        # Disjoint and ordered: the first must end before the second begins.
        assert segs[0].end_s < segs[1].start_s
        assert all(s.reason == "activity" for s in segs)
        assert all(s.score > 0 for s in segs)

    def test_bursts_are_chronological(self) -> None:
        segs = suggest_significant_segments(_burst_signal(), FS)
        assert segs == sorted(segs, key=lambda s: s.start_s)

    def test_max_segments_keeps_highest_scoring(self) -> None:
        segs = suggest_significant_segments(_burst_signal(), FS, max_segments=1)
        assert len(segs) == 1

    def test_flat_signal_falls_back_to_whole(self) -> None:
        flat = np.zeros(5 * FS)
        segs = suggest_significant_segments(flat, FS)
        assert len(segs) == 1
        assert segs[0].reason == "whole"
        assert segs[0].start_s == 0.0
        assert segs[0].end_s == pytest.approx(5.0, abs=0.01)

    def test_short_signal_returns_whole(self) -> None:
        segs = suggest_significant_segments(np.zeros(500), FS)  # 0.5 s
        assert len(segs) == 1
        assert segs[0].reason == "whole"

    def test_min_duration_drops_short_bursts(self) -> None:
        rng = np.random.default_rng(1)
        sig = rng.normal(0.0, 0.01, size=6 * FS)
        # A single very short (0.1 s) spike must be rejected as noise.
        sig[3000:3100] += 0.5
        segs = suggest_significant_segments(sig, FS, min_duration_s=0.5)
        assert all(s.reason == "whole" for s in segs) or all(
            s.duration_s >= 0.4 for s in segs
        )


def _series_signal() -> np.ndarray:
    """Six efforts in a row over a floor that never returns to silence.

    Which is what a muscle asked for six repetitions actually does: between one
    contraction and the next the envelope falls to a fraction of the peak but
    stays well above the electrical noise. Reproduced from the bench recording
    of 1 September (peaks around 0.15 mV, valleys around 0.006, noise floor
    0.002), because with a synthetic signal that goes properly silent between
    bursts the defect does not appear at all.
    """
    rng = np.random.default_rng(1)
    n = 10 * FS
    sig = rng.normal(0.0, 0.002, size=n)
    t_all = np.arange(n) / FS
    # A low sustained tone across the whole series: this is what keeps the
    # envelope above the noise threshold between one effort and the next.
    i0, i1 = int(1.5 * FS), int(8.5 * FS)
    sig[i0:i1] += 0.030 * np.sin(2 * np.pi * 90.0 * t_all[i0:i1])
    for k in range(6):
        a = 2.0 + k
        j0, j1 = int(a * FS), int((a + 0.6) * FS)
        sig[j0:j1] += 0.40 * np.sin(2 * np.pi * 90.0 * t_all[j0:j1])
    return sig


class TestASeriesOfEffortsIsNotOneFragment:
    """A run of contractions must arrive as one row each.

    The threshold that finds activity asks "is this above the noise?", and
    across a series the answer stays yes throughout, so the six efforts came
    back as a single block. A block can only be kept or discarded whole, and
    discarding one bad repetition is the reason the editor exists.
    """

    def test_the_six_efforts_come_back_separately(self) -> None:
        segs = suggest_significant_segments(_series_signal(), FS)
        assert len(segs) == 6, [f"{s.start_s:.2f}-{s.end_s:.2f}" for s in segs]

    def test_each_one_lands_on_its_own_effort(self) -> None:
        segs = suggest_significant_segments(_series_signal(), FS)
        for k, seg in enumerate(segs):
            a = 2.0 + k
            assert seg.start_s < a + 0.6 and seg.end_s > a, (
                f"el fragmento {k} ({seg.start_s:.2f}-{seg.end_s:.2f}) no cae "
                f"sobre el esfuerzo {a:.1f}-{a + 0.6:.1f}"
            )

    def test_they_do_not_swallow_the_pauses(self) -> None:
        """Each row is the contraction, not the contraction plus the rest that
        follows it — otherwise its RMS reads lower than the effort was."""
        segs = suggest_significant_segments(_series_signal(), FS)
        assert all(s.duration_s < 0.9 for s in segs), [
            round(s.duration_s, 2) for s in segs
        ]

    def test_a_lone_burst_is_left_exactly_as_it_was(self) -> None:
        """The split must not disturb what the threshold already separated."""
        assert len(suggest_significant_segments(_burst_signal(), FS)) == 2


class TestNormalise:
    def test_clamps_to_recording(self) -> None:
        segs = normalise_segments([Segment(-1.0, 3.0), Segment(8.0, 20.0)], 10.0)
        assert segs[0].start_s == 0.0
        assert segs[-1].end_s == 10.0

    def test_merges_overlapping(self) -> None:
        segs = normalise_segments([Segment(1.0, 4.0), Segment(3.0, 6.0)], 10.0)
        assert len(segs) == 1
        assert (segs[0].start_s, segs[0].end_s) == (1.0, 6.0)

    def test_orders_and_keeps_disjoint(self) -> None:
        segs = normalise_segments([Segment(6.0, 7.0), Segment(1.0, 2.0)], 10.0)
        assert [s.start_s for s in segs] == [1.0, 6.0]

    def test_drops_empty_after_clamp(self) -> None:
        segs = normalise_segments([Segment(12.0, 15.0)], 10.0)
        assert segs == []

    def test_total_duration(self) -> None:
        segs = [Segment(0.0, 2.0), Segment(5.0, 6.5)]
        assert total_duration_s(segs) == pytest.approx(3.5)
