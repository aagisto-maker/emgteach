"""Fatigue analysis from segment-wise spectral and amplitude metrics.

The classical surface-EMG fatigue indicator is the **descent of the
median frequency (MDF) over the duration of a sustained contraction**:
as motor units fatigue, conduction velocity decreases and the power
spectrum shifts towards lower frequencies. A polynomial fit of MDF
versus time captures both monotonic and convex/concave trends.

A second function fits RMS against MDF in the force-fatigue plane,
giving the well-known triangular trajectory of a fatiguing
contraction.

Two things stand between that regression and a verdict, and both were put
here after a forearm recording of intermittent contractions was reported as
"Fatigue: DETECTED, MDF -26.4 %" when nothing had fatigued:

* **the median frequency of silence is not a measurement.** The segmenter
  windows the whole selection, rest included, and a resting segment is
  amplifier noise — broadband, so its MDF sits far above a contraction's. In
  an intermittent protocol the regression is then fitted through two mixed
  populations, and any drift in how many of each fall early or late in the
  recording comes out as a slope. :func:`active_segments` keeps the segments
  where the muscle was working;
* **the sign of a slope is not evidence.** Fitted through the active segments
  of that same recording, the trend explained 8 % of the variance — a line
  drawn through a cloud. :func:`fatigue_verdict` reports a trend only when the
  fit supports one, and says so plainly when it does not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.polynomial.polynomial import polyfit, polyval

if TYPE_CHECKING:
    import numpy.typing as npt

    BoolArray = npt.NDArray[np.bool_]
    FloatArray = npt.NDArray[np.float64]


__all__ = [
    "active_segments",
    "fatigue_verdict",
    "fit_mdf_vs_time",
    "fit_rms_vs_mdf",
]

#: The three verdicts :func:`fatigue_verdict` can return.
FATIGUE = "fatigue"
NO_FATIGUE = "none"
INCONCLUSIVE = "inconclusive"


def active_segments(
    rms_seg: FloatArray | np.ndarray, ratio: float = 0.30
) -> BoolArray:
    """Mask of the segments in which the muscle was actually contracting.

    A segment counts as active when its RMS reaches *ratio* of the recording's
    own strong-segment level (the 95th percentile of the segment RMS values).
    Self-contained on purpose: the fatigue analysis has to work on a recording
    with no MVC reference, so the yardstick is the selection itself.

    Returns an all-``True`` mask when nothing would pass, so a sustained
    contraction — where every segment is active — is never emptied by this,
    and neither is a recording quiet throughout: that one is left for
    :func:`fatigue_verdict` to call inconclusive on the fit.
    """
    rms = np.asarray(rms_seg, dtype=np.float64)
    if rms.size == 0:
        return np.zeros(0, dtype=bool)
    fuerte = float(np.percentile(rms, 95.0))
    if fuerte <= 0.0:
        return np.ones(rms.size, dtype=bool)
    mask = rms >= ratio * fuerte
    return mask if mask.any() else np.ones(rms.size, dtype=bool)


def fatigue_verdict(
    slope_sign: int,
    r_squared: float,
    n_segments: int,
    *,
    min_r2: float = 0.30,
    min_segments: int = 4,
) -> str:
    """``"fatigue"``, ``"none"`` or ``"inconclusive"`` — the one place that decides.

    The interface, the PDF report and the CSV export all used to read the sign
    of the slope directly, which meant three surfaces printing "fatigue" in red
    off a line that fitted nothing. A falling median frequency is the classic
    sign of myoelectric fatigue, but only as the *trend* of a contraction that
    was actually held: below ``min_r2`` there is no trend to speak of, and the
    honest answer is that this recording does not settle the question.
    """
    if n_segments < min_segments or slope_sign == 0:
        return INCONCLUSIVE
    if float(r_squared) < min_r2:
        return INCONCLUSIVE
    return FATIGUE if slope_sign < 0 else NO_FATIGUE


def fit_mdf_vs_time(
    t_seg: FloatArray | np.ndarray,
    mdf_seg: FloatArray | np.ndarray,
    degree: int = 2,
    t_eval: FloatArray | np.ndarray | None = None,
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
    t_eval : array-like, optional
        Where to evaluate the display curves. Defaults to ``t_seg``. Pass the
        full segment axis when the fit itself was restricted to the active
        segments (see :func:`active_segments`), so the panels can draw the
        trend across the whole recording while the numbers come from the part
        of it that was a contraction.

    Returns
    -------
    dict
        ``coefs`` (polynomial, lowest-degree first, length ``degree + 1``),
        ``fitted`` (polynomial evaluated at ``t_eval``),
        ``slope`` (regression slope, Hz/s; negative = fatigue),
        ``slope_per_min`` (slope in Hz/min),
        ``intercept`` (regression intercept, Hz),
        ``r_squared`` (coefficient of determination of the linear fit),
        ``pct_decline`` (percentage MDF drop from the fitted start to the
        fitted end, relative to the fitted initial value; positive =
        fatigue), ``linear_fitted`` (the regression line at ``t_eval``),
        ``slope_sign`` (-1, 0 or +1; sign of ``slope``).
    """
    t_seg = np.asarray(t_seg, dtype=np.float64)
    mdf_seg = np.asarray(mdf_seg, dtype=np.float64)
    t_out = t_seg if t_eval is None else np.asarray(t_eval, dtype=np.float64)
    n = len(t_seg)

    # -- polynomial trend curve (display only) --
    if n < degree + 1:
        mean_mdf = float(np.mean(mdf_seg)) if mdf_seg.size > 0 else 0.0
        coefs = np.zeros(degree + 1)
        fitted = np.full_like(t_out, mean_mdf)
    else:
        coefs = polyfit(t_seg, mdf_seg, degree)  # lowest degree first
        fitted = polyval(t_out, coefs)

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
    linear_fitted = intercept + slope * t_out

    # R^2 of the linear fit — against the points it was fitted to, which are
    # not necessarily the ones the curve is drawn over.
    ss_res = float(np.sum((mdf_seg - (intercept + slope * t_seg)) ** 2))
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
