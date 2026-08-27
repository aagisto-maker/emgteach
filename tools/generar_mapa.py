"""Render the flow map: one PNG per language, practical and tab.

    python tools/generar_mapa.py

Writes into ``src/emgteach/resources/mapa/<lang>/``. The images are committed,
so the help does not need matplotlib at run time — but they can go stale,
which is what ``tests/test_mapa.py`` guards.

The drawing is deliberately plain. It is a map, not a figure: boxes, arrows
and labels, with everything the current practical does not use faded but left
in place, so the reader sees what they are not using rather than a different
diagram each time.

Every string is **measured and made to fit** its box rather than sized by eye.
Guessing widths does not survive translation: a label that fits in English
runs out of its box in Spanish, and the first version of this drawing had
"Contracción agonista / antagonista" hanging off both ends of its band.
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
#: Below this the text is unreadable; better to see it overflow while
#: reviewing than to ship something nobody can read.
CUERPO_MINIMO = 5.6


def _ancho_datos(fig, ax, t) -> float:
    """Width of a drawn text, in the axes' own coordinates."""
    caja = t.get_window_extent(renderer=fig.canvas.get_renderer())
    return abs(caja.transformed(ax.transData.inverted()).width)


#: Strings that could not be made to fit without going below the floor.
#: Collected rather than raised: one bad translation should not stop the other
#: 23 maps being rendered, but it must not pass unmentioned either.
APRETADOS: list[str] = []


def _texto(fig, ax, x, y, s, *, cabe_en=None, cuerpo=8.0, **kw):
    """Draw text, shrinking it until it fits ``cabe_en`` data units."""
    t = ax.text(x, y, s, fontsize=cuerpo, **kw)
    if cabe_en:
        ancho = _ancho_datos(fig, ax, t)
        if ancho > cabe_en:
            if cuerpo * cabe_en / ancho < CUERPO_MINIMO:
                APRETADOS.append(s)
            t.set_fontsize(max(CUERPO_MINIMO, cuerpo * cabe_en / ancho))
    return t


def _caja(fig, ax, n, encendido: bool) -> None:
    alfa = 1.0 if encendido else APAGADO
    if n.rombo:
        cx, cy = n.x, n.y
        ax.add_patch(mpatches.Polygon(
            [(cx, cy - n.h / 2), (cx + n.w / 2, cy), (cx, cy + n.h / 2),
             (cx - n.w / 2, cy)],
            closed=True, fill=False, edgecolor=TINTA, linewidth=1.2, alpha=alfa,
        ))
        # A rhombus is only that wide at its waist, so the question gets about
        # two thirds of the nominal width.
        _texto(fig, ax, cx, cy, n.titulo, cabe_en=n.w * 0.66, cuerpo=8.4,
               ha="center", va="center", color=TINTA, fontweight="bold",
               alpha=alfa)
        for i, linea in enumerate(n.lineas):
            _texto(fig, ax, cx, cy + n.h / 2 + 14 + i * 12, linea,
                   cabe_en=n.w * 1.25, cuerpo=7.6, ha="center", va="center",
                   color=SUAVE, alpha=alfa)
        return

    ax.add_patch(mpatches.FancyBboxPatch(
        (n.x, n.y), n.w, n.h, boxstyle="round,pad=0,rounding_size=3",
        fill=False, edgecolor=TINTA, linewidth=1.5, alpha=alfa,
    ))
    # Centred on the box rather than pinned 22 units below its top: the
    # branch boxes are shorter than the spine ones, and with a fixed offset
    # their second line came to rest on the bottom border.
    util = n.w - 28
    alto = 22 + len(n.lineas) * 14
    y0 = n.y + (n.h - alto) / 2
    _texto(fig, ax, n.x + 14, y0 + 11, n.titulo, cabe_en=util, cuerpo=8.8,
           color=TINTA, fontweight="bold", va="center", alpha=alfa)
    for i, linea in enumerate(n.lineas):
        _texto(fig, ax, n.x + 14, y0 + 29 + i * 14, linea, cabe_en=util,
               cuerpo=7.4, color=SUAVE, va="center", alpha=alfa)


def _flecha(fig, ax, e, encendido: bool) -> None:
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
    if not e.etiqueta_xy:
        return

    # A label sitting beside a horizontal arrow has the gap between the two
    # boxes to live in and nothing more; that gap is the last segment's
    # length. 20 rather than a token margin: a label that merely *fits* ends
    # flush against both boxes and reads as if it were touching them. A label
    # placed clear of the boxes says its own width instead.
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    horizontal = abs(x1 - x0) > abs(y1 - y0)
    cabe = e.etiqueta_ancho or (abs(x1 - x0) - 20 if horizontal else None)

    _texto(fig, ax, *e.etiqueta_xy, e.etiqueta, cabe_en=cabe, cuerpo=7.2,
           ha="center", va="bottom", color=SUAVE, alpha=alfa)


def dibujar(modo: str, estacion: int, destino: Path | None) -> None:
    """Draw one map; with ``destino`` None, draw it without writing a file.

    The dry run is what the test uses: it only wants to know whether every
    string fitted, and rendering to disk 24 times to find that out would make
    the check slow enough that nobody keeps it.
    """
    fig, ax = plt.subplots(figsize=(ANCHO / 100, ALTO / 100), dpi=150)
    ax.set_xlim(0, ANCHO)
    ax.set_ylim(ALTO, 0)          # y downwards, as the coordinates are written
    ax.axis("off")
    fig.canvas.draw()             # a renderer has to exist before measuring

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
        _flecha(fig, ax, e, modo in e.modos)
    for n in NODOS():
        _caja(fig, ax, n, modo in n.modos)

    # The band naming the practical is sized to its own text: the four names
    # differ by half again in length, and there are two languages.
    medida = _texto(fig, ax, 0, -100, mode_label(modo), cuerpo=10,
                    fontweight="bold", va="center")
    ancho_banda = min(_ancho_datos(fig, ax, medida) + 34, 460)
    medida.remove()
    # Pushed to the very top: at y=12 the longest name ("Contracción
    # agonista / antagonista") reaches far enough right to sit over the first
    # spine label, and clipped its ascenders.
    ax.add_patch(mpatches.FancyBboxPatch(
        (26, 2), ancho_banda, 26, boxstyle="round,pad=0,rounding_size=3",
        facecolor=color, edgecolor="none",
    ))
    _texto(fig, ax, 26 + ancho_banda / 2, 15, mode_label(modo),
           cabe_en=ancho_banda - 24, cuerpo=10, ha="center", va="center",
           color="white", fontweight="bold")

    # At the foot, not beside the band: the top right is now where the
    # Analysis → MVC label lives, and two lines of grey text at the same
    # height read as one crowded paragraph.
    _texto(fig, ax, ANCHO - 26, ALTO - 16,
           tr("The recording travels from left to right"),
           cuerpo=8, ha="right", va="center", color=SUAVE)

    if destino is not None:
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
    if APRETADOS:
        print(f"\n{len(set(APRETADOS))} cadenas no caben ni al cuerpo mínimo "
              f"({CUERPO_MINIMO} pt); acórtelas o ensanche su caja:")
        for s in sorted(set(APRETADOS)):
            print(f"  · {s}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
