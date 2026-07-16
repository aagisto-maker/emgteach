"""Force-velocity / load-velocity muscle study from one multi-rep recording.

The teaching protocol: the subject lifts several **known** loads (one repetition
per load) in a single recording, with the accelerometer on the moving segment
and the EMG on the muscle. This module turns that recording into the classic
curves of muscle mechanics:

* **Load-velocity** — the known load against the peak shortening velocity
  (from the accelerometer). Velocity rises as the load falls.
* **Force-velocity** — the same relationship normalised to each variable's
  maximum, so it takes the familiar Hill shape without needing an absolute
  force sensor (in isotonic conditions the force the muscle exerts equals the
  load it moves).
* **Power** — load x velocity, peaking at an intermediate load.
* **Recruitment** — load against EMG amplitude: heavier loads need more
  activation (Henneman's size principle). This is the electrophysiological
  angle a plain force-velocity curve cannot show.

The accelerometer here is **uncalibrated** (normalised g), so the velocity is
in *arbitrary units*: the **shape** of the curves is meaningful, the absolute
m/s is not without a per-device calibration. Force is the **known external
load** entered by the user — emgteach has no force cell.
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.signal import iirfilter, sosfiltfilt

__all__ = [
    "force_velocity_curves",
    "rep_metrics",
    "segment_contractions",
    "velocity_from_acc",
]


def velocity_from_acc(
    acc: np.ndarray, fs: float, hp_cutoff: float = 0.5
) -> np.ndarray:
    """Estimate segment velocity (arbitrary units) from the accelerometer.

    High-passes the acceleration to drop gravity and slow drift, integrates it
    once (cumulative trapezoid), then high-passes the velocity again to remove
    the residual integration drift. The result is a zero-mean velocity trace in
    arbitrary units (the accelerometer is uncalibrated), suitable for comparing
    the **relative** peak velocity across repetitions.

    Parameters
    ----------
    acc : array-like
        Accelerometer signal (normalised g).
    fs : float
        Sampling frequency (Hz).
    hp_cutoff : float, optional
        High-pass cut-off (Hz) applied before and after integration. Default
        0.5.
    """
    a = np.asarray(acc, dtype=np.float64)
    if a.size < 10:
        return np.zeros_like(a)
    a = a - float(np.mean(a))
    sos = iirfilter(
        2, hp_cutoff, btype="high", fs=fs, ftype="butter", output="sos"
    )
    a_hp = sosfiltfilt(sos, a)
    v = cumulative_trapezoid(a_hp, dx=1.0 / fs, initial=0.0)
    return sosfiltfilt(sos, v)


def segment_contractions(
    envelope: np.ndarray,
    fs: float,
    k: float = 3.0,
    baseline_s: float = 0.5,
    min_duration_s: float = 0.2,
    merge_gap_s: float = 0.15,
) -> list[tuple[int, int]]:
    """Find contraction bursts in an EMG envelope: one ``(start, end)`` per rep.

    A sample is "active" when the envelope exceeds ``baseline + k·SD`` estimated
    from the first ``baseline_s`` seconds (with a floor at 10 % of the envelope
    maximum so a noisy baseline does not swallow everything). Contiguous active
    runs closer than ``merge_gap_s`` are merged, and runs shorter than
    ``min_duration_s`` are dropped. Returns sample-index windows in order.
    """
    env = np.asarray(envelope, dtype=np.float64)
    n = env.size
    if n == 0:
        return []
    nb = min(int(baseline_s * fs), n)
    if nb > 1:
        thr = float(np.mean(env[:nb]) + k * np.std(env[:nb]))
    else:
        thr = float(np.mean(env))
    thr = max(thr, 0.10 * float(np.max(env)))

    active = env > thr
    if not active.any():
        return []
    # Run boundaries via the transitions of the boolean mask.
    edges = np.diff(active.astype(np.int8))
    starts = list(np.where(edges == 1)[0] + 1)
    ends = list(np.where(edges == -1)[0] + 1)
    if active[0]:
        starts.insert(0, 0)
    if active[-1]:
        ends.append(n)

    runs = list(zip(starts, ends, strict=True))
    # Merge runs separated by a short gap.
    merge_gap = int(merge_gap_s * fs)
    merged: list[tuple[int, int]] = []
    for s, e in runs:
        if merged and s - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    # Drop runs that are too short to be a real contraction.
    min_dur = int(min_duration_s * fs)
    return [(s, e) for s, e in merged if e - s >= min_dur]


def rep_metrics(
    emg_envelope: np.ndarray,
    velocity: np.ndarray,
    windows: list[tuple[int, int]],
) -> tuple[np.ndarray, np.ndarray]:
    """Per-repetition ``(emg_amplitude, peak_velocity)`` arrays.

    For each ``(start, end)`` window, the EMG amplitude is the peak envelope
    value and the peak velocity is the maximum absolute velocity — the
    fastest shortening reached during the lift.
    """
    emg = np.asarray(emg_envelope, dtype=np.float64)
    vel = np.asarray(velocity, dtype=np.float64)
    emg_amp: list[float] = []
    peak_vel: list[float] = []
    for i0, i1 in windows:
        seg_e = emg[i0:i1]
        seg_v = np.abs(vel[i0:i1])
        emg_amp.append(float(np.max(seg_e)) if seg_e.size else 0.0)
        peak_vel.append(float(np.max(seg_v)) if seg_v.size else 0.0)
    return np.asarray(emg_amp), np.asarray(peak_vel)


def force_velocity_curves(
    loads: np.ndarray, velocities: np.ndarray
) -> dict[str, np.ndarray]:
    """Build the load-velocity, normalised force-velocity and power curves.

    Parameters
    ----------
    loads : array-like
        Known external load per repetition (any consistent unit, e.g. kg).
    velocities : array-like
        Peak velocity per repetition (arbitrary units from the accelerometer).

    Returns
    -------
    dict
        Sorted-by-load ``load`` and ``velocity`` arrays; ``power`` = load times
        velocity; and the max-normalised ``force_norm`` / ``velocity_norm``
        (0-1) that give the Hill-shaped force-velocity curve without an
        absolute force sensor.
    """
    load = np.asarray(loads, dtype=np.float64)
    vel = np.asarray(velocities, dtype=np.float64)
    order = np.argsort(load)
    load, vel = load[order], vel[order]
    power = load * vel
    fmax = float(np.max(load)) if load.size and np.max(load) > 0 else 1.0
    vmax = float(np.max(vel)) if vel.size and np.max(vel) > 0 else 1.0
    return {
        "load": load,
        "velocity": vel,
        "power": power,
        "force_norm": load / fmax,
        "velocity_norm": vel / vmax,
    }
