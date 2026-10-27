"""The fragments the editor proposes, without the editor.

Reading the channels of a recording and proposing the fragments to analyse —
the detection over the span, one row per lift, each row widened to its
contraction on the envelope, the hundredths — as functions over arrays, with
no Qt. ``gui/widgets/fragment_selection.py`` calls them; anything that only
needs the proposal (a script, a test) can call them without opening a window.

The span is the stretch the editor works in: in a two-phase session, the
recording phase. The calibration is signal too, and run over the whole file
the detector proposed its six maximal efforts as fragments of the task.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from emgteach.coactivation import _DOMINANCE
from emgteach.dsp import process_offline
from emgteach.force_velocity import marker_owners
from emgteach.selection import (
    DEFAULT_DETECTION,
    REST_MIN_S,
    Segment,
    activity_threshold,
    normalise_segments,
    suggest_significant_segments,
)

__all__ = [
    "default_detection",
    "detect",
    "envelope",
    "filters",
    "fit_rows",
    "fit_to_envelope",
    "one_per_lift",
    "read_channels",
    "rest_level",
    "span_within",
    "suggest_fragments",
    "to_hundredths",
]

#: Candidates are looked for at this share of the sensitivity, and never
#: below the floor, under which the resting noise itself clears the line.
_K_CANDIDATE = 0.5
_K_CANDIDATE_MIN = 1.0

#: How far ahead of its cue a lift may start and still be that lift.
_ANTICIPO_S = 0.5
#: A piece that starts this close after the one a cue took is the same lift,
#: split by the detector at a dip.
_UNION_S = 0.1
#: The small margin a proposed row keeps either side of its contraction,
#: which runs from where the envelope leaves rest to where it returns to it
#: — «rest» being the dotted line half the sensitivity draws, the one the
#: candidates are found with. See fit_to_envelope.
_BORDE_MARGEN_S = 0.05


def default_detection(k: float | None = None,
                      rest_fraction: float = 0.0) -> dict[str, float]:
    """The detection settings the editor opens on, co-activation rule included.

    ``k`` is the practical's own sensitivity (see
    :func:`emgteach.modes.mode_detection_k`); without it, the core default.
    With a ``rest_fraction`` (:func:`emgteach.modes.mode_rest_fraction`), a
    fragment ends only after :data:`emgteach.selection.REST_MIN_S` at rest.
    """
    d = dict(DEFAULT_DETECTION)
    d["both_ratio"] = float(_DOMINANCE)
    if k is not None:
        d["k"] = float(k)
    if rest_fraction > 0.0:
        d["rest_fraction"] = float(rest_fraction)
        d["merge_gap_s"] = REST_MIN_S
    return d


def filters(filter_kwargs: Mapping[str, float]) -> dict[str, float]:
    """``f_low``/``f_high``/``f_notch``/``f_env``, with the editor's defaults."""
    return {
        "f_low": float(filter_kwargs.get("f_low", 20.0)),
        "f_high": float(filter_kwargs.get("f_high", 450.0)),
        "f_notch": float(filter_kwargs.get("f_notch", 50.0)),
        "f_env": float(filter_kwargs.get("f_env", 5.0)),
    }


def span_within(span: tuple[float, float] | None, duration_s: float) -> tuple[float, float]:
    """The stretch to work in, inside the recording; the whole of it without one."""
    if not span:
        return (0.0, duration_s)
    return (max(0.0, float(span[0])), min(duration_s, float(span[1])))


def read_channels(
    edf_path: str, channel_name: str, channel_name_2: str | None = None
) -> tuple[np.ndarray, float, np.ndarray | None]:
    """One or two channels of an EDF: ``(raw, fs, raw_2)``.

    The second channel is None when it is not asked for, or no longer in the
    file.
    """
    from emgteach.io import read_edf_mne

    edf = read_edf_mne(edf_path, channel_name)
    raw_2 = None
    if channel_name_2:
        try:
            raw_2 = read_edf_mne(edf_path, channel_name_2)["emg_raw"]
        except Exception:  # pragma: no cover — channel gone from the file
            raw_2 = None
    return edf["emg_raw"], float(edf["sfreq"]), raw_2


