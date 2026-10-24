"""What the guided sessions measured, read back from the file.

The session marks (:mod:`emgteach.sessions`) say where each measured stretch
was; this module turns those stretches into the numbers the analysis tab, the
report and the phones show. Qt-free, like the rest of the analytic core.

The fatigue, sustained: from the analysis' sliding windows over the effort,
the MDF and the RMS of its first and last five seconds and the seconds until
each fell 10 and 20 %. Intermittent: one row per contraction, its RMS after
the first second (the peak is the start of each contraction and does not
fall) and its MDF.

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
    "EDGE_S",
    "SETTLE_S",
    "HoldResult",
    "RepResult",
    "StepResult",
    "change_pct",
    "gradation_steps",
    "hold_result",
    "intermittent_reps",
    "is_monotonic",
    "reps_trend_pct",
    "spans_in_analysis_time",
    "time_to_decline",
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


# ---------------------------------------------------------------------------
# The fatigue: a sustained maximum, and an intermittent one
# ---------------------------------------------------------------------------

#: Seconds at each end of a sustained maximum compared with each other.
EDGE_S = 5.0


def time_to_decline(t, values, pct: float, *, base_n: int = 3) -> float | None:
    """When *values* first fell *pct* per cent below where they began.

    Where they began is the median of the first *base_n* values; a value
    counts once the median of it and the two before it is below the line,
    so a single low window — a breath, a shift of the grip — does not end the
    count. In the units of *t*, from its first value; ``None`` if the fall
    never comes.
    """
    tt = np.asarray(t, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    if v.size < base_n + 1 or tt.size != v.size:
        return None
    base = float(np.median(v[:base_n]))
    if not np.isfinite(base) or base <= 0:
        return None
    linea = base * (1.0 - float(pct) / 100.0)
    for i in range(base_n, v.size):
        if float(np.median(v[max(0, i - 2): i + 1])) < linea:
            return float(tt[i] - tt[0])
    return None


def change_pct(first: float | None, last: float | None) -> float | None:
    """How much *last* differs from *first*, in per cent of *first*."""
    if first is None or last is None or not first:
        return None
    return 100.0 * (float(last) - float(first)) / float(first)


@dataclass(frozen=True)
class HoldResult:
    """A sustained maximum, from its windows: how much it fell, and when."""

    seconds: float
    mdf_start_hz: float | None
    mdf_end_hz: float | None
    rms_start_mv: float | None
    rms_end_mv: float | None
    #: Seconds from the start of the effort until the MDF (or the RMS) had
    #: fallen 10 and 20 % below where it began; ``None`` if it did not.
    t_mdf_10: float | None
    t_mdf_20: float | None
    t_rms_10: float | None
    t_rms_20: float | None

    @property
    def mdf_change_pct(self) -> float | None:
        return change_pct(self.mdf_start_hz, self.mdf_end_hz)

    @property
    def rms_change_pct(self) -> float | None:
        return change_pct(self.rms_start_mv, self.rms_end_mv)


def hold_result(t_seg, mdf_seg, rms_seg, active=None, *,
                seg_len_s: float = 1.0, edge_s: float = EDGE_S) -> HoldResult | None:
    """The sustained maximum's numbers, from the analysis' sliding windows.

    *t_seg* are the windows' starts, in seconds from the start of the effort
    (the analysed span is the effort); each window is placed at its centre.
    Windows where the muscle had let go (*active* false) are left out: the
    MDF of silence is not a measurement.
    """
    t = np.asarray(t_seg, dtype=np.float64) + 0.5 * float(seg_len_s)
    mdf = np.asarray(mdf_seg, dtype=np.float64)
    rms = np.asarray(rms_seg, dtype=np.float64)
    if t.size < 2 or mdf.size != t.size or rms.size != t.size:
        return None
    if active is not None:
        m = np.asarray(active, dtype=bool)
        if m.size == t.size and m.any():
            t, mdf, rms = t[m], mdf[m], rms[m]
    dur = float(t[-1] + 0.5 * seg_len_s)
    ini = t <= t[0] + edge_s
    fin = t >= t[-1] - edge_s

    def media(x, sel):
        return float(np.median(x[sel])) if sel.any() else None

    return HoldResult(
        seconds=dur,
        mdf_start_hz=media(mdf, ini), mdf_end_hz=media(mdf, fin),
        rms_start_mv=media(rms, ini), rms_end_mv=media(rms, fin),
        t_mdf_10=time_to_decline(t, mdf, 10.0), t_mdf_20=time_to_decline(t, mdf, 20.0),
        t_rms_10=time_to_decline(t, rms, 10.0), t_rms_20=time_to_decline(t, rms, 20.0),
    )


@dataclass(frozen=True)
class RepResult:
    """One contraction of the intermittent maximum."""

    n: int
    start_s: float
    end_s: float
    #: RMS of the filtered signal over the contraction after its first
    #: second — not its peak, which is the start and does not fall.
    rms_mv: float
    mdf_hz: float | None


def intermittent_reps(
    session: GuidedSession | None,
    kept: Sequence[tuple[float, float, float]],
    *,
    fs: float,
    emg_filtered,
    f_low: float = 20.0,
    f_high: float = 450.0,
    settle_s: float = SETTLE_S,
) -> list[RepResult]:
    """The intermittent maximum's contractions, measured; empty otherwise."""
    if (session is None or session.family != "HOLD"
            or session.params.get("mode") != "intermittent" or fs <= 0):
        return []
    filt = np.asarray(emg_filtered, dtype=np.float64)
    reps: list[RepResult] = []
    for tramo, a, b in spans_in_analysis_time(session.spans_named("rep"), kept):
        a_hold = a + min(float(settle_s), 0.5 * (b - a))
        i0 = max(0, min(round(a_hold * fs), filt.size))
        i1 = max(i0, min(round(b * fs), filt.size))
        if i1 - i0 < 2:
            continue
        trozo = filt[i0:i1]
        mdf = None
        if (i1 - i0) / fs >= _MIN_S_FOR_MDF:
            mdf = float(compute_psd_mnf_mdf(trozo, fs, f_low=f_low, f_high=f_high)["mdf"])
        n = tramo.number("n")
        reps.append(RepResult(int(n) if n else len(reps) + 1, a, b,
                              float(np.sqrt(np.mean(trozo ** 2))), mdf))
    return reps


def reps_trend_pct(reps: Sequence[RepResult]) -> float | None:
    """The RMS's straight-line trend, in % of the first contraction per contraction."""
    if len(reps) < 3 or not reps[0].rms_mv:
        return None
    x = np.arange(len(reps), dtype=np.float64)
    y = 100.0 * np.array([r.rms_mv for r in reps]) / reps[0].rms_mv
    return float(np.polyfit(x, y, 1)[0])
