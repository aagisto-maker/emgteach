"""Render the forearm electrode-placement figure, in both languages.

    python tools/generar_electrodos.py        # both
    python tools/generar_electrodos.py en     # English only

Writes ``docs/electrodos_antebrazo_<lang>.png``, the figure the placement
guide and the manuals carry. It is the same drawing as the article's figure
of where the muscles are, built over the same base and with the same
construction, so the manual and the paper cannot drift apart.

The figure exists because "put the electrodes on the muscle belly" is not an
instruction anyone can follow precisely. What makes placement repeatable is a
**bony landmark to measure from**, plus a palpation test to confirm the muscle
underneath is the intended one. Both are drawn, and the landmark is the same
for the two channels: **the epicondyle of its own side, 5 cm away along the
belly** — the medial one for the flexor, the lateral one for the extensor.
The styloid processes are not used: they were in the construction the first
version drew, as the far end of a line the pair sat a third or a quarter of
the way down, and that is not how the pair is placed at the bench.

There is **one reference, on the olecranon**, shared by both channels: with
both pairs over the same muscle, taking either sensor's reference away changed
neither the amplitude nor the noise, so a second one buys nothing and is one
more connection to get wrong.

Each muscle is drawn in **its channel's colour in the application** —
``COLOUR_1`` and ``COLOUR_2`` of :mod:`emgteach.charts`, the ones its traces
and load bars carry — because a reader looks at this figure and then at the
screen, and two keys for the same two muscles is one too many.

The anatomical base (``tools/recorrido/base_brazos_v2.png``, shared with the
guided tour's pictures) is an AI-generated image of two forearms, made without
text or electrodes; the muscle bellies, the landmarks, the electrode positions
and every measurement on top of it are the author's, drawn to scale: elbow
crease to wrist is 25 cm, and from that come the 5 cm from each epicondyle,
the 2 cm between electrodes and the 10 mm of each one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Polygon
from matplotlib.path import Path as MplPath
from PIL import Image

from emgteach.charts import COLOUR_1, COLOUR_2

RAIZ = Path(__file__).resolve().parent.parent
BASE = Path(__file__).resolve().parent / "recorrido" / "base_brazos_v2.png"
DESTINO = RAIZ / "docs"

TEXTOS = {
    "es": {
        "titulo": "Dónde están los músculos y dónde van los electrodos",
        "cara_a": "A · Cara anterior", "cara_b": "B · Cara posterior",
        "canal_1": "Canal 1", "canal_2": "Canal 2",
        "musculo_1": "flexor radial del carpo",
        "musculo_2": "extensores radiales del carpo",
        "rotulo_1": "flexor radial\ndel carpo",
        "rotulo_2": "extensores\nradiales del carpo",
        "epitroclea": "epitróclea", "epicondilo": "epicóndilo\nlateral",
        "olecranon": "olécranon",
        "banda_1": "Los electrodos van sobre el VIENTRE del músculo, donde es ancho, nunca sobre el tendón.",
        "banda_2": "Referencia: una sola, sobre el olécranon, compartida por los dos canales.",
        "banda_3": "Localízalos palpando: canal 1 con flexión de muñeca y los dedos extendidos, canal 2 con",
        "banda_4": "extensión de muñeca. Marca con rotulador antes de limpiar la piel y pegar los electrodos.",
    },
    "en": {
        "titulo": "Where the muscles are and where the electrodes go",
        "cara_a": "A · Anterior aspect", "cara_b": "B · Posterior aspect",
        "canal_1": "Channel 1", "canal_2": "Channel 2",
        "musculo_1": "flexor carpi radialis",
        "musculo_2": "extensor carpi radialis",
        "rotulo_1": "flexor carpi\nradialis",
        "rotulo_2": "extensor carpi\nradialis",
        "epitroclea": "medial\nepicondyle", "epicondilo": "lateral\nepicondyle",
        "olecranon": "olecranon",
        "banda_1": "Electrodes go over the muscle BELLY, where it is widest — never over the tendon.",
        "banda_2": "Reference: a single one, on the olecranon, shared by both channels.",
        "banda_3": "Find them by palpation: channel 1 with wrist flexion and the fingers extended, channel 2",
        "banda_4": "with wrist extension. Mark with a pen before cleaning the skin and applying the electrodes.",
    },
}

# The base, cropped to the two forearms, and the author's construction in
# pixels of that crop.
_im = Image.open(BASE).convert("RGB")
_a = np.asarray(_im)
_nb = _a.astype(int).sum(2) < 720
_cols = np.where(_nb.any(0))[0]
_rows = np.where(_nb.any(1))[0]
IM = _im.crop((_cols.min() - 14, _rows.min() - 8, _cols.max() + 15,
               _rows.max() + 9)).crop((0, 0, 550, 572))
_M = np.asarray(IM).astype(int).sum(2) < 700

Y_CODO, Y_MUNECA = 230, 510
CM_PX = (Y_MUNECA - Y_CODO) / 25.0
EPITROCLEA, EPICONDILO = (184, 236), (480, 230)
#: The point of the elbow seen from behind, between the epicondyles and
#: nearer the medial one: where the one reference goes.
OLECRANON = (400, 200)
#: Control points of each muscle's course, from origin to insertion.
FCR = [(184, 236), (158, 300), (130, 372), (106, 448), (88, 542)]
ECR = [(482, 216), (470, 286), (462, 356), (464, 436), (470, 528)]
#: How far down the belly the pair sits, from its own epicondyle.
DESDE_EPICONDILO_CM = 5.0

ANCHO_IN = 6.5
ESC = (ANCHO_IN * 72 * 0.60) / IM.size[0]
IMG_W, IMG_H = IM.size[0] * ESC, IM.size[1] * ESC
ALTO_IN = (IMG_H + 176) / 72
W, H = ANCHO_IN * 72, ALTO_IN * 72

MUS_F, MUS_E = COLOUR_1, COLOUR_2        # the application's key, not the figure's
HUESO, TXT, REF, AZUL_T = "#333333", "#1f2933", "#12833f", "#1F4E79"


def cm(v: float) -> float:
    """Real centimetres, in pixels of the base."""
    return v * CM_PX


def curva(ctrl, n: int = 160):
    """A smooth course through the control points, parameterised by t."""
    c = np.asarray(ctrl, float)
    t = np.linspace(0, 1, len(c))
    tt = np.linspace(0, 1, n)
    cx = np.polyfit(t, c[:, 0], min(3, len(c) - 1))
    cy = np.polyfit(t, c[:, 1], min(3, len(c) - 1))
    return np.polyval(cx, tt), np.polyval(cy, tt), tt


class Lamina:
    """One figure: the base image placed in it, and everything drawn on top."""

    def __init__(self, t: dict) -> None:
        self.t = t
        self.fig = plt.figure(figsize=(ANCHO_IN, ALTO_IN), dpi=300)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(0, H)
        self.ax.axis("off")
        self.x0 = (W - IMG_W) / 2
        self.y0 = H - 62 - IMG_H
        self.ax.imshow(np.asarray(IM), zorder=1, aspect="auto",
                       extent=[self.x0, self.x0 + IMG_W,
                               self.y0, self.y0 + IMG_H])

    def px(self, x: float, y: float) -> tuple[float, float]:
        return (self.x0 + x * ESC, self.y0 + IMG_H - y * ESC)

    def silueta(self, x0: int, x1: int) -> MplPath:
        """The arm's outline between two columns, to clip a belly with."""
        izq, der = [], []
        for y in range(8, _M.shape[0] - 2):
            f = np.where(_M[y, x0:x1])[0]
            if len(f) < 8:
                continue
            izq.append((x0 + f.min(), y))
            der.append((x0 + f.max(), y))
        return MplPath([self.px(a, b) for a, b in izq + der[::-1]])

    def vientre(self, ctrl, w_max_cm: float, color: str, clip):
        """The belly: wide in the proximal third, a thin tendon distally."""
        xs, ys, tt = curva(ctrl)
        perfil = np.interp(tt, [0.0, 0.10, 0.30, 0.55, 0.72, 1.0],
                           [0.30, 0.85, 1.00, 0.62, 0.20, 0.13]) * cm(w_max_cm)
        dx, dy = np.gradient(xs), np.gradient(ys)
        n = np.hypot(dx, dy)
        nx, ny = -dy / n, dx / n
        poly = np.vstack([np.stack([xs + nx * perfil, ys + ny * perfil], 1),
                          np.stack([xs - nx * perfil, ys - ny * perfil], 1)[::-1]])
        par = Polygon([self.px(*p) for p in poly], closed=True, fc=color,
                      alpha=.46, ec=color, lw=1.0, zorder=4)
        self.ax.add_patch(par)
        par.set_clip_path(clip, transform=self.ax.transData)
        return xs, ys

    def rotulo_musculo(self, xp, yp, etq, color, dx, ha) -> None:
        """The muscle's name outside the arm, with a leader line."""
        x, y = self.px(xp, yp)
        self.ax.plot([x, x + dx], [y, y], color=color, lw=0.8, alpha=.8, zorder=7)
        self.ax.text(x + dx + (3 if ha == "left" else -3), y, etq, fontsize=8.2,
                     color=color, fontweight="bold", ha=ha, va="center",
                     zorder=8, linespacing=1.2)

    def electrodos(self, xp, yp, ang, lado) -> None:
        d = cm(2.0) / 2 * ESC
        r = cm(1.0) / 2 * ESC
        x, y = self.px(xp, yp)
        ux, uy = np.sin(np.radians(ang)), np.cos(np.radians(ang))
        for s in (+1, -1):
            self.ax.add_patch(Circle((x + s * d * ux, y + s * d * uy), r,
                                     fc="#2b2b2b", ec="white", lw=1.2, zorder=9))
            self.ax.add_patch(Circle((x + s * d * ux, y + s * d * uy), r * 0.34,
                                     fc="#e8e8e8", zorder=10))
        self.ax.annotate("", xy=(x + d * ux + lado * 13, y + d * uy),
                         xytext=(x - d * ux + lado * 13, y - d * uy), zorder=9,
                         arrowprops=dict(arrowstyle="<->", color=TXT, lw=0.9,
                                         shrinkA=0, shrinkB=0))
        self.ax.text(x + lado * 16, y, "2 cm", fontsize=8.2, color=TXT, zorder=9,
                     ha="left" if lado > 0 else "right", va="center")

    def hueso(self, xp, yp, etq, dxp, dyp, ha, relleno="white") -> None:
        """A palpable bony landmark: the thing placement is measured from."""
        x, y = self.px(xp, yp)
        x2, y2 = self.px(xp + dxp, yp + dyp)
        self.ax.add_patch(Circle((x, y), 3.2, fc=relleno, ec=HUESO, lw=1.4, zorder=9))
        self.ax.plot([x, x2], [y, y2], color=HUESO, lw=0.9, zorder=8)
        self.ax.text(x2 + (3 if ha == "left" else -3), y2, etq, fontsize=8.2,
                     color=HUESO, ha=ha, va="center", zorder=9, linespacing=1.25)

    def par_del_canal(self, ctrl, w_max_cm, color, clip, origen, lado, dx_cota):
        """A muscle with its pair, measured from its own epicondyle."""
        xs, ys = self.vientre(ctrl, w_max_cm, color, clip)
        i = int(np.argmin(np.abs(np.hypot(xs - origen[0], ys - origen[1])
                                 - cm(DESDE_EPICONDILO_CM))))
        ang = np.degrees(np.arctan2(xs[i + 3] - xs[i - 3],
                                    -(ys[i + 3] - ys[i - 3])))
        self.electrodos(xs[i], ys[i], ang, lado=lado)
        xm, ym = self.px(*origen)
        xn, yn = self.px(xs[i], ys[i])
        self.ax.annotate("", xy=(xn, yn), xytext=(xm, ym), zorder=7,
                         arrowprops=dict(arrowstyle="<->", color=color, lw=1.0,
                                         shrinkA=4, shrinkB=7))
        self.ax.text((xm + xn) / 2 + dx_cota, (ym + yn) / 2, "5 cm", fontsize=8.2,
                     color=color, fontweight="bold",
                     ha="right" if dx_cota < 0 else "left", va="center", zorder=8)

    def referencia(self, xp, yp, etq) -> None:
        """The one reference, on the olecranon."""
        x, y = self.px(xp, yp)
        self.ax.add_patch(Circle((x, y), 5.0, fc=REF, ec="white", lw=1.4, zorder=10))
        self.ax.add_patch(Circle((x, y), 1.8, fc="white", zorder=11))
        x2, y2 = self.px(xp - 40, yp - 34)
        self.ax.plot([x, x2], [y, y2], color=HUESO, lw=0.9, zorder=8)
        self.ax.text(x2 - 3, y2, etq, fontsize=8.2, color=HUESO, ha="right",
                     va="center", linespacing=1.25, zorder=9)

    def banda(self) -> None:
        """The legend under the two panels."""
        t = self.t
        y0, alto = 14, 92
        self.ax.add_patch(FancyBboxPatch(
            (26, y0), W - 52, alto, boxstyle="round,pad=0,rounding_size=6",
            fc="#f5f2ec", ec="#d9cbb8", lw=1.0, zorder=1))
        y = y0 + alto - 18
        self.ax.add_patch(Circle((44, y), 5.4, fc="#2b2b2b", ec="white", lw=1.4, zorder=3))
        self.ax.add_patch(Circle((44, y), 1.9, fc="#e8e8e8", zorder=4))
        self.ax.text(58, y, t["banda_1"], fontsize=8.5, color=TXT, va="center")
        y -= 21
        self.ax.add_patch(Circle((44, y), 5.4, fc=REF, ec="white", lw=1.4, zorder=3))
        self.ax.add_patch(Circle((44, y), 1.9, fc="white", zorder=4))
        self.ax.text(58, y, t["banda_2"], fontsize=8.5, color=TXT, va="center")
        y -= 22
        self.ax.text(44, y, t["banda_3"], fontsize=8.5, color=TXT, va="center")
        y -= 13
        self.ax.text(44, y, t["banda_4"], fontsize=8.5, color=TXT, va="center")


