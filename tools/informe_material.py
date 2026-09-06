"""Material adjunto del informe y figuras del artículo: medidas, PDF, CSV y capturas.

Toma un registro real de dos canales del banco, lo pasa por los mismos
trabajadores y exportadores que usa la aplicación, y deja las salidas en
`docs/`. Imprime además los números que pide el apartado 8 del informe.

Dos invocaciones, para dos destinatarios distintos:

    python tools/informe_material.py
        El material del informe interno: en español, ventana de 1920 px, a
        `docs/informe-sourcebook/`.

    python tools/informe_material.py --articulo
        El material publicable: en inglés, ventana de 1150 px — que es la que
        se lee al ancho de página de la revista — y las capturas concretas que
        piden las figuras 3, 4 y 7, a `docs/articulo-advances/`.

**Ninguna ruta personal sale en el material.** El registro se copia antes a
una carpeta neutra (`C:\\Records\\ejemplo.edf` por omisión) y la aplicación se
conduce desde allí, de modo que ni la barra de archivo de las capturas ni la
cabecera del CSV enseñan `C:\\Users\\...`. El sujeto se identifica con un
código (`P01`), que es lo que imprime el PDF.

No modifica el código de la aplicación: solo la conduce.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import numpy as np
from PySide6.QtCore import QElapsedTimer, QPoint, QRect, QSettings
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QGroupBox

from emgteach.coactivation import coactivation_index, resting_level
from emgteach.gui.app import MainWindow
from emgteach.gui.tour import build_tour
from emgteach.i18n import set_language, tr
from emgteach.modes import MODE_PAIR, MODE_SINGLE, MODES
from emgteach.phases import parse_phase_markers

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parent.parent

#: El registro del par del 3 de septiembre, con el protocolo ya validado
#: (puño cerrado contra el canto de la mesa).
ORIGEN = Path(r"C:\Records\emg_2026-09-03_12-57.edf")

#: Dónde se pone el registro para conducir la aplicación. Tiene que ser una
#: ruta que se pueda enseñar: sale en la barra de archivo de cada captura y en
#: la cabecera del CSV.
NEUTRA = Path(r"C:\Records")

#: El sujeto, en el material publicado. El PDF lo imprime como «Test
#: identifier»; el EDF de ejemplo ya venía sin nombre.
SUJETO = "P01"

app = QApplication.instance() or QApplication([])


def espera(tab, atributo: str = "_last_result") -> None:
    if getattr(tab, "_worker", None) is not None:
        tab._worker.wait(180000)
    reloj = QElapsedTimer()
    reloj.start()
    while getattr(tab, atributo) is None and reloj.elapsed() < 30000:
        app.processEvents()
    for _ in range(40):
        app.processEvents()


def _asienta() -> None:
    """Deja que Qt termine de colocar todo antes de la foto."""
    for _ in range(20):
        app.processEvents()


def medidas(result: dict, nombre: str) -> None:
    """Los números del apartado 8, tal como los deja el análisis."""
    print("\n--- medidas de banco ---")
    print(f"archivo            : {nombre}")
    print(f"duración analizada : {result.get('duration', 0):.1f} s "
          f"de {result.get('full_duration_s', 0):.1f} s")
    for n in (1, 2):
        suf = "" if n == 1 else "_2"
        ref = result.get(f"mvc_ref{suf}")
        nom = result.get(f"channel_name{suf}") or f"canal {n}"
        fuente = result.get(f"mvc_ref_source{suf}", "?")
        print(f"referencia CVM {nom:<5}: "
              f"{'—' if not ref else f'{ref:.4f} mV'}   (procedencia: {fuente})")
    env1 = np.asarray(result.get("emg_envelope", []), dtype=float)
    bruto2 = result.get("emg_envelope_2")
    env2 = np.asarray(bruto2 if bruto2 is not None else [], dtype=float)
    r1, r2 = result.get("mvc_ref"), result.get("mvc_ref_2")
    if env1.size and r1:
        p1 = 100.0 * env1 / r1
        print(f"reposo canal 1     : {resting_level(p1):.2f} % CVM "
              f"({resting_level(env1) * 1000:.1f} µV)")
        print(f"máximo de la tarea : {float(np.max(p1)):.0f} % CVM (canal 1)")
    if env2.size and r2:
        p2 = 100.0 * env2 / r2
        print(f"reposo canal 2     : {resting_level(p2):.2f} % CVM "
              f"({resting_level(env2) * 1000:.1f} µV)")
        print(f"máximo de la tarea : {float(np.max(p2)):.0f} % CVM (canal 2)")
    if env1.size and env2.size and r1 and r2:
        fs = float(result.get("fs", 1000.0))
        res = coactivation_index(
            100.0 * env1 / r1, 100.0 * env2 / r2, fs,
            name_1=result.get("channel_name", ""),
            name_2=result.get("channel_name_2", ""),
        )
        print("coactivación (registro completo): "
              f"{res.reason if res.index is None else f'{res.index:.0f} %'} "
              f"(medias {res.mean_1:.1f} % y {res.mean_2:.1f} % CVM)")
        r = float(np.corrcoef(env1[:min(env1.size, env2.size)],
                              env2[:min(env1.size, env2.size)])[0, 1])
        print(f"correlación de las dos envolventes: r = {r:.3f}")
    fases = parse_phase_markers(result.get("markers", []))
    print(f"repeticiones de calibración en el fichero: {len(fases.cal_reps)}")


def abrir_ventana(modo: str, ancho: int, alto: int) -> MainWindow:
    s = QSettings("emgteach-informe", "material")
    s.clear()
    s.setValue("app/mode", modo)
    s.setValue("app/tour_offer", False)
    win = MainWindow(s)
    win.resize(ancho, alto)
    win.show()
    _asienta()
    return win


#: Ancho de página de la revista, en pulgadas, para el cálculo de legibilidad.
PAGINA_PULGADAS = 6.5

#: Mínimo legible que pide la revisión.
MINIMO_PUNTOS = 8.0


def puntos_impresos(ancho_px: int) -> float:
    """A cuántos puntos queda el texto de la interfaz al ancho de página.

    Una captura de ``ancho_px`` impresa a 6,5 pulgadas se ve a
    ``ancho_px / 6,5`` puntos por pulgada, y el texto de la interfaz mide lo
    que mida la fuente de la aplicación. Esto es aritmética, no una opinión
    sobre la captura: **con una ventana de 1150 px el texto sale a 4,9 pt**,
    no a los 8 que pide la revisión, porque la ventana no puede encogerse por
    debajo de 880 px y ni siquiera ahí se llega. A 8 pt solo se llega
    recortando: 702 px de ancho de imagen, y de ahí para abajo.
    """
    alto = QFontMetrics(app.font()).height()
    return alto / (ancho_px / PAGINA_PULGADAS) * 72.0


def guardar(win: MainWindow, destino: Path, nombre: str) -> None:
    win.grab().save(str(destino / nombre))
    print(f"  {nombre:32s} {win.width()}x{win.height()} px  ->  "
          f"{puntos_impresos(win.width()):.1f} pt")


def caja(padre, titulo: str) -> QGroupBox | None:
    """El recuadro que se titula así. Por el título y no por un nombre de
    objeto, porque los recuadros no llevan nombre y el título es lo que se lee
    en la propia pantalla."""
    for grp in padre.findChildren(QGroupBox):
        if grp.title() == titulo:
            return grp
    return None


def recorte(win: MainWindow, destino: Path, nombre: str, controles,
            margen: int = 10) -> None:
    """Un recorte de la ventana alrededor de unos controles.

    Es lo único que llega a los 8 puntos al ancho de página: una ventana
    entera, por pequeña que se haga, no. Cada recorte dice a cuántos puntos
    queda, y avisa cuando se queda corto, para que la decisión se tome con el
    número delante.
    """
    rects = []
    for w in controles:
        if w is None or not w.isVisible():
            continue
        rects.append(QRect(w.mapTo(win, QPoint(0, 0)), w.size()))
    if not rects:
        print(f"  !! {nombre}: no hay nada visible que recortar")
        return
    r = rects[0]
    for otro in rects[1:]:
        r = r.united(otro)
    r = r.adjusted(-margen, -margen, margen, margen).intersected(win.rect())
    win.grab(r).save(str(destino / nombre))
    pt = puntos_impresos(r.width())
    aviso = "" if pt >= MINIMO_PUNTOS else f"   <- por debajo de {MINIMO_PUNTOS:.0f} pt"
    print(f"  {nombre:32s} {r.width()}x{r.height()} px  ->  {pt:.1f} pt{aviso}")


def paso_del_recorrido(win: MainWindow, titulo: str) -> bool:
    """Deja el recorrido guiado abierto en el paso que se llame ``titulo``.

    Devuelve si lo encontró: el recorrido se construye según el modo, y el
    paso de agonista/antagonista solo existe en la práctica del par.
    """
    coach = win._coach
    coach.stop()
    coach.start(build_tour(win), on_tab=win._tabs.setCurrentIndex)
    for _ in range(20):
        if not coach.isVisible():
            return False
        if coach._steps[coach._index].title == titulo:
            _asienta()
            return True
        coach.next()
    return False


def figura_3(destino: Path, ancho: int, alto: int) -> None:
    """Figura 3: la aplicación se configura eligiendo la práctica.

    Las dos capturas tienen que medir lo mismo para poder ponerse una al lado
    de la otra, así que es la misma ventana cambiando de modo, no dos
    ventanas. Y va sin registro cargado a propósito: lo que la figura enseña
    es la configuración, no una señal.

    Las figuras 4 y 7 necesitan un registro analizado debajo, y salen de la
    pasada principal. La 5 (el registro en vivo durante la presa) y la 6
    (patrón recíproco frente a coactivación) no salen de aquí: la primera
    necesita a alguien apretando y la segunda es una figura de matplotlib,
    `tools/figura6.py`.
    """
    print("\n--- figura 3: elegir la práctica ---")
    win = abrir_ventana(MODE_SINGLE, ancho, alto)
    win._tabs.setCurrentIndex(0)
    _asienta()
    guardar(win, destino, "fig3a_practica_single.png")
    _recorte_de_la_practica(win, destino, "fig3a_practica_single")

    win._combo_mode.setCurrentIndex(MODES.index(MODE_PAIR))
    _asienta()
    guardar(win, destino, "fig3b_practica_par.png")
    _recorte_de_la_practica(win, destino, "fig3b_practica_par")
    win.close()
    _asienta()


def _recorte_de_la_practica(win: MainWindow, destino: Path, base: str) -> None:
    """Lo que la figura 3 afirma, en dos trozos limpios.

    En uno solo no sale: el selector está arriba a la derecha y el recuadro de
    carga abajo a la izquierda, y el rectángulo que abarca los dos se lleva por
    delante media pantalla y corta los recuadros vecinos. Dos recortes entran
    enteros y se apilan en la figura — la causa arriba, la consecuencia abajo.
    """
    recorte(win, destino, f"{base}_selector.png",
            [win._combo_mode, win._lbl_nivel])
    recorte(win, destino, f"{base}_carga.png",
            [caja(win._tab_adq, tr("Muscle load (live MVC)"))])


def figura_de_la_guia(win: MainWindow, destino: Path, titulo: str,
                      nombre: str) -> None:
    """Figura 4: un paso de la guía, sobre el registro ya analizado.

    Sobre el análisis hecho, no sobre una pantalla vacía: el paso habla de dos
    envolventes superpuestas y de la tabla de debajo, y una captura con los
    paneles en blanco ilustraría lo contrario de lo que dice el texto.
    """
    if paso_del_recorrido(win, titulo):
        guardar(win, destino, nombre)
        coach = win._coach
        recorte(win, destino, nombre.replace(".png", "_recorte.png"),
                [coach._panel, coach._steps[coach._index].widget()])
    else:
        print(f"  !! no encontré el paso «{titulo}»")
    win._coach.stop()
    _asienta()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--articulo", action="store_true",
                    help="preajuste del material publicable: inglés, 1150 px "
                         "y las capturas de las figuras")
    ap.add_argument("--lang", choices=("es", "en"), default=None,
                    help="idioma de la interfaz, y por tanto del PDF y del CSV")
    ap.add_argument("--ancho", type=int, default=None)
    ap.add_argument("--alto", type=int, default=None)
    ap.add_argument("--salida", type=Path, default=None)
    ap.add_argument("--origen", type=Path, default=ORIGEN,
                    help="el registro de banco del que sale todo")
    ap.add_argument("--neutra", type=Path, default=NEUTRA,
                    help="carpeta desde la que se conduce la aplicación; su "
                         "ruta es la que se ve en las capturas y en el CSV")
    ap.add_argument("--sujeto", default=SUJETO)
    args = ap.parse_args()

    lang = args.lang or ("en" if args.articulo else "es")
    ancho = args.ancho or (1150 if args.articulo else 1920)
    alto = args.alto or (760 if args.articulo else 1032)
    salida = args.salida or (RAIZ / "docs" /
                             ("articulo-advances" if args.articulo
                              else "informe-sourcebook"))
    salida.mkdir(parents=True, exist_ok=True)
    set_language(lang)

    if not args.origen.exists():
        raise SystemExit(f"no encuentro {args.origen}")

    # La copia publicable, con el nombre del apartado 8 del informe. En el
    # material del artículo no se repite: es el mismo fichero que ya está
    # publicado con el informe, y duplicar 600 kB de binario en el repositorio
    # no añade nada.
    ejemplo = RAIZ / "docs" / "informe-sourcebook" / "ejemplo_par_FCR_ECR.edf"
    if not args.articulo:
        ejemplo = salida / "ejemplo_par_FCR_ECR.edf"
        shutil.copy2(args.origen, ejemplo)
    print(f"EDF de ejemplo: {ejemplo}")

    args.neutra.mkdir(parents=True, exist_ok=True)
    trabajo = args.neutra / "ejemplo.edf"
    shutil.copy2(args.origen, trabajo)
    print(f"conducido desde: {trabajo}   (sujeto {args.sujeto})")

    if args.articulo:
        figura_3(salida, ancho, alto)

    print("\n--- capturas de las tres pestañas ---")
    win = abrir_ventana(MODE_PAIR, ancho, alto)

    # --- Adquisición: el registro, en revisión -----------------------------
    adq = win._tab_adq
    win._tabs.setCurrentIndex(0)
    adq._mostrar_registro(str(trabajo))
    _asienta()
    guardar(win, salida, "captura_adquisicion.png")

    # --- Análisis ----------------------------------------------------------
    ana = win._tab_ana
    win._tabs.setCurrentIndex(1)
    ana._edit_path.setText(str(trabajo))
    ana._populate_channels(str(trabajo))
    ana._chk_compare2.setChecked(True)
    ana._iniciar_analisis()
    espera(ana)
    win._coach.stop()
    win._paso_pendiente = None
    _asienta()
    guardar(win, salida, "captura_analisis.png")
    if args.articulo:
        figura_de_la_guia(win, salida, tr("Agonist and antagonist"),
                          "fig4a_guia_agonista.png")
        win._tabs.setCurrentIndex(1)
        _asienta()

    from emgteach.exports import write_analysis_csv
    from emgteach.reports import build_session_report

    write_analysis_csv(ana._last_result, str(salida / "ejemplo_analisis.csv"))
    print("  ejemplo_analisis.csv")
    build_session_report(str(salida / "ejemplo_informe.pdf"), ana._last_result,
                         meta={"student_code": args.sujeto})
    print("  ejemplo_informe.pdf")

    medidas(ana._last_result, ejemplo.name)

    # --- Normalización CVM -------------------------------------------------
    cvm = win._tab_cvm
    win._tabs.setCurrentIndex(2)
    cvm._dismiss_entry_screen()
    cvm._edit_path.setText(str(trabajo))
    cvm._populate_channels(str(trabajo), ask=False)
    cvm._refresh_compute_enabled()
    cvm._iniciar_calculo()
    espera(cvm)
    cvm._dismiss_entry_screen()
    win._coach.stop()
    _asienta()
    guardar(win, salida, "captura_normalizacion.png")
    if args.articulo:
        # Figura 7: la misma pantalla, bajada del todo. El APDF de carga
        # muscular vive al final del área de gráficas y en la posición de
        # arranque asoma solo el título: la figura tiene que enseñar el panel
        # entero, con el nombre del músculo encima.
        barra = cvm._viz_scroll.verticalScrollBar()
        barra.setValue(barra.maximum())
        _asienta()
        guardar(win, salida, "fig7_apdf.png")
        # Los dos por separado: juntos ocupan casi el ancho de la ventana y
        # vuelven a caer por debajo de los 8 puntos. La curva y sus números
        # son dos cosas, y la figura los puede apilar.
        recorte(win, salida, "fig7_apdf_recorte.png", [cvm._apdf_canvas])
        recorte(win, salida, "fig7_datos_recorte.png", [cvm._data_box])
        barra.setValue(0)
        _asienta()
        figura_de_la_guia(win, salida, tr("Why normalise at all"),
                          "fig4b_guia_normalizar.png")

    win.close()
    _asienta()


if __name__ == "__main__":
    main()
