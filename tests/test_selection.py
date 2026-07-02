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
