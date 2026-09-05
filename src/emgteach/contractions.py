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

from collections.abc import Iterable, Sequence
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
#: or a near-zero one means the movement was already under way when the
#: muscle fired (a different movement, a bounce, the smoothing's own
#: spread), and a very long one means no movement followed.
_EMD_RANGE_MS = (5.0, 400.0)

#: How far after the muscle's onset the movement is looked for.
_MOVE_SEARCH_S = 1.0

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
    #: Which channel the numbers above belong to (1 or 2), and what the
    #: *other* muscle did meanwhile in a two-channel recording — ``None``
    #: with one channel. The table shows the leader; the chart shows both,
    #: side by side, which is where a co-activation is seen rather than read.
    channel: int = 1
    rms_mv_other: float | None = None
    peak_pct_other: float | None = None
    #: Peak velocity of the segment over the contraction, in the arbitrary
    #: units of an uncalibrated accelerometer; ``None`` without one.
    velocity_au: float | None = None

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def by_muscle(self, which: int) -> tuple[float, float | None]:
        """``(rms_mv, peak_pct)`` of muscle 1 or 2, whichever led."""
        if which == self.channel:
            return self.rms_mv, self.peak_pct
        return (self.rms_mv_other or 0.0), self.peak_pct_other


def _movement_after(
    move: np.ndarray, fs: float, i_emg: int, rest: float,
) -> float | None:
    """When the segment began to move once the muscle had fired.

    The first sample past ``i_emg`` above rest plus a fifth of the rise the
    movement makes in the second that follows. The muscle's own onset is
    found by walking back from its peak; doing the same for the movement
    found the lowering of the load as often as the lift — an effort with a
    weight is two accelerations, and the second is often the bigger — and
    put the delay at the wrong end of the effort, three hundred
    milliseconds and more.
    """
    fin = min(move.size, i_emg + round(_MOVE_SEARCH_S * fs))
    if fin <= i_emg or i_emg < 0:
        return None
    tramo = move[i_emg:fin]
    pico = float(np.max(tramo)) - rest
    if pico <= 0.0:
        return None
    umbral = rest + _MOVE_ONSET_FRACTION * pico
    idx = np.flatnonzero(tramo > umbral)
    if idx.size == 0:
        return None
    return (i_emg + int(idx[0])) / fs


def _recortar_al_esfuerzo(
    seg: Segment, fs: float, actividad: np.ndarray,
) -> Segment:
    """The stretch of ``seg`` in which the effort was made: from the first
    sample above a fifth of the segment's peak activity to the last.

    A fragment is drawn round an effort, not on it — the editor's proposals
    carry their rise and fall, the wizard's windows start at the cue and
    run to the next — and a row's RMS over the rest on either side would be
    the rest's number as much as the effort's. A segment with no activity
    in it is kept as it is.
    """
    i0, i1 = max(0, round(seg.start_s * fs)), min(actividad.size, round(seg.end_s * fs))
    if i1 <= i0:
        return seg
    tramo = actividad[i0:i1]
    pico = float(np.max(tramo))
    if pico <= 0.0:
        return seg
    activo = np.flatnonzero(tramo > _MOVE_ONSET_FRACTION * pico)
    if activo.size == 0:
        return seg
    return Segment((i0 + int(activo[0])) / fs, (i0 + int(activo[-1]) + 1) / fs,
                   label=seg.label)


def _fast_envelope(x: np.ndarray, fs: float, win_s: float = 0.05) -> np.ndarray:
    """The rectified signal averaged over ``win_s``: an envelope fast enough
    to place an onset by. The 5 Hz envelope of the panels spreads each rise
    tens of milliseconds to either side, which is the size of the delay
    being measured."""
    w = max(1, round(win_s * fs))
    return np.convolve(np.abs(np.asarray(x, dtype=np.float64)), np.ones(w) / w,
                       mode="same")


def _running_mean_max(env: np.ndarray, w: int) -> float:
    """The highest mean over a window of ``w`` samples (the sustained peak)."""
    if env.size == 0:
        return 0.0
    if w <= 1 or env.size < w:
        return float(np.max(env))
    kernel = np.ones(w, dtype=np.float64) / float(w)
    return float(np.max(np.convolve(env, kernel, mode="valid")))


