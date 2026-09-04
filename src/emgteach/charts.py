"""The two summary charts of the analysis: contractions, and co-activation.

They replaced two tables, and their first version was the tables drawn as
bars: one bar per contraction. The author's verdict on that was exact — no
conclusion comes out of it. A chart earns its place by showing a *relation*
from which a conclusion can be read, so the contraction chart is now two
small panels: the series along time, with the trend fitted and its slope
written down, and a relation plane. For one muscle the plane is amplitude
against median frequency, contraction by contraction — the joint analysis of
spectrum and amplitude of Luttmann and colleagues (2000): a drift towards
higher amplitude and lower frequency is fatigue, towards both higher is more
force, and the other two quadrants are their opposites. For two muscles it
is the activation plane, one muscle against the other, with the wedge in
which the application calls a contraction co-activation drawn on it: a
flexion lies along one axis, an extension along the other, a grip inside the
wedge, and the slider that sets the wedge is seen doing so.

The co-activation box, with its one to three windows, cannot show a relation
and does not pretend to: one short bar per window with the index, and the
two mean activations under the window's name.

Both functions draw into a ``Figure`` they are handed, so the same picture
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
COLOUR_BOTH = "#8E44AD"
_COLOUR_MDF = "#333333"
_COLOUR_OVER = "#B0243A"
_COLOUR_NOT_REPORTED = "#8A6500"
_COLOUR_INDEX = "#5B7DB1"
_COLOUR_TREND = "#7F8C8D"

#: Fewer contractions than this and a fitted trend is a line through noise.
_MIN_FOR_TREND = 4


def _value(row: Any, which: int, use_pct: bool) -> float:
    rms, pct = row.by_muscle(which)
    return float(pct) if (use_pct and pct is not None) else float(rms)


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.polyfit(x, y, 1)[0])


def _quitar_marco(ax) -> None:
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


#: The panels the contraction chart can show. ``relation`` is the one a
#: conclusion is read off (amplitude against MDF with one muscle, one muscle
#: against the other with two); ``category`` and ``dominance`` need two
#: muscles; ``load`` needs the load markers of the guided force-velocity
#: acquisition. ``both`` is the series and the relation side by side.
CONTRACTION_VIEWS = ("relation", "series", "category", "dominance", "load", "both")
_PANELES = ("relation", "series", "category", "dominance", "load")


def draw_contraction_chart(
    fig,
    rows: Sequence[Any],
    *,
    name_1: str,
    name_2: str = "",
    both_ratio: float = 0.5,
    small: bool = False,
    view: str | Sequence[str] = "both",
    loads: Sequence[float | None] | None = None,
) -> None:
    """One or more panels of the contraction chart into ``fig``.

    ``rows`` are :class:`emgteach.contractions.Contraction`; ``both_ratio``
    is the rule under which a contraction counts as co-activation (the
    weaker muscle's peak as a share of the stronger's), drawn as a wedge on
    the two-muscle plane and as a band on the dominance bars. ``small``
    trims the type for the tab's canvas. ``view`` is a name from
    :data:`CONTRACTION_VIEWS`, or a sequence of panel names drawn side by
    side (the report does that; in the tab one panel at a time fills the
    box, since two in a box that low were a thumbnail of each). ``loads``
    is the load of each row in kg, or ``None``, from
    :func:`emgteach.contractions.load_of_each`; only the ``load`` panel
    reads it.
    """
    if isinstance(view, str):
        if view not in CONTRACTION_VIEWS:
            raise ValueError(f"view must be one of {CONTRACTION_VIEWS}, not {view!r}")
        paneles = ("series", "relation") if view == "both" else (view,)
    else:
        paneles = tuple(view)
        for p in paneles:
            if p not in _PANELES:
                raise ValueError(f"unknown panel {p!r}; panels are {_PANELES}")
    fig.clear()
    fs = 7 if small else 8
    if not rows:
        ax = fig.add_subplot(111)
        ax.set_axis_off()
        ax.text(0.5, 0.5, tr("No contractions"), ha="center", va="center",
                fontsize=fs, color="#888888", transform=ax.transAxes)
        return
    n = len(rows)
    x = np.arange(1, n + 1, dtype=float)
    dos = bool(name_2) and any(r.rms_mv_other is not None for r in rows)
    use_pct = all(r.peak_pct is not None for r in rows)
    unidad = tr("Peak (% MVC)") if use_pct else tr("RMS (mV)")
    v1 = np.array([_value(r, 1, use_pct) for r in rows])
    v2 = np.array([_value(r, 2, use_pct) for r in rows]) if dos else None

    anchos = [3, 2] if paneles == ("series", "relation") else None
    gs = fig.add_gridspec(1, len(paneles), width_ratios=anchos)
    # Every panel's axes first, then the drawing: the series twins an MDF
    # axis onto its own, and made on the fly that twin would sit between the
    # panels in ``fig.axes`` — whoever reads the figure back finds the
    # panels first, in order, and the twin last.
    ejes = [None if panel == "load" else fig.add_subplot(gs[i])
            for i, panel in enumerate(paneles)]
    for i, panel in enumerate(paneles):
        if panel == "load":
            _por_carga(fig, gs[i], rows, v1, unidad, loads, fs)
            continue
        ax = ejes[i]
        if panel == "series":
            _serie(ax, rows, x, v1, v2, name_1, name_2, dos, use_pct, unidad, fs)
        elif panel == "relation":
            if dos and v2 is not None:
                _plano_de_activacion(ax, rows, v1, v2, name_1, name_2, unidad,
                                     both_ratio, fs)
            else:
                _jasa(ax, rows, v1, unidad, fs)
        elif not (dos and v2 is not None):
            _nota(ax, tr("This view needs two muscles."), fs)
        elif panel == "category":
            _por_categoria(ax, rows, v1, v2, name_1, name_2, unidad, use_pct, fs)
        else:
            _dominancia(ax, rows, v1, v2, name_1, name_2, both_ratio, fs)


def _nota(ax, texto: str, fs: int) -> None:
    ax.set_axis_off()
    ax.text(0.5, 0.5, texto, ha="center", va="center", fontsize=fs - 1,
            color="#888888", wrap=True, transform=ax.transAxes)


def _categoria_de(row: Any, name_1: str, name_2: str) -> str:
    if row.muscle == name_1:
        return name_1
    if row.muscle == name_2:
        return name_2
    return tr("Co-activation")


def _colores(rows, name_1: str, name_2: str) -> list[str]:
    return [COLOUR_1 if r.muscle == name_1 else COLOUR_2 if r.muscle == name_2
            else COLOUR_BOTH for r in rows]


def _por_categoria(ax, rows, v1, v2, name_1, name_2, unidad, use_pct, fs) -> None:
    """Grouped by who led: the mean of each muscle per category as a pale
    bar, and every contraction as a dot on it. The reciprocal pattern and
    the grip in one picture — a flexion is one tall bar and one on the
    floor, a grip two tall ones."""
    cats: list[str] = []
    for r in rows:
        c = _categoria_de(r, name_1, name_2)
        if c not in cats:
            cats.append(c)
    x = np.arange(len(cats), dtype=float)
    w = 0.36
    rng = np.random.default_rng(0)
    cuenta = {c: sum(1 for r in rows if _categoria_de(r, name_1, name_2) == c)
              for c in cats}
    for j, (v, col, nombre) in enumerate(((v1, COLOUR_1, name_1), (v2, COLOUR_2, name_2))):
        medias = []
        for i, c in enumerate(cats):
            sel = [k for k, r in enumerate(rows) if _categoria_de(r, name_1, name_2) == c]
            vals = v[sel]
            medias.append(float(vals.mean()))
            ax.plot(x[i] + (j - 0.5) * w + rng.normal(0, 0.04, len(vals)), vals, "o",
                    color=col, ms=3.5, alpha=0.85, zorder=3)
        ax.bar(x + (j - 0.5) * w, medias, width=w, color=col, alpha=0.3,
               label=nombre, zorder=2)
    if use_pct:
        ax.axhline(5.0, color="#999999", lw=0.6, ls=":", zorder=1)
        ax.text(x[-1] + 0.5, 5.5, tr("floor 5 %"), fontsize=fs - 1, color="#999999",
                ha="right", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{c} ({cuenta[c]})" for c in cats], fontsize=fs)
    ax.set_ylabel(unidad, fontsize=fs)
    ax.tick_params(axis="y", labelsize=fs)
    # Headroom above the tallest bar for the legend, inside the axes: on
    # the title line it ran into the title once the panel shared a figure.
    tope = float(max(v1.max(), v2.max(), 1e-9))
    ax.set_ylim(0, tope * 1.35)
    ax.set_title(tr("Mean per category, and each contraction"), fontsize=fs, pad=3)
    ax.legend(fontsize=fs - 1, frameon=False, loc="upper left", ncol=2,
              handlelength=1.2, columnspacing=0.8)
    ax.grid(axis="y", lw=0.4, alpha=0.4, zorder=0)
    _quitar_marco(ax)


def _dominancia(ax, rows, v1, v2, name_1, name_2, ratio, fs) -> None:
    """One diverging bar per contraction: to the right when the first
    muscle led, to the left when the second did, as far as the difference
    over the sum. The band in the middle is where the rule calls it
    co-activation — the same ratio as the wedge on the plane."""
    n = len(rows)
    d = (v1 - v2) / np.maximum(v1 + v2, 1e-9)
    r = max(0.05, min(0.95, float(ratio)))
    banda = (1.0 - r) / (1.0 + r)
    y = np.arange(n)[::-1]
    ax.axvspan(-banda, banda, color=COLOUR_BOTH, alpha=0.10, lw=0, zorder=0)
    ax.barh(y, d, color=_colores(rows, name_1, name_2), height=0.65, zorder=2)
    ax.axvline(0.0, color="#888888", lw=0.6, zorder=1)
    paso = 2 if n > 12 else 1
    ax.set_yticks(y[::paso])
    ax.set_yticklabels([str(r_.n) for r_ in rows][::paso], fontsize=fs - 1)
    # A row of headroom above the first bar, for the band's name.
    ax.set_ylim(-0.6, n + 0.3)
    ax.set_xlim(-1.05, 1.05)
    ax.set_xticks([-1.0, 0.0, 1.0])
    ax.set_xticklabels([tr("only {name}").format(name=name_2), tr("equal"),
                        tr("only {name}").format(name=name_1)], fontsize=fs)
    etiquetas = ax.get_xticklabels()
    etiquetas[0].set_color(COLOUR_2)
    etiquetas[2].set_color(COLOUR_1)
    ax.text(0.0, n - 0.15, tr("Co-activation"), ha="center", va="center",
            fontsize=fs - 1, color=COLOUR_BOTH, zorder=3)
    ax.set_ylabel(tr("Contraction"), fontsize=fs)
    ax.set_title(tr("Who leads, and by how much"), fontsize=fs, pad=3)
    ax.tick_params(axis="y", length=0)
    _quitar_marco(ax)


def _por_carga(fig, celda, rows, v1, unidad, loads, fs) -> None:
    """Three small panels grouped by the load of the guided acquisition:
    amplitude, electromechanical delay and MDF, each as dots with the mean
    marked. Exercise 3b asks exactly this."""
    cargas = list(loads) if loads is not None else [None] * len(rows)
    if len(cargas) != len(rows) or all(c is None for c in cargas):
        ax = fig.add_subplot(celda)
        _nota(ax, tr("This view needs the load markers of the guided "
                     "force-velocity acquisition."), fs)
        return
    sub = celda.subgridspec(1, 3, wspace=0.5)
    cats: list[float | None] = sorted({c for c in cargas if c is not None})
    if any(c is None for c in cargas):
        cats.append(None)
    # Short tick labels — «2 · 3 · 5 · none» under an axis that says «Load
    # (kg)» — because «2 kg 3 kg 5 kg no load» ran together in a panel a
    # third of the box wide.
    nombres = [tr("none") if c is None else f"{c:g}" for c in cats]

    def dibujar(ax, valores, etiqueta, titulo, color) -> None:
        rng = np.random.default_rng(0)
        for i, c in enumerate(cats):
            vals = np.array([v for v, ld in zip(valores, cargas, strict=True)
                             if ld == c and v is not None and np.isfinite(v)], dtype=float)
            if not vals.size:
                continue
            ax.plot(i + rng.normal(0, 0.05, vals.size), vals, "o", color=color, ms=3.5,
                    alpha=0.8, zorder=3)
            ax.hlines(float(vals.mean()), i - 0.28, i + 0.28, color=color, lw=2.0, zorder=4)
        ax.set_xlim(-0.6, len(cats) - 0.4)
        ax.set_xticks(range(len(cats)))
        ax.set_xticklabels(nombres, fontsize=fs - 1)
        ax.set_xlabel(tr("Load (kg)"), fontsize=fs - 1)
        ax.set_ylabel(etiqueta, fontsize=fs)
        ax.set_title(titulo, fontsize=fs, pad=3)
        ax.tick_params(axis="y", labelsize=fs - 1)
        ax.grid(axis="y", lw=0.4, alpha=0.4, zorder=0)
        _quitar_marco(ax)

    dibujar(fig.add_subplot(sub[0]), list(v1), unidad, tr("Amplitude by load"), COLOUR_1)
    dibujar(fig.add_subplot(sub[1]), [r.emd_ms for r in rows], tr("EMD (ms)"),
            tr("EMD by load"), "#2E7D32")
    dibujar(fig.add_subplot(sub[2]), [r.mdf_hz for r in rows], tr("MDF (Hz)"),
            tr("MDF by load"), _COLOUR_MDF)


def _serie(ax_t, rows, x, v1, v2, name_1, name_2, dos, use_pct, unidad, fs) -> None:
    """The series along time, with its trend and the MDF on its own axis."""
    n = len(rows)
    # ── The series along time, with its trend ─────────────────────────
    # The fitted slope goes into the muscle's own legend entry («FCR +4.5
    # %/contr.»), not into an entry of its own: the legend sits above the
    # axes in a single row, and a row is what fits there.
    etiqueta_1 = name_1 or ""
    if not dos and n >= _MIN_FOR_TREND:
        pend = _slope(x, v1)
        ax_t.plot(x, np.polyval(np.polyfit(x, v1, 1), x), "--", color=COLOUR_1,
                  lw=0.8, alpha=0.7, zorder=2)
        etiqueta_1 = (tr("{name} {slope:+.1f} %/contr.") if use_pct
                      else tr("{name} {slope:+.2f} mV/contr.")).format(
                          name=name_1, slope=pend)
    ax_t.plot(x, v1, "-o", color=COLOUR_1, ms=3.5, lw=1.0, label=etiqueta_1 or None,
              zorder=3)
    if dos and v2 is not None:
        ax_t.plot(x, v2, "-o", color=COLOUR_2, ms=3.5, lw=1.0, label=name_2,
                  zorder=3)
    if use_pct:
        ax_t.axhline(100.0, color=_COLOUR_OVER, lw=0.7, ls="--", zorder=1)
    tope = float(max(v1.max(), v2.max() if v2 is not None else 0.0, 1e-9))
    ax_t.set_ylim(0, max(tope * 1.25, 112.0 if use_pct else tope * 1.25))
    ax_t.set_xlim(0.5, n + 0.5)
    ax_t.set_xticks(x)
    ax_t.set_xticklabels([str(r.n) for r in rows], fontsize=fs)
    ax_t.set_xlabel(tr("Contraction"), fontsize=fs)
    ax_t.set_ylabel(unidad, fontsize=fs)
    ax_t.tick_params(axis="y", labelsize=fs)
    ax_t.grid(axis="y", lw=0.4, alpha=0.4, zorder=0)
    _quitar_marco(ax_t)
    # Electromechanical delay over its point, where there is one.
    for i, r in enumerate(rows):
        if r.emd_ms is not None:
            ax_t.text(x[i], max(v1[i], v2[i] if v2 is not None else 0.0),
                      f"{r.emd_ms:.0f} ms", ha="center", va="bottom",
                      fontsize=fs - 1, color="#555555")
    # The median frequency on its own axis: coloured by who led when there
    # are two muscles (a series that mixes the two has no single trend), one
    # dotted line and a fitted slope when there is one.
    con_mdf = [(x[i], float(r.mdf_hz), r) for i, r in enumerate(rows)
               if r.mdf_hz is not None]
    handles, labels = ax_t.get_legend_handles_labels()
    if con_mdf:
        ax_m = ax_t.twinx()
        xs = np.array([c[0] for c in con_mdf])
        ys = np.array([c[1] for c in con_mdf])
        if dos:
            for xi, yi, r in con_mdf:
                ax_m.plot([xi], [yi], "o", mfc="white", ms=4,
                          mec=COLOUR_2 if r.channel == 2 else COLOUR_1, zorder=4)
            ax_m.plot([], [], "o", mfc="white", mec=_COLOUR_MDF, ms=4,
                      label=tr("MDF (Hz)"))
        else:
            etiqueta_mdf = tr("MDF (Hz)")
            if len(con_mdf) >= _MIN_FOR_TREND:
                ax_m.plot(xs, np.polyval(np.polyfit(xs, ys, 1), xs), "--",
                          color=_COLOUR_MDF, lw=0.8, alpha=0.7, zorder=2)
                etiqueta_mdf = tr("MDF {slope:+.1f} Hz/contr.").format(
                    slope=_slope(xs, ys))
            ax_m.plot(xs, ys, ":", color=_COLOUR_MDF, lw=0.7, zorder=3)
            ax_m.plot(xs, ys, "o", mfc="white", mec=_COLOUR_MDF, ms=4, zorder=4,
                      label=etiqueta_mdf)
        ax_m.set_ylabel(tr("MDF (Hz)"), fontsize=fs)
        ax_m.tick_params(axis="y", labelsize=fs)
        lo, hi = float(ys.min()), float(ys.max())
        margen = max(10.0, 0.25 * (hi - lo))
        ax_m.set_ylim(max(0.0, lo - margen), hi + margen)
        ax_m.spines["top"].set_visible(False)
        h2, l2 = ax_m.get_legend_handles_labels()
        handles, labels = handles + h2, labels + l2
    if handles:
        # Above the axes, one row, where the title would be: inside, it sat
        # on the data.
        ax_t.legend(handles, labels, fontsize=fs - 1, loc="lower left",
                    bbox_to_anchor=(0.0, 1.0), ncol=len(handles), frameon=False,
                    handlelength=1.4, columnspacing=0.9, borderaxespad=0.0,
                    handletextpad=0.4)


def _plano_de_activacion(ax, rows, v1, v2, name_1, name_2, unidad, ratio, fs) -> None:
    """One muscle against the other, with the co-activation wedge drawn."""
    lim = float(max(v1.max(), v2.max(), 1e-9)) * 1.18
    r = max(0.05, min(0.95, float(ratio)))
    # The wedge: the weaker muscle at or above ``ratio`` of the stronger,
    # i.e. between the lines y = r·x and y = x / r.
    ax.fill([0.0, lim, lim, r * lim], [0.0, r * lim, lim, lim],
            color=COLOUR_BOTH, alpha=0.10, lw=0, zorder=0)
    ax.plot([0.0, lim], [0.0, r * lim], color=COLOUR_BOTH, lw=0.6, ls="--",
            alpha=0.6, zorder=1)
    ax.plot([0.0, r * lim], [0.0, lim], color=COLOUR_BOTH, lw=0.6, ls="--",
            alpha=0.6, zorder=1)
    ax.plot([0.0, lim], [0.0, lim], color="#BBBBBB", lw=0.5, ls=":", zorder=1)
    for i, row in enumerate(rows):
        if row.muscle == name_1:
            c = COLOUR_1
        elif row.muscle == name_2:
            c = COLOUR_2
        else:
            c = COLOUR_BOTH
        ax.plot([v1[i]], [v2[i]], "o", color=c, ms=4.5, zorder=3)
        ax.annotate(str(row.n), (v1[i], v2[i]), textcoords="offset points",
                    xytext=(3, 3), fontsize=fs - 1, color="#444444", zorder=4)
    # The region labels hug the far edges — the right edge for the muscle on
    # x, the top edge for the muscle on y — where no point can be, since the
    # limits leave a margin beyond the strongest contraction. In the corner
    # by the axis they sat on the very points they were naming.
    ax.text(0.985 * lim, 0.5 * r * lim, tr("{name} leads").format(name=name_1),
            ha="right", va="center", fontsize=fs - 1, color=COLOUR_1, rotation=90)
    ax.text(0.5 * r * lim, 0.985 * lim, tr("{name} leads").format(name=name_2),
            ha="center", va="top", fontsize=fs - 1, color=COLOUR_2)
    ax.text(0.72 * lim, 0.72 * lim, tr("Co-activation"), ha="center", va="center",
            fontsize=fs - 1, color=COLOUR_BOTH, rotation=45)
    # The same limits on both axes, so the dotted diagonal is where the two
    # muscles are equal — but not a square: forced square in a box three
    # times wider than tall, the plane was a stamp with white on each side.
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel(f"{name_1} · {unidad}", fontsize=fs, color=COLOUR_1)
    ax.set_ylabel(f"{name_2} · {unidad}", fontsize=fs, color=COLOUR_2)
    ax.set_title(tr("Who leads each contraction"), fontsize=fs, pad=3)
    ax.tick_params(labelsize=fs)
    _quitar_marco(ax)


def _jasa(ax, rows, v1, unidad, fs) -> None:
    """Amplitude against median frequency, contraction by contraction.

    The joint analysis of spectrum and amplitude (Luttmann et al., 2000):
    each contraction is a point, joined in order; the quadrants are read
    against the first one.
    """
    puntos = [(float(r.mdf_hz), v1[i], r.n) for i, r in enumerate(rows)
              if r.mdf_hz is not None]
    if len(puntos) < 2:
        ax.set_axis_off()
        ax.text(0.5, 0.5,
                tr("The relation needs at least two contractions with an MDF."),
                ha="center", va="center", fontsize=fs - 1, color="#888888",
                wrap=True, transform=ax.transAxes)
        return
    xs = np.array([p[0] for p in puntos])
    ys = np.array([p[1] for p in puntos])
    ax.plot(xs, ys, "-", color=_COLOUR_TREND, lw=0.7, alpha=0.8, zorder=2)
    ax.plot(xs, ys, "o", color=COLOUR_1, ms=4, zorder=3)
    for xi, yi, k in puntos:
        ax.annotate(str(k), (xi, yi), textcoords="offset points", xytext=(3, 3),
                    fontsize=fs - 1, color="#444444", zorder=4)
    # The crosshair through the first contraction: the quadrants are where
    # the rest of the series went from there.
    ax.axvline(xs[0], color="#BBBBBB", lw=0.5, ls=":", zorder=1)
    ax.axhline(ys[0], color="#BBBBBB", lw=0.5, ls=":", zorder=1)
    dx = max(6.0, 0.3 * float(np.ptp(xs)))
    dy = max(0.2 * float(np.ptp(ys)), 0.12 * float(ys.max()), 1e-6)
    x0, x1 = float(xs.min()) - dx, float(xs.max()) + dx
    y0, y1 = max(0.0, float(ys.min()) - dy), float(ys.max()) + dy
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    esquinas = (
        (x0, y1, "left", "top", tr("fatigue")),
        (x1, y1, "right", "top", tr("more force")),
        (x0, y0, "left", "bottom", tr("less force")),
        (x1, y0, "right", "bottom", tr("recovery")),
    )
    for ex, ey, ha, va, texto in esquinas:
        ax.text(ex, ey, texto, ha=ha, va=va, fontsize=fs - 1, color="#999999",
                style="italic", zorder=1)
    ax.set_xlabel(tr("MDF (Hz)"), fontsize=fs)
    ax.set_ylabel(unidad, fontsize=fs)
    ax.set_title(tr("Amplitude against MDF (JASA)"), fontsize=fs, pad=3)
    ax.tick_params(labelsize=fs)
    _quitar_marco(ax)


def draw_coactivation_chart(
    fig,
    results: Sequence[Any],
    *,
    name_1: str,
    name_2: str,
    small: bool = False,
) -> None:
    """One line per window: its name on the left, the index as a bar, and
    the two means written after it.

    ``results`` are :class:`emgteach.coactivation.CoactivationResult`. A
    window whose index is not reported gets a hatched empty bar and the word.
    Everything of a window sits on its one line — the first version stacked
    the means under the name in a second line of tick label, and three
    windows in a box 150 px high were a smudge.
    """
    fig.clear()
    ax = fig.add_subplot(111)
    fs = 8 if small else 9
    if not results:
        ax.set_axis_off()
        return
    n = len(results)
    y = np.arange(n)[::-1]
    etiquetas = []
    for yi, r in zip(y, results, strict=True):
        ini, fin = r.window_s
        tramo = f" ({ini:.0f}–{fin:.0f} s)" if fin > ini else ""  # noqa: RUF001
        etiquetas.append(f"{r.label}{tramo}")
        medias = f"{name_1} {r.mean_1:.0f} · {name_2} {r.mean_2:.0f}"
        if r.index is not None:
            idx = float(r.index)
            ax.barh(yi, idx, height=0.6, color=_COLOUR_INDEX, zorder=2)
            # Inside the bar once there is room, so a high index never runs
            # into the means written after the scale.
            if idx >= 30:
                ax.text(idx - 2, yi, f"{idx:.0f} %", va="center", ha="right",
                        fontsize=fs, fontweight="bold", color="white", zorder=3)
            else:
                ax.text(idx + 2, yi, f"{idx:.0f} %", va="center", ha="left",
                        fontsize=fs, fontweight="bold", zorder=3)
            ax.text(103, yi, medias, va="center", ha="left", fontsize=fs - 1,
                    color="#555555", zorder=3)
        else:
            ax.barh(yi, 100.0, height=0.6, facecolor="white", edgecolor="#CCCCCC",
                    hatch="///", lw=0.6, zorder=2)
            ax.text(2, yi, tr("not reported"), va="center", ha="left", fontsize=fs,
                    color=_COLOUR_NOT_REPORTED, zorder=3,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
            ax.text(103, yi, medias, va="center", ha="left", fontsize=fs - 1,
                    color="#555555", zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(etiquetas, fontsize=fs)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlim(0, 150)
    ax.set_xticks([0, 50, 100])
    ax.tick_params(axis="x", labelsize=fs)
    ax.set_xlabel(tr("Index (%) · means in % MVC"), fontsize=fs)
    ax.grid(axis="x", lw=0.4, alpha=0.4, zorder=0)
    _quitar_marco(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
