"""A sheet for each laboratory station: the agonist/antagonist practical in six
pictures, to print and laminate.

What costs time in a practical is the first time through, not the practical:
in the pilot a round went from sixteen minutes to four once the steps were
known. So the steps go where they can be seen without asking — on the bench,
one sheet per station — as pictures with a few words, not a page of text.

Six panels, in the order they happen: the electrodes, the practical and
Connect, Start recording (which opens the warm-up), the calibration and what to
do for each muscle, the task, and the analysis. The pictures are the guided
tour's own (``tools/imagenes_recorrido.py``) and captures of the application
itself, taken off-screen, so the buttons on the sheet are the buttons on the
screen, in the same language. The task and the fragment editor are shown on
``docs/informe-sourcebook/ejemplo_tres_maniobras.edf``, the author's own
recording of the three manoeuvres. The calibration's numbers come from the
code, and the task's from the practical guide.

Run from the repository root::

    python tools/hoja_puesto.py

It writes ``docs/hoja-puesto/hoja_puesto_{es,en}.pdf`` (A4, landscape) and a PNG
of each.
"""

from __future__ import annotations

import os
import tempfile
import textwrap
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
ASSETS = RAIZ / "src" / "emgteach" / "gui" / "assets" / "recorrido"
EJEMPLO = DOCS / "informe-sourcebook" / "ejemplo_tres_maniobras.edf"
SALIDA = DOCS / "hoja-puesto"

TITULO, TXT, GRIS, BORDE = "#1F4E79", "#1f2933", "#55636F", "#C9D3DD"
W, H = 842, 595                       # A4 landscape, in points
DPI = 200
POR = "\u00d7"                        # the multiplication sign, U+00D7

TEXTOS = {
    "es": {
        "cabecera": "emgteach · Práctica agonista / antagonista de la muñeca",
        "seis": "Seis pasos",
        "pie": "¿Dudas? El «?» de cada cuadro de la aplicación lo explica.",
        "t": ["Electrodos", "Conectar", "Grabar", "Calibración", "La tarea", "Analizar"],
        "s": [
            "canal 1 FCR · canal 2 ECR · referencia sobre el cúbito",
            "con la placa encendida",
            "calentamiento: {warm} s, 2 o 3 contracciones suaves",
            "{n} {por} FCR · {n} {por} ECR · a tope {dur} s cuando lo pida",
            "{f} flexiones · {e} extensiones · {p} presa de 5 s · 2 s quieto entre maniobras",
            "la línea amarilla dice el paso; al final, el informe PDF",
        ],
    },
    "en": {
        "cabecera": "emgteach · Agonist / antagonist practical, wrist",
        "seis": "Six steps",
        "pie": "Questions? The «?» on each box of the application explains it.",
        "t": ["Electrodes", "Connect", "Record", "Calibration", "The task", "Analyse"],
        "s": [
            "channel 1 FCR · channel 2 ECR · reference on the ulna",
            "with the board switched on",
            "warm-up: {warm} s, two or three easy contractions",
            "{n} {por} FCR · {n} {por} ECR · flat out for {dur} s when asked",
            "{f} flexions · {e} extensions · {p} grip of 5 s · 2 s still in between",
            "the yellow line says the step; last, the PDF report",
        ],
    },
}


def _cifra(x: float, idioma: str) -> str:
    t = f"{x:g}"
    return t.replace(".", ",") if idioma == "es" else t


