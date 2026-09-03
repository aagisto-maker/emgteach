"""One row per contraction: the bridge between the trace and the physiology.

The student makes six efforts and used to receive one global RMS. The
figure showed six bursts; the number described the eighteen seconds around
them. What a laboratory table needs is the six: when each one was, how long
it lasted, how hard it was against the maximum, and where its spectrum sat.
This module produces exactly that, from the same contraction proposer the
fragment editor uses, so the rows here are the rows the student would see
there.

Everything is computed on the analysed span and expressed in its clock, so
``start_s`` lines up with the panels' time axis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from emgteach.coactivation import dominant_muscle, resting_level
from emgteach.dsp import compute_psd_mnf_mdf
from emgteach.selection import Segment, normalise_segments, suggest_significant_segments

#: A contraction shorter than this has too few cycles of anything for a
#: median frequency to mean something; the row still shows its RMS.
_MIN_S_FOR_MDF = 0.25

#: Where the movement is taken to begin, as a share of its peak above rest
#: within the contraction. High enough to sit above the noise of an
#: uncalibrated accelerometer, low enough to catch the start of the rise.
_MOVE_ONSET_FRACTION = 0.20

#: Electromechanical delays outside this range are not delays: a negative
#: one means the movement began before the muscle fired (a different
#: movement, or a bounce), and a very long one means no movement followed.
_EMD_RANGE_MS = (0.0, 400.0)

#: A proposed window whose peak above rest is below this share of the
#: recording's strongest peak is noise the detector let through, not a
#: contraction, and gets no row.
_NOISE_FRACTION = 0.10


@dataclass(frozen=True)
class Contraction:
    """What one contraction was worth.

    ``muscle`` is the name of the muscle the numbers belong to: with two
    channels, the one that led the contraction (or ``both_label`` for a
    co-contraction, in which case the numbers are the stronger muscle's);
    with one channel, that channel's name. ``peak_pct`` is the highest
    *sustained* level (the reference's own half-second window) against the
    reference, and is ``None`` without one. ``emd_ms`` is the
    electromechanical delay — from the electrical onset to the start of the
    movement — where an accelerometer on the moving segment allows it.
    """

    n: int
    start_s: float
    end_s: float
    muscle: str
    rms_mv: float
    peak_pct: float | None
    mdf_hz: float | None
    emd_ms: float | None = None

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def _running_mean_max(env: np.ndarray, w: int) -> float:
    """The highest mean over a window of ``w`` samples (the sustained peak)."""
    if env.size == 0:
        return 0.0
    if w <= 1 or env.size < w:
        return float(np.max(env))
    kernel = np.ones(w, dtype=np.float64) / float(w)
    return float(np.max(np.convolve(env, kernel, mode="valid")))


def _onset_s(
    signal: np.ndarray, fs: float, i0: int, i1: int, rest: float
) -> float | None:
    """First moment after ``i0`` where ``signal`` clearly rises.

    Used for the muscle and for the limb alike, at the same fraction of
    each one's own peak: an onset taken at the threshold crossing for one
    and at a fifth of the peak for the other would put most of the
    envelope's rise time into the delay.
    """
    tramo = signal[i0:i1]
    if tramo.size == 0:
        return None
    pico = float(np.max(tramo)) - rest
    if pico <= 0.0:
        return None
    umbral = rest + _MOVE_ONSET_FRACTION * pico
    idx = np.flatnonzero(tramo > umbral)
    if idx.size == 0:
        return None
    return (i0 + int(idx[0])) / fs


def contraction_table(
    *,
    fs: float,
    emg_raw,
    emg_filtered,
    envelope,
    mvc_ref: float | None = None,
    emg_raw_2=None,
    emg_filtered_2=None,
    envelope_2=None,
    mvc_ref_2: float | None = None,
    name_1: str = "",
    name_2: str = "",
    both_label: str = "both",
    movement=None,
    f_low: float = 20.0,
    f_high: float = 450.0,
    f_notch: float = 50.0,
    f_env: float = 5.0,
    window_s: float = 0.5,
) -> list[Contraction]:
    """The contractions of the analysed span, one row each.

    The proposer is run on each channel and the two lists are merged, as the
    fragment editor does, so a series of flexions and extensions yields every
    effort and not only those of the channel on display. A span with no
    clear activity yields an empty list, not a row for the whole recording:
    a table that said «contraction 1: 0.0-18.2 s» would be describing the
    absence of one.
    """
    raw = np.asarray(emg_raw, dtype=np.float64).ravel()
    filt = np.asarray(emg_filtered, dtype=np.float64).ravel()
    env = np.asarray(envelope, dtype=np.float64).ravel()
    n = raw.size
    if n == 0:
        return []
    total_s = n / fs
    filtros = dict(f_low=f_low, f_high=f_high, f_notch=f_notch, f_env=f_env)

    segs = [s for s in suggest_significant_segments(raw, fs, **filtros)
            if s.reason != "whole"]
    dos = emg_raw_2 is not None and envelope_2 is not None
    env2 = np.asarray(envelope_2, dtype=np.float64).ravel() if dos else None
    filt2 = (np.asarray(emg_filtered_2, dtype=np.float64).ravel()
             if dos and emg_filtered_2 is not None else None)
    if dos:
        raw2 = np.asarray(emg_raw_2, dtype=np.float64).ravel()
        segs += [s for s in suggest_significant_segments(raw2, fs, **filtros)
                 if s.reason != "whole"]
        segs = normalise_segments(segs, total_s)
    if not segs:
        return []

    w = max(1, round(window_s * fs))
    move = np.asarray(movement, dtype=np.float64).ravel() if movement is not None else None
    rest_move = resting_level(move) if move is not None else 0.0
    cola = round(0.5 * fs)

    # Each muscle's resting level and its strongest peak above it. A proposed
    # window whose peak is a small fraction of that is the detector reacting
    # to noise — on a recording with a very quiet rest its threshold sits
    # just above the floor — and it must not appear here as a row, least of
    # all as a «co-contraction» of two muscles that were both silent.
    rest1 = resting_level(env)
    rest2 = resting_level(env2) if env2 is not None else 0.0
    pmax1 = float(np.max(env)) - rest1
    pmax2 = (float(np.max(env2)) - rest2) if env2 is not None else 0.0
    suelo = _NOISE_FRACTION * max(pmax1, pmax2)

    filas: list[Contraction] = []
    for s in segs:
        i0, i1 = max(0, round(s.start_s * fs)), min(n, round(s.end_s * fs))
        if i1 <= i0:
            continue
        p1 = float(np.max(env[i0:i1])) - rest1
        p2 = (float(np.max(env2[i0:i1])) - rest2) if env2 is not None else 0.0
        if max(p1, p2) < suelo:
            continue
        # Which muscle these numbers belong to.
        canal = 1
        nombre = name_1
        if dos and env2 is not None:
            lider = dominant_muscle(env, env2, fs, (s.start_s, s.end_s),
                                    ref_1=mvc_ref, ref_2=mvc_ref_2)
            if lider == 2:
                canal, nombre = 2, name_2
            elif lider is None:
                # A co-contraction shows the stronger muscle's numbers, and
                # "stronger" is a share of each one's own maximum wherever
                # there is one: in millivolts the muscle with the closer
                # electrodes wins every time.
                nombre = both_label
                if mvc_ref and mvc_ref_2:
                    canal = 2 if p2 / mvc_ref_2 > p1 / mvc_ref else 1
                else:
                    canal = 2 if p2 > p1 else 1
        k = len(filas) + 1
        e = env2 if (canal == 2 and env2 is not None) else env
        f = filt2 if (canal == 2 and filt2 is not None) else filt
        ref = mvc_ref_2 if canal == 2 else mvc_ref

        rms = float(np.sqrt(np.mean(f[i0:i1] ** 2))) if f.size else 0.0
        pico = None
        if ref:
            pico = 100.0 * _running_mean_max(e[i0:i1], w) / float(ref)
        mdf = None
        if (i1 - i0) / fs >= _MIN_S_FOR_MDF and f.size:
            try:
                mdf = float(compute_psd_mnf_mdf(
                    f[i0:i1], fs, f_low=f_low, f_high=f_high,
                    nperseg=min(int(fs), i1 - i0))["mdf"])
            except Exception:
                mdf = None
        emd = None
        if move is not None and move.size >= i1:
            fin = min(move.size, i1 + cola)
            t_emg = _onset_s(e, fs, i0, fin, resting_level(e))
            t_move = _onset_s(move, fs, i0, fin, rest_move)
            if t_emg is not None and t_move is not None:
                candidato = (t_move - t_emg) * 1000.0
                if _EMD_RANGE_MS[0] <= candidato <= _EMD_RANGE_MS[1]:
                    emd = candidato
        filas.append(Contraction(
            n=k, start_s=float(s.start_s), end_s=float(s.end_s), muscle=nombre,
            rms_mv=rms, peak_pct=pico, mdf_hz=mdf, emd_ms=emd,
        ))
    return filas


def mean_emd_ms(rows: list[Contraction]) -> float | None:
    """The mean electromechanical delay over the rows that have one."""
    valores = [r.emd_ms for r in rows if r.emd_ms is not None]
    return float(np.mean(valores)) if valores else None


__all__ = ["Contraction", "Segment", "contraction_table", "mean_emd_ms"]