def _onset_s(
    signal: np.ndarray, fs: float, i0: int, i1: int, rest: float, back: int = 0,
) -> float | None:
    """When the rise that leads to the peak in ``[i0, i1)`` began.

    From the peak, back while the signal stays above rest plus a fifth of
    the peak's height; the search may reach ``back`` samples before ``i0``.
    Used for the muscle and for the limb alike, at the same fraction of each
    one's own peak: an onset taken at the threshold crossing for one and at
    a fifth of the peak for the other would put most of the envelope's rise
    time into the delay.

    Scanning forward from ``i0`` took the window's first sample for the
    onset whenever the window began, as the detector's do, on the threshold
    crossing — the muscle was already up, the limb often too, and the delay
    came out as zero on the bench. Walking back from the peak finds the rise
    this contraction made and stops at the rest between it and the one
    before, instead of running into that one's tail.
    """
    if i1 <= i0 or i0 >= signal.size:
        return None
    i1 = min(i1, signal.size)
    cima = i0 + int(np.argmax(signal[i0:i1]))
    pico = float(signal[cima]) - rest
    if pico <= 0.0:
        return None
    umbral = rest + _MOVE_ONSET_FRACTION * pico
    ini = max(0, i0 - int(back))
    j = cima
    while j > ini and signal[j - 1] > umbral:
        j -= 1
    return j / fs