def envelope(raw: np.ndarray | None, fs: float,
             filter_kwargs: Mapping[str, float]) -> np.ndarray | None:
    """The envelope of a channel, or None when there is no channel."""
    if raw is None:
        return None
    try:
        f = filters(filter_kwargs)
        return process_offline(
            raw, fs, f_low=f["f_low"], f_high=f["f_high"], f_notch=f["f_notch"],
            f_env=f["f_env"],
        )["emg_envelope"]
    except Exception:  # pragma: no cover — very short/degenerate signal
        return np.abs(raw)


def to_hundredths(filas: list[Segment]) -> list[Segment]:
    """Rows as the table holds them — hundredths of a second — and at least a
    hundredth apart.

    The detector's split pieces share their boundary sample, so two rows could
    touch, and fragments that touch are merged before the analysis: the editor
    showed a contraction more than the analysis measured, without a word.
    Rounding the ends inward, and moving a touching start past the end before
    it, keeps each row its own fragment.
    """
    out: list[Segment] = []
    for f in sorted(filas, key=lambda s: s.start_s):
        a = float(np.ceil(round(f.start_s * 100.0, 6))) / 100.0
        b = float(np.floor(round(f.end_s * 100.0, 6))) / 100.0
        if out and a <= out[-1].end_s:
            a = round(out[-1].end_s + 0.01, 2)
        if b > a:
            out.append(Segment(a, b, f.score, f.reason, f.label))
    return out


def detect(
    raw: np.ndarray,
    fs: float,
    filter_kwargs: Mapping[str, float],
    detection: Mapping[str, float],
    k: float,
    span: tuple[float, float],
    raw_2: np.ndarray | None = None,
) -> list[Segment]:
    """What the detector finds at sensitivity ``k`` in the span, in the file's clock.

    Both muscles, not just the one on display: the selection crops *both*
    channels, so proposing only the contractions of the channel that happens
    to be selected quietly decided which half of the session got analysed.
    """
    a, b = span
    i0, i1 = round(a * fs), round(b * fs)
    f = filters(filter_kwargs)

    def detecta(canal: np.ndarray) -> list[Segment]:
        return suggest_significant_segments(
            canal[i0:i1],
            fs,
            f_low=f["f_low"],
            f_high=f["f_high"],
            f_notch=f["f_notch"],
            f_env=f["f_env"],
            k=k,
            min_duration_s=detection["min_duration_s"],
            merge_gap_s=detection["merge_gap_s"],
            prominence=detection["prominence"],
            rest_fraction=detection.get("rest_fraction", 0.0),
        )

    # Back into the file's own clock: the worker crops by these numbers.
    filas = [
        Segment(a + x.start_s, a + x.end_s, x.score, x.reason, x.label)
        for x in detecta(raw)
    ]
    if raw_2 is not None:
        filas += [
            Segment(a + x.start_s, a + x.end_s, x.score, x.reason, x.label)
            for x in detecta(raw_2)
        ]
        filas = normalise_segments(filas, len(raw) / fs)
    return to_hundredths(filas)


def rest_level(env: np.ndarray, fs: float, span: tuple[float, float], k: float) -> float:
    """The level a row's contraction is measured out to, for one envelope.

    The line half the sensitivity draws, never above the detector's own.
    """
    a0, b0 = span
    tramo = np.asarray(env[round(a0 * fs):round(b0 * fs)], dtype=np.float64)
    _b, umbral = activity_threshold(tramo, k)
    _b, reposo = activity_threshold(tramo, max(_K_CANDIDATE_MIN, k * _K_CANDIDATE))
    return min(reposo, umbral)