def capturas(idioma: str, carpeta: Path) -> dict[str, Path]:
    """The application's own controls and panels, captured off-screen."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from emgteach.force_velocity import parse_fv_load_markers
    from emgteach.gui.app import MainWindow
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog
    from emgteach.gui.widgets.mvc_overlay import MvcOverlay
    from emgteach.i18n import set_language, tr
    from emgteach.io import edf_duration, read_edf_markers
    from emgteach.modes import MODE_PAIR, mode_detection_k, mode_label
    from emgteach.mvc import parse_mvc_ref_markers
    from emgteach.phases import parse_phase_markers
    from emgteach.profiles import EMG_PROFILE

    set_language(idioma)
    out: dict[str, Path] = {}

    def guardar(nombre, pix):
        ruta = carpeta / f"{nombre}_{idioma}.png"
        pix.save(str(ruta))
        out[nombre] = ruta

    def boton(b):
        b.setEnabled(True)
        b.adjustSize()
        return b.grab()

    settings = QSettings(str(carpeta / f"hoja_{idioma}.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings)
    win.resize(1400, 900)
    win.show()
    app.processEvents()
    combo = win._combo_mode
    for i in range(combo.count()):
        if combo.itemText(i) == mode_label(MODE_PAIR):
            combo.setCurrentIndex(i)
    app.processEvents()
    adq, ana = win._tab_adq, win._tab_ana

    guardar("practica", combo.grab())
    guardar("conectar", boton(adq._btn_conectar))
    guardar("grabar", boton(adq._btn_grabar))
    texto = adq._btn_grabar.text()
    adq._btn_grabar.setText(tr("Stop recording"))
    guardar("detener", boton(adq._btn_grabar))
    adq._btn_grabar.setText(texto)
    guardar("fragmentos", boton(ana._btn_fragmentos))
    guardar("informe", boton(ana._btn_informe))

    ov = MvcOverlay()
    ov.show_ready(
        tr("Warm up first"), int(EMG_PROFILE.warmup_s),
        tr("Two or three easy contractions of each muscle. The first "
           "maximal effort of a session is never the strongest one."),
    )
    app.processEvents()
    guardar("calentamiento", ov.grab())
    ov.hide_overlay()

    marcas = read_edf_markers(str(EJEMPLO))
    refs = parse_mvc_ref_markers(marcas)
    tramo = parse_phase_markers(marcas).rec_span(
        edf_duration(str(EJEMPLO)), parse_fv_load_markers(marcas)
    )
    dlg = FragmentSelectionDialog.from_edf(
        str(EJEMPLO), "FCR", dict(EMG_PROFILE.filter_kwargs()), span=tramo,
        # No names: this panel is about what to do, and which muscle led each
        # contraction is the analysis's to say, on screen, where it can be
        # corrected. Shaded plainly, the picture shows the task and no more.
        naming=False, channel_name_2="ECR",
        default_k=mode_detection_k(MODE_PAIR),
        mvc_ref=refs.get(0), mvc_ref_2=refs.get(1),
    )
    dlg.resize(1280, 800)
    dlg.show()
    app.processEvents()
    guardar("tarea", dlg._canvas.grab())
    dlg._siguiente()
    app.processEvents()
    # Only the three decisions, so the strip prints large enough to read.
    zona = dlg._btn_mantener.geometry().united(dlg._btn_dividir.geometry())
    guardar("revisar", dlg.grab(zona.adjusted(-4, -4, 4, 4)))
    guardar("usar", boton(dlg._btn_ok))
    dlg.close()
    win.close()
    return out


def _recorte(ruta: Path, destino: Path, arriba: float, abajo: float = 0.0) -> Path:
    """The picture without its title band (the panel's title replaces it) and,
    where the panel's own line says the same, without its legend. Written to
    ``destino``, never beside the original: the tour's folder is packed whole
    into the application."""
    im = Image.open(ruta)
    salida = destino / (ruta.stem + "_hoja.png")
    im.crop((0, int(im.height * arriba), im.width,
             int(im.height * (1.0 - abajo)))).save(salida)
    return salida


def _colocar(fig, imagenes, x, y, w, h, *, px_a_pt=0.9, flecha="↓"):
    """Stack ``imagenes`` in the box, scaled to fit, with arrows between.

    A captured button is a few dozen pixels high; it is never enlarged past
    ``px_a_pt`` points per pixel, so it prints at the size a button has on a
    screen instead of as a blurred slab.
    """
    ims = [np.asarray(Image.open(r).convert("RGB")) for r in imagenes]
    hueco = 16 if len(ims) > 1 else 0
    anchos = [min(w, im.shape[1] * px_a_pt) for im in ims]
    altos = [a * im.shape[0] / im.shape[1] for a, im in zip(anchos, ims, strict=True)]
    total = sum(altos) + hueco * (len(ims) - 1)
    k = min(1.0, h / total) if total else 1.0
    cursor = y + h - (h - total * k) / 2
    for i, (im, a, al) in enumerate(zip(ims, anchos, altos, strict=True)):
        a, al = a * k, al * k
        cursor -= al
        axi = fig.add_axes([(x + (w - a) / 2) / W, cursor / H, a / W, al / H])
        axi.imshow(im, interpolation="lanczos")
        axi.axis("off")
        if i < len(ims) - 1:
            fig.text((x + w / 2) / W, (cursor - hueco / 2 * k) / H, flecha,
                     fontsize=12, color=GRIS, ha="center", va="center")
            cursor -= hueco * k


def componer(idioma: str, cap: dict[str, Path]) -> tuple[Path, Path]:
    from emgteach.modes import MODE_PAIR, mode_expected_contractions
    from emgteach.profiles import EMG_PROFILE

    t = TEXTOS[idioma]
    tmp = cap["practica"].parent
    f, e, p = mode_expected_contractions(MODE_PAIR)
    cifras = {"warm": _cifra(EMG_PROFILE.warmup_s, idioma), "n": EMG_PROFILE.mvc_bursts,
              "dur": _cifra(EMG_PROFILE.mvc_burst_s, idioma), "f": f, "e": e, "p": p,
              "por": POR}
    imagenes = [
        [_recorte(ASSETS / f"electrodos_{idioma}.png", tmp, 0.065, 0.12)],
        [cap["practica"], cap["conectar"]],
        [cap["grabar"], cap["calentamiento"]],
        [_recorte(ASSETS / f"calibracion_{idioma}.png", tmp, 0.11)],
        [cap["tarea"], cap["detener"]],
        [cap["fragmentos"], cap["revisar"], cap["usar"], cap["informe"]],
    ]

    fig = plt.figure(figsize=(W / 72, H / 72), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.text(26, H - 28, t["cabecera"], fontsize=17, fontweight="bold", color=TITULO,
            va="center")
    ax.text(W - 26, H - 28, t["seis"], fontsize=12, color=GRIS, ha="right", va="center")

    mx, arriba, abajo, hueco = 20, H - 50, 30, 12
    cw = (W - 2 * mx - 2 * hueco) / 3
    ch = (arriba - abajo - hueco) / 2
    for k in range(6):
        col, fila = k % 3, k // 3
        x = mx + col * (cw + hueco)
        y = arriba - (fila + 1) * ch - fila * hueco
        ax.add_patch(FancyBboxPatch((x, y), cw, ch, boxstyle="round,pad=0,rounding_size=10",
                                    fc="white", ec=BORDE, lw=1.4))
        ax.add_patch(Circle((x + 22, y + ch - 22), 15, fc=TITULO, ec="none"))
        ax.text(x + 22, y + ch - 22, str(k + 1), fontsize=16, fontweight="bold",
                color="white", ha="center", va="center")
        ax.text(x + 44, y + ch - 22, t["t"][k], fontsize=15, fontweight="bold",
                color=TXT, va="center")
        # One or two lines under the picture, never over the next panel.
        linea = textwrap.fill(t["s"][k].format(**cifras), 46)
        ax.text(x + cw / 2, y + 19, linea, fontsize=9.4, color=TXT, ha="center",
                va="center", linespacing=1.2)
        _colocar(fig, imagenes[k], x + 10, y + 38, cw - 20, ch - 80)

    ax.text(W / 2, 14, t["pie"], fontsize=10, color=GRIS, ha="center", va="center")
    pdf = SALIDA / f"hoja_puesto_{idioma}.pdf"
    png = SALIDA / f"hoja_puesto_{idioma}.png"
    fig.savefig(pdf, facecolor="white")
    fig.savefig(png, dpi=110, facecolor="white")
    plt.close(fig)
    return pdf, png


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        carpeta = Path(tmp)
        for idioma in ("es", "en"):
            cap = capturas(idioma, carpeta)
            for ruta in componer(idioma, cap):
                print(ruta.relative_to(RAIZ))


if __name__ == "__main__":
    main()
