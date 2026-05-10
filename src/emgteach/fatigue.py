"""Fatigue analysis from segment-wise spectral and amplitude metrics.

The classical surface-EMG fatigue indicator is the **descent of the
median frequency (MDF) over the duration of a sustained contraction**:
as motor units fatigue, conduction velocity decreases and the power
spectrum shifts towards lower frequencies. A polynomial fit of MDF
against time captures both monotonic and convex/concave trends.

A second function fits RMS against MDF in the force-fatigue plane,
giving the well-known triangular trajectory of a fatiguing
contraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.polynomial.polynomial import polyfit, polyval

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


__all__ = [
    "fit_mdf_vs_time",
    "fit_rms_vs_mdf",
]


def fit_mdf_vs_time(
    t_seg: FloatArray | np.ndarray,
    mdf_seg: FloatArray | np.ndarray,
    degree: int = 2,
) -> dict[str, Any]:
    """Polynomial fit of MDF against time for fatigue trend detection.

    A negative ``slope_sign`` (i.e. the fitted curve descends from
    start to end) is the standard indicator of muscular fatigue.

    Parameters
    ----------
    t_seg : array-like
        Segment timestamps (seconds).
    mdf_seg : array-like
        Median-frequency value per segment (Hz).
    degree : int, optional
        Polynomial degree (default 2).

    Returns
    -------
    dict
        ``coefs`` (lowest-degree first, length ``degree + 1``),
        ``fitted`` (polynomial evaluated at ``t_seg``),
        ``slope_sign`` (-1, 0 or +1; -1 indicates fatigue trend).
    """
    t_seg = np.asarray(t_seg, dtype=np.float64)
    mdf_seg = np.asarray(mdf_seg, dtype=np.float64)

    if len(t_seg) < degree + 1:
        mean_mdf = float(np.mean(mdf_seg)) if mdf_seg.size > 0 else 0.0
        fitted = np.full_like(t_seg, mean_mdf)
        return {
            "coefs": np.zeros(degree + 1),
            "fitted": fitted,
            "slope_sign": 0,
        }

    coefs = polyfit(t_seg, mdf_seg, degree)  # lowest degree first
    fitted = polyval(t_seg, coefs)
    slope_sign = int(np.sign(fitted[-1] - fitted[0]))

    return {
        "coefs": coefs,
        "fitted": fitted,
        "slope_sign": slope_sign,
    }


def fit_rms_vs_mdf(
    mdf_seg: FloatArray | np.ndarray,
    rms_seg: FloatArray | np.ndarray,
    degree: int = 2,
    n_points: int = 100,
) -> dict[str, Any]:
    """Polynomial fit of RMS against MDF (force-fatigue plane).

    Parameters
    ----------
    mdf_seg, rms_seg : array-like
        Per-segment MDF (Hz) and RMS (mV) values.
    degree : int, optional
        Polynomial degree (default 2).
    n_points : int, optional
        Number of points used to densely evaluate the fitted curve
        across the MDF range (default 100).

    Returns
    -------
    dict
        ``coefs`` (lowest-degree first), ``mdf_range`` (1-D, Hz) and
        ``fitted`` (RMS values at ``mdf_range``).
    """
    mdf_seg = np.asarray(mdf_seg, dtype=np.float64)
    rms_seg = np.asarray(rms_seg, dtype=np.float64)

    if len(mdf_seg) < degree + 1:
        return {
            "coefs": np.zeros(degree + 1),
            "mdf_range": mdf_seg.copy(),
            "fitted": rms_seg.copy(),
        }

    coefs = polyfit(mdf_seg, rms_seg, degree)
    mdf_range = np.linspace(float(mdf_seg.min()), float(mdf_seg.max()), n_points)
    fitted = polyval(mdf_range, coefs)

    return {
        "coefs": coefs,
        "mdf_range": mdf_range,
        "fitted": fitted,
    }
