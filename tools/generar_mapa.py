"""Render the flow map: one PNG per language, practical and tab.

    python tools/generar_mapa.py

Writes into ``src/emgteach/gui/../resources/mapa/<lang>/``. The images are
committed, so the help does not need matplotlib at run time — but they can go
stale, which is what ``tests/test_mapa.py`` guards: it fails if a practical
exists with no picture.

The drawing is deliberately plain. It is a map, not a figure: boxes, arrows
and labels, with everything the current practical does not use faded but left
in place, so the reader sees what they are not using rather than a different
diagram each time.
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emgteach.gui.mapa import (
    ENLACES,
    ESTACIONES,
    MAPA_DIR,
    NODOS,
)
from emgteach.i18n import set_language, tr
from emgteach.modes import (
    MODES,
    mode_complexity_colour,
    mode_label,
)

ANCHO, ALTO = 940, 520
TINTA = "#16202A"
SUAVE = "#4A5A68"
APAGADO = 0.13


def _caja(ax, n, encendido: bool) -> None:
    alfa = 1.0 if encendido else APAGADO
    if n.rombo:
        cx, cy = n.x, n.y
        ax.add_patch(mpatches.Polygon(
            [(cx, cy - n.h / 2), (cx + n.w / 2, cy), (cx, cy + n.h / 2),
             (cx - n.w / 2, cy)],
            closed=True, fill=False, edgecolor=TINTA, linewidth=1.2, alpha=alfa,
        ))
        ax.text(cx, cy, n.titulo, ha="center", va="center", color=TINTA,
                fontsize=8.4, fontweight="bold", alpha=alfa)
        # The note goes *below* the diamond: inside, it would have to be
        # shorter than the shape is wide at that height, which is not much.
        for i, linea in enumerate(n.lineas):
            ax.text(cx, cy + n.h / 2 + 14 + i * 12, linea, ha="center",
                    va="center", color=SUAVE, fontsize=7.6, alpha=alfa)
        return

    ax.add_patch(mpatches.FancyBboxPatch(
        (n.x, n.y), n.w, n.h, boxstyle="round,pad=0,rounding_size=3",
        fill=False, edgecolor=TINTA, linewidth=1.5, alpha=alfa,
    ))
    ax.text(n.x + 14, n.y + 22, n.titulo, color=TINTA, fontsize=8.8,
            fontweight="bold", va="center", alpha=alfa)
    for i, linea in enumerate(n.lineas):
        ax.text(n.x + 14, n.y + 42 + i * 14, linea, color=SUAVE, fontsize=7.4,
                va="center", alpha=alfa)


def _flecha(ax, e, encendido: bool) -> None:
    alfa = 1.0 if encendido else APAGADO
    estilo = (0, (4, 3)) if e.discontinuo else "solid"
    pts = e.puntos
    for a, b in pairwise(pts[:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=TINTA, linewidth=1.3,
                linestyle=estilo, alpha=alfa, solid_capstyle="round")
    ax.annotate(
        "", xy=pts[-1], xytext=pts[-2],
        arrowprops={"arrowstyle": "-|>", "color": TINTA, "linewidth": 1.3,
                    "linestyle": estilo, "alpha": alfa,
                    "shrinkA": 0, "shrinkB": 0},
    )
    if e.etiqueta and e.etiqueta_xy:
        ax.text(*e.etiqueta_xy, e.etiqueta, ha="center", va="bottom",
                color=SUAVE, fontsize=7.2, alpha=alfa)
    for i, linea in enumerate(e.lineas_etiqueta):
        x, y = e.etiqueta_xy or (0, 0)
        ax.text(x, y + i * 10, linea, ha="center", va="bottom", color=SUAVE,
                fontsize=7.2, alpha=alfa)


def dibujar(modo: str, estacion: int, destino: Path) -> None:
    fig, ax = plt.subplots(figsize=(ANCHO / 100, ALTO / 100), dpi=150)
    ax.set_xlim(0, ANCHO)
    ax.set_ylim(ALTO, 0)          # y downwards, as the coordinates are written
    ax.axis("off")

    color = mode_complexity_colour(modo)

    # The ring goes first so the box is drawn over it.
    for n in NODOS():
        if n.estacion == estacion:
            ax.add_patch(mpatches.FancyBboxPatch(
                (n.x - 8, n.y - 8), n.w + 16, n.h + 16,
                boxstyle="round,pad=0,rounding_size=5",
                fill=False, edgecolor=color, linewidth=3,
            ))

    for e in ENLACES():
        _flecha(ax, e, modo in e.modos)
    for n in NODOS():
        _caja(ax, n, modo in n.modos)

    # Which practical this picture is of, in its own colour.
    ax.add_patch(mpatches.FancyBboxPatch(
        (26, 12), 300, 30, boxstyle="round,pad=0,rounding_size=3",
        facecolor=color, edgecolor="none",
    ))
    ax.text(176, 27, mode_label(modo), ha="center", va="center",
            color="white", fontsize=10, fontweight="bold")
    ax.text(
        ANCHO - 26, 27,
        tr("The recording travels from left to right"),
        ha="right", va="center", color=SUAVE, fontsize=8,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, bbox_inches="tight", pad_inches=0.12,
                facecolor="white")
    plt.close(fig)


def main() -> int:
    hechos = 0
    for lang in ("es", "en"):
        set_language(lang)
        for modo in MODES:
            for estacion in ESTACIONES:
                destino = MAPA_DIR / lang / f"mapa-{modo}-{estacion}.png"
                dibujar(modo, estacion, destino)
                hechos += 1
    print(f"{hechos} mapas en {MAPA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
