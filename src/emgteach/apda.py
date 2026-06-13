"""Muscle-load analysis via Jonsson's APDF (Amplitude Probability
Distribution Function).

Jonsson's method [1]_ characterises the muscular load sustained during a
task from the amplitude distribution of the MVC-normalised EMG envelope.
Three load levels are read off the cumulative distribution:

* **static** — the load exceeded **90 %** of the time (the 10th percentile,
  ``P10``): the near-continuous background load on the muscle;
* **median** — the load exceeded **50 %** of the time (``P50``): the typical
  working load;
* **peak** — the load exceeded **10 %** of the time (the 90th percentile,
  ``P90``): the recurrent high-effort load.

Each level is compared against a recommended maximum (% MVC); exceeding it
flags an ergonomic risk (muscular tiredness / fatigue). The thresholds are
configurable (they live in :class:`~emgteach.profiles.SignalProfile`).

This module implements the *method*; it is independent of any particular
acquisition software. It is intentionally Qt-free so the GUI workers and
the offline analysis can both use it.

.. [1] Jonsson, B. (1978). Kinesiology: with special reference to
   electromyographic kinesiology. *Electroencephalography and Clinical
   Neurophysiology, Supplement*, 34, 417-428. See also Jonsson, B. (1982),
   *Journal of Human Ergology*, 11, 73-88.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]

__all__ = [
    "ApdfResult",
    "LoadLevel",
    "OnlineLoad",
    "classify_load",
    "compute_apdf",
]

# Jonsson level definitions: amplitude-distribution percentile per level.
# static = exceeded 90 % of the time -> P10; median -> P50; peak -> P90.
_STATIC_PCTL = 10.0
_MEDIAN_PCTL = 50.0
_PEAK_PCTL = 90.0


@dataclass(frozen=True)
class LoadLevel:
    """One Jonsson load level (static / median / peak)."""

    name: str          # "static" / "median" / "peak"
    percentile: float  # amplitude-distribution percentile it corresponds to
    value: float       # the load, in % MVC
    limit: float       # recommended maximum, in % MVC
    exceeds: bool      # value > limit


@dataclass(frozen=True)
class ApdfResult:
    """Result of :func:`compute_apdf`.

    ``load`` / ``cumulative`` are the APDF curve: for each load level
    ``load[i]`` (% MVC), ``cumulative[i]`` is the percentage of time the
    signal stayed at or below it.
    """

    load: FloatArray
    cumulative: FloatArray
    static: LoadLevel
    median: LoadLevel
    peak: LoadLevel

    @property
    def levels(self) -> tuple[LoadLevel, LoadLevel, LoadLevel]:
        return (self.static, self.median, self.peak)

    @property
    def any_exceeds(self) -> bool:
        return any(level.exceeds for level in self.levels)


def compute_apdf(
    emg_norm: FloatArray | np.ndarray,
    static_limit: float = 5.0,
    median_limit: float = 14.0,
    peak_limit: float = 70.0,
    n_points: int = 200,
) -> ApdfResult:
    """Amplitude Probability Distribution Function of an MVC-normalised signal.

    Parameters
    ----------
    emg_norm : array-like
        EMG envelope already expressed in % MVC (see
        :func:`emgteach.mvc.normalise_to_mvc`).
    static_limit, median_limit, peak_limit : float, optional
        Recommended maxima (% MVC) for the static, median and peak levels.
        Defaults follow common ergonomic guidance derived from Jonsson.
    n_points : int, optional
        Number of points used to sample the cumulative curve (default 200).

    Returns
    -------
    ApdfResult
        The APDF curve plus the three classified load levels.

    Raises
    ------
    ValueError
        If ``emg_norm`` has no finite samples.
    """
    arr = np.asarray(emg_norm, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("emg_norm has no finite samples.")
    arr = np.clip(arr, 0.0, None)  # a % MVC envelope is non-negative

    static_v = float(np.percentile(arr, _STATIC_PCTL))
    median_v = float(np.percentile(arr, _MEDIAN_PCTL))
    peak_v = float(np.percentile(arr, _PEAK_PCTL))

    # Cumulative curve. Cap the x-axis just past the peak / the bulk of the
    # data so rare outliers do not flatten the informative region.
    hi = max(float(np.percentile(arr, 99.5)), peak_v * 1.1, 1.0)
    load = np.linspace(0.0, hi, int(n_points))
    ordered = np.sort(arr)
    cumulative = np.searchsorted(ordered, load, side="right") / arr.size * 100.0

    def _level(name: str, pctl: float, value: float, limit: float) -> LoadLevel:
        return LoadLevel(
            name=name,
            percentile=pctl,
            value=value,
            limit=float(limit),
            exceeds=value > float(limit),
        )

    return ApdfResult(
        load=load,
        cumulative=cumulative,
        static=_level("static", _STATIC_PCTL, static_v, static_limit),
        median=_level("median", _MEDIAN_PCTL, median_v, median_limit),
        peak=_level("peak", _PEAK_PCTL, peak_v, peak_limit),
    )


def classify_load(value: float, warning_limit: float, danger_limit: float) -> str:
    """Classify a load value (% MVC) as ``"normal"`` / ``"warning"`` / ``"danger"``.

    ``"danger"`` at or above ``danger_limit`` (fatigue zone), ``"warning"`` at
    or above ``warning_limit`` (tiredness zone), otherwise ``"normal"``.
    """
    if value >= danger_limit:
        return "danger"
    if value >= warning_limit:
        return "warning"
    return "normal"


class OnlineLoad:
    """Running muscle-load monitor for a stream of % MVC envelope samples.

    Used during acquisition: feed it the envelope normalised to % MVC (against
    a pre-acquired MVC reference) with :meth:`add`, then read the running
    Jonsson levels (:attr:`static` / :attr:`median` / :attr:`peak`), the recent
    :attr:`current` load and its :attr:`status` (normal / warning / danger).

    It is Qt-free and keeps only bounded ring buffers, so it is safe to drive
    from a real-time data callback.
    """

    def __init__(
        self,
        warning_limit: float = 30.0,
        danger_limit: float = 50.0,
        recent_n: int = 500,
        maxlen: int = 600_000,
    ) -> None:
        self.warning_limit = float(warning_limit)
        self.danger_limit = float(danger_limit)
        self._buf: deque[float] = deque(maxlen=int(maxlen))
        self._recent: deque[float] = deque(maxlen=int(recent_n))

    def reset(self) -> None:
        self._buf.clear()
        self._recent.clear()

    def add(self, pct_mvc: FloatArray | np.ndarray | list) -> None:
        """Ingest a block of % MVC envelope samples."""
        arr = np.asarray(pct_mvc, dtype=np.float64)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return
        vals = arr.tolist()
        self._buf.extend(vals)
        self._recent.extend(vals)

    @property
    def n(self) -> int:
        return len(self._buf)

    @property
    def current(self) -> float:
        """Recent mean load (% MVC) — the value the status is based on."""
        return float(np.mean(self._recent)) if self._recent else 0.0

    def _pct(self, p: float) -> float:
        return float(np.percentile(self._buf, p)) if self._buf else 0.0

    @property
    def static(self) -> float:
        return self._pct(_STATIC_PCTL)

    @property
    def median(self) -> float:
        return self._pct(_MEDIAN_PCTL)

    @property
    def peak(self) -> float:
        return self._pct(_PEAK_PCTL)

    @property
    def status(self) -> str:
        return classify_load(self.current, self.warning_limit, self.danger_limit)