def construir(lang: str) -> Path:
    t = TEXTOS[lang]
    lm = Lamina(t)
    lm.ax.text(W / 2, H - 16, t["titulo"], fontsize=12.5, fontweight="bold",
               color=AZUL_T, ha="center", va="center")
    xa, _ = lm.px(125, 0)
    xb, _ = lm.px(414, 0)
    for xc, cara, canal, musculo, col in (
        (xa, t["cara_a"], t["canal_1"], t["musculo_1"], MUS_F),
        (xb, t["cara_b"], t["canal_2"], t["musculo_2"], MUS_E),
    ):
        lm.ax.text(xc, H - 33, cara, fontsize=9.6, fontweight="bold",
                   color=TXT, ha="center")
        lm.ax.text(xc, H - 45, canal, fontsize=8.6, fontweight="bold",
                   color=col, ha="center")
        lm.ax.text(xc, H - 56, musculo, fontsize=8.4, color=col, ha="center")

    clip_a, clip_b = lm.silueta(30, 265), lm.silueta(300, 545)
    # A · the flexor, measured from the medial epicondyle.
    lm.par_del_canal(FCR, 1.5, MUS_F, clip_a, EPITROCLEA, lado=-1, dx_cota=-11)
    lm.rotulo_musculo(112, 420, t["rotulo_1"], MUS_F, -58, "right")
    lm.hueso(*EPITROCLEA, t["epitroclea"], 26, -30, "left")
    # B · the extensor, measured from the lateral epicondyle, the same way.
    lm.par_del_canal(ECR, 1.7, MUS_E, clip_b, EPICONDILO, lado=-1, dx_cota=9)
    lm.rotulo_musculo(468, 430, t["rotulo_2"], MUS_E, 14, "left")
    lm.hueso(*EPICONDILO, t["epicondilo"], 24, -30, "left")
    lm.referencia(*OLECRANON, t["olecranon"])
    lm.banda()

    ruta = DESTINO / f"electrodos_antebrazo_{lang}.png"
    lm.fig.savefig(ruta, dpi=300, facecolor="white")
    plt.close(lm.fig)
    return ruta


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    idiomas = [a for a in sys.argv[1:] if a in TEXTOS] or ["es", "en"]
    for lang in idiomas:
        ruta = construir(lang)
        print(f"  {ruta.relative_to(RAIZ)}  {ANCHO_IN} × {ALTO_IN:.2f} in")
    return 0


if __name__ == "__main__":
    sys.exit(main())
