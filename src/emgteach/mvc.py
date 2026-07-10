"""Maximum Voluntary Contraction (MVC) normalisation helpers.

The MVC reference is computed from the EMG envelope of a calibration
trial in which the subject performs the strongest possible contraction
of the target muscle. The 95th percentile of the envelope is used
rather than the raw maximum, as it is robust against motion artefacts
and brief electrode glitches that would otherwise saturate the
reference.

Subsequent recordings are then expressed as a percentage of MVC, which
is the unit in which clinical and research surface-EMG measurements
are conventionally reported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


__all__ = [
    "adaptive_ylim",
    "compute_mvc",
    "mvc_from_reps",
    "normalise_to_mvc",
]


def compute_mvc(
    emg_envelope: FloatArray | np.ndarray, percentile: float = 95.0
) -> float:
    """Robust MVC reference amplitude from the calibration envelope.

    Returns the requested percentile of the envelope, falling back to
    the maximum only when the percentile evaluates to zero or below.

    Parameters
    ----------
    emg_envelope : array-like
        Envelope (low-pass filtered, rectified EMG) of the MVC
        calibration trial.
    percentile : float, optional
        Percentile to use as MVC reference (default 95).

    Returns
    -------
    float
        The reference amplitude in the same units as ``emg_envelope``.
    """
    env = np.asarray(emg_envelope, dtype=np.float64)
    value = float(np.percentile(env, percentile))
    if value <= 0:
        value = float(np.max(env))
    return value


def mvc_from_reps(reps: list, percentile: float = 95.0) -> float:
    """MVC reference from one or more maximal-contraction repetitions.

    Each entry of *reps* is the envelope of a single maximal contraction;
    the reference is the **largest** per-repetition :func:`compute_mvc`
    value, the gold-standard "best of N" rule. Empty repetitions are
    ignored; returns ``0.0`` when there is no usable data.

    Parameters
    ----------
    reps : sequence of array-like
        One envelope per maximal-contraction repetition.
    percentile : float, optional
        Percentile passed to :func:`compute_mvc` (default 95).

    Returns
    -------
    float
        The reference amplitude (max across repetitions), or ``0.0``.
    """
    best = 0.0
    for rep in reps:
        arr = np.asarray(rep, dtype=np.float64)
        if arr.size:
            best = max(best, compute_mvc(arr, percentile))
    return best


def normalise_to_mvc(
    emg_envelope: FloatArray | np.ndarray, mvc_ref: float
) -> FloatArray:
    """Express ``emg_envelope`` as a percentage of MVC reference.

    Parameters
    ----------
    emg_envelope : array-like
        Envelope to normalise.
    mvc_ref : float
        Reference amplitude from :func:`compute_mvc` (must be > 0).

    Returns
    -------
    ndarray
        Envelope scaled to the [0, 100+] %MVC range.

    Raises
    ------
    ValueError
        If ``mvc_ref`` is non-positive.
    """
    if mvc_ref <= 0:
        raise ValueError("MVC reference amplitude must be positive.")
    return (np.asarray(emg_envelope, dtype=np.float64) / mvc_ref) * 100.0


def adaptive_ylim(
    emg_normalised: FloatArray | np.ndarray,
    n_plot: int,
    margin: float = 0.10,
) -> float:
    """Y-axis upper limit for normalised plots, with sensible headroom.

    Returns the larger of 110 %MVC and the 99th percentile of the
    visible window times ``1 + margin``. This keeps fast peaks of
    saturating contractions visible while keeping the plot tidy at
    rest.

    Parameters
    ----------
    emg_normalised : array-like
        Envelope already expressed in %MVC units.
    n_plot : int
        Number of leading samples included in the current plot view.
    margin : float, optional
        Fractional headroom above the 99th percentile (default 0.10).

    Returns
    -------
    float
        Suggested upper Y-axis limit (%MVC).
    """
    visible = np.asarray(emg_normalised, dtype=np.float64)[:n_plot]
    p99 = float(np.percentile(visible, 99))
    return max(110.0, p99 * (1.0 + margin))
