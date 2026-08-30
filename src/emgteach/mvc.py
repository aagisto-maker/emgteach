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

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterable

    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


__all__ = [
    "AUTO_COLOR",
    "AUTO_LOAD_MSG",
    "AUTO_SUFFIX",
    "OverlayCurve",
    "adaptive_ylim",
    "compute_mvc",
    "mvc_from_reps",
    "mvc_peak_hold",
    "mvc_ref_marker",
    "normalise_to_mvc",
    "overlay_curves",
    "parse_mvc_ref_markers",
]

# Wording used wherever an auto-normalised result is marked — on screen and in
# the PDF report alike. Kept here, in one place, so the two never drift apart
# and so a single i18n entry covers both.
AUTO_COLOR = "#cc0000"
AUTO_SUFFIX = " (auto-normalised, not %MVC)"
AUTO_LOAD_MSG = (
    "Muscle-load analysis requires an MVC reference recording. Select one to "
    "interpret these values as muscle load limits."
)


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


def mvc_peak_hold(
    emg_envelope: FloatArray | np.ndarray,
    window_samples: int,
    percentile: float = 95.0,
) -> float:
    """MVC reference from the strongest *sustained* window of the envelope.

    Slides a window of ``window_samples`` over the calibration envelope and
    returns the **highest window mean** — i.e. the largest amplitude the
    subject actually held for that long. This is more representative of the
    true maximum than the percentile of the whole trace, which is diluted by
    the ramp-up and the fatigue decay of a held contraction (so brief phasic
    contractions afterwards overshoot 100 %MVC less often).

    Falls back to :func:`compute_mvc` when the trace is shorter than one
    window (or the window is not positive).

    Parameters
    ----------
    emg_envelope : array-like
        Envelope of the maximal-contraction calibration trial.
    window_samples : int
        Length of the sustained window, in samples (e.g. ``0.5 s * fs``).
    percentile : float, optional
        Percentile used by the :func:`compute_mvc` fallback (default 95).

    Returns
    -------
    float
        The reference amplitude in the same units as ``emg_envelope``.
    """
    env = np.asarray(emg_envelope, dtype=np.float64)
    w = int(window_samples)
    if w < 1 or env.size < w:
        return compute_mvc(env, percentile)
    # Moving average over `w` samples via a cumulative sum (O(n)).
    csum = np.cumsum(np.insert(env, 0, 0.0))
    window_means = (csum[w:] - csum[:-w]) / w
    value = float(np.max(window_means))
    if value <= 0:
        value = float(np.max(env)) if env.size else 0.0
    return value


def mvc_from_reps(
    reps: list,
    percentile: float = 95.0,
    window_samples: int | None = None,
) -> float:
    """MVC reference from one or more maximal-contraction repetitions.

    Each entry of *reps* is the envelope of a single maximal contraction;
    the reference is the **largest** per-repetition value, the gold-standard
    "best of N" rule. Empty repetitions are ignored; returns ``0.0`` when
    there is no usable data.

    Parameters
    ----------
    reps : sequence of array-like
        One envelope per maximal-contraction repetition.
    percentile : float, optional
        Percentile used to summarise each repetition (default 95).
    window_samples : int, optional
        When given, each repetition is summarised with
        :func:`mvc_peak_hold` (strongest sustained window) instead of the
        plain percentile of the whole repetition.

    Returns
    -------
    float
        The reference amplitude (max across repetitions), or ``0.0``.
    """
    best = 0.0
    for rep in reps:
        arr = np.asarray(rep, dtype=np.float64)
        if arr.size:
            if window_samples:
                val = mvc_peak_hold(arr, window_samples, percentile)
            else:
                val = compute_mvc(arr, percentile)
            best = max(best, val)
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
    """Y-axis upper limit for normalised plots: fills the panel, clips nothing.

    Returns the larger of 110 %MVC and the highest value in the visible window
    times ``1 + margin``.

    It used to take the 99th percentile instead of the maximum, and claimed in
    this docstring to keep fast peaks visible — which it did not. A brief
    maximal effort is exactly the sample that sits above the 99th percentile,
    so the peak of the contraction was drawn past the top of the axis and the
    student read a flat top where the real maximum was. Whatever a tidier
    y-axis is worth, it is not worth cutting the measurement off.

    Parameters
    ----------
    emg_normalised : array-like
        Envelope already expressed in %MVC units.
    n_plot : int
        Number of leading samples included in the current plot view.
    margin : float, optional
        Fractional headroom above the maximum (default 0.10).

    Returns
    -------
    float
        Suggested upper Y-axis limit (%MVC).
    """
    visible = np.asarray(emg_normalised, dtype=np.float64)[:n_plot]
    visible = visible[np.isfinite(visible)]
    if visible.size == 0:
        return 110.0
    return max(110.0, float(visible.max()) * (1.0 + margin))


