"""Build the pictures the guided tour shows, from one base image.

The pictures of the tour have to leave no doubt — where the electrodes go,
what to do when the screen says FCR or ECR — and a small picture does that
better as a diagram over one arm than as a set of photographs: one base, and
every picture a crop of it with the anatomy drawn on top. The base
(``recorrido/base_brazos_v2.png``) is an AI-generated image of two forearms,
made without text or electrodes; the muscle bellies, the landmarks and the
electrode positions are the author's, taken as they are from the construction
of the article's Figure 1:

* flexor carpi radialis: medial epicondyle to the base of the second
  metacarpal; electrodes on the belly, 5 cm from the epicondyle;
* extensor carpi radialis: lateral epicondyle towards the ulnar styloid;
  electrodes a quarter of the way down that line;
* the reference over the ulnar styloid, one for both channels;
* the pair 2 cm apart, along the muscle.

What changes from the figure is the colour, which follows the application's
panels — first muscle blue, second red — because that is the key students
learn on screen, and the size of the lettering, which is set for a panel a
few hundred pixels wide. The calibration's numbers are read from the
constants the wizard runs on, so the picture cannot fall behind the protocol.

Run from the repository root::

    python tools/imagenes_recorrido.py

It writes ``src/emgteach/gui/assets/recorrido/{electrodos,calibracion}_{es,en}.png``.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Polygon
from PIL import Image

from emgteach.charts import COLOUR_1, COLOUR_2
from emgteach.gui.tabs.acquisition import MVC_READY_S, MVC_REST_S
from emgteach.profiles import EMG_PROFILE

RAIZ = Path(__file__).resolve().parent
BASE = RAIZ / "recorrido" / "base_brazos_v2.png"
SALIDA = RAIZ.parent / "src" / "emgteach" / "gui" / "assets" / "recorrido"

MUS_1, MUS_2 = COLOUR_1, COLOUR_2        # the application's key, not the figure's
HUESO, TXT, REF, TITULO = "#333333", "#1f2933", "#12833f", "#1F4E79"
DPI = 200                                 # 2x for high-density screens

# ---------------------------------------------------------------- the base
_im = Image.open(BASE).convert("RGB")
_a = np.asarray(_im)
_nb = _a.astype(int).sum(2) < 720
_cols = np.where(_nb.any(0))[0]
_rows = np.where(_nb.any(1))[0]
IM = _im.crop((_cols.min() - 14, _rows.min() - 8, _cols.max() + 15,
               _rows.max() + 9)).crop((0, 0, 550, 572))
_M = np.asarray(IM).astype(int).sum(2) < 700

# The author's construction, in pixels of the cropped base.
Y_CODO, Y_MUNECA = 230, 510
CM_PX = (Y_MUNECA - Y_CODO) / 25.0
FCR = [(184, 236), (158, 300), (130, 372), (106, 448), (88, 542)]
ECR = [(482, 216), (470, 286), (462, 356), (464, 436), (470, 528)]
EPITROCLEA, EPICONDILO = (184, 236), (480, 230)
ESTILOIDES_CUBITO = (409, Y_MUNECA + 4)


def cm(v: float) -> float:
    return v * CM_PX


def curva(ctrl, n=160):
    c = np.asarray(ctrl, float)
    t = np.linspace(0, 1, len(c))
    tt = np.linspace(0, 1, n)
    cx = np.polyfit(t, c[:, 0], min(3, len(c) - 1))
    cy = np.polyfit(t, c[:, 1], min(3, len(c) - 1))
    return np.polyval(cx, tt), np.polyval(cy, tt), tt


def punto_fcr():
    """Electrode centre on the FCR belly, 5 cm from the epicondyle."""
    xs, ys, _ = curva(FCR)
    i = int(np.argmin(np.abs(np.hypot(xs - EPITROCLEA[0], ys - EPITROCLEA[1]) - cm(5.0))))
    ang = np.degrees(np.arctan2(xs[i + 3] - xs[i - 3], -(ys[i + 3] - ys[i - 3])))
    return xs[i], ys[i], ang


def punto_ecr():
    """Electrode centre on the ECR belly, a quarter of the way from the
    lateral epicondyle to the ulnar styloid."""
    xs, ys, _ = curva(ECR)
    xq = EPICONDILO[0] + 0.25 * (ESTILOIDES_CUBITO[0] - EPICONDILO[0])
    yq = Y_CODO + 0.25 * (Y_MUNECA - Y_CODO)
    j = int(np.argmin(np.hypot(xs - xq, ys - yq)))
    ang = np.degrees(np.arctan2(xs[j + 3] - xs[j - 3], -(ys[j + 3] - ys[j - 3])))
    return xs[j], ys[j], ang


class Lienzo:
    """One axes in points, with the base image placed in it."""

    def __init__(self, ax, recorte, x0, y0, ancho):
        self.ax = ax
        self.rx0, self.ry0, self.rx1, self.ry1 = recorte
        self.esc = ancho / (self.rx1 - self.rx0)
        self.x0, self.y0 = x0, y0
        self.alto = (self.ry1 - self.ry0) * self.esc
        sub = np.asarray(IM)[self.ry0:self.ry1, self.rx0:self.rx1]
        ax.imshow(sub, extent=[x0, x0 + ancho, y0, y0 + self.alto], zorder=1,
                  aspect="auto")

    def px(self, x, y):
        return (self.x0 + (x - self.rx0) * self.esc,
                self.y0 + self.alto - (y - self.ry0) * self.esc)

    def silueta(self, x0, x1):
        izq, der = [], []
        for y in range(max(8, self.ry0), min(_M.shape[0] - 2, self.ry1)):
            f = np.where(_M[y, x0:x1])[0]
            if len(f) < 8:
                continue
            izq.append((x0 + f.min(), y))
            der.append((x0 + f.max(), y))
        from matplotlib.path import Path as MplPath
        return MplPath([self.px(a, b) for a, b in izq + der[::-1]])

    def vientre(self, ctrl, w_max_cm, color, clip):
        xs, ys, tt = curva(ctrl)
        wmax = cm(w_max_cm)
        perfil = np.interp(tt, [0.0, 0.10, 0.30, 0.55, 0.72, 1.0],
                           [0.30, 0.85, 1.00, 0.62, 0.20, 0.13]) * wmax
        dx, dy = np.gradient(xs), np.gradient(ys)
        n = np.hypot(dx, dy)
        nx, ny = -dy / n, dx / n
        poly = np.vstack([np.stack([xs + nx * perfil, ys + ny * perfil], 1),
                          np.stack([xs - nx * perfil, ys - ny * perfil], 1)[::-1]])
        par = Polygon([self.px(*p) for p in poly], closed=True, fc=color,
                      alpha=.56, ec=color, lw=1.2, zorder=4)
        self.ax.add_patch(par)
        par.set_clip_path(clip, transform=self.ax.transData)

    def electrodos(self, x, y, ang):
        d = cm(2.0) / 2 * self.esc
        r = max(cm(1.0) / 2 * self.esc, 4.2)
        cx, cy = self.px(x, y)
        ux, uy = np.sin(np.radians(ang)), np.cos(np.radians(ang))
        for s in (+1, -1):
            self.ax.add_patch(Circle((cx + s * d * ux, cy + s * d * uy), r,
                                     fc="#2b2b2b", ec="white", lw=1.4, zorder=9))
            self.ax.add_patch(Circle((cx + s * d * ux, cy + s * d * uy), r * .34,
                                     fc="#e8e8e8", zorder=10))

    def referencia(self, x, y):
        cx, cy = self.px(x, y)
        self.ax.add_patch(Circle((cx, cy), 6.0, fc=REF, ec="white", lw=1.6, zorder=10))
        self.ax.add_patch(Circle((cx, cy), 2.2, fc="white", zorder=11))

    def hito(self, x, y, texto, dx, dy, ha, tam):
        cx, cy = self.px(x, y)
        self.ax.add_patch(Circle((cx, cy), 3.6, fc="white", ec=HUESO, lw=1.5, zorder=9))
        self.ax.plot([cx, cx + dx], [cy, cy + dy], color=HUESO, lw=1.0, zorder=8)
        desp = {"left": 3, "right": -3}.get(ha, 0)
        self.ax.text(cx + dx + desp, cy + dy + (2 if ha == "center" else 0), texto,
                     fontsize=tam, color=HUESO, ha=ha,
                     va="bottom" if ha == "center" else "center", zorder=9,
                     linespacing=1.15)


TEXTOS = {
    "es": {
        "electrodos": "Dónde van los electrodos",
        "canal1": "Canal 1 · FCR", "canal2": "Canal 2 · ECR",
        "cara1": "flexor radial del carpo\ncara anterior",
        "cara2": "extensores radiales del carpo\ncara posterior",
        "epitroclea": "epitróclea", "epicondilo": "epicóndilo\nlateral",
        "estiloides": "estiloides\ndel cúbito",
        "par": "pareja sobre el vientre del músculo, a lo largo de él",
        "ref": "referencia: una sola, para los dos canales",
        "calibracion": "La calibración, paso a paso",
        "calent": "Calentamiento\n{warm} s\n2 o 3 contracciones\nsuaves de cada músculo",
        "fcr": "FCR\n{n} esfuerzos máximos\nde {dur} s",
        "ecr": "ECR\n{n} esfuerzos máximos\nde {dur} s",
        "cada": "Cada esfuerzo: aviso de {cue} s  →  a tope {dur} s, hasta que la cuenta llegue a 0  →  descanso de {rest} s",
        "gesto_fcr": "Cuando pone FCR\npuño cerrado, palma arriba\nbajo el borde de la mesa;\nempujar hacia arriba",
        "gesto_ecr": "Cuando pone ECR\ndorso de la mano contra\nel tablero, antebrazo\npronado, dedos relajados",
    },
    "en": {
        "electrodos": "Where the electrodes go",
        "canal1": "Channel 1 · FCR", "canal2": "Channel 2 · ECR",
        "cara1": "flexor carpi radialis\nanterior face",
        "cara2": "extensor carpi radialis\nposterior face",
        "epitroclea": "medial\nepicondyle", "epicondilo": "lateral\nepicondyle",
        "estiloides": "ulnar\nstyloid",
        "par": "pair on the muscle belly, along the muscle",
        "ref": "reference: one, shared by both channels",
        "calibracion": "The calibration, step by step",
        "calent": "Warm-up\n{warm} s · two or three\neasy contractions\nof each muscle",
        "fcr": "FCR\n{n} maximal efforts\nof {dur} s",
        "ecr": "ECR\n{n} maximal efforts\nof {dur} s",
        "cada": "Each effort: {cue} s warning  →  flat out for {dur} s, until the count reaches 0  →  {rest} s rest",
        "gesto_fcr": "When it says FCR\nfist closed, palm up\nunder the table edge;\npush upwards",
        "gesto_ecr": "When it says ECR\nback of the hand against\nthe table top, forearm\npronated, fingers relaxed",
    },
}


def _cifra(x: float, idioma: str) -> str:
    t = f"{x:g}"
    return t.replace(".", ",") if idioma == "es" else t


def _figura(ancho_pt, alto_pt):
    fig = plt.figure(figsize=(ancho_pt / 72, alto_pt / 72), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ancho_pt)
    ax.set_ylim(0, alto_pt)
    ax.axis("off")
    return fig, ax


def _leyenda_electrodo(ax, x, y, relleno, centro):
    ax.add_patch(Circle((x, y), 5.2, fc=relleno, ec="white", lw=1.4, zorder=3))
    ax.add_patch(Circle((x, y), 1.9, fc=centro, zorder=4))


def electrodos(idioma: str) -> Path:
    t = TEXTOS[idioma]
    W, H = 380, 420
    fig, ax = _figura(W, H)
    ax.text(W / 2, H - 15, t["electrodos"], fontsize=13, fontweight="bold",
            color=TITULO, ha="center", va="center")
    lz = Lienzo(ax, (20, 150, 550, 572), 8, 58, W - 16)
    for xc, canal, cara, col in ((125, t["canal1"], t["cara1"], MUS_1),
                                 (414, t["canal2"], t["cara2"], MUS_2)):
        x, _ = lz.px(xc, 0)
        ax.text(x, H - 36, canal, fontsize=10.5, fontweight="bold", color=col, ha="center")
        ax.text(x, H - 50, cara, fontsize=8.2, color=col, ha="center", va="top",
                linespacing=1.1)
    lz.vientre(FCR, 1.5, MUS_1, lz.silueta(30, 265))
    lz.vientre(ECR, 1.7, MUS_2, lz.silueta(300, 545))
    lz.electrodos(*punto_fcr())
    lz.electrodos(*punto_ecr())
    lz.referencia(*ESTILOIDES_CUBITO)
    lz.hito(*EPITROCLEA, t["epitroclea"], 20, -26, "left", 8.2)
    lz.hito(*EPICONDILO, t["epicondilo"], -4, 26, "center", 8.2)
    xr, yr = lz.px(*ESTILOIDES_CUBITO)
    ax.plot([xr, xr - 22], [yr, yr + 16], color=HUESO, lw=1.0, zorder=8)
    ax.text(xr - 25, yr + 16, t["estiloides"], fontsize=8.2, color=HUESO,
            ha="right", va="center", linespacing=1.15, zorder=9)
    # The 5 cm that places the FCR pair, from the epicondyle.
    xe, ye = lz.px(*EPITROCLEA)
    xf, yf, _ = punto_fcr()
    xn, yn = lz.px(xf, yf)
    ax.annotate("", xy=(xn, yn), xytext=(xe, ye), zorder=7,
                arrowprops=dict(arrowstyle="<->", color=MUS_1, lw=1.1,
                                shrinkA=4, shrinkB=8))
    ax.text((xe + xn) / 2 - 7, (ye + yn) / 2, "5 cm", fontsize=8.6,
            fontweight="bold", color=MUS_1, ha="right", va="center", zorder=8)
    # Legend.
    ax.add_patch(FancyBboxPatch((8, 6), W - 16, 44,
                                boxstyle="round,pad=0,rounding_size=5",
                                fc="#f5f2ec", ec="#d9cbb8", lw=1.0, zorder=1))
    _leyenda_electrodo(ax, 22, 37, "#2b2b2b", "#e8e8e8")
    ax.text(33, 37, t["par"], fontsize=8.4, color=TXT, va="center")
    _leyenda_electrodo(ax, 22, 18, REF, "white")
    ax.text(33, 18, t["ref"], fontsize=8.4, color=TXT, va="center")
    ruta = SALIDA / f"electrodos_{idioma}.png"
    fig.savefig(ruta, dpi=DPI, facecolor="white")
    plt.close(fig)
    return ruta


def calibracion(idioma: str) -> Path:
    t = TEXTOS[idioma]
    p = EMG_PROFILE
    c = {"warm": _cifra(p.warmup_s, idioma), "n": p.mvc_bursts,
         "dur": _cifra(p.mvc_burst_s, idioma), "cue": _cifra(MVC_READY_S, idioma),
         "rest": _cifra(MVC_REST_S, idioma)}
    W, H = 380, 246
    fig, ax = _figura(W, H)
    ax.text(W / 2, H - 15, t["calibracion"], fontsize=13, fontweight="bold",
            color=TITULO, ha="center", va="center")
    # The sequence, in order: warm-up, then each muscle.
    cajas = ((t["calent"].format(**c), "#6B7580"),
             (t["fcr"].format(**c), MUS_1),
             (t["ecr"].format(**c), MUS_2))
    ancho, alto, y0 = 112, 62, H - 100
    xs = [8, 8 + ancho + 14, 8 + 2 * (ancho + 14)]
    for x, (texto, col) in zip(xs, cajas, strict=True):
        ax.add_patch(FancyBboxPatch((x, y0), ancho, alto,
                                    boxstyle="round,pad=0,rounding_size=6",
                                    fc="white", ec=col, lw=1.8, zorder=2))
        cabeza, _, resto = texto.partition("\n")
        ax.text(x + ancho / 2, y0 + alto - 12, cabeza, fontsize=10,
                fontweight="bold", color=col, ha="center", va="center", zorder=3)
        ax.text(x + ancho / 2, y0 + alto - 24, resto, fontsize=7.8, color=TXT,
                ha="center", va="top", linespacing=1.15, zorder=3)
    for x in xs[:2]:
        ax.annotate("", xy=(x + ancho + 13, y0 + alto / 2),
                    xytext=(x + ancho + 1, y0 + alto / 2),
                    arrowprops=dict(arrowstyle="-|>", color="#6B7580", lw=1.4))
    ax.text(W / 2, y0 - 12, t["cada"].format(**c), fontsize=7.6, color=TXT,
            ha="center", va="center", wrap=True)
    # Which forearm, and what to do, for each name on the screen.
    for (recorte, ctrl, wcm, x0, col, clave, punto, xs_sil) in (
        ((30, 180, 265, 572), FCR, 1.5, 8, MUS_1, "gesto_fcr", punto_fcr(), (30, 265)),
        ((300, 180, 545, 572), ECR, 1.7, W / 2 + 4, MUS_2, "gesto_ecr", punto_ecr(), (300, 545)),
    ):
        lz = Lienzo(ax, recorte, x0, 8, 64)
        lz.vientre(ctrl, wcm, col, lz.silueta(*xs_sil))
        lz.electrodos(*punto)
        if clave == "gesto_ecr":
            lz.referencia(*ESTILOIDES_CUBITO)
        cabeza, _, resto = t[clave].partition("\n")
        ax.text(x0 + 70, 8 + lz.alto - 6, cabeza, fontsize=9.2, fontweight="bold",
                color=col, ha="left", va="top")
        ax.text(x0 + 70, 8 + lz.alto - 22, resto, fontsize=7.9, color=TXT,
                ha="left", va="top", linespacing=1.2)
    ruta = SALIDA / f"calibracion_{idioma}.png"
    fig.savefig(ruta, dpi=DPI, facecolor="white")
    plt.close(fig)
    return ruta


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for idioma in ("es", "en"):
        for hacer in (electrodos, calibracion):
            ruta = hacer(idioma)
            with Image.open(ruta) as im:
                print(f"{ruta.relative_to(RAIZ.parent)}  {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
