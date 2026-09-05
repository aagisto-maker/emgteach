"""Drawing helpers shared by the screen panels and the report figures.

Whatever is drawn on both has to come from one place, or the PDF the
student hands in stops matching the panel they were looking at. These take
a matplotlib axis and the analysis result and know nothing about Qt.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from emgteach.i18n import tr


def draw_spectrum_before_filter(ax: Any, result: Mapping[str, Any]) -> None:
    """The raw spectrum, faint, behind the filtered one.

    The student is told a band-pass and a notch were applied; here they see
    what was taken away — the mains line at 50 Hz, the movement below
    20 Hz. The axis stays scaled to the filtered spectrum on purpose: those
    two features can be tens of times taller, and letting them set the
    scale would flatten the spectrum the panel is about. They go off the
    top, which is the point.
    """
    f = result.get("frequencies_raw")
    p = result.get("psd_raw")
    if f is None or p is None:
        return
    ax.plot(f, p, color="#9AA5B1", lw=1.0, alpha=0.85,
            label=tr("Before the filter (raw)"))
    psd = np.asarray(result.get("psd", ()), dtype=np.float64)
    top = float(np.max(psd)) if psd.size else 0.0
    if top > 0.0:
        ax.set_ylim(0.0, top * 1.35)


def draw_emd_note(ax: Any, result: Mapping[str, Any]) -> None:
    """The mean electromechanical delay, in the corner of the movement panel.

    The number itself lives in the contraction table; this is the reminder
    on the figure that the gap between the two curves has a name and a
    value.
    """
    emd = result.get("emd_ms_mean")
    if emd is None:
        return
    filas = [c for c in (result.get("contractions") or []) if c.emd_ms is not None]
    ax.text(
        0.99, 0.03,
        tr("Electromechanical delay: {ms:.0f} ms (mean of {n})").format(
            ms=float(emd), n=len(filas)),
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=7, color="#D35400",
    )