# ---------------------------------------------------------------------------
# The MVC reference, carried inside the recording
# ---------------------------------------------------------------------------
# EDF annotation written by the MVC-calibration wizard, one per muscle, e.g.
# "MVC ref ch=1 value=0.4213 mV". The analysis tab reads them back so each
# channel can be expressed as a percentage of *its own* maximum.
#
# The reference used to live only in memory, which is why the offline analysis
# could not use it: it was lost when the application closed, and the analysis
# tab starts from the file. Writing it as an annotation is the same solution
# the guided force-velocity wizard already uses for its loads
# (:func:`emgteach.force_velocity.fv_load_marker`), and it fits the design rule
# that the EDF carries the raw signal plus the facts of the session, with
# everything else recomputed.
_MVC_REF_RE = re.compile(
    r"MVC\s+ref\s+ch=\s*(\d+)\s+value=\s*([0-9]*\.?[0-9]+)", re.IGNORECASE
)


def mvc_ref_marker(channel_index: int, ref_mv: float) -> str:
    """The EDF annotation label for one channel's MVC reference.

    ``channel_index`` is 0-based; the label carries it 1-based, which is how
    the channels are numbered on screen.
    """
    return f"MVC ref ch={channel_index + 1} value={ref_mv:.6g} mV"


def parse_mvc_ref_markers(
    markers: Iterable[tuple[float, str]],
) -> dict[int, float]:
    """Read ``{channel_index_0based: reference_mV}`` back from EDF annotations.

    Annotations that are not MVC references — the student's own marks, the
    force-velocity loads — are ignored. If a channel was calibrated more than
    once in the same recording the **last** one wins: that is the reference the
    subject finished with, and the one that matches the electrodes as they
    ended up placed.
    """
    refs: dict[int, float] = {}
    for _onset, desc in sorted(markers, key=lambda m: float(m[0])):
        match = _MVC_REF_RE.search(str(desc))
        if not match:
            continue
        channel = int(match.group(1)) - 1
        value = float(match.group(2))
        if channel >= 0 and value > 0:
            refs[channel] = value
    return refs


@dataclass(frozen=True)
class OverlayCurve:
    """One curve of the agonist/antagonist panel, with the axis it belongs on.

    The unit is decided once, here, for the screen and the PDF alike: the
    figure in the report is the one the student hands in, so the two must not
    be able to disagree about what the axis means.
    """

    data: FloatArray
    ylabel: str
    title: str
    #: Empty unless the panel had to fall back to millivolts.
    warning: str = ""


def overlay_curves(result) -> tuple[OverlayCurve, OverlayCurve | None]:
    """The two curves of the overlaid-envelopes panel, in the right unit.

    With an MVC reference for **both** muscles the envelopes become percentages
    of each muscle's own maximum, which is the only form in which two different
    muscles can be compared at all. Without them the panel stays in millivolts
    and says so in the figure: a fallback that quietly looked comparable would
    be worse than one that admits it is not.

    Units are never mixed on the one axis — a reference for only one of the two
    channels is treated as none, because a % MVC curve beside a millivolt curve
    invites exactly the comparison the panel exists to make possible.
    """
    from emgteach.i18n import tr

    env1 = np.asarray(result["emg_envelope"], dtype=np.float64)
    raw2 = result.get("emg_envelope_2")
    env2 = None if raw2 is None else np.asarray(raw2, dtype=np.float64)
    ref1 = result.get("mvc_ref")
    ref2 = result.get("mvc_ref_2")

    comparing = env2 is not None
    in_pct = bool(ref1) and (bool(ref2) or not comparing)

    if in_pct:
        title = tr("9. Overlaid envelopes (agonist/antagonist), % MVC")
        ylabel = tr("Activation (% MVC)")
        first = OverlayCurve(env1 / float(ref1) * 100.0, ylabel, title)
        second = (
            None if env2 is None
            else OverlayCurve(env2 / float(ref2) * 100.0, ylabel, title)
        )
        return first, second

    title = tr("9. Overlaid envelopes (agonist/antagonist)")
    ylabel = tr("Amplitude ({units})").format(units=result.get("dimension", "mV"))
    warning = tr(
        "Millivolts are not comparable between two muscles. Calibrate MVC "
        "while recording to compare them."
    ) if comparing else ""
    first = OverlayCurve(env1, ylabel, title, warning)
    second = (
        None if env2 is None else OverlayCurve(env2, ylabel, title, warning)
    )
    return first, second
