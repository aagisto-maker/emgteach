"""Figura 6 del artículo: del patrón recíproco a la coactivación.

Dos paneles con la misma escala de tiempo y el mismo eje vertical en % CVM:

    (a) las flexiones y las extensiones alternadas — el patrón recíproco, un
        músculo activo mientras el otro calla;
    (b) la presa — los dos a la vez, que es la coactivación.

Las dos envolventes van superpuestas, cada ventana con nombre queda sombreada
y rotulada con su índice, y el eje vertical es el mismo en los dos paneles:
sin eso la comparación no se sostiene, porque lo que la figura afirma es
precisamente que en (b) las dos curvas suben juntas y en (a) no.

    python tools/figura6.py --edf C:\\Records\\P01_tuned.edf

El registro tiene que ser el **afinado**, con los fragmentos ya nombrados en
la pestaña de Análisis: las ventanas de la figura son esos nombres. Un
registro sin nombrar se dibuja igual, en un solo tramo y diciéndolo, que es lo
que pasa con `ejemplo_par_FCR_ECR.edf` — sirve para probar la herramienta, no
como figura.

La señal no se vuelve a procesar aquí: se conduce la aplicación y se dibuja lo
que ella calcula, para que la figura no pueda discrepar de los números del
artículo.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import matplotlib
import numpy as np
from PySide6.QtCore import QElapsedTimer, QSettings
from PySide6.QtWidgets import QApplication

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from emgteach.gui.app import MainWindow
from emgteach.i18n import set_language
from emgteach.modes import MODE_PAIR

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parent.parent

#: Lienzo de la revista: 6,5 pulgadas es el ancho de página en columna única.
ANCHO_PULGADAS, ALTO_PULGADAS = 6.5, 4.0

#: Ninguna letra por debajo de 8 puntos, que es el mínimo legible una vez
#: escalada la figura al ancho de página.
PUNTOS = 8

#: Los mismos dos colores que usa la aplicación para agonista y antagonista,
#: para que quien vea la figura y luego la pantalla reconozca cuál es cuál.
AZUL, ROJO = "#1f4fd8", "#c0392b"

#: Los rótulos de la figura, aquí y no en `i18n.py`: son de esta herramienta,
#: no de la aplicación, y el catálogo de la aplicación solo debe llevar lo que
#: alguien puede leer en su pantalla.
ROTULOS = {
    "en": {
        "y": "Activation (% MVC)",
        "x": "Time within the manoeuvre (s)",
        "a": "(a) Alternating flexion and extension — reciprocal pattern",
        "b": "(b) Grip — the two muscles together",
        "coact": "co-activation",
        "vacio": "No window of this kind in this recording",
    },
    "es": {
        "y": "Activación (% CVM)",
        "x": "Tiempo dentro de la maniobra (s)",
        "a": "(a) Flexión y extensión alternadas — patrón recíproco",
        "b": "(b) Presa — los dos músculos a la vez",
        "coact": "coactivación",
        "vacio": "Este registro no tiene una ventana de ese tipo",
    },
}

app = QApplication.instance() or QApplication([])


def analiza(edf: Path) -> dict:
    """Conduce la aplicación sobre el registro y devuelve su resultado."""
    s = QSettings("emgteach-figura6", "material")
    s.clear()
    s.setValue("app/mode", MODE_PAIR)
    s.setValue("app/tour_offer", False)
    win = MainWindow(s)
    win.resize(1400, 900)
    win.show()
    for _ in range(20):
        app.processEvents()

    ana = win._tab_ana
    win._tabs.setCurrentIndex(1)
    ana._edit_path.setText(str(edf))
    ana._populate_channels(str(edf))
    ana._chk_compare2.setChecked(True)
    ana._iniciar_analisis()
    if ana._worker is not None:
        ana._worker.wait(180000)
    reloj = QElapsedTimer()
    reloj.start()
    while ana._last_result is None and reloj.elapsed() < 30000:
        app.processEvents()
    for _ in range(40):
        app.processEvents()

    result = ana._last_result
    win.close()
    for _ in range(10):
        app.processEvents()
    if result is None:
        raise SystemExit(f"el análisis de {edf} no devolvió nada")
    return result


def ventanas(result: dict, presa: re.Pattern) -> tuple[list, list]:
    """Reparte las ventanas con nombre entre los dos paneles."""
    tabla = list(result.get("coactivation") or [])
    if not tabla:
        return [], []
    de_presa = [w for w in tabla if w.label and presa.search(w.label)]
    resto = [w for w in tabla if w not in de_presa]
    return resto, de_presa


def _span(lista) -> tuple[float, float] | None:
    if not lista:
        return None
    a = min(w.window_s[0] for w in lista)
    b = max(w.window_s[1] for w in lista)
    return (a, b) if b > a else None


def _dibuja_panel(ax, result: dict, tramos, span, largo: float, techo: float,
                  titulo: str, txt: dict) -> None:
    """Un panel: las dos envolventes en % CVM y las ventanas sombreadas."""
    times = np.asarray(result.get("times", []), dtype=float)
    e1 = np.asarray(result.get("emg_envelope", []), dtype=float)
    bruto2 = result.get("emg_envelope_2")
    e2 = np.asarray(bruto2 if bruto2 is not None else [], dtype=float)
    r1, r2 = float(result.get("mvc_ref") or 0), float(result.get("mvc_ref_2") or 0)
    n1, n2 = result.get("channel_name", "1"), result.get("channel_name_2", "2")

    ax.set_title(titulo, fontsize=PUNTOS + 1)
    ax.set_xlim(0, largo)
    ax.set_ylim(0, techo)
    ax.set_ylabel(txt["y"], fontsize=PUNTOS)
    ax.tick_params(labelsize=PUNTOS)
    ax.axhline(100.0, color="0.55", lw=0.6, ls=":", zorder=1)

    if span is None:
        ax.text(0.5, 0.5, txt["vacio"],
                transform=ax.transAxes, ha="center", va="center",
                fontsize=PUNTOS, color="0.35")
        return

    a, b = span
    dentro = (times >= a) & (times <= b)
    t = times[dentro] - a
    if e1.size and r1:
        ax.plot(t, 100.0 * e1[dentro] / r1, color=AZUL, lw=0.9, label=n1,
                zorder=3)
    if e2.size and r2:
        ax.plot(t, 100.0 * e2[dentro] / r2, color=ROJO, lw=0.9, label=n2,
                zorder=3)

    for w in tramos:
        x0, x1 = w.window_s[0] - a, w.window_s[1] - a
        # Una sola ventana que ocupa el panel entero no se sombrea: el gris a
        # sangre no separaría nada de nada, solo ensuciaría la figura.
        if (x1 - x0) < 0.98 * (b - a):
            ax.axvspan(x0, x1, color="0.88", zorder=0)
            ax.axvline(x0, color="0.7", lw=0.5, zorder=1)
        indice = "—" if w.index is None else f"{w.index:.0f} %"
        ax.text((x0 + x1) / 2, techo * 0.99,
                f"{w.label}\n{txt['coact']} {indice}",
                ha="center", va="top", fontsize=PUNTOS, linespacing=1.2,
                bbox={"facecolor": "white", "edgecolor": "none",
                      "alpha": 0.75, "pad": 1.0})
    ax.legend(fontsize=PUNTOS, loc="upper right", framealpha=0.9)


def dibuja(result: dict, salida: Path, nombre: str, presa: re.Pattern,
           txt: dict) -> None:
    reciproco, de_presa = ventanas(result, presa)
    span_a, span_b = _span(reciproco), _span(de_presa)
    largos = [s[1] - s[0] for s in (span_a, span_b) if s]
    largo = max(largos) if largos else 1.0

    # Un solo techo para los dos paneles: es lo que hace comparables las dos
    # mitades de la figura.
    e1 = np.asarray(result.get("emg_envelope", []), dtype=float)
    bruto2 = result.get("emg_envelope_2")
    e2 = np.asarray(bruto2 if bruto2 is not None else [], dtype=float)
    r1, r2 = float(result.get("mvc_ref") or 0), float(result.get("mvc_ref_2") or 0)
    # Con holgura por arriba: los rótulos de cada ventana van dentro del panel,
    # y sin esa banda libre caerían encima de los picos.
    picos = [100.0 * float(np.max(e)) / r
             for e, r in ((e1, r1), (e2, r2)) if e.size and r]
    techo = max(140.0, 10.0 * np.ceil((max(picos) * 1.32) / 10.0) if picos else 0)

    plt.rcParams.update({"font.size": PUNTOS, "axes.titlesize": PUNTOS + 1})
    fig, (ax_a, ax_b) = plt.subplots(
        2, 1, figsize=(ANCHO_PULGADAS, ALTO_PULGADAS), sharex=True,
        constrained_layout=True)

    _dibuja_panel(ax_a, result, reciproco, span_a, largo, techo, txt["a"], txt)
    _dibuja_panel(ax_b, result, de_presa, span_b, largo, techo, txt["b"], txt)
    ax_b.set_xlabel(txt["x"], fontsize=PUNTOS)

    salida.mkdir(parents=True, exist_ok=True)
    png, pdf = salida / f"{nombre}.png", salida / f"{nombre}.pdf"
    fig.savefig(png, dpi=300)
    fig.savefig(pdf)
    plt.close(fig)
    print(f"  {png.name}   ({ANCHO_PULGADAS} x {ALTO_PULGADAS} in, 300 dpi)")
    print(f"  {pdf.name}")

    print("\n--- ventanas de la figura ---")
    if not reciproco and not de_presa:
        print("  ninguna: el registro no trae ventanas de coactivación")
    for etiqueta, grupo in (("(a)", reciproco), ("(b)", de_presa)):
        for w in grupo:
            indice = "—" if w.index is None else f"{w.index:.0f} %"
            print(f"  {etiqueta} {w.label:<22} {w.window_s[0]:6.1f} a "
                  f"{w.window_s[1]:6.1f} s   coactivación {indice}   "
                  f"(medias {w.mean_1:.1f} % y {w.mean_2:.1f} % CVM)")
    if not result.get("coactivation_from_markers", True):
        print("\n  !! el registro no tiene fragmentos con nombre: lo que se "
              "dibuja es el tramo entero,\n     que no es una medida de nada. "
              "Sirve para probar la herramienta, no como figura.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edf", type=Path, required=True,
                    help="el registro afinado, con los fragmentos nombrados")
    ap.add_argument("--salida", type=Path,
                    default=RAIZ / "docs" / "articulo-advances")
    ap.add_argument("--nombre", default="figura6")
    ap.add_argument("--lang", choices=("es", "en"), default="en")
    ap.add_argument("--presa", default=r"presa|grip",
                    help="con qué nombre reconocer la ventana de la presa")
    args = ap.parse_args()

    if not args.edf.exists():
        raise SystemExit(f"no encuentro {args.edf}")
    set_language(args.lang)
    print(f"figura 6 desde: {args.edf}")
    dibuja(analiza(args.edf), args.salida, args.nombre,
           re.compile(args.presa, re.IGNORECASE), ROTULOS[args.lang])


if __name__ == "__main__":
    main()
