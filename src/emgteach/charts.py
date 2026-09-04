"""The two summary charts of the analysis: contractions, and co-activation.

They replaced two tables. A table of eighteen rows with seven numbers each
is the right thing to copy into a laboratory report and the wrong thing to
*read*: which effort was the strongest, whether the antagonist joined in,
where the spectrum sat, are all questions a bar answers before a number does.
So the screen draws these and keeps the tables behind a button, and the
report carries both.

Both functions draw into an ``Axes`` they are handed, so the same picture
appears in the tab (a Qt canvas) and in the PDF (a figure rendered to PNG).
Qt-free on purpose; matplotlib only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from emgteach.i18n import tr

__all__ = ["COLOUR_1", "COLOUR_2", "draw_coactivation_chart", "draw_contraction_chart"]

#: The two muscles' colours, the same everywhere in the application.
COLOUR_1 = "#4169E1"
COLOUR_2 = "#D62728"
_COLOUR_MDF = "#333333"
_COLOUR_OVER = "#B0243A"
_COLOUR_NOT_REPORTED = "#8A6500"


def _muscle_values(rows: Sequence[Any], which: int, use_pct: bool) -> list[float]:
    """The bar height of muscle ``which`` in every row."""
    out = []
    for r in rows:
        rms, pct = r.by_muscle(which)
        out.append(float(pct) if (use_pct and pct is not None) else float(rms))
    return out


def draw_contraction_chart(
    ax,
    rows: Sequence[Any],
    *,
    name_1: str,
    name_2: str = "",
    small: bool = False,
) -> None:
    """One bar per contraction: its peak against the maximum, or its RMS.

    With two muscles, two bars per contraction in the two muscles' colours:
    a flexion is a tall blue bar beside a short red one, and a co-activation
    is two tall bars — the thing the label in the table only *says*. The
    median frequency rides on a second axis as a dot per contraction, and
    the electromechanical delay, where the accelerometer gives one, is
    written over its bar.

    ``rows`` are :class:`emgteach.contractions.Contraction`. ``small`` trims
    the type for the tab's canvas.
    """
    ax.clear()
    if not rows:
        ax.set_axis_off()
        return
    fs_txt = 7 if small else 8
    n = len(rows)
    x = np.arange(1, n + 1)
    dos = bool(name_2) and any(r.rms_mv_other is not None for r in rows)
    use_pct = all(r.peak_pct is not None for r in rows)
    unidad = tr("Peak (% MVC)") if use_pct else tr("RMS (mV)")

    if dos:
        w = 0.38
        v1 = _muscle_values(rows, 1, use_pct)
        v2 = _muscle_values(rows, 2, use_pct)
        ax.bar(x - w / 2, v1, w, color=COLOUR_1, label=name_1, zorder=2)
        ax.bar(x + w / 2, v2, w, color=COLOUR_2, label=name_2, zorder=2)
        tope = max(max(v1, default=0.0), max(v2, default=0.0))
    else:
        w = 0.6
        v1 = _muscle_values(rows, 1, use_pct)
        ax.bar(x, v1, w, color=COLOUR_1, label=name_1 or None, zorder=2)
        tope = max(v1, default=0.0)

    if use_pct:
        # The 100 % line: a bar above it says the calibration was not a
        # maximum, which is the one thing worth seeing before anything else.
        ax.axhline(100.0, color=_COLOUR_OVER, lw=0.8, ls="--", zorder=1)
        for i, r in enumerate(rows):
            if r.peak_pct is not None and r.peak_pct > 100.0:
                ax.plot([x[i]], [r.peak_pct], marker="v", color=_COLOUR_OVER,
                        ms=5, zorder=4)
    ax.set_ylim(0, max(tope * 1.25, 100.0 * 1.15 if use_pct else tope * 1.25) or 1.0)
    ax.set_ylabel(unidad, fontsize=fs_txt)
    ax.set_xlabel(tr("Contraction"), fontsize=fs_txt)
    ax.set_xticks(x)
    ax.set_xticklabels([str(r.n) for r in rows], fontsize=fs_txt)
    ax.tick_params(axis="y", labelsize=fs_txt)
    ax.grid(axis="y", lw=0.4, alpha=0.4, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    # Electromechanical delay over its bar, where there is one.
    for i, r in enumerate(rows):
        if r.emd_ms is not None:
            altura = max(_muscle_values([r], 1, use_pct)[0],
                         _muscle_values([r], 2, use_pct)[0] if dos else 0.0)
            ax.text(x[i], altura, f"{r.emd_ms:.0f} ms", ha="center",
                    va="bottom", fontsize=fs_txt - 1, color="#555555")

    # The median frequency on its own axis: a dot per contraction, joined by
    # a faint line so a drift along a series reads as a slope.
    con_mdf = [(x[i], r.mdf_hz) for i, r in enumerate(rows) if r.mdf_hz is not None]
    if con_mdf:
        ax2 = ax.twinx()
        xs, ys = zip(*con_mdf, strict=True)
        ax2.plot(xs, ys, color=_COLOUR_MDF, lw=0.7, ls=":", zorder=3)
        ax2.plot(xs, ys, "o", mfc="white", mec=_COLOUR_MDF, ms=4, zorder=4,
                 label=tr("MDF (Hz)"))
        ax2.set_ylabel(tr("MDF (Hz)"), fontsize=fs_txt)
        ax2.tick_params(axis="y", labelsize=fs_txt)
        lo, hi = min(ys), max(ys)
        margen = max(10.0, 0.2 * (hi - lo))
        ax2.set_ylim(max(0.0, lo - margen), hi + margen)
        ax2.spines["top"].set_visible(False)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        if h1 or h2:
            ax.legend(h1 + h2, l1 + l2, fontsize=fs_txt - 1, loc="upper left",
                      ncol=3, frameon=False)
    elif dos:
        ax.legend(fontsize=fs_txt - 1, loc="upper left", ncol=2, frameon=False)


def draw_coactivation_chart(
    ax,
    results: Sequence[Any],
    *,
    name_1: str,
    name_2: str,
    small: bool = False,
) -> None:
    """One group per window: the two mean activations, and the index over them.

    The two means sit beside the index on purpose, as the table did: a bare
    86 % reads as «both worked hard» when it may mean «both were equally
    quiet», and in this practical the antagonist's mean *is* the finding.
    A window whose index is not reported gets its two bars and the reason
    in place of the number.

    ``results`` are :class:`emgteach.coactivation.CoactivationResult`.
    """
    ax.clear()
    if not results:
        ax.set_axis_off()
        return
    fs_txt = 7 if small else 8
    n = len(results)
    x = np.arange(n)
    w = 0.36
    m1 = [float(r.mean_1) for r in results]
    m2 = [float(r.mean_2) for r in results]
    ax.bar(x - w / 2, m1, w, color=COLOUR_1, label=name_1, zorder=2)
    ax.bar(x + w / 2, m2, w, color=COLOUR_2, label=name_2, zorder=2)
    tope = max(max(m1, default=0.0), max(m2, default=0.0), 1.0)
    indices = [r.index for r in results if r.index is not None]
    tope = max(tope, max(indices, default=0.0))
    for i, r in enumerate(results):
        cima = max(m1[i], m2[i])
        if r.index is not None:
            ax.plot([x[i]], [r.index], marker="D", color=_COLOUR_MDF, ms=5, zorder=4)
            ax.text(x[i], r.index + 0.04 * tope, f"{r.index:.0f} %", ha="center",
                    va="bottom", fontsize=fs_txt, fontweight="bold", zorder=5)
        else:
            ax.text(x[i], cima + 0.04 * tope, tr("not reported"), ha="center",
                    va="bottom", fontsize=fs_txt - 1, color=_COLOUR_NOT_REPORTED,
                    zorder=5)
    ax.set_ylim(0, tope * 1.35)
    etiquetas = []
    for r in results:
        ini, fin = r.window_s
        etiquetas.append(
            f"{r.label}\n{ini:.1f}–{fin:.1f} s" if fin > ini else str(r.label)  # noqa: RUF001
        )
    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas, fontsize=fs_txt)
    ax.set_ylabel(tr("Mean activation (% MVC) · index (%)"), fontsize=fs_txt)
    ax.tick_params(axis="y", labelsize=fs_txt)
    ax.grid(axis="y", lw=0.4, alpha=0.4, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.plot([], [], marker="D", color=_COLOUR_MDF, ls="", ms=5,
            label=tr("Co-activation index"))
    ax.legend(fontsize=fs_txt - 1, loc="upper left", ncol=3, frameon=False)
