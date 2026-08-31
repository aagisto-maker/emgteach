"""Agonist/antagonist co-activation, by the index of Falconer and Winter.

Of all the activity recorded in a pair of muscles, what fraction is *shared* —
exerted by both at once? The index is that fraction, from 0 to 100 %:

.. math::

    CCI = 100 \\cdot \\frac{2 \\int \\min(E_1, E_2)\\,dt}{\\int (E_1 + E_2)\\,dt}

with both envelopes expressed as a percentage of **their own muscle's** MVC.
The factor of two is what lets the index reach 100 % when the two curves
coincide; 0 % means one muscle was working and the other was not.

Falconer and Winter's [1]_ is the most cited index by a wide margin, it is
bounded, it does not ask which of the two muscles is the agonist, and it is
the most robust of the family to the choice of normalisation [2]_ — which
matters in teaching, because a student's MVC protocol is not a research
laboratory's. Rudolph's index would suit a course about joint stiffness or
energetic cost better; one index explained well beats two to choose between,
and their values are not comparable anyway.

**This index measures similarity of shape, not amount of activation**, and
that is its trap: two muscles at rest have similar baseline noise, so the
index approaches 100 % on a recording where nothing happened. It is the same
silent failure as auto-normalisation — a number that looks like a finding and
is not — so the three safeguards below are not optional:

* activation below a floor in *either* channel and the index is not reported
  at all (never a greyed or parenthesised number: reported or not reported);
* each envelope has its own resting level subtracted first, so a high
  baseline cannot smuggle a recording past that floor;
* the index is computed **per window**, between markers, because it was
  conceived for short quasi-stationary windows and means nothing spread over
  a recording that mixes rest, flexion, extension and grip.

This module is Qt-free, like :mod:`emgteach.apda`, so the analysis worker and
any offline use share it.

.. [1] Falconer K, Winter DA. Quantitative assessment of co-contraction at the
   ankle joint in walking. *Electromyogr Clin Neurophysiol* 25: 135-149, 1985.
   PMID 3987606.
.. [2] Carey HD, De Groote F, Sawers A. A comparative analysis of
   co-contraction indices using synthetic EMG data: implications for selection
   and interpretation. *PLoS One* 21: e0343081, 2026.
   doi:10.1371/journal.pone.0343081.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.integrate import trapezoid

from emgteach.i18n import tr

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]

__all__ = [
    "CoactivationResult",
    "coactivation_by_window",
    "coactivation_index",
    "resting_level",
]


@dataclass(frozen=True)
class CoactivationResult:
    """One window's co-activation, with the two means it must be read beside.

    ``index`` is ``None`` whenever the window fails a safeguard, and ``reason``
    then says which one in words the interface can show in place of a number.

    The two means travel with the index on purpose. A bare 86 % reads as "both
    muscles were very active" when it may equally mean "both were equally
    quiet", and in the teaching case the antagonist's mean *is* the finding —
    the index only summarises it.
    """

    index: float | None
    mean_1: float
    mean_2: float
    window_s: tuple[float, float]
    reason: str | None = None
    #: The marker that opened this window, for the table's first column.
    label: str = ""


def resting_level(envelope) -> float:
    """The muscle's own resting level, as the 10th percentile of its envelope.

    Estimated over the **whole analysed span**, not per window: a window that
    is entirely grip has a high 10th percentile, and subtracting that would
    erase the very activation being measured. What is wanted is the level the
    muscle returns to, which only the span as a whole can show.
    """
    arr = np.asarray(envelope, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    return float(np.percentile(arr, 10.0)) if arr.size else 0.0


def _above_rest(envelope, rest: float) -> FloatArray:
    arr = np.asarray(envelope, dtype=np.float64) - float(rest)
    return np.clip(arr, 0.0, None)


#: How much quiet to leave after the last activity when the final window is
#: closed at the end of the effort. Enough not to clip the release of a
#: contraction, short enough that the pause does not dilute the mean.
_COLA_S = 0.5


def _fin_de_la_actividad(
    a1: FloatArray, a2: FloatArray, fs: float, floor_pct: float
) -> int | None:
    """The last sample where either muscle was working, plus a short tail.

    Every marked window is closed by the *next* mark — the operator saying
    where that phase ended — except the last one, which runs to wherever the
    recording happened to be stopped. A student who marks the sustained grip
    and then rests before pressing stop gets that rest inside the window: it
    pulls the mean down and can push it under the floor, so the phase they did
    perform is reported as "not measured".

    "The last time either muscle was above the floor" rather than "the first
    time both fall below it": the envelope dips between bursts of an
    intermittent effort, and cutting at the first dip would end the window in
    the middle of the work.

    Returns ``None`` when nothing rises above the floor, so the window is left
    alone — a window with no activity in it has a reason of its own to give,
    and trimming it to nothing would replace that reason with a worse one.
    """
    activo = np.flatnonzero((a1 > floor_pct) | (a2 > floor_pct))
    if not activo.size:
        return None
    return int(activo[-1]) + max(1, round(_COLA_S * float(fs)))


def coactivation_index(
    env_1_pct_mvc,
    env_2_pct_mvc,
    fs: float,
    *,
    floor_pct: float = 5.0,
    rest_1: float | None = None,
    rest_2: float | None = None,
    window_s: tuple[float, float] = (0.0, 0.0),
    label: str = "",
    name_1: str = "",
    name_2: str = "",
) -> CoactivationResult:
    """Falconer-Winter co-activation for one window of two %MVC envelopes.

    ``rest_1`` / ``rest_2`` are the muscles' resting levels, normally measured
    over the whole analysed span with :func:`resting_level` and passed in; when
    omitted they are taken from this window, which is only right if the window
    *is* the span.
    """
    e1 = np.asarray(env_1_pct_mvc, dtype=np.float64)
    e2 = np.asarray(env_2_pct_mvc, dtype=np.float64)
    n = min(e1.size, e2.size)
    e1, e2 = e1[:n], e2[:n]
    if n < 2:
        return CoactivationResult(
            None, 0.0, 0.0, window_s,
            tr("not reported — window too short"), label,
        )

    a1 = _above_rest(e1, resting_level(e1) if rest_1 is None else rest_1)
    a2 = _above_rest(e2, resting_level(e2) if rest_2 is None else rest_2)
    mean_1, mean_2 = float(np.mean(a1)), float(np.mean(a2))

    # Safeguard: below the floor the index measures the likeness of two
    # baselines and climbs towards 100 %. Say why, do not print a number.
    for mean, name, fallback in (
        (mean_1, name_1, 1), (mean_2, name_2, 2),
    ):
        if mean < floor_pct:
            return CoactivationResult(
                None, mean_1, mean_2, window_s,
                tr("not reported — {name} below {floor:.0f} % MVC").format(
                    name=name or tr("Muscle {n}").format(n=fallback),
                    floor=floor_pct,
                ),
                label,
            )

    dx = 1.0 / float(fs)
    total = float(trapezoid(a1 + a2, dx=dx))
    if total <= 0.0:
        return CoactivationResult(
            None, mean_1, mean_2, window_s,
            tr("not reported — no activation above rest"), label,
        )
    shared = float(trapezoid(np.minimum(a1, a2), dx=dx))
    index = 100.0 * 2.0 * shared / total
    return CoactivationResult(
        min(100.0, max(0.0, index)), mean_1, mean_2, window_s, None, label
    )


def coactivation_by_window(
    env_1_pct_mvc,
    env_2_pct_mvc,
    fs: float,
    markers: Sequence[tuple[float, str]] | None = None,
    *,
    floor_pct: float = 5.0,
    t0: float = 0.0,
    name_1: str = "",
    name_2: str = "",
) -> tuple[list[CoactivationResult], bool]:
    """One index per marked window, and whether the windows came from markers.

    Each marker opens a window that runs to the next one. The **last** one is
    closed at the end of the activity instead of at the end of the recording —
    see :func:`_fin_de_la_actividad` — because nothing else closes it and the
    quiet before the stop button is not part of the phase.

    With no markers the whole analysed span is reported as a single window and
    the second return value is ``False``, which the interface turns into a
    visible warning: an index over a recording that mixes rest, flexion and
    grip is not a measurement of anything. That window is deliberately *not*
    trimmed — it is already labelled as not a measurement, and tidying it
    would only make it look like one.
    """
    e1 = np.asarray(env_1_pct_mvc, dtype=np.float64)
    e2 = np.asarray(env_2_pct_mvc, dtype=np.float64)
    n = min(e1.size, e2.size)
    duration = n / float(fs)
    # Rest is measured once, over the whole span; see resting_level().
    rest_1, rest_2 = resting_level(e1), resting_level(e2)

    marks = sorted(
        (float(t) - t0, str(lbl)) for t, lbl in (markers or [])
        if 0.0 <= float(t) - t0 < duration
    )
    if not marks:
        return [coactivation_index(
            e1, e2, fs, floor_pct=floor_pct, rest_1=rest_1, rest_2=rest_2,
            window_s=(t0, t0 + duration), label=tr("Whole recording"),
            name_1=name_1, name_2=name_2,
        )], False

    a1, a2 = _above_rest(e1, rest_1), _above_rest(e2, rest_2)
    bounds = [t for t, _ in marks] + [duration]
    out: list[CoactivationResult] = []
    for i, (start, lbl) in enumerate(marks):
        end = bounds[i + 1]
        i0, i1 = round(start * fs), round(end * fs)
        if i == len(marks) - 1:
            # Only the last one: every other window is closed by the operator's
            # next mark, which is a statement about the session. This one was
            # closed by whenever they reached for the stop button.
            fin = _fin_de_la_actividad(a1[i0:i1], a2[i0:i1], fs, floor_pct)
            if fin is not None:
                i1 = min(i1, i0 + fin)
                end = i1 / float(fs)
        # A window too short to measure still gets its row. Dropping it left
        # the student who marked something looking at a table that does not
        # mention it, which reads as the mark not having been registered.
        out.append(coactivation_index(
            e1[i0:i1], e2[i0:i1], fs, floor_pct=floor_pct,
            rest_1=rest_1, rest_2=rest_2,
            window_s=(t0 + start, t0 + end), label=lbl,
            name_1=name_1, name_2=name_2,
        ))
    return out, True