def fit_to_envelope(
    filas: list[Segment],
    envs: Sequence[np.ndarray],
    fs: float,
    span: tuple[float, float],
    detection: Mapping[str, float],
) -> list[Segment]:
    """Each row from where its contraction leaves rest to where it returns.

    For every channel whose envelope clears the detector's line inside
    the row — for as long as the detector asks of a contraction —, start
    at the row's peak on that envelope and walk out on each side while
    the envelope stays above rest. Rest is the line half the sensitivity
    draws, dotted on the plot, the one the candidates are found with:
    the detector's own line cuts the foot of the rise and the end of the
    fall, which is what had to be widened by hand, and a share of the
    peak was tried and rejected — on an intense contraction any share
    above zero ended the row earlier than the detector did. The row is
    the union over those
    channels, plus ``_BORDE_MARGEN_S`` either side, and never reaches
    into the row before or after it or out of the span. A row no
    channel clears is left as it was, and so is a lift's window that
    stands in for a contraction the detector did not find.

    Walking from the peak, a row that held a contraction and the tail
    of something else keeps the contraction; which is what a lift that
    the detector had run into the next second needed.
    """
    if not filas:
        return filas
    a0, b0 = span
    i0, i1 = round(a0 * fs), round(b0 * fs)
    k = detection["k"]
    minimo = max(1, round(detection["min_duration_s"] * fs))
    canales = []
    for env in envs:
        tramo = np.asarray(env[i0:i1], dtype=np.float64)
        _base, umbral = activity_threshold(tramo, k)
        canales.append((env, umbral, rest_level(env, fs, span, k)))
    orden = sorted(filas, key=lambda f: f.start_s)
    salida: list[Segment] = []
    for n, f in enumerate(orden):
        antes = salida[-1].end_s if salida else a0
        despues = orden[n + 1].start_s if n + 1 < len(orden) else b0
        lo, hi = round(antes * fs), round(despues * fs) - 1
        j0 = max(lo, round(f.start_s * fs))
        j1 = min(hi + 1, round(f.end_s * fs))
        ini = fin = None
        # A lift's window proposed because nothing was detected in it
        # has no contraction to fit, and is there to be looked at.
        for env, umbral, reposo in ([] if f.reason == "marker" else canales):
            if j1 <= j0:
                break
            pico = j0 + int(np.argmax(env[j0:j1]))
            if env[pico] <= umbral:
                continue
            # Held over the line as long as the detector asks of a
            # contraction: a flicker of noise over it is not one.
            sobre_i = sobre_d = pico
            while sobre_i > lo and env[sobre_i - 1] > umbral:
                sobre_i -= 1
            while sobre_d < hi and env[sobre_d + 1] > umbral:
                sobre_d += 1
            if sobre_d - sobre_i + 1 < minimo:
                continue
            izq = pico
            while izq > lo and env[izq - 1] > reposo:
                izq -= 1
            der = pico
            while der < hi and env[der + 1] > reposo:
                der += 1
            ini = izq if ini is None else min(ini, izq)
            fin = der if fin is None else max(fin, der)
        if ini is None or fin is None:
            salida.append(f)
            continue
        a = max(antes, ini / fs - _BORDE_MARGEN_S)
        b = min(despues, (fin + 1) / fs + _BORDE_MARGEN_S)
        salida.append(Segment(a, b, f.score, f.reason, f.label) if b > a else f)
    return to_hundredths(salida)


