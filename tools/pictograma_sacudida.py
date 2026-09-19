"""The pictogram of the calibration: brief and explosive, not held.

The one counter-intuitive gesture of the practical. Everything else the
wizard asks for is what the words say — six contractions, a grip — but a
*maximal* effort, to anyone who has lifted anything, means leaning into it
and holding; and a reference measured off a plateau is not the maximum the
task will be compared against.

So the picture says the shape of the effort and nothing else: a sharp peak,
ticked, beside a plateau, crossed. **No anatomy and no words**, which is why
one drawing serves every pair — including the ones nobody has drawn a
forearm for — and why it needs no translating. It is drawn for the panel it
appears in, about 300 px wide, and read at a glance rather than studied.

    python tools/pictograma_sacudida.py

Writes ``src/emgteach/gui/assets/recorrido/sacudida_en.png``. The ``_en`` is
what :func:`emgteach.gui.imagenes.imagen` looks for first; without a Spanish
one it falls back to this, which is the right answer for a picture with no
words in it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SALIDA = (Path(__file__).resolve().parents[1] / "src" / "emgteach" / "gui"
          / "assets" / "recorrido" / "sacudida_en.png")

VERDE = "#27AE60"
ROJO = "#C0392B"
#: The panel this is drawn on is near-black, and the page of the
#: manual it may end up in is white, so the baseline is a mid grey:
#: visible on both, loud on neither.
TINTA = "#9A9AA6"


def _pico(t: np.ndarray) -> np.ndarray:
    """A brief, explosive effort: up fast, down fast."""
    return np.exp(-(((t - 0.30) / 0.075) ** 2))


def _meseta(t: np.ndarray) -> np.ndarray:
    """The same effort leaned into and held, which is what it must not be."""
    subida = 1 / (1 + np.exp(-(t - 0.22) / 0.05))
    bajada = 1 / (1 + np.exp((t - 0.80) / 0.05))
    return subida * bajada


def dibuja(destino: Path = SALIDA) -> Path:
    fig, ejes = plt.subplots(1, 2, figsize=(3.4, 1.30), dpi=200)
    t = np.linspace(0, 1, 400)
    for ax, y, color, marca in (
        (ejes[0], _pico(t), VERDE, "✓"),
        (ejes[1], _meseta(t), ROJO, "✗"),
    ):
        ax.plot(t, y, color=color, linewidth=2.6, solid_capstyle="round")
        ax.fill_between(t, 0, y, color=color, alpha=0.16)
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.08, 1.55)
        ax.axis("off")
        # The mark goes in the corner, away from the curve it judges.
        # Grande: a la distancia a la que se mira este panel, el visto y la
        # cruz son lo primero que se lee, y son lo que dice cuál de las dos
        # formas se pide.
        ax.text(0.95, 1.30, marca, color=color, fontsize=26, fontweight="bold",
                ha="right", va="top")
        # A baseline, so the shape reads as a signal and not as a hill.
        ax.plot([0, 1], [0, 0], color=TINTA, linewidth=0.9, alpha=0.8)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.04, wspace=0.18)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, transparent=True)
    plt.close(fig)
    return destino


if __name__ == "__main__":
    ruta = dibuja()
    print(ruta, ruta.stat().st_size, "bytes")
    sys.exit(0)
