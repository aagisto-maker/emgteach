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
    ROW_LEAD_S,
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
    "one_per_step",
    "read_channels",
    "recording_proposal",
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
#: Where fragments end only at rest, the shortest stretch that counts at the
#: end of a row: the envelope at or under the dotted rest line, or rising
#: again from the bottom of its fall, for less than this is noise, and
#: neither ends the row sooner nor holds it open (as
#: emgteach.selection._FLICKER_S).
_CAIDA_MIN_S = 0.1


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

    Where fragments end only at rest (``detection["rest_fraction"]``, the
    one-muscle practical), rest is that rule's: the baseline plus that
    share of the row's peak above it, the line its end was found at. And
    the row starts :data:`emgteach.selection.ROW_LEAD_S` before its
    contraction leaves it, the same for every row: on the noise of a
    lower line, a step began half a second before its flank and the next
    on it (the bench with exe #143).

    That share of the peak still separates two contractions, but it is not
    where the row ends. The row follows the fall that carries on from it
    to the first point where the envelope is back at the dotted rest line;
    or, if it rises again before getting there, to the bottom of the fall
    (:func:`_fin_de_la_caida`). What rises after that — a hump, a second
    twitch — is not the row's and stays dotted, a click away. On a strong
    step 5 % of the peak is many times the rest, and the end of the letting
    go after the cue was left out (Ángel's gradation of 6 November 2026).
    And the row runs from the first to the last contraction the detector put
    in it — a peak at least ``detection["prominence"]`` of the tallest one's
    height, the share the detector itself asks of a contraction of its own:
    a series of brisk contractions with less than a second of rest between
    them is one fragment by the rule of 27 October, and walked from its
    tallest peak it was cut at the first dip, its other contractions left
    dotted beside it (the bench's free recording of the same day). A hump
    after the fall, a seventh or an eighth of the step's height, is not one.
    """
    if not filas:
        return filas
    a0, b0 = span
    i0, i1 = round(a0 * fs), round(b0 * fs)
    k = detection["k"]
    fraccion = float(detection.get("rest_fraction", 0.0))
    minimo = max(1, round(detection["min_duration_s"] * fs))
    breve = max(1, round(_CAIDA_MIN_S * fs))
    canales = []
    for env in envs:
        tramo = np.asarray(env[i0:i1], dtype=np.float64)
        base, umbral = activity_threshold(tramo, k)
        canales.append((env, base, umbral, rest_level(env, fs, span, k)))
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
        for env, base, umbral, reposo in ([] if f.reason == "marker" else canales):
            if j1 <= j0:
                break
            linea = reposo                 # the dotted line, whatever rule ends the row
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
            if fraccion > 0.0:
                reposo = base + fraccion * (float(env[pico]) - base)
            izq = der = pico
            if fraccion > 0.0:
                # From the first to the last contraction the detector put in
                # the row — a peak a share of the tallest high, its own rule
                # for a contraction — not only the tallest one.
                alto = base + detection["prominence"] * (float(env[pico]) - base)
                grandes = j0 + np.flatnonzero(env[j0:j1] > alto)
                izq, der = int(grandes[0]), int(grandes[-1])
            while izq > lo and env[izq - 1] > reposo:
                izq -= 1
            while der < hi and env[der + 1] > reposo:
                der += 1
            if fraccion > 0.0:
                der = _fin_de_la_caida(env, der, hi, linea,
                                       max(linea - base, 0.0), breve)
            ini = izq if ini is None else min(ini, izq)
            fin = der if fin is None else max(fin, der)
        if ini is None or fin is None:
            salida.append(f)
            continue
        a = max(antes, ini / fs - (ROW_LEAD_S if fraccion > 0.0 else _BORDE_MARGEN_S))
        b = min(despues, (fin + 1) / fs + _BORDE_MARGEN_S)
        salida.append(Segment(a, b, f.score, f.reason, f.label) if b > a else f)
    return to_hundredths(salida)


def _fin_de_la_caida(env: np.ndarray, der: int, hi: int, linea: float,
                     margen: float, breve: int) -> int:
    """The last sample of the fall that carries on from sample *der*, never
    past *hi*.

    The fall ends at the first point where the envelope is back at the
    dotted rest line *linea* — the sample before it — or, if the envelope
    rises again before getting there, more than *margen* over the lowest
    point it had reached, at that lowest point: what rises then is not the
    fall. Either has to hold for *breve* samples, or the end of the row
    would move with the noise.
    """
    fondo = der
    j = der + 1
    while j <= hi:
        v = env[j]
        if v <= linea:
            if np.all(env[j:min(hi + 1, j + breve)] <= linea):
                return j - 1
        elif v > env[fondo] + margen:
            if np.all(env[j:min(hi + 1, j + breve)] > env[fondo] + margen):
                return fondo
        elif v < env[fondo]:
            fondo = j
        j += 1
    return hi


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


def one_per_step(
    detectadas: list[Segment],
    steps: Sequence[tuple[float, float]],
    envs: Sequence[np.ndarray],
    fs: float,
    span: tuple[float, float],
    detection: Mapping[str, float],
) -> list[Segment]:
    """One row per step of a gradation, and nothing else.

    *steps* are the steps' windows in file time, from the mark that opens
    each to where its contraction may still be letting go
    (:func:`emgteach.guided.step_windows`). A step takes the detected row
    that overlaps its window — from ``_ANTICIPO_S`` before its mark — the
    most, with any other row not yet taken that starts inside it; a step
    the detector found nothing in is proposed as its window, to be looked
    at. What falls outside every step stays a candidate, a click away: on
    the bench of 6 November 2026 a jerk at the start of the recording was
    a sixth row for five steps. Each row is then fitted to its contraction
    (:func:`fit_to_envelope`), out to rest.
    """
    tomadas: set[int] = set()
    elegidas: list[Segment] = []
    for a_marca, b in steps:
        a = a_marca - _ANTICIPO_S
        solape = [(min(b, f.end_s) - max(a, f.start_s), j)
                  for j, f in enumerate(detectadas) if j not in tomadas]
        solape = [(s, j) for s, j in solape if s > 0.0]
        if not solape:
            elegidas.append(Segment(a_marca, b, reason="marker"))
            continue
        _s, j = max(solape)
        suyas = [j] + [k for k, f in enumerate(detectadas)
                       if k not in tomadas and k != j and a <= f.start_s < b]
        tomadas.update(suyas)
        f = detectadas[j]
        elegidas.append(Segment(min(detectadas[k].start_s for k in suyas),
                                max(detectadas[k].end_s for k in suyas),
                                f.score, f.reason, f.label))
    return fit_to_envelope(elegidas, envs, fs, span, detection)


def fit_rows(
    detectadas: list[Segment],
    lifts: Sequence[tuple[float, float]],
    envs: Sequence[np.ndarray],
    fs: float,
    span: tuple[float, float],
    detection: Mapping[str, float],
    steps: Sequence[tuple[float, float]] = (),
) -> list[Segment]:
    """The detector's rows as the editor proposes them: one per lift when the
    recording has the wizard's lifts, one per step when it has a gradation,
    each widened to its contraction when neither."""
    if lifts:
        return one_per_lift(detectadas, lifts, envs, fs, span, detection)
    if steps:
        return one_per_step(detectadas, steps, envs, fs, span, detection)
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
    steps: Sequence[tuple[float, float]] | None = None,
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
                    envs, fs, tramo, det,
                    [(float(a), float(b)) for a, b in (steps or ())])


def recording_proposal(
    edf_path: str,
    *,
    k: float | None = None,
    rest_fraction: float = 0.0,
    filter_kwargs: Mapping[str, float] | None = None,
) -> list[Segment]:
    """What the fragment editor proposes when it opens on *edf_path*, in the
    file's clock, read from the file alone.

    The same rules the analysis tab hands the editor: the recording phase as
    the span; a fixed load or a train of quick contractions as the one row
    its analysis reads (:func:`emgteach.guided.load_row`,
    :func:`emgteach.guided.train_span`); one row per lift the wizard marked,
    or per step of a gradation; otherwise what the detector finds, at the
    practical's ``k`` and ``rest_fraction``. On the file's first two EMG
    channels. The review of a recording draws these, so what it shows is
    what the editor will propose (Ángel, 6 November 2026).
    """
    from emgteach.force_velocity import lift_windows_s, parse_fv_load_markers
    from emgteach.guided import load_row, step_windows, train_span
    from emgteach.io import edf_duration, list_edf_emg_channels, read_edf_markers
    from emgteach.phases import parse_phase_markers
    from emgteach.sessions import parse_session_markers

    nombres = list_edf_emg_channels(edf_path)
    if not nombres:
        return []
    marcas = read_edf_markers(edf_path)
    duracion = edf_duration(edf_path)
    cargas = parse_fv_load_markers(marcas)
    span = parse_phase_markers(marcas).rec_span(duracion, cargas)
    raw, fs, raw_2 = read_channels(edf_path, nombres[0],
                                   nombres[1] if len(nombres) > 1 else None)
    filtros = filters(filter_kwargs or {})
    sesion = parse_session_markers(marcas)
    if sesion is not None:
        env = envelope(raw, fs, filtros)
        ventana = load_row(sesion, env, fs) or train_span(sesion, env, fs)
        if ventana is not None:
            return [Segment(float(ventana[0]), float(ventana[1]), reason="session")]
    filas = suggest_fragments(
        raw, fs, filtros, span=span, raw_2=raw_2, default_k=k,
        lifts=lift_windows_s(cargas, duracion) if cargas else None,
        rest_fraction=rest_fraction, steps=step_windows(sesion),
    )
    return [f for f in filas if f.reason != "whole"]
