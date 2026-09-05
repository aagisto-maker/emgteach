"""Material adjunto del informe para el Sourcebook: medidas, PDF, CSV y capturas.

Toma un registro real de dos canales del banco, lo pasa por los mismos
trabajadores y exportadores que usa la aplicación, y deja en
`docs/informe-sourcebook/` el EDF de ejemplo, el informe PDF, el CSV y una
captura de cada pestaña con ese archivo cargado. Imprime además los números
que pide el apartado 8 del informe.

    python tools/informe_material.py

No modifica el código de la aplicación: solo la conduce.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import numpy as np
from PySide6.QtCore import QElapsedTimer, QSettings
from PySide6.QtWidgets import QApplication

from emgteach.coactivation import coactivation_index, resting_level
from emgteach.gui.app import MainWindow
from emgteach.i18n import set_language
from emgteach.phases import parse_phase_markers

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "informe-sourcebook"
SALIDA.mkdir(parents=True, exist_ok=True)

#: El registro del par del 3 de septiembre, con el protocolo ya validado
#: (puño cerrado contra el canto de la mesa).
ORIGEN = Path(r"C:\Records\emg_2026-09-03_12-57.edf")
EJEMPLO = SALIDA / "ejemplo_par_FCR_ECR.edf"

ANCHO, ALTO = 1920, 1032

app = QApplication.instance() or QApplication([])
set_language("es")


def espera(tab, atributo: str = "_last_result") -> None:
    if getattr(tab, "_worker", None) is not None:
        tab._worker.wait(180000)
    reloj = QElapsedTimer()
    reloj.start()
    while getattr(tab, atributo) is None and reloj.elapsed() < 30000:
        app.processEvents()
    for _ in range(40):
        app.processEvents()


def medidas(result: dict) -> None:
    """Los números del apartado 8, tal como los deja el análisis."""
    print("\n--- medidas de banco ---")
    print(f"archivo            : {EJEMPLO.name}")
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


def main() -> None:
    if not ORIGEN.exists():
        raise SystemExit(f"no encuentro {ORIGEN}")
    shutil.copy2(ORIGEN, EJEMPLO)
    print(f"EDF de ejemplo copiado: {EJEMPLO}")

    s = QSettings("emgteach-informe", "material")
    s.clear()
    s.setValue("app/mode", "pair")
    s.setValue("app/tour_offer", False)
    win = MainWindow(s)
    win.resize(ANCHO, ALTO)
    win.show()
    app.processEvents()

    # --- Adquisición: el registro, en revisión -----------------------------
    adq = win._tab_adq
    win._tabs.setCurrentIndex(0)
    adq._mostrar_registro(str(EJEMPLO))
    app.processEvents()
    win.grab().save(str(SALIDA / "captura_adquisicion.png"))
    print("captura_adquisicion.png")

    # --- Análisis ----------------------------------------------------------
    ana = win._tab_ana
    win._tabs.setCurrentIndex(1)
    ana._edit_path.setText(str(EJEMPLO))
    ana._populate_channels(str(EJEMPLO))
    ana._chk_compare2.setChecked(True)
    ana._iniciar_analisis()
    espera(ana)
    win._coach.stop()
    win._paso_pendiente = None
    app.processEvents()
    win.grab().save(str(SALIDA / "captura_analisis.png"))
    print("captura_analisis.png")

    from emgteach.exports import write_analysis_csv
    from emgteach.reports import build_session_report

    write_analysis_csv(ana._last_result, str(SALIDA / "ejemplo_analisis.csv"))
    print("ejemplo_analisis.csv")
    build_session_report(str(SALIDA / "ejemplo_informe.pdf"), ana._last_result)
    print("ejemplo_informe.pdf")

    medidas(ana._last_result)

    # --- Normalización CVM -------------------------------------------------
    cvm = win._tab_cvm
    win._tabs.setCurrentIndex(2)
    cvm._dismiss_entry_screen()
    cvm._edit_path.setText(str(EJEMPLO))
    cvm._populate_channels(str(EJEMPLO), ask=False)
    cvm._refresh_compute_enabled()
    cvm._iniciar_calculo()
    espera(cvm)
    cvm._dismiss_entry_screen()
    win._coach.stop()
    app.processEvents()
    win.grab().save(str(SALIDA / "captura_normalizacion.png"))
    print("captura_normalizacion.png")

    win.close()
    app.processEvents()


if __name__ == "__main__":
    main()
