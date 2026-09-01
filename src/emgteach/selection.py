"""Assisted selection of the significant fragments of a recording.

Choosing which part of a recording to analyse is a critical, error-prone
step: keep too much and rest/setup noise dilutes the metrics; keep too
little and the estimate is unstable. This module automates the *proposal*
of the informative fragments — the active-contraction periods — while
leaving the final decision to the user, who can accept, tweak, add or
drop fragments in the GUI editor.

The core is :func:`suggest_significant_segments`: it filters the raw
signal, derives the envelope, estimates a robust resting baseline, and
returns the runs where the envelope rises clearly above that baseline for
long enough to matter. :func:`normalise_segments` clamps and merges a
user-edited list so the downstream analysis always receives clean,
non-overlapping windows.

Everything here is pure and GUI-free, so it is unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.integrate import trapezoid

from emgteach.dsp import process_offline

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]

__all__ = [
    "Segment",
    "normalise_segments",
    "suggest_significant_segments",
    "total_duration_s",
]


@dataclass(frozen=True)
class Segment:
    """A candidate analysis fragment ``[start_s, end_s]`` with a score.

    Attributes
    ----------
    start_s, end_s : float
        Fragment bounds in seconds from the start of the recording.
    score : float
        Relative significance (higher = more informative). For an
        automatic suggestion it is the area under the envelope over the
        fragment (activity x duration); for a manually added fragment it
        is 0.
    reason : str
        Short machine tag explaining why the fragment was proposed
        (``"activity"``, ``"whole"``, ``"manual"``).
    label : str
        What the operator says this fragment *is* — "Grip", "Flexion". Empty
        for a fragment that is only a stretch of signal worth keeping.

        The distinction matters because no algorithm can supply it. The onset
        detector says "a contraction started here"; the co-activation table
        needs "this window is the grip", and the difference between flexion,
        extension and grip is not in the shape of the envelope — it is in what
        the subject was asked to do. A named fragment is the operator saying
        so, after the fact, over a trace they can see.
    """

    start_s: float
    end_s: float
    score: float = 0.0
    reason: str = ""
    label: str = ""

    @property
    def duration_s(self) -> float:
        """Fragment length in seconds."""
        return self.end_s - self.start_s


def total_duration_s(segments: list[Segment]) -> float:
    """Total kept time (s) across all fragments."""
    return float(sum(s.duration_s for s in segments))


def _find_runs(active: np.ndarray) -> list[tuple[int, int]]:
    """Return inclusive ``(start, end)`` index runs where ``active`` is True."""
    idx = np.flatnonzero(active)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate([[idx[0]], idx[breaks + 1]])
    ends = np.concatenate([idx[breaks], [idx[-1]]])
    return [(int(s), int(e)) for s, e in zip(starts, ends, strict=True)]


def suggest_significant_segments(
    emg_raw: FloatArray | np.ndarray,
    fs: float,
    *,
    f_low: float = 20.0,
    f_high: float = 450.0,
    f_notch: float = 50.0,
    f_env: float = 5.0,
    k: float = 3.0,
    min_duration_s: float = 0.5,
    merge_gap_s: float = 0.3,
    max_segments: int | None = None,
) -> list[Segment]:
    """Propose the informative fragments (active periods) of a recording.

    The envelope is thresholded at ``baseline + k · noise``, where the
    baseline and noise are estimated **robustly** from the quieter 40% of
    the envelope (median and scaled MAD), so the detection works whether
    the recording is mostly rest with short bursts or a long sustained
    contraction with little rest. Contiguous active periods closer than
    ``merge_gap_s`` are merged, and periods shorter than ``min_duration_s``
    are dropped as noise.

    Parameters
    ----------
    emg_raw : array-like
        Raw signal (mV).
    fs : float
        Sampling frequency (Hz).
    f_low, f_high, f_notch, f_env : float
        Filter cut-offs used to derive the envelope (defaults match the
        EMG profile).
    k : float, optional
        Threshold sensitivity in robust standard deviations above the
        resting baseline (default 3).
    min_duration_s : float, optional
        Minimum length of a kept fragment (default 0.5 s).
    merge_gap_s : float, optional
        Active periods separated by less than this are merged (default
        0.3 s).
    max_segments : int, optional
        If given, keep only the ``max_segments`` highest-scoring fragments
        (still returned in chronological order).

    Returns
    -------
    list of Segment
        Proposed fragments in chronological order. If no clear activity is
        found, a single fragment spanning the whole recording is returned
        (tagged ``"whole"``) so the user always has a sensible default to
        edit rather than an empty selection.
    """
    emg = np.asarray(emg_raw, dtype=np.float64).ravel()
    n = emg.size
    total_s = n / fs

    # Too short to segment meaningfully: propose the whole thing.
    if n < int(fs):
        return [Segment(0.0, total_s, score=0.0, reason="whole")]

    env = process_offline(
        emg, fs, f_low=f_low, f_high=f_high, f_notch=f_notch, f_env=f_env
    )["emg_envelope"]

    # Robust resting baseline from the quieter 40% of the envelope.
    low = env[env <= np.percentile(env, 40.0)]
    base = float(np.median(low)) if low.size else float(np.median(env))
    mad = float(np.median(np.abs(low - base))) * 1.4826 if low.size else 0.0
    if mad <= 0.0:
        mad = float(np.std(env)) or 1e-9
    threshold = base + k * mad

    active = env > threshold
    runs = _find_runs(active)

    # Merge runs whose inter-gap is shorter than merge_gap_s.
    merge_gap = round(merge_gap_s * fs)
    merged: list[tuple[int, int]] = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    min_len = round(min_duration_s * fs)
    segments: list[Segment] = []
    dt = 1.0 / fs
    for start, end in merged:
        if end - start + 1 < min_len:
            continue
        area = float(trapezoid(env[start : end + 1], dx=dt))
        segments.append(
            Segment(
                start_s=start / fs,
                end_s=(end + 1) / fs,
                score=area,
                reason="activity",
            )
        )

    if not segments:
        # Nothing rose clearly above baseline: default to the whole recording.
        return [Segment(0.0, total_s, score=0.0, reason="whole")]

    if max_segments is not None and len(segments) > max_segments:
        top = sorted(segments, key=lambda s: s.score, reverse=True)[:max_segments]
        segments = sorted(top, key=lambda s: s.start_s)

    return segments


def normalise_segments(
    segments: list[Segment],
    full_duration_s: float,
    *,
    min_duration_s: float = 0.0,
) -> list[Segment]:
    """Clamp, order and merge a (possibly user-edited) fragment list.

    Bounds are clamped to ``[0, full_duration_s]``, fragments shorter than
    ``min_duration_s`` are dropped, and any overlapping or touching
    fragments are merged so the downstream analysis receives disjoint,
    chronologically ordered windows. Scores of merged fragments are summed
    and the ``reason`` of the earliest is kept.

    Parameters
    ----------
    segments : list of Segment
        Fragments to normalise (any order).
    full_duration_s : float
        Length of the recording; fragments are clamped to it.
    min_duration_s : float, optional
        Minimum kept length after clamping (default 0, i.e. keep all
        non-empty fragments).

    Returns
    -------
    list of Segment
        Disjoint, ordered, clamped fragments.
    """
    clamped: list[Segment] = []
    for s in segments:
        a = max(0.0, min(float(s.start_s), full_duration_s))
        b = max(0.0, min(float(s.end_s), full_duration_s))
        if b - a > max(0.0, min_duration_s) or (min_duration_s == 0.0 and b > a):
            clamped.append(Segment(a, b, s.score, s.reason, s.label))

    clamped.sort(key=lambda s: s.start_s)

    merged: list[Segment] = []
    for s in clamped:
        if merged and s.start_s <= merged[-1].end_s:
            prev = merged[-1]
            merged[-1] = Segment(
                prev.start_s,
                max(prev.end_s, s.end_s),
                prev.score + s.score,
                prev.reason,
                # The earlier name wins, like the reason. Two fragments that
                # overlap are one stretch, and the operator named its start.
                prev.label or s.label,
            )
        else:
            merged.append(s)
    return merged
