"""What the guided sessions measured, read back from the file.

The session marks (:mod:`emgteach.sessions`) say where each measured stretch
was; this module turns those stretches into the numbers the analysis tab, the
report and the phones show. Qt-free, like the rest of the analytic core.

The gradation: one row per step, with the target the student was asked for,
the level they held, its RMS and its MDF. **The level held is the mean of the
envelope over the step after its first second**: the first second is the
reaching for the level, not the holding of it, and a peak would be the
overshoot of that reach. In % MVC, which the gradation always has — it
calibrates first.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from emgteach.dsp import compute_psd_mnf_mdf
from emgteach.sessions import GuidedSession, MeasuredSpan

__all__ = [
    "SETTLE_S",
    "StepResult",
    "gradation_steps",
    "is_monotonic",
    "spans_in_analysis_time",
]

#: Seconds at the start of each step left out of its level: the reach.
SETTLE_S = 1.0

#: Shorter than this, a stretch has too few cycles of anything for an MDF.
_MIN_S_FOR_MDF = 0.25


def spans_in_analysis_time(
    spans: Iterable[MeasuredSpan],
    kept: Sequence[tuple[float, float, float]],
) -> list[tuple[MeasuredSpan, float, float]]:
    """Each stretch in the analysed signal's time, or left out.

    *kept* is one ``(start_s, end_s, offset_s)`` per piece of the file the
    analysis kept, in file time, with where that piece begins in the
    analysed (concatenated) signal. A stretch that does not lie whole inside
    one piece is left out: half a step is not a step.
    """
    out = []
    for tramo in spans:
        for a, b, offset in kept:
            if a - 1e-9 <= tramo.start_s and tramo.end_s <= b + 1e-9:
                out.append((tramo, offset + tramo.start_s - a,
                            offset + tramo.end_s - a))
                break
    return out


@dataclass(frozen=True)
class StepResult:
    """One step of the gradation."""

    k: int
    #: What the student was asked for, % MVC.
    target_pct: float
    #: The step in the analysed signal's time.
    start_s: float
    end_s: float
    #: Mean envelope over the step after its first second, in mV and % MVC.
    held_mv: float
    held_pct: float | None
    #: RMS of the filtered signal over the same stretch, mV.
    rms_mv: float
    mdf_hz: float | None

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


def gradation_steps(
    session: GuidedSession | None,
    kept: Sequence[tuple[float, float, float]],
    *,
    fs: float,
    emg_filtered,
    envelope,
    mvc_ref: float | None,
    f_low: float = 20.0,
    f_high: float = 450.0,
    settle_s: float = SETTLE_S,
) -> list[StepResult]:
    """The gradation's steps, measured; empty when the file has no gradation."""
    if session is None or session.family != "GRAD" or fs <= 0:
        return []
    filt = np.asarray(emg_filtered, dtype=np.float64)
    env = np.asarray(envelope, dtype=np.float64)
    pasos: list[StepResult] = []
    for tramo, a, b in spans_in_analysis_time(session.spans_named("step"), kept):
        # The reach is left out, but never the whole step.
        a_hold = a + min(float(settle_s), 0.5 * (b - a))
        i0 = max(0, min(round(a_hold * fs), env.size))
        i1 = max(i0, min(round(b * fs), env.size))
        if i1 - i0 < 2:
            continue
        nivel = float(np.mean(env[i0:i1]))
        trozo = filt[i0:i1]
        rms = float(np.sqrt(np.mean(trozo ** 2)))
        mdf = None
        if (i1 - i0) / fs >= _MIN_S_FOR_MDF:
            mdf = float(compute_psd_mnf_mdf(trozo, fs, f_low=f_low, f_high=f_high)["mdf"])
        k = tramo.number("k")
        pasos.append(StepResult(
            k=int(k) if k else len(pasos) + 1,
            target_pct=float(tramo.number("pct", 0.0) or 0.0),
            start_s=a, end_s=b, held_mv=nivel,
            held_pct=(100.0 * nivel / mvc_ref) if mvc_ref else None,
            rms_mv=rms, mdf_hz=mdf,
        ))
    return pasos


def is_monotonic(steps: Sequence[StepResult]) -> bool:
    """Whether every step held more than the one before, in % MVC or mV."""
    valores = [s.held_pct if s.held_pct is not None else s.held_mv for s in steps]
    return len(valores) >= 2 and all(b > a for a, b in itertools.pairwise(valores))
