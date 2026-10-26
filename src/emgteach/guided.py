"""What the guided sessions measured, read back from the file.

The session marks (:mod:`emgteach.sessions`) say where each measured stretch
was; this module turns those stretches into the numbers the analysis tab, the
report and the phones show. Qt-free, like the rest of the analytic core.

The fatigue, sustained: from the analysis' sliding windows over the effort,
the MDF and the RMS of its start and its end (a quarter of it, at most five
seconds) and the seconds until
each fell 10 and 20 %. Intermittent: one row per contraction, its RMS after
the first second (the peak is the start of each contraction and does not
fall) and its MDF.

The gradation: one row per step, with the target the student was asked for,
the level they held, its RMS and its MDF. **The level held is the mean of the
envelope over the plateau of the step's contraction**: after its first second,
which is the reaching for the level, not the holding of it (a peak would be
the overshoot of that reach), and before its letting go. In % MVC, which the
gradation always has — it calibrates first.

**A step, a contraction or a train is the activity found inside its marks,
run on past their end** (:data:`MARGIN_S`). The marks are the cues; the
subject begins some tenths of a second after the one that opens a stretch
and lets go up to a second after the one that closes it (Ángel's bench with
the board, 26 October 2026). Measured on the marks alone, each step took rest
at its start and lost its end, and the train lost its last two contractions.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from emgteach.coactivation import resting_level
from emgteach.contractions import trim_to_effort
from emgteach.dsp import compute_psd_mnf_mdf
from emgteach.selection import Segment
from emgteach.sessions import GuidedSession, MeasuredSpan

__all__ = [
    "EDGE_S",
    "MARGIN_S",
    "RELEASE_S",
    "SETTLE_S",
    "TRAIN_RMS_MS",
    "HoldResult",
    "RepResult",
    "StepResult",
    "TrainResult",
    "change_pct",
    "gradation_steps",
    "hold_result",
    "intermittent_reps",
    "is_monotonic",
    "measured_windows",
    "processing_floor_pct",
    "rapid_train",
    "reps_trend_pct",
    "spans_in_analysis_time",
    "time_to_decline",
]

#: Seconds at the start of each step left out of its level: the reach.
SETTLE_S = 1.0

#: Seconds after the mark that closes a step, a contraction or the train that
#: still belong to it: the subject lets go after the cue, not on it. Never
#: into the next stretch, nor past the session's end.
MARGIN_S = 1.5

#: Seconds at the end of a contraction left out of its level, at most: the
#: letting go.
RELEASE_S = 0.5

#: Seconds kept clear before the next stretch's mark: a zero-phase envelope
#: rises a tenth of a second before the contraction it draws, and the next
#: contraction's rise is not this one's letting go.
_GUARDA_S = 0.25

#: The stretches run on past their marks. Not the sustained maximum's effort:
#: its analysed span is the effort, and its protocol is being revised.
_CON_MARGEN = frozenset({"step", "rep", "train"})

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


def measured_windows(
    session: GuidedSession | None,
    kept: Sequence[tuple[float, float, float]],
    names: Iterable[str] | None = None,
    *,
    margin_s: float = MARGIN_S,
) -> list[tuple[MeasuredSpan, float, float]]:
    """The session's stretches in the analysed signal's time, each run on
    past its end by *margin_s* — never into the next stretch nor past the
    session's end — so the contraction a cue asked for is inside it whole.

    What the contraction table and the guided measures look inside: the
    activity found in a window (:func:`emgteach.contractions.trim_to_effort`)
    is the step, the contraction or the train.
    """
    if session is None:
        return []
    tramos = sorted(session.spans, key=lambda t: t.start_s)
    nombres = None if names is None else set(names)
    fin = session.end_s
    out = []
    for i, t in enumerate(tramos):
        if nombres is not None and t.name not in nombres:
            continue
        for _tramo, a, b in spans_in_analysis_time([t], kept):
            if t.name in _CON_MARGEN:
                hasta = t.end_s + float(margin_s)
                if i + 1 < len(tramos):
                    hasta = min(hasta, tramos[i + 1].start_s - _GUARDA_S)
                if fin is not None:
                    hasta = min(hasta, fin)
                # Nor past the piece of the file the analysis kept it in.
                pieza = next(p for p in kept
                             if p[0] - 1e-9 <= t.start_s and t.end_s <= p[1] + 1e-9)
                hasta = min(hasta, pieza[1])
                b = a + max(t.duration_s, hasta - t.start_s)
                t = MeasuredSpan(t.name, t.start_s, t.start_s + (b - a), t.params)
            out.append((t, a, b))
    return out


def _actividad(envelope) -> np.ndarray:
    """The envelope above its rest: what an effort is found on, as the
    contraction table finds it."""
    env = np.asarray(envelope, dtype=np.float64)
    return env - resting_level(env) if env.size else env


def _contraccion(actividad: np.ndarray, fs: float, a: float, b: float) -> tuple[float, float]:
    """The contraction inside ``[a, b]``: from the first sample above a fifth
    of its peak activity to the last, as in the contraction table."""
    seg = trim_to_effort(Segment(a, b), fs, actividad)
    return seg.start_s, seg.end_s


def _meseta(on: float, off: float, settle_s: float) -> tuple[float, float]:
    """The plateau of a contraction: without its reach nor its letting go,
    and never less than its middle half."""
    dur = max(0.0, off - on)
    return on + min(float(settle_s), 0.5 * dur), off - min(RELEASE_S, 0.25 * dur)


@dataclass(frozen=True)
class StepResult:
    """One step of the gradation."""

    k: int
    #: What the student was asked for, % MVC.
    target_pct: float
    #: The step's contraction in the analysed signal's time.
    start_s: float
    end_s: float
    #: Mean envelope over the contraction's plateau, in mV and % MVC.
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
    actividad = _actividad(env)
    pasos: list[StepResult] = []
    for tramo, a, b in measured_windows(session, kept, ("step",)):
        a, b = _contraccion(actividad, fs, a, b)
        m0, m1 = _meseta(a, b, settle_s)
        i0 = max(0, min(round(m0 * fs), env.size))
        i1 = max(i0, min(round(m1 * fs), env.size))
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

#: Seconds at each end of a sustained maximum compared with each other, at
#: most: a quarter of the effort when it is shorter than twenty seconds, so
#: the ten-second maximum compares its first and last 2.5 s and not the same
#: windows twice.
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
    borde = min(float(edge_s), dur / 4.0)
    ini = t <= t[0] + borde
    fin = t >= t[-1] - borde

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
    #: RMS of the filtered signal over the contraction's plateau, after its
    #: first second — not its peak, which is the start and does not fall.
    rms_mv: float
    mdf_hz: float | None


def intermittent_reps(
    session: GuidedSession | None,
    kept: Sequence[tuple[float, float, float]],
    *,
    fs: float,
    emg_filtered,
    envelope=None,
    f_low: float = 20.0,
    f_high: float = 450.0,
    settle_s: float = SETTLE_S,
) -> list[RepResult]:
    """The intermittent maximum's contractions, measured; empty otherwise.

    Each is the contraction found inside its marks run on past their end, on
    *envelope* (a 100 ms moving RMS of the signal without one).
    """
    if (session is None or session.family != "HOLD"
            or session.params.get("mode") != "intermittent" or fs <= 0):
        return []
    filt = np.asarray(emg_filtered, dtype=np.float64)
    actividad = _actividad(envelope if envelope is not None
                           else _moving_rms(filt, fs, 100.0))
    reps: list[RepResult] = []
    for tramo, a, b in measured_windows(session, kept, ("rep",)):
        a, b = _contraccion(actividad, fs, a, b)
        m0, m1 = _meseta(a, b, settle_s)
        i0 = max(0, min(round(m0 * fs), filt.size))
        i1 = max(i0, min(round(m1 * fs), filt.size))
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


# ---------------------------------------------------------------------------
# The quick contractions: the peaks and the floor between them
# ---------------------------------------------------------------------------

#: The moving RMS the train is measured on, ms. Not the analysis' envelope:
#: at four or five contractions a second its 5 Hz filter alone keeps the
#: floor at a fifth to a third of the peak (worked out with ideal pulses);
#: a 50 ms RMS keeps it near a tenth, and the rest of what is seen is the
#: subject's. What the processing contributes at the rate achieved is
#: measured and given apart (:func:`processing_floor_pct`).
TRAIN_RMS_MS = 50.0


def _moving_rms(x, fs: float, window_ms: float):
    x = np.asarray(x, dtype=np.float64)
    w = max(1, round(window_ms / 1000.0 * fs))
    return np.sqrt(np.convolve(x ** 2, np.ones(w) / w, mode="same"))


def _peaks_and_floors(s, fs: float):
    """Each contraction's peak, and the floor between it and the next.

    A contraction is a peak of *s* standing out by a third of the train's
    range, at least 0.12 s from the next (more than eight a second is not a
    voluntary rhythm). The floor is the lowest fifth of the trace between
    two peaks: not its minimum, which on a noisy trace is a sample, not a
    level.
    """
    from scipy.signal import find_peaks

    s = np.asarray(s, dtype=np.float64)
    if s.size < 3:
        return np.array([], int), np.array([]), np.array([])
    rango = float(np.percentile(s, 95) - np.percentile(s, 5))
    picos, _ = find_peaks(s, distance=max(1, round(0.12 * fs)),
                          prominence=max(1e-12, rango / 3.0))
    suelos = np.array([float(np.percentile(s[a:b], 20))
                       for a, b in itertools.pairwise(picos) if b > a + 1])
    return picos, s[picos], suelos


def processing_floor_pct(rate_hz: float, fs: float = 1000.0,
                         window_ms: float = TRAIN_RMS_MS, seed: int = 0) -> float:
    """The floor, in % of the peak, that the measure itself leaves between
    contractions at *rate_hz*, with a perfect relaxation: noise switched on
    for half of each period and off for the other half, measured as a train
    is. What a recording shows above this is the subject's.
    """
    if rate_hz <= 0:
        return 0.0
    rng = np.random.default_rng(seed)
    periodo = 1.0 / float(rate_hz)
    n = round(12 * periodo * fs)
    t = np.arange(n) / fs
    activa = (t % periodo) < 0.5 * periodo
    x = rng.normal(0.0, 1.0, n) * np.where(activa, 1.0, 0.0)
    # Through the same filters the recording goes through: their ringing at
    # each switch is part of what the measure leaves in the gaps.
    from emgteach.dsp import process_offline

    s = _moving_rms(process_offline(x, fs)["emg_filtered"], fs, window_ms)
    i0 = round(2 * periodo * fs)
    _p, alturas, suelos = _peaks_and_floors(s[i0:], fs)
    if not alturas.size or not suelos.size:
        return 0.0
    return 100.0 * float(np.mean(suelos)) / float(np.mean(alturas))


@dataclass(frozen=True)
class TrainResult:
    """The quick contractions: how fast, and what the peaks and the floor did."""

    seconds: float
    n: int
    rate_hz: float
    #: The trace measured (moving RMS), from the start of the train, and the
    #: time and height of each peak.
    t: tuple[float, ...]
    rms: tuple[float, ...]
    peak_times: tuple[float, ...]
    peaks_mv: tuple[float, ...]
    #: The floor between consecutive peaks, mV.
    floors_mv: tuple[float, ...]
    #: The trace at rest before the train, mV.
    rest_mv: float | None
    #: The last third of the peaks against the first third, %.
    peak_change_pct: float | None
    #: The floor as % of the peaks, in the first and the last third.
    floor_start_pct: float | None
    floor_end_pct: float | None
    #: What the measure alone leaves at this rate, % of the peak.
    processing_floor_pct: float


def _tercios(v):
    v = np.asarray(v, dtype=np.float64)
    k = max(1, v.size // 3)
    return float(np.mean(v[:k])), float(np.mean(v[-k:]))


def rapid_train(
    session: GuidedSession | None,
    kept: Sequence[tuple[float, float, float]],
    *,
    fs: float,
    emg_filtered,
    window_ms: float = TRAIN_RMS_MS,
    rest_s: float = 2.0,
) -> TrainResult | None:
    """The train of quick contractions, measured; ``None`` without one.

    The train is the activity inside its marks run on past their end
    (:func:`measured_windows`): the subject stops some tenths of a second
    after the cue, and the contractions made meanwhile are the train's —
    measured between the marks, the bench of 26 October 2026 counted 28 of
    its 30. Its duration is the activity's, from its first contraction to
    its last.
    """
    if session is None or session.family != "FAST" or fs <= 0:
        return None
    tramos = measured_windows(session, kept, ("train",))
    if not tramos:
        return None
    _tramo, a, b = tramos[-1]
    filt = np.asarray(emg_filtered, dtype=np.float64)
    s_todo = _moving_rms(filt, fs, window_ms)
    i0 = max(0, min(round(a * fs), s_todo.size))
    i1 = max(i0, min(round(b * fs), s_todo.size))
    if i1 - i0 < round(0.5 * fs):
        return None
    s = s_todo[i0:i1]
    r0 = max(0, i0 - round(rest_s * fs))
    reposo = float(np.median(s_todo[r0:i0])) if i0 - r0 > 10 else None
    picos, alturas, suelos = _peaks_and_floors(s, fs)
    activo = trim_to_effort(Segment(0.0, s.size / fs), fs, s - (reposo or 0.0))
    dur = activo.end_s - activo.start_s
    n = int(alturas.size)
    ritmo = (n - 1) / ((picos[-1] - picos[0]) / fs) if n >= 2 and picos[-1] > picos[0] else 0.0
    cambio = suelo_ini = suelo_fin = None
    if n >= 3:
        ini, fin = _tercios(alturas)
        cambio = change_pct(ini, fin)
    if suelos.size >= 3 and n >= 3:
        s_ini, s_fin = _tercios(suelos)
        p_ini, p_fin = _tercios(alturas)
        suelo_ini = 100.0 * s_ini / p_ini if p_ini else None
        suelo_fin = 100.0 * s_fin / p_fin if p_fin else None
    paso = max(1, round(0.005 * fs))           # the trace at 200 Hz is plenty to draw
    return TrainResult(
        seconds=dur, n=n, rate_hz=float(ritmo),
        t=tuple(float(x) for x in np.arange(0, s.size, paso) / fs),
        rms=tuple(float(x) for x in s[::paso]),
        peak_times=tuple(float(x) for x in picos / fs),
        peaks_mv=tuple(float(x) for x in alturas),
        floors_mv=tuple(float(x) for x in suelos),
        rest_mv=reposo, peak_change_pct=cambio,
        floor_start_pct=suelo_ini, floor_end_pct=suelo_fin,
        processing_floor_pct=processing_floor_pct(ritmo, fs, window_ms) if ritmo else 0.0,
    )
