"""Rellena los bloques literales de `docs/INFORME-estado-para-Sourcebook.md`.

El informe describe lo que la aplicación dice en pantalla, y un revisor que la
descargue va a comparar sus textos con el artículo. Por eso las cadenas no se
copian a mano: se leen del código y del catálogo de traducción, y este guion
las escribe en el sitio del marcador correspondiente.

    python tools/informe_bloques.py

Es idempotente: vuelve a poner el marcador al final de cada bloque, así que se
puede ejecutar de nuevo cuando cambie el código.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from emgteach import i18n  # noqa: E402
from emgteach.gui.tabs import analysis as ana_mod  # noqa: E402
from emgteach.profiles import EMG_PROFILE  # noqa: E402

INFORME = RAIZ / "docs" / "INFORME-estado-para-Sourcebook.md"
FUENTE = RAIZ / "src" / "emgteach"


def es(clave: str) -> str:
    return i18n._ES.get(clave, "(sin entrada en el catálogo)")


def linea_de(ruta: Path, patron: str) -> int:
    """Primera línea de `ruta` que casa con `patron`, o 0."""
    rx = re.compile(patron)
    for i, ln in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        if rx.search(ln):
            return i
    return 0


def rel(ruta: Path) -> str:
    return str(ruta.relative_to(RAIZ)).replace("\\", "/")


# ---------------------------------------------------------------- 4. tabla ---

PERFIL = FUENTE / "profiles.py"
ADQ = FUENTE / "gui" / "tabs" / "acquisition.py"
BIT = FUENTE / "devices" / "bitalino.py"
ARD = FUENTE / "devices" / "arduino.py"

#: (rótulo EN, valor, unidad, dónde se cambia, fichero, patrón para la línea)
PARAMETROS = [
    ("Sampling rate", EMG_PROFILE.sample_frequency, "Hz",
     "no editable", PERFIL, r"sample_frequency: int"),
    ("Band-pass, low cut", EMG_PROFILE.f_low, "Hz",
     "no editable", PERFIL, r"f_low: float"),
    ("Band-pass, high cut", EMG_PROFILE.f_high, "Hz",
     "no editable", PERFIL, r"f_high: float"),
    ("Notch", EMG_PROFILE.f_notch, "Hz",
     "no editable", PERFIL, r"f_notch: float"),
    ("Envelope cutoff frequency (Hz):", EMG_PROFILE.f_env, "Hz",
     "Análisis y Normalización CVM · casilla numérica (solo en cinemática)",
     PERFIL, r"f_env: float"),
    ("RMS window", EMG_PROFILE.rms_window_ms, "ms",
     "no editable", PERFIL, r"rms_window_ms: float"),
    ("Spectral segment length", EMG_PROFILE.seg_len_s, "s",
     "no editable", PERFIL, r"seg_len_s: float"),
    ("Spectral overlap", EMG_PROFILE.overlap, "fracción",
     "no editable", PERFIL, r"overlap: float"),
    ("MVC percentile", EMG_PROFILE.mvc_percentile, "%",
     "no editable", PERFIL, r"mvc_percentile: float"),
    ("MVC peak window", EMG_PROFILE.mvc_peak_window_s, "s",
     "no editable", PERFIL, r"mvc_peak_window_s: float"),
    ("Calibration efforts", EMG_PROFILE.mvc_bursts, "repeticiones",
     "no editable", PERFIL, r"mvc_bursts: int"),
    ("Duration of one effort", EMG_PROFILE.mvc_burst_s, "s",
     "no editable", PERFIL, r"mvc_burst_s: float"),
    ("Warm-up", EMG_PROFILE.warmup_s, "s",
     "no editable", PERFIL, r"warmup_s: float"),
    ("Preparation countdown", EMG_PROFILE.prep_countdown_s, "s",
     "no editable", PERFIL, r"prep_countdown_s: float"),
    ("Ready countdown", None, "s",
     "no editable (MVC_READY_S = 3,0)", ADQ, r"^MVC_READY_S"),
    ("Rest between repetitions", None, "s",
     "no editable (MVC_REST_S = 2,0)", ADQ, r"^MVC_REST_S"),
    ("Auto-onset k", EMG_PROFILE.onset_k, "desv. típicas",
     "Adquisición · «Marcadores de eventos» · k", PERFIL, r"onset_k: float"),
    ("Onset baseline", EMG_PROFILE.onset_baseline_s, "s",
     "no editable", PERFIL, r"onset_baseline_s: float"),
    ("Onset refractory", EMG_PROFILE.onset_refractory_s, "s",
     "no editable", PERFIL, r"onset_refractory_s: float"),
    ("Jonsson static limit (P10)", EMG_PROFILE.apda_static_limit, "% CVM",
     "no editable", PERFIL, r"apda_static_limit: float"),
    ("Jonsson median limit (P50)", EMG_PROFILE.apda_median_limit, "% CVM",
     "no editable", PERFIL, r"apda_median_limit: float"),
    ("Jonsson peak limit (P90)", EMG_PROFILE.apda_peak_limit, "% CVM",
     "no editable", PERFIL, r"apda_peak_limit: float"),
    ("Mean-activation limit", EMG_PROFILE.apda_mean_limit, "% CVM",
     "no editable", PERFIL, r"apda_mean_limit: float"),
    ("Live warning zone", EMG_PROFILE.apda_warning_limit, "% CVM",
     "Adquisición · «Carga muscular» · Aviso", PERFIL, r"apda_warning_limit"),
    ("Live danger zone", EMG_PROFILE.apda_danger_limit, "% CVM",
     "Adquisición · «Carga muscular» · Peligro", PERFIL, r"apda_danger_limit"),
    ("Co-activation floor", EMG_PROFILE.coact_floor_pct, "% CVM",
     "no editable", PERFIL, r"coact_floor_pct: float"),
    ("Implausible MVC", EMG_PROFILE.mvc_implausible_pct, "% CVM",
     "no editable", PERFIL, r"mvc_implausible_pct: float"),
    ("Minimum rest ratio", EMG_PROFILE.mvc_min_rest_ratio, "veces el reposo",
     "no editable", PERFIL, r"mvc_min_rest_ratio: float"),
    ("Cross-talk limit", EMG_PROFILE.mvc_crosstalk_pct, "% de su referencia",
     "no editable", PERFIL, r"mvc_crosstalk_pct: float"),
    ("Fatigue R² threshold", 0.30, "—",
     "no editable (`fatigue_verdict(min_r2=)`)",
     FUENTE / "fatigue.py", r"min_r2: float = 0.30"),
    ("Fatigue minimum segments", EMG_PROFILE.fatigue_min_segments, "ventanas",
     "no editable", PERFIL, r"fatigue_min_segments: int"),
    ("Fatigue active ratio", EMG_PROFILE.fatigue_active_ratio, "fracción",
     "no editable", PERFIL, r"fatigue_active_ratio: float"),
    ("BITalino ADC", 1023, "cuentas (10 bits)",
     "no editable", BIT, r"_ADC_MAX = "),
    ("BITalino V_ref", 3.3, "V", "no editable", BIT, r"_V_REF = "),
    ("BITalino EMG gain", 1009.0, "—", "no editable", BIT, r"_GAIN_EMG = "),
    ("Arduino ADC", 1023.0, "cuentas (10 bits)",
     "no editable", ARD, r"_ADC_MAX = "),
    ("Arduino V_ref", 5.0, "V", "no editable", ARD, r"_V_REF = "),
    ("MyoWare gain", 200.0, "—", "no editable", ARD, r"_GAIN = "),
    ("F-V lifts per load", None, "levantamientos",
     "Adquisición · «Parámetros de la F-V…»", ADQ, r"^FV_REPS_DEF"),
    ("F-V preparation", None, "s",
     "Adquisición · «Parámetros de la F-V…»", ADQ, r"^FV_PREP_DEF_S"),
    ("F-V lift time", None, "s",
     "Adquisición · «Parámetros de la F-V…»", ADQ, r"^FV_LIFT_DEF_S"),
]

VALOR_EN_LINEA = re.compile(r"=\s*([0-9.]+)")


def bloque_parametros() -> str:
    filas = ["| Parámetro (EN) | Rótulo en pantalla (ES) | Valor | Unidad | "
             "Dónde se cambia | archivo:línea |",
             "|---|---|---|---|---|---|"]
    for en, valor, unidad, donde, ruta, patron in PARAMETROS:
        n = linea_de(ruta, patron)
        if valor is None:
            texto = ruta.read_text(encoding="utf-8").splitlines()[n - 1]
            m = VALOR_EN_LINEA.search(texto)
            valor = m.group(1) if m else "?"
        traducido = i18n._ES.get(en)
        rotulo = traducido if traducido else "—"
        v = str(valor).replace(".", ",")
        filas.append(f"| {en} | {rotulo} | {v} | {unidad} | {donde} | "
                     f"`{rel(ruta)}:{n}` |")
    return "\n".join(filas)


# --------------------------------------------------------------- 6. avisos ---

SEÑALES = (
    "⚠", "not reported", "flat", "saturated", "weak signal", "no signal",
    "mains", "50 Hz", "too short", "inconclusive", "no calibration",
    "not a maximal", "could not", "failed", "error", "Error", "below",
    "cannot", "does not", "no reference", "without calibration",
    "not separated", "implausible", "never left", "no rest",
)


def literales(ruta: Path):
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
                and nodo.func.id == "tr" and nodo.args
                and isinstance(nodo.args[0], ast.Constant)
                and isinstance(nodo.args[0].value, str)):
            yield nodo.lineno, nodo.args[0].value


def bloque_avisos() -> str:
    vistos: set[str] = set()
    filas: list[tuple[str, int, str]] = []
    for ruta in sorted(FUENTE.rglob("*.py")):
        if ruta.name == "i18n.py":
            continue
        for linea, texto in literales(ruta):
            if texto in vistos or not any(s in texto for s in SEÑALES):
                continue
            vistos.add(texto)
            filas.append((rel(ruta), linea, texto))
    filas.sort()
    out = [f"Son **{len(filas)}** mensajes distintos. Se listan tal como están "
           "en el código, sin reordenar ni resumir.\n"]
    for ruta, linea, en in filas:
        out.append(f"- **`{ruta}:{linea}`**")
        out.append(f"  - EN: {en}")
        out.append(f"  - ES: {es(en)}")
    return "\n".join(out)


# ----------------------------------------------------------------- 3. tour ---

def bloque_tour() -> str:
    ruta = FUENTE / "gui" / "tour.py"
    árbol = ast.parse(ruta.read_text(encoding="utf-8"))
    pasos: list[tuple[int, list[str]]] = []
    for nodo in ast.walk(árbol):
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
                and nodo.func.id == "CoachStep"):
            textos = []
            for arg in nodo.args:
                if (isinstance(arg, ast.Call)
                        and isinstance(arg.func, ast.Name)
                        and arg.func.id == "tr" and arg.args
                        and isinstance(arg.args[0], ast.Constant)):
                    textos.append(arg.args[0].value)
            if textos:
                pasos.append((nodo.lineno, textos))
    pasos.sort()
    out = [f"El recorrido tiene **{len(pasos)}** pasos definidos en "
           f"`{rel(ruta)}`; cuáles se muestran depende de la práctica.\n"]
    for linea, textos in pasos:
        out.append(f"- **`{rel(ruta)}:{linea}`**")
        for t in textos:
            out.append(f"  - EN: {t}")
            out.append(f"  - ES: {es(t)}")
    return "\n".join(out)


# -------------------------------------------------------------- 5. paneles ---

def bloque_paneles() -> str:
    filas = ["| Nº | Nombre largo (EN) | Nombre largo (ES) | "
             "Etiqueta corta (ES) |", "|---|---|---|---|"]
    for i, (largo, corto) in enumerate(
            zip(ana_mod._PANEL_NOMBRES, ana_mod._PANEL_SHORT_LABELS,
                strict=True), start=1):
        filas.append(f"| {i} | {largo} | {es(largo)} | {es(corto)} |")
    return "\n".join(filas)


BLOQUES = {
    "<<<PARAMETROS>>>": bloque_parametros,
    "<<<AVISOS>>>": bloque_avisos,
    "<<<TOUR>>>": bloque_tour,
    "<<<PANELES>>>": bloque_paneles,
}

texto = INFORME.read_text(encoding="utf-8")
for marca, hacer in BLOQUES.items():
    cuerpo = hacer()
    patron = re.compile(
        re.escape(marca) + r".*?" + re.escape(marca), re.S)
    nuevo = f"{marca}\n\n{cuerpo}\n\n{marca}"
    if patron.search(texto):
        # `sub` con una cadena interpretaría \1 y compañía; con una función
        # que ignora la coincidencia, no. `nuevo` va por argumento por
        # defecto para no cerrar sobre la variable del bucle.
        texto = patron.sub(lambda _m, n=nuevo: n, texto, count=1)
    elif marca in texto:
        texto = texto.replace(marca, nuevo, 1)
    else:
        print(f"  aviso: no encuentro {marca} en el informe")
    print(f"  {marca}: {len(cuerpo.splitlines())} líneas")
INFORME.write_text(texto, encoding="utf-8")
print(f"escrito {rel(INFORME)}")
