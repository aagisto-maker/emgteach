"""Fatigue analysis from segment-wise spectral and amplitude metrics.

The classical surface-EMG fatigue indicator is the **descent of the
median frequency (MDF) over the duration of a sustained contraction**:
as motor units fatigue, conduction velocity decreases and the power
spectrum shifts towards lower frequencies. A polynomial fit of MDF
versus time captures both monotonic and convex/concave trends.

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
    """Fatigue trend of the median frequency (MDF) versus time.

    The primary, quantitative fatigue index is the **slope of a linear
    least-squares regression of MDF on time**. A negative slope (MDF
    falling as the contraction progresses) is the standard sign of
    myoelectric fatigue; its magnitude in Hz/s, the goodness of fit
    (``r_squared``) and the overall percentage decline give a single,
    reportable number instead of the fragile sign of a parabola's
    endpoints. A polynomial fit is still returned for the display curve.

    Parameters
    ----------
    t_seg : array-like
        Segment timestamps (seconds).
    mdf_seg : array-like
        Median-frequency value per segment (Hz).
    degree : int, optional
        Degree of the polynomial trend curve for display (default 2).

    Returns
    -------
    dict
        ``coefs`` (polynomial, lowest-degree first, length ``degree + 1``),
        ``fitted`` (polynomial evaluated at ``t_seg``),
        ``slope`` (regression slope, Hz/s; negative = fatigue),
        ``slope_per_min`` (slope in Hz/min),
        ``intercept`` (regression intercept, Hz),
        ``r_squared`` (coefficient of determination of the linear fit),
        ``pct_decline`` (percentage MDF drop from the fitted start to the
        fitted end, relative to the fitted initial value; positive =
        fatigue), ``linear_fitted`` (the regression line at ``t_seg``),
        ``slope_sign`` (-1, 0 or +1; sign of ``slope``).
    """
    t_seg = np.asarray(t_seg, dtype=np.float64)
    mdf_seg = np.asarray(mdf_seg, dtype=np.float64)
    n = len(t_seg)

    # -- polynomial trend curve (display only) --
    if n < degree + 1:
        mean_mdf = float(np.mean(mdf_seg)) if mdf_seg.size > 0 else 0.0
        coefs = np.zeros(degree + 1)
        fitted = np.full_like(t_seg, mean_mdf)
    else:
        coefs = polyfit(t_seg, mdf_seg, degree)  # lowest degree first
        fitted = polyval(t_seg, coefs)

    # -- primary index: linear regression of MDF on time --
    result: dict[str, Any] = {
        "coefs": coefs,
        "fitted": fitted,
        "slope": 0.0,
        "slope_per_min": 0.0,
        "intercept": 0.0,
        "r_squared": 0.0,
        "pct_decline": 0.0,
        "linear_fitted": fitted.copy(),
        "slope_sign": 0,
    }
    # A slope needs at least two segments at two distinct times.
    if n < 2 or np.ptp(t_seg) == 0.0:
        return result

    intercept, slope = (float(v) for v in polyfit(t_seg, mdf_seg, 1))
    linear_fitted = intercept + slope * t_seg

    # R^2 of the linear fit.
    ss_res = float(np.sum((mdf_seg - linear_fitted) ** 2))
    ss_tot = float(np.sum((mdf_seg - np.mean(mdf_seg)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0

    # Percentage decline over the recording, relative to the fitted start.
    mdf_start = intercept + slope * float(t_seg[0])
    mdf_end = intercept + slope * float(t_seg[-1])
    pct_decline = (
        (mdf_start - mdf_end) / mdf_start * 100.0 if abs(mdf_start) > 1e-9 else 0.0
    )

    result.update(
        slope=slope,
        slope_per_min=slope * 60.0,
        intercept=intercept,
        r_squared=r_squared,
        pct_decline=pct_decline,
        linear_fitted=linear_fitted,
        slope_sign=int(np.sign(slope)),
    )
    return result


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
