"""What the guided sessions measured, read back from the file.

The session marks (:mod:`emgteach.sessions`) say where each measured stretch
was; this module turns those stretches into the numbers the analysis tab, the
report and the phones show. Qt-free, like the rest of the analytic core.

The fatigue: a fixed load held with the biceps, read in the spectrum. MDF and
MNF in windows of a second against time, with their straight lines, the
seconds until the MDF fell 10 %, and the RMS beside them: fatigue lowers the
frequency, and under a submaximal load the amplitude may hold or rise (the
bench's biceps, 26 October 2026: MDF down 16 % in 90 s, RMS flat).

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
    "LOAD_MIN_RATIO",
    "LOAD_RATIO_AT_S",
    "LOAD_RATIO_FROM_S",
    "LOAD_SKIP_S",
    "MARGIN_S",
    "RELEASE_S",
    "REST_WARN_MV",
    "SETTLE_S",
    "TRAIN_RMS_MS",
    "LoadResult",
    "StepResult",
    "TrainResult",
    "Trend",
    "change_pct",
    "effort_ratio",
    "fatigue_unmeasured",
    "fragments_hull",
    "gradation_reference_text",
    "gradation_steps",
    "is_monotonic",
    "load_fatigue",
    "load_piece",
    "load_span",
    "load_verdict",
    "mdf_trend_applies",
    "measured_windows",
    "processing_floor_pct",
    "rapid_train",
    "rest_level",
    "spans_in_analysis_time",
    "time_to_decline",
    "train_span",
    "weak_signal_warning",
]

#: Seconds at the start of each step left out of its level: the reach. One
#: second until 3.10.0; 1.5 since each step is asked to be reached slowly, in
#: 1-2 s, and the bench's steps began with a brief peak (Ángel, 3.10.1).
SETTLE_S = 1.5

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
_CON_MARGEN = frozenset({"step", "train"})

#: The share of a stretch's marked length the chosen fragments must keep of
#: it for it to be measured (measured_windows): a fragment round the
#: contraction keeps nearly all of it, one cut across it about half.
_MIN_KEPT = 0.6

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

    With fragments chosen, each stretch is measured in the piece that keeps
    most of it, over the part that piece keeps, if that is at least
    :data:`_MIN_KEPT` of its marked length. Not only when its marks are both
    inside: a fragment chosen round a contraction leaves out the cue that
    opened it, some tenths of a second of rest before, and every step was
    then left out (Ángel's bench, 26 October 2026: five fragments, one per
    step, and «1 step»). Half a step is still not a step.
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
        hasta = t.end_s
        if t.name in _CON_MARGEN:
            hasta = t.end_s + float(margin_s)
            if i + 1 < len(tramos):
                hasta = min(hasta, tramos[i + 1].start_s - _GUARDA_S)
            if fin is not None:
                hasta = min(hasta, fin)
            hasta = max(hasta, t.end_s)
        mejor = None
        for x, y, offset in kept:
            ini, fin_p = max(t.start_s, x), min(hasta, y)
            if fin_p > ini and (mejor is None or fin_p - ini > mejor[1] - mejor[0]):
                mejor = (ini, fin_p, x, offset)
        if mejor is None or mejor[1] - mejor[0] < _MIN_KEPT * t.duration_s - 1e-9:
            continue
        ini, fin_p, x, offset = mejor
        out.append((MeasuredSpan(t.name, ini, fin_p, t.params),
                    offset + ini - x, offset + fin_p - x))
    return out


def fatigue_unmeasured(result) -> str | None:
    """Why the summary gives no fatigue verdict for this analysis, or ``None``.

    The verdict on the summary card, the report and the phones comes from
    the same measure as the session's view, or is not given: over a train of
    quick contractions nothing is held, and a fixed load whose chosen
    fragments keep less than 3 s of it cannot be read — the general fit over
    the pieces glued together said «Fatigue: detected (MDF -27 %)» over
    4.6 s while the view said it could not measure (the final bench, B3).
    """
    from emgteach.i18n import tr

    if not mdf_trend_applies(result.get("guided_session")):
        return tr("Not measured (quick contractions: nothing held)")
    if result.get("load_note"):
        return tr("Not measured (the chosen fragments keep less than 3 s of the held load)")
    return None


def mdf_trend_applies(session: GuidedSession | None) -> bool:
    """Whether the MDF's trend over the analysed span can say anything about
    fatigue: not over a train of quick contractions, ten seconds of brief
    ones with no contraction held for the trend to show (Ángel's bench,
    26 October 2026: «Fatigue: not conclusive» beside the train's own
    numbers)."""
    return session is None or session.family != "FAST"


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


def gradation_reference_text(result) -> str | None:
    """What the gradation's percentages are of, for the view and the report —
    and, when the maximal step went above the calibration, that it did;
    ``None`` without a gradation measured in per cent."""
    from emgteach.i18n import tr
    from emgteach.sessions import GRAD_MVC_WINDOW_S

    ref = result.get("mvc_ref")
    if not result.get("grad_steps") or not ref:
        return None
    texto = tr("Reference: the MVC, its highest mean over {w:g} s ({mvc:.3f} mV), "
               "as the level held is a mean.").format(w=GRAD_MVC_WINDOW_S, mvc=ref)
    pico = (result.get("task_peak_pct") or {}).get(result.get("channel_name"))
    if pico is not None and pico > 100.0:
        texto += " " + tr("The maximal step went above the calibration: {pct:.0f} %.").format(
            pct=pico)
    return texto


def is_monotonic(steps: Sequence[StepResult]) -> bool:
    """Whether every step held more than the one before, in % MVC or mV."""
    valores = [s.held_pct if s.held_pct is not None else s.held_mv for s in steps]
    return len(valores) >= 2 and all(b > a for a, b in itertools.pairwise(valores))


# ---------------------------------------------------------------------------
# The fatigue: a fixed load held, read in the spectrum
# ---------------------------------------------------------------------------

#: The analysis of a held load starts this long after the activity does:
#: picking up the weight is not the contraction that tires.
LOAD_SKIP_S = 2.0
#: The windows the spectrum is followed with: 1 s, every half second (the
#: analysis' own segments), and the means over 5 s that the view draws.
LOAD_WIN_S = 1.0
LOAD_STEP_S = 0.5
LOAD_BLOCK_S = 5.0
#: Fatigue is a significant fall of the MDF (its slope's p below this) of at
#: least this much, % of where its line begins. Not an R² threshold: on the
#: bench's biceps (26 October 2026) the MDF fell 16 % in 90 s with p ~ 1e-8
#: and an R² of 0.3 — a real fall under a spectrum's own scatter.
LOAD_MAX_P = 0.01
LOAD_MIN_FALL_PCT = 10.0
#: A rest above this before the effort, mV, says an electrode is loose. A
#: coarse check only (Ángel, 26 October 2026): the bench's two biceps rested
#: at 0.019 and 0.022 mV (envelope medians), the good one and the bad one
#: alike; what told them apart is the next.
REST_WARN_MV = 0.03
#: The held load's envelope over the rest's, below which the signal is too
#: weak to read fatigue in: the bench's good biceps held at 3.7 times its
#: rest (4.1 in the effort's seconds 2 to 5, what is checked live), the bad
#: one at 1.5 (1.1), with the same mains in both. Not the 50 Hz peak against
#: the spectrum: it was the same mains, and the bad one's ratio was higher
#: only because its EMG was weak.
LOAD_MIN_RATIO = 2.0
#: The live check: the envelope from this second of the effort to the next.
LOAD_RATIO_FROM_S = 2.0
LOAD_RATIO_AT_S = 5.0


def time_to_decline(t, values, pct: float, *, base_n: int = 3,
                    span: int = 3) -> float | None:
    """When *values* first fell *pct* per cent below where they began.

    Where they began is the median of the first *base_n* values; a value
    counts once the median of it and the *span* - 1 before it is below the
    line, so a single low window — a breath, a shift of the grip — does not
    end the count. In the units of *t*, from its first value; ``None`` if the
    fall never comes.
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
        if float(np.median(v[max(0, i - span + 1): i + 1])) < linea:
            return float(tt[i] - tt[0])
    return None