def one_per_lift(
    detectadas: list[Segment],
    lifts: Sequence[tuple[float, float]],
    envs: Sequence[np.ndarray],
    fs: float,
    span: tuple[float, float],
    detection: Mapping[str, float],
) -> list[Segment]:
    """One row per lift the wizard marked, and nothing else.

    Each lift takes the contraction its marker announced; a lift whose
    window the detector found nothing in is proposed as the window, to
    be looked at rather than lost. What is left over stays a candidate.

    The contraction is **cut to the lift's window**, from half a second
    before the cue (``_ANTICIPO_S``: a lift can start a little ahead of
    it) to the window's end. The detector joins the lift to whatever
    the muscle did just before, and just before the cue it was picking
    up the weight: on the bench one row began four seconds early.

    And the other way round, the detector can **split** a lift at a dip:
    in a rehearsal the first lift came out as 48.16-48.64 and
    48.65-49.42 s, and the cue took the first half, a row of 0.48 s
    where the others lasted 1.5 to 2. A piece starting less than
    ``_UNION_S`` after the one the cue took, inside the same window and
    claimed by no other cue, is joined to it before the row is cut.
    """
    duenos = marker_owners(
        [a for a, _b in lifts],
        [(f.start_s, f.end_s) for f in detectadas])
    tomadas = {j for j in duenos if j is not None}
    orden = sorted(range(len(detectadas)), key=lambda k: detectadas[k].start_s)
    elegidas: list[Segment] = []
    for (a, b), j in zip(lifts, duenos, strict=True):
        if j is None:
            elegidas.append(Segment(a, b, reason="marker"))
            continue
        f = detectadas[j]
        fin_trozo = f.end_s
        for k in orden:
            g = detectadas[k]
            if k == j or g.start_s < f.start_s:
                continue
            if (k in tomadas or g.start_s - fin_trozo >= _UNION_S
                    or g.start_s >= b):
                break
            fin_trozo = max(fin_trozo, g.end_s)
        elegidas.append(Segment(f.start_s, fin_trozo, f.score, f.reason, f.label))
    # The edges by the envelope, and then the lift's own window.
    filas = []
    ajustadas = fit_to_envelope(elegidas, envs, fs, span, detection)
    for (a, b), f in zip(lifts, ajustadas, strict=True):
        ini, fin = max(f.start_s, a - _ANTICIPO_S), min(f.end_s, b)
        filas.append(Segment(ini, fin, f.score, f.reason, f.label)
                     if fin > ini else f)
    return to_hundredths(filas)


def fit_rows(
    detectadas: list[Segment],
    lifts: Sequence[tuple[float, float]],
    envs: Sequence[np.ndarray],
    fs: float,
    span: tuple[float, float],
    detection: Mapping[str, float],
) -> list[Segment]:
    """The detector's rows as the editor proposes them: one per lift when the
    recording has the wizard's lifts, each widened to its contraction when not."""
    if lifts:
        return one_per_lift(detectadas, lifts, envs, fs, span, detection)
    return fit_to_envelope(detectadas, envs, fs, span, detection)


def suggest_fragments(
    raw: np.ndarray,
    fs: float,
    filter_kwargs: Mapping[str, float],
    *,
    span: tuple[float, float] | None = None,
    raw_2: np.ndarray | None = None,
    detection: Mapping[str, float] | None = None,
    default_k: float | None = None,
    lifts: Sequence[tuple[float, float]] | None = None,
    rest_fraction: float = 0.0,
) -> list[Segment]:
    """The fragments the editor proposes when it opens, without its names.

    The same inputs as ``FragmentSelectionDialog``: ``detection`` overrides
    the practical's ``default_k`` and the core defaults, as the editor's
    sliders do.
    """
    raw = np.asarray(raw, dtype=np.float64).ravel()
    raw_2 = None if raw_2 is None else np.asarray(raw_2, dtype=np.float64).ravel()
    tramo = span_within(span, len(raw) / fs)
    det = default_detection(default_k, rest_fraction)
    if detection:
        det.update({k: float(v) for k, v in detection.items() if k in det})
    envs = [e for e in (envelope(raw, fs, filter_kwargs),
                        envelope(raw_2, fs, filter_kwargs)) if e is not None]
    filas = detect(raw, fs, filter_kwargs, det, det["k"], tramo, raw_2)
    return fit_rows(filas, [(float(a), float(b)) for a, b in (lifts or ())],
                    envs, fs, tramo, det)