def load_of_each(
    rows: Sequence[Contraction],
    load_markers: Iterable[tuple[float, float]],
    max_window_s: float = 6.5,
) -> list[float | None]:
    """The load, in kg, each contraction was made under — or ``None``.

    ``load_markers`` are the ``(onset_s, load_kg)`` pairs the guided
    force-velocity wizard left at the start of each load's window (see
    :func:`emgteach.force_velocity.parse_fv_load_markers`; the analysis
    worker hands them over as ``fv_loads``, in the analysed span's own
    time). A contraction belongs to the last marker before its midpoint,
    provided the midpoint falls within ``max_window_s`` of it — the wizard's
    windows are six seconds. A contraction with no marker close enough (the
    calibration efforts, a recording made without the wizard) gets ``None``,
    and the chart that groups by load puts those in a group of their own
    rather than losing them.
    """
    marcas = sorted((float(t), float(kg)) for t, kg in load_markers)
    out: list[float | None] = []
    for r in rows:
        mid = 0.5 * (float(r.start_s) + float(r.end_s))
        carga: float | None = None
        for onset, kg in marcas:
            if onset <= mid + 0.5:
                carga = kg if mid - onset <= max_window_s else None
            else:
                break
        out.append(carga)
    return out


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
    velocity=None,
    segments: Sequence[Segment] | None = None,
    f_low: float = 20.0,
    f_high: float = 450.0,
    f_notch: float = 50.0,
    f_env: float = 5.0,
    window_s: float = 0.5,
    k: float = 3.0,
    min_duration_s: float = 0.5,
    merge_gap_s: float = 0.3,
    prominence: float = 0.25,
    both_ratio: float = 0.5,
) -> list[Contraction]:
    """The contractions of the analysed span, one row each.

    ``k``, ``min_duration_s``, ``merge_gap_s`` and ``prominence`` are the
    detection settings of :func:`suggest_significant_segments`, and
    ``both_ratio`` the co-activation rule of :func:`dominant_muscle`: the
    same numbers the fragment editor lets the student move, so the rows here
    are the rows they saw there.

    The proposer is run on each channel and the two lists are merged, as the
    fragment editor does, so a series of flexions and extensions yields every
    effort and not only those of the channel on display. A span with no
    clear activity yields an empty list, not a row for the whole recording:
    a table that said «contraction 1: 0.0-18.2 s» would be describing the
    absence of one.

    With ``segments`` — the fragments the operator accepted, in this span's
    time — nothing is detected: those are the rows, in that order, numbered
    as the editor numbered them. Detecting again inside their concatenation
    renumbered them and split or merged a few, and the chart said «7» of
    what the editor had called «12». ``velocity`` is the segment's velocity
    from :func:`emgteach.force_velocity.velocity_from_acc`, sampled with the
    signal; each row takes its peak over the contraction.
    """
    raw = np.asarray(emg_raw, dtype=np.float64).ravel()
    filt = np.asarray(emg_filtered, dtype=np.float64).ravel()
    env = np.asarray(envelope, dtype=np.float64).ravel()
    n = raw.size
    if n == 0:
        return []
    total_s = n / fs
    filtros = dict(
        f_low=f_low, f_high=f_high, f_notch=f_notch, f_env=f_env,
        k=k, min_duration_s=min_duration_s, merge_gap_s=merge_gap_s,
        prominence=prominence,
    )

    dos = emg_raw_2 is not None and envelope_2 is not None
    env2 = np.asarray(envelope_2, dtype=np.float64).ravel() if dos else None
    filt2 = (np.asarray(emg_filtered_2, dtype=np.float64).ravel()
             if dos and emg_filtered_2 is not None else None)
    if segments is not None:
        # Each fragment trimmed to the effort inside it, on whichever
        # muscle rose more above its rest.
        actividad = env - resting_level(env)
        if env2 is not None:
            actividad = np.maximum(actividad, env2 - resting_level(env2))
        segs = [_recortar_al_esfuerzo(s, fs, actividad)
                for s in segments if s.end_s > s.start_s]
    else:
        segs = [s for s in suggest_significant_segments(raw, fs, **filtros)
                if s.reason != "whole"]
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
    vel = np.asarray(velocity, dtype=np.float64).ravel() if velocity is not None else None
    cola = round(0.5 * fs)
    # Fast envelopes for the onsets alone; every other number comes from
    # the envelope the panels show.
    e_rapida = _fast_envelope(filt, fs) if move is not None else None
    e_rapida2 = (_fast_envelope(filt2, fs) if move is not None and filt2 is not None
                 else None)

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
                                    ref_1=mvc_ref, ref_2=mvc_ref_2,
                                    both_ratio=both_ratio)
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
        if move is not None and move.size >= i1 and e_rapida is not None:
            fin = min(move.size, i1 + cola)
            e_r = e_rapida2 if (canal == 2 and e_rapida2 is not None) else e_rapida
            t_emg = _onset_s(e_r, fs, i0, fin, resting_level(e_r), back=cola)
            t_move = (_movement_after(move, fs, round(t_emg * fs), rest_move)
                      if t_emg is not None else None)
            if t_emg is not None and t_move is not None:
                candidato = (t_move - t_emg) * 1000.0
                if _EMD_RANGE_MS[0] <= candidato <= _EMD_RANGE_MS[1]:
                    emd = candidato
        velocidad = None
        if vel is not None and vel.size >= i1:
            fin_v = min(vel.size, i1 + cola)
            velocidad = float(np.max(np.abs(vel[i0:fin_v]))) if fin_v > i0 else None
        # The other muscle's own numbers over the same stretch, for the chart
        # that draws the two side by side.
        rms_otro = pico_otro = None
        if dos and env2 is not None:
            e_o = env if canal == 2 else env2
            f_o = filt if canal == 2 else filt2
            ref_o = mvc_ref if canal == 2 else mvc_ref_2
            if f_o is not None and f_o.size:
                rms_otro = float(np.sqrt(np.mean(f_o[i0:i1] ** 2)))
            if ref_o:
                pico_otro = 100.0 * _running_mean_max(e_o[i0:i1], w) / float(ref_o)
        filas.append(Contraction(
            n=k, start_s=float(s.start_s), end_s=float(s.end_s), muscle=nombre,
            rms_mv=rms, peak_pct=pico, mdf_hz=mdf, emd_ms=emd,
            channel=canal, rms_mv_other=rms_otro, peak_pct_other=pico_otro,
            velocity_au=velocidad,
        ))
    return filas


def mean_emd_ms(rows: list[Contraction]) -> float | None:
    """The mean electromechanical delay over the rows that have one."""
    valores = [r.emd_ms for r in rows if r.emd_ms is not None]
    return float(np.mean(valores)) if valores else None


__all__ = ["Contraction", "Segment", "contraction_table", "mean_emd_ms"]