def change_pct(first: float | None, last: float | None) -> float | None:
    """How much *last* differs from *first*, in per cent of *first*."""
    if first is None or last is None or not first:
        return None
    return 100.0 * (float(last) - float(first)) / float(first)


@dataclass(frozen=True)
class Trend:
    """A straight line through a measure against time, and how well it fits."""

    slope: float
    #: The line at the first and the last window.
    start: float
    end: float
    r2: float
    p: float

    @property
    def change_pct(self) -> float | None:
        return change_pct(self.start, self.end)


def _trend(t, v) -> Trend | None:
    from scipy.stats import linregress

    t = np.asarray(t, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if t.size < 3 or np.ptp(t) <= 0:
        return None
    r = linregress(t, v)
    return Trend(slope=float(r.slope), start=float(r.intercept + r.slope * t[0]),
                 end=float(r.intercept + r.slope * t[-1]),
                 r2=float(r.rvalue ** 2), p=float(r.pvalue))


@dataclass(frozen=True)
class LoadResult:
    """A fixed load held: what the spectrum and the amplitude did."""

    seconds: float
    #: Each window's centre, from the start of the analysed span, and its
    #: MDF, MNF (Hz) and RMS (mV).
    t: tuple[float, ...]
    mdf: tuple[float, ...]
    mnf: tuple[float, ...]
    rms: tuple[float, ...]
    #: The means over 5 s, as the view draws them.
    block_t: tuple[float, ...]
    block_mdf: tuple[float, ...]
    block_mnf: tuple[float, ...]
    mdf_trend: Trend | None
    mnf_trend: Trend | None
    rms_trend: Trend | None
    #: Seconds until the MDF had fallen 10 % (a 5 s running median against
    #: its first 5 s); ``None`` if it did not.
    t_mdf_10: float | None
    #: emgteach.fatigue's FATIGUE, NO_FATIGUE or INCONCLUSIVE.
    verdict: str


def load_verdict(trend: Trend | None, n: int) -> str:
    """Fatigue when the MDF fell significantly and by at least a tenth."""
    from emgteach.fatigue import FATIGUE, INCONCLUSIVE, NO_FATIGUE

    if trend is None or n < 10 or not np.isfinite(trend.p):
        return INCONCLUSIVE
    if trend.p >= LOAD_MAX_P:
        return INCONCLUSIVE
    caida = trend.change_pct
    if trend.slope < 0 and caida is not None and caida <= -LOAD_MIN_FALL_PCT:
        return FATIGUE
    return NO_FATIGUE


def load_fatigue(emg_filtered, fs: float, *, f_low: float = 20.0,
                 f_high: float = 450.0) -> LoadResult | None:
    """The held load's spectrum and amplitude, window by window, and their lines.

    *emg_filtered* is the analysed span, which for the load session is the
    held contraction (:func:`load_span`). MDF and MNF of each window over the
    analysis band, its RMS; a straight line through each against time; the
    seconds until the MDF fell 10 %; and the verdict (:func:`load_verdict`).
    """
    x = np.asarray(emg_filtered, dtype=np.float64)
    if fs <= 0:
        return None
    w = round(LOAD_WIN_S * fs)
    paso = max(1, round(LOAD_STEP_S * fs))
    if x.size < w * 3:
        return None
    t, mdf, mnf, rms = [], [], [], []
    for i0 in range(0, x.size - w + 1, paso):
        trozo = x[i0:i0 + w]
        r = compute_psd_mnf_mdf(trozo, fs, f_low=f_low, f_high=f_high)
        t.append((i0 + w / 2) / fs)
        mdf.append(float(r["mdf"]))
        mnf.append(float(r["mnf"]))
        rms.append(float(np.sqrt(np.mean(trozo ** 2))))
    tt = np.array(t)
    bloque = max(1, round(LOAD_BLOCK_S / LOAD_STEP_S))
    bloques = range(0, tt.size - bloque + 1, bloque)
    por_tramo = round(LOAD_BLOCK_S / LOAD_STEP_S)
    tendencia = _trend(tt, mdf)
    return LoadResult(
        seconds=x.size / fs,
        t=tuple(t), mdf=tuple(mdf), mnf=tuple(mnf), rms=tuple(rms),
        block_t=tuple(float(np.mean(tt[i:i + bloque])) for i in bloques),
        block_mdf=tuple(float(np.mean(mdf[i:i + bloque])) for i in bloques),
        block_mnf=tuple(float(np.mean(mnf[i:i + bloque])) for i in bloques),
        mdf_trend=tendencia, mnf_trend=_trend(tt, mnf), rms_trend=_trend(tt, rms),
        t_mdf_10=time_to_decline(tt, mdf, 10.0, base_n=por_tramo, span=por_tramo),
        verdict=load_verdict(tendencia, tt.size),
    )


def load_span(session: GuidedSession | None, envelope, fs: float) -> tuple[float, float] | None:
    """The held contraction of a load session, in file time.

    From :data:`LOAD_SKIP_S` after the activity begins — the student picks
    the weight up on the cue, and that is not the contraction that tires — to
    where the activity falls or the effort's mark ends it, whichever comes
    first. The activity is found as the contraction table finds it, above the
    rest the session measured before the effort.
    """
    if session is None or session.family != "HOLD" or session.params.get("mode") != "load":
        return None
    esfuerzos = session.spans_named("effort")
    if not esfuerzos or fs <= 0:
        return None
    esfuerzo = esfuerzos[-1]
    env = np.asarray(envelope, dtype=np.float64)
    reposos = session.spans_named("rest")
    if reposos:
        r0 = max(0, round(reposos[-1].start_s * fs))
        r1 = min(env.size, round(reposos[-1].end_s * fs))
        reposo = float(np.median(env[r0:r1])) if r1 > r0 else resting_level(env)
    else:
        reposo = resting_level(env)
    a0 = max(0.0, esfuerzo.start_s - 3.0)          # the countdown, when one picks it up early
    on, off = _contraccion(env - reposo, fs, a0, esfuerzo.end_s)
    a, b = on + LOAD_SKIP_S, min(off, esfuerzo.end_s)
    return (a, b) if b - a >= 3 * LOAD_WIN_S else None


def load_piece(span: tuple[float, float] | None,
               pieces: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
    """The part of the held load the chosen fragments keep, in file time.

    A student who chose fragments still reads the load in one piece: the
    longest stretch where a fragment and the load's *span* overlap, if it
    lasts at least three windows. ``None`` when no fragment covers that much
    of the load. Not the fragments glued together: a line through windows
    from both sides of a cut would join two moments of the fatigue.
    """
    if span is None:
        return None
    cruces = [(max(a, span[0]), min(b, span[1])) for a, b in pieces]
    cruces = [(a, b) for a, b in cruces if b - a >= 3 * LOAD_WIN_S]
    return max(cruces, key=lambda c: c[1] - c[0]) if cruces else None


def effort_ratio(effort_envelope, rest_mv: float | None) -> float | None:
    """How many times the rest the held effort's envelope is (its median)."""
    env = np.asarray(effort_envelope, dtype=np.float64)
    if rest_mv is None or rest_mv <= 0 or env.size == 0:
        return None
    return float(np.median(env)) / float(rest_mv)


def weak_signal_warning(ratio: float | None) -> str | None:
    """The warning for an effort that barely rises above the rest, or ``None``.

    Two causes, and the student can tell which: a poor contact, or a weight
    too light for the muscle to work at a level the electrodes see.
    """
    from emgteach.i18n import tr

    if ratio is None or ratio >= LOAD_MIN_RATIO:
        return None
    return tr("Weak signal: the effort barely exceeds the rest (×{x:.1f}). Check the "  # noqa: RUF001
              "electrodes' contact or use a heavier weight.").format(x=ratio)


def train_span(session: GuidedSession | None, envelope, fs: float) -> tuple[float, float] | None:
    """The train of quick contractions in file time: from its first
    contraction to its last, inside its marks run on by :data:`MARGIN_S`.

    What the fragment editor proposes for it, as one row. Its detector made
    one row per contraction, and the train glued out of them had lost the
    rests between them — its floor and its rate (the bench with exe #139).
    The activity is found above the rest of the 3 s before the cue.
    """
    if session is None or session.family != "FAST" or fs <= 0:
        return None
    ventanas = measured_windows(session, [(0.0, float("inf"), 0.0)], ("train",))
    if not ventanas:
        return None
    tramo, a, b = ventanas[-1]
    env = np.asarray(envelope, dtype=np.float64)
    r0, r1 = max(0, round((tramo.start_s - 3.0) * fs)), max(0, round(tramo.start_s * fs))
    reposo = float(np.median(env[r0:r1])) if r1 - r0 > 10 else resting_level(env)
    on, off = _contraccion(env - reposo, fs, a, b)
    return (on, off) if off > on else None


def fragments_hull(session: GuidedSession | None, pieces: Sequence[tuple[float, float]],
                   name: str) -> tuple[float, float] | None:
    """From the first to the last chosen fragment inside a stretch's window,
    in file time, if that covers :data:`_MIN_KEPT` of its marked length.

    A train is measured over that stretch of the recording, not over the
    fragments glued: chosen one per contraction they keep no rest between
    them, and the floor and the rate are what is measured there.
    """
    if session is None:
        return None
    for tramo, a, b in measured_windows(session, [(0.0, float("inf"), 0.0)], (name,)):
        dentro = [(max(a, x), min(b, y)) for x, y in pieces if min(b, y) > max(a, x)]
        if not dentro:
            return None
        ini, fin = min(x for x, _ in dentro), max(y for _, y in dentro)
        return (ini, fin) if fin - ini >= _MIN_KEPT * tramo.duration_s - 1e-9 else None
    return None


def rest_level(session: GuidedSession | None, envelope, fs: float) -> float | None:
    """The envelope's median over the rest a session measured, mV."""
    if session is None or fs <= 0:
        return None
    reposos = session.spans_named("rest")
    if not reposos:
        return None
    env = np.asarray(envelope, dtype=np.float64)
    r0 = max(0, round(reposos[-1].start_s * fs))
    r1 = min(env.size, round(reposos[-1].end_s * fs))
    return float(np.median(env[r0:r1])) if r1 > r0 else None


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
