"""Minimal two-language (English / Spanish) internationalisation.

The source code uses **English** strings as the canonical keys (the
developer-facing layer). The Spanish translations live in the ``_ES`` map
below. Call :func:`tr` to translate a key to the current language::

    from emgteach.i18n import tr
    label = tr("Connect")          # -> "Conectar" in Spanish, "Connect" in English

Strings with runtime values keep ``str.format`` placeholders, identical in
both languages::

    tr("Connecting to {name}…").format(name=device.name)

The language is chosen once at start-up (see :func:`resolve_startup_language`)
and changing it in the GUI takes effect on restart, so a process-wide global
is sufficient. This module is intentionally Qt-free so the non-GUI layers
(``dsp``, ``devices``, ``reports``) can use it too; the only Qt dependency
(``QLocale`` auto-detection) is imported lazily inside
:func:`resolve_startup_language`.
"""

from __future__ import annotations

from typing import Any

# Supported language codes.
LANGUAGES = ("en", "es")

# Current language; English is the canonical default.
_LANG = "en"

# English (canonical key) -> Spanish translation. Populated near the bottom of
# this module. Missing keys fall back to the English text, so an incomplete
# map degrades gracefully (English shows through) instead of crashing.
_ES: dict[str, str] = {}


def set_language(lang: str) -> None:
    """Set the active language (``"en"`` or ``"es"``; anything else → English)."""
    global _LANG
    _LANG = "es" if lang == "es" else "en"


def get_language() -> str:
    """Return the active language code (``"en"`` or ``"es"``)."""
    return _LANG


def tr(text: str) -> str:
    """Translate an English canonical key into the active language."""
    if _LANG == "es":
        return _ES.get(text, text)
    return text


def resolve_startup_language(settings: Any = None) -> str:
    """Decide the start-up language.

    Uses the value saved in ``settings`` under ``"app/language"`` if present;
    otherwise auto-detects from the operating-system locale (Spanish → ``"es"``,
    anything else → ``"en"``).
    """
    if settings is not None:
        saved = settings.value("app/language", "")
        if saved in LANGUAGES:
            return str(saved)
    try:  # lazy Qt import — keeps the module Qt-free for the non-GUI layers
        from PySide6.QtCore import QLocale

        if QLocale().language() == QLocale.Language.Spanish:
            return "es"
    except Exception:  # pragma: no cover — defensive (no Qt / headless)
        pass
    return "en"


# ---------------------------------------------------------------------------
# English -> Spanish translations
# ---------------------------------------------------------------------------
# Organised by area. Keys must match the English text passed to tr() verbatim
# (including {placeholders} and trailing ellipsis "…").

_ES = {
    # --- app / window ---
    "EMG Bioinstrumentation": "EMG Bioinstrumentación",
    "Arduino platforms (BITalino and MyoWare)": "Plataformas Arduino (BITalino y MyoWare)",
    "Acquisition": "Adquisición",
    "Analysis": "Análisis",
    "MVC normalisation": "Normalización CVM",
    "Interface language": "Idioma de la interfaz",
    "About EMG Bioinstrumentation": "Acerca de EMG Bioinstrumentación",
    "Language": "Idioma",
    "The language change will take effect when you restart the application.":
        "El cambio de idioma se aplicará al reiniciar la aplicación.",
    "Version": "Versión",
    "Faculty of Pharmacy, Complutense University of Madrid":
        "Facultad de Farmacia, Universidad Complutense de Madrid",

    # --- acquisition worker / GUI ---
    "Loading EMG signal: {path}": "Cargando señal EMG: {path}",
    "Connecting to {name}…": "Conectando con {name}…",
    "Connection established. Starting acquisition.": "Conexión establecida. Iniciando adquisición.",
    "Onset (auto)": "Inicio (auto)",
    "Onset (auto) — {label}": "Inicio (auto) — {label}",
    "Automatic onset detection enabled (k={k:.1f}).":
        "Detección automática de inicio activada (k={k:.1f}).",
    "Recording to: {path}": "Grabando en: {path}",
    "Connection to {name} lost: {error}": "Conexión con {name} perdida: {error}",
    "Warning — EDF write error: {error}": "Aviso — error de escritura EDF: {error}",
    "{name} disconnected.": "{name} desconectado.",
    "Warning — annotation error: {error}": "Aviso — error de anotación: {error}",
    "EDF file saved: {path}": "Archivo EDF guardado: {path}",
    "Warning — EDF close error: {error}": "Aviso — error al cerrar el EDF: {error}",
    "sensor_labels has {n} entries but the device reports {m} channel(s).":
        "Las etiquetas de sensor tienen {n} entradas pero el dispositivo informa de {m} canal(es).",
    "Device configuration": "Configuración del dispositivo",
    "Default": "Por defecto",
    "Restore default MAC ({mac})": "Restaurar MAC por defecto ({mac})",
    "Refresh": "Refrescar",
    "Refresh the list of available serial ports": "Refrescar lista de puertos serie disponibles",
    "EDF destination folder": "Carpeta de destino EDF",
    "Channels:": "Canales:",
    "1 (single sensor)": "1 (un sensor)",
    "2 (agonist / antagonist)": "2 (agonista / antagonista)",
    "Labels:": "Etiquetas:",
    "Name of this channel's muscle/sensor (max. 16 characters; "
    "used as the channel label in the EDF file).":
        "Nombre del músculo/sensor de este canal (máx. 16 caracteres; "
        "se usa como etiqueta del canal en el archivo EDF).",
    "Event log": "Registro de eventos",
    "Acquisition control": "Control de adquisición",
    "Connect": "Conectar",
    "Disconnect": "Desconectar",
    "Start recording": "Iniciar grabación",
    "Stop recording": "Detener grabación",
    "Device communication status": "Estado de comunicación con el dispositivo",
    "Status: disconnected": "Estado: desconectado",
    "Status: connected (ready to record)": "Estado: conectado (listo para grabar)",
    "Status: recording…": "Estado: grabando…",
    "Event markers": "Marcadores de eventos",
    "Contraction onset": "Inicio contracción",
    "Contraction end": "Fin contracción",
    "Fatigue": "Fatiga",
    "Rest": "Reposo",
    "Other…": "Otro…",
    "Other": "Otro",
    "MARK": "MARCAR",
    "Auto-onset": "Auto-inicio",
    "Automatically marks the contraction onset when the envelope "
    "exceeds the threshold (baseline + k·SD of the resting period).":
        "Marca automáticamente el inicio de contracción cuando la "
        "envolvente supera el umbral (línea base + k·DE del reposo).",
    "Threshold in standard deviations above the resting period "
    "(lower = more sensitive).":
        "Umbral en desviaciones típicas sobre el reposo (menor = más sensible).",
    "Real-time EMG signal": "Señal EMG en tiempo real",
    "Time window:": "Ventana temporal:",
    "Widen the window (see more time)": "Ampliar ventana (ver más tiempo)",
    "Narrow the window (more detail)": "Reducir ventana (más detalle)",
    "Narrow the window (see less time, more detail)":
        "Reducir ventana (ver menos tiempo, más detalle)",
    "s visible": "s visibles",
    "ms visible": "ms visibles",
    "Colour of each channel in the plots": "Color de cada canal en las gráficas",
    "Reset scales": "Reset escalas",
    "Restore Y ranges and time window to initial values":
        "Restaurar rangos Y y ventana temporal a valores iniciales",
    "Zoom in (vertical) — {label}": "Ampliar (vertical) — {label}",
    "Zoom out (vertical) — {label}": "Reducir (vertical) — {label}",
    # Vertical-zoom sidebar button letters (raw/filtered/envelope initials).
    # "F" and "E" are identical in both languages and fall through to the key.
    "R": "B",
    "Raw EMG signal (mV)": "Señal EMG en bruto (mV)",
    "Filtered EMG (notch 50 Hz + band-pass 20-450 Hz)":
        "EMG filtrado (notch 50 Hz + paso-banda 20-450 Hz)",
    "Envelope (5 Hz low-pass filter, causal with continuous state)":
        "Envolvente (filtro paso-bajo 5 Hz, causal con estado continuo)",
    "Select destination folder": "Seleccionar carpeta de destino",
    "Enter the BITalino MAC address before connecting.":
        "Introduce la dirección MAC del BITalino antes de conectar.",
    "Select a COM port for the Arduino before connecting.":
        "Selecciona un puerto COM para el Arduino antes de conectar.",
    "Device configured: {desc}. Press 'Start recording'.":
        "Dispositivo configurado: {desc}. Pulsa 'Iniciar grabación'.",
    "Device disconnected.": "Dispositivo desconectado.",
    "Press M to quickly add a marker with the selected label.":
        "Pulsa M para marcar rápidamente con la etiqueta seleccionada.",
    "Custom marker": "Marcador personalizado",
    "Description (max. 60 characters):": "Descripción (máx. 60 caracteres):",
    "Marker added: t={t:.1f} s — {label}": "Marca añadida: t={t:.1f} s — {label}",
    "Recording finished. File: {path}": "Grabación finalizada. Archivo: {path}",
    "No data from the device — connection not established.":
        "Sin datos del dispositivo — conexión no establecida.",
    "No data from the device for {s:.1f} s — forcing disconnection.":
        "Sin datos del dispositivo durante {s:.1f} s — forzando desconexión.",

    # --- analysis worker / GUI ---
    "Loading file: {path}": "Cargando archivo: {path}",
    "Channel «{name}» — {fs:.0f} Hz — {dur:.1f} s": "Canal «{name}» — {fs:.0f} Hz — {dur:.1f} s",
    "Applying the processing pipeline (DSP)…": "Aplicando la cadena de procesado (DSP)…",
    "Computing PSD, MNF and MDF…": "Calculando PSD, MNF y MDF…",
    "Computing segment-wise RMS and MDF…": "Calculando RMS y MDF por ventana…",
    "Polynomial fatigue fit (degree 2)…": "Ajuste polinómico de fatiga (grado 2)…",
    "Fatigue trend detected (MDF decreases over time).":
        "Tendencia de fatiga detectada (la MDF desciende con el tiempo).",
    "No fatigue (MDF increases or stays stable).":
        "Sin fatiga (la MDF aumenta o se mantiene estable).",
    "MDF trend undefined (signal too short or constant).":
        "Tendencia de MDF indeterminada (señal demasiado corta o constante).",
    "Analysis parameters": "Parámetros de análisis",
    "EDF file:": "Archivo EDF:",
    "Select an EDF file…": "Selecciona un archivo EDF…",
    "Browse…": "Explorar…",
    "Analyse": "Analizar",
    "Save figure (PNG)": "Guardar figura (PNG)",
    "Generate PDF report": "Generar informe PDF",
    "EMG channel:": "Canal EMG:",
    "EMG channel of the EDF to analyse. Filled with the channels of "
    "the file when you select it (e.g. agonist/antagonist).":
        "Canal EMG del EDF a analizar. Se rellena con los canales del archivo "
        "al seleccionarlo (p. ej. agonista/antagonista).",
    "Envelope cutoff frequency (Hz):": "Frec. corte envolvente (Hz):",
    "Student:": "Alumno/a:",
    "Code:": "Código:",
    "Panels to show": "Paneles a mostrar",
    "1A. Raw": "1A. Bruta",
    "1B. Filt.+rect.": "1B. Filtr.+rect.",
    "2. Env. vs RMS": "2. Env. vs RMS",
    "3. Env. norm.": "3. Env. norm.",
    "4. PSD": "4. PSD",
    "5. RMS/window": "5. RMS/ventana",
    "6. MDF/time": "6. MDF/tiempo",
    "7. RMS vs MDF": "7. RMS vs MDF",
    "Redraw": "Redibujar",
    "Markers": "Marcadores",
    "Markers ({n}):": "Marcadores ({n}):",
    "No markers": "Sin marcadores",
    "Go": "Ir",
    "Display window": "Ventana de visualización",
    "Reset window": "Reset ventana",
    "Widen the time window (×2)": "Ampliar ventana temporal (×2)",
    "Narrow the time window (÷2)": "Reducir ventana temporal (÷2)",
    "Analysis summary": "Resumen del análisis",
    "Start:": "Inicio:",
    "Duration:": "Duración:",
    "File:": "Archivo:",
    "Mean frequency (MNF):": "Frecuencia Media (MNF):",
    "Median frequency (MDF):": "Frecuencia Mediana (MDF):",
    "Fatigue:": "Fatiga:",
    "MDF slope:": "Pendiente MDF:",
    "Global RMS:": "RMS global:",
    "1A. Raw signal": "1A. Señal bruta",
    "1B. Filtered + rectified": "1B. Filtrada + rectificada",
    "2. Envelope vs RMS": "2. Envolvente vs RMS",
    "3. Normalised envelope": "3. Envolvente normalizada",
    "4. PSD with MNF/MDF": "4. PSD con MNF/MDF",
    "5. RMS per window": "5. RMS por ventana",
    "6. MDF vs time (fatigue)": "6. MDF vs tiempo (fatiga)",
    "1A. Raw EMG signal": "1A. Señal EMG bruta",
    "Filtered EMG (20-450 Hz)": "EMG filtrado (20-450 Hz)",
    "1B. Filtered + rectified EMG signal": "1B. Señal EMG filtrada + rectificada",
    "Rectified EMG": "EMG rectificado",
    "LP envelope (zero-phase)": "Envolvente LP (fase cero)",
    "RMS envelope": "Envolvente RMS",
    "2. EMG signal envelope": "2. Envolvente de la señal EMG",
    "Normalised envelope (max=1)": "Envolvente normalizada (max=1)",
    "3. Envelope normalised to maximum": "3. Envolvente normalizada al máximo",
    "Normalised amplitude (0-1)": "Amplitud normalizada (0-1)",
    "4. Power spectral density (PSD)": "4. Densidad espectral de potencia (PSD)",
    "Frequency (Hz)": "Frecuencia (Hz)",
    "RMS per 1 s window": "RMS por ventana de 1 s",
    "5. RMS amplitude over time": "5. Amplitud RMS en el tiempo",
    "Median frequency per window": "Frecuencia mediana por ventana",
    "Trend (degree-2 polynomial)": "Tendencia (polinomio grado 2)",
    "6. Fatigue trend: median frequency vs. time\n"
    "   (a decrease indicates muscle fatigue)":
        "6. Tendencia de fatiga: frecuencia mediana vs. tiempo\n"
        "   (un descenso indica fatiga muscular)",
    "Degree-2 polynomial fit": "Ajuste polinómico grado 2",
    "7. Amplitude (force) vs median frequency (fatigue)":
        "7. Relación amplitud (fuerza) vs frecuencia mediana (fatiga)",
    "Select EDF file": "Seleccionar archivo EDF",
    "EDF files (*.edf *.EDF)": "Archivos EDF (*.edf *.EDF)",
    "Save figure": "Guardar figura",
    "PNG images (*.png)": "Imágenes PNG (*.png)",
    "Figure saved to: {path}": "Figura guardada en: {path}",
    "Report graphs": "Gráficos del informe",
    "Tick the graphs to add to the report:": "Marca los gráficos que se añadirán al informe:",
    "PDF report generated: {path}": "Informe PDF generado: {path}",
    "Error generating the PDF report: {error}": "Error al generar el informe PDF: {error}",
    "Amplitude (mV)": "Amplitud (mV)",
    "Time (s)": "Tiempo (s)",
    # Progress bar + fatigue summary (analysis tab).
    "Ready": "Listo",
    "Analysing…  %p%": "Analizando…  %p%",
    "Fatigue: DETECTED (MDF decreasing)": "Fatiga: DETECTADA (MDF decrece)",
    "Fatigue: Not detected (MDF stable or increasing)":
        "Fatiga: No detectada (MDF estable o crece)",
    "Fatigue: Undetermined (insufficient signal)":
        "Fatiga: Indeterminada (Señal insuficiente)",

    # --- MVC worker / GUI ---
    "Signal loaded — {fs:.0f} Hz — {dur:.1f} s — units: {units}":
        "Señal cargada — {fs:.0f} Hz — {dur:.1f} s — unidades: {units}",
    "Processing test signal (notch → band-pass → envelope)…":
        "Procesando señal de prueba (notch → paso-banda → envolvente)…",
    "Loading MVC file: {path}": "Cargando archivo CVM: {path}",
    "Processing MVC signal…": "Procesando señal CVM…",
    "external MVC file (percentile {p:.0f})": "archivo CVM externo (percentil {p:.0f})",
    "Could not load the MVC file ({error}). Falling back to auto-normalisation.":
        "No se pudo cargar el archivo CVM ({error}). Se usa auto-normalización.",
    "auto (percentile {p:.0f} of the test signal)":
        "automática (percentil {p:.0f} de la señal de prueba)",
    "MVC reference amplitude: {value:.4f} {units} ({source})":
        "Amplitud CVM de referencia: {value:.4f} {units} ({source})",
    "Mean normalised activation: {value:.1f} % MVC":
        "Activación media normalizada: {value:.1f} % CVM",
    "MVC normalisation parameters": "Parámetros de normalización CVM",
    "Test EDF:": "EDF de prueba:",
    "Select the EDF file to normalise…": "Selecciona el archivo EDF a normalizar…",
    "MVC reference EDF (optional):": "EDF de referencia CVM (opcional):",
    "Leave empty for auto-normalisation…": "Dejar vacío para auto-normalización…",
    "Remove": "Quitar",
    "EMG channel of the EDF to normalise. Filled with the channels "
    "of the test file when you select it.":
        "Canal EMG del EDF a normalizar. Se rellena con los canales "
        "del archivo de prueba al seleccionarlo.",
    "Compute MVC": "Calcular CVM",
    "Normalisation summary": "Resumen de normalización",
    "MVC reference:": "CVM referencia:",
    "Mean activation:": "Activación media:",
    "MVC source:": "Fuente CVM:",
    "1. Filtered and rectified EMG signal": "1. Señal EMG filtrada y rectificada",
    "Amplitude ({units})": "Amplitud ({units})",
    "MVC ref: {value:.4f} {units}": "CVM ref: {value:.4f} {units}",
    "2. Envelope and MVC reference amplitude": "2. Envolvente y amplitud de referencia CVM",
    "3. EMG signal normalised to MVC (% MVC)": "3. Señal EMG normalizada al CVM (% CVM)",
    "% MVC": "% CVM",
    "Activation (% MVC)": "Activación (% CVM)",
    "100 % MVC": "100 % CVM",
    "Select test EDF": "Seleccionar EDF de prueba",
    "Select MVC reference EDF": "Seleccionar EDF de referencia CVM",
    # -- muscle-load analysis (Jonsson APDF) --
    "Muscle load:": "Carga muscular:",
    "Static": "Estático",
    "Median": "Mediano",
    "Peak": "Pico",
    "4. Muscle-load distribution (APDF, Jonsson)":
        "4. Distribución de carga muscular (APDF, Jonsson)",
    "Load (% MVC)": "Carga (% CVM)",
    "Cumulative % of time": "% del tiempo acumulado",
    "Muscle load (Jonsson) — static {st:.1f} %, median {md:.1f} %, peak {pk:.1f} % MVC":
        "Carga muscular (Jonsson) — estático {st:.1f} %, mediano {md:.1f} %, "
        "pico {pk:.1f} % CVM",

    # --- DSP diagnostics ---
    "Possible saturation: {pct:.1f}% of samples sit at ADC extremes "
    "for runs ≥ 10 ms. Check electrode contact and gain.":
        "Posible saturación: el {pct:.1f}% de las muestras están en los extremos "
        "del ADC durante tramos ≥ 10 ms. Revisa el contacto del electrodo y la ganancia.",
    "Suspiciously flat baseline at the start of the recording. "
    "May indicate a disconnected electrode or misconfigured gain.":
        "Línea base sospechosamente plana al inicio del registro. "
        "Puede indicar un electrodo desconectado o una ganancia mal configurada.",

    # --- devices ---
    "The serial port is already open.": "El puerto serie ya está abierto.",
    "The Arduino on {port} did not reply READY within {timeout:.0f} s.":
        "El Arduino en {port} no respondió READY en {timeout:.0f} s.",
    "The Arduino device is not open.": "El dispositivo Arduino no está abierto.",
    "Timeout while reading from the Arduino — connection lost.":
        "Tiempo de espera agotado al leer del Arduino — conexión perdida.",
    "BitalinoDevice requires the optional 'bitalino' extra. "
    'Install it with: pip install "emgteach[bitalino]"':
        "BitalinoDevice requiere el extra opcional 'bitalino'. "
        'Instálalo con: pip install "emgteach[bitalino]"',
    "A BITalino connection is already active. Close it before opening another.":
        "Ya hay una conexión BITalino activa. Ciérrala antes de abrir otra.",
    "The BITalino device is not open.": "El dispositivo BITalino no está abierto.",

    # --- PDF report ---
    "Yes — MDF decreases over time ({slope:+.2f} Hz/s)":
        "Sí — la MDF desciende con el tiempo ({slope:+.2f} Hz/s)",
    "No — MDF stays stable or increases ({slope:+.2f} Hz/s)":
        "No — la MDF se mantiene o aumenta ({slope:+.2f} Hz/s)",
    "Undetermined (short or constant signal)": "Indeterminada (señal corta o constante)",
    "Filtered (mV)": "Filtrada (mV)",
    "EMG signal — channel «{name}»": "Señal EMG — canal «{name}»",
    "Envelope (mV)": "Envolvente (mV)",
    "Rectified": "Rectificado",
    "Filtered (20-450 Hz)": "Filtrado (20-450 Hz)",
    "LP envelope": "Envolvente LP",
    "Amplitude (0-1)": "Amplitud (0-1)",
    "MDF per window": "MDF por ventana",
    "Trend (degree 2)": "Tendencia (grado 2)",
    "Degree-2 fit": "Ajuste grado 2",
    "6. Fatigue: median frequency (MDF) vs time":
        "6. Fatiga: frecuencia mediana (MDF) vs tiempo",
    "7. Amplitude (RMS) vs median frequency (MDF)":
        "7. Amplitud (RMS) vs frecuencia mediana (MDF)",
    "EMG recording and analysis report": "Informe de registro y análisis de EMG",
    "Student: {name}": "Alumno/a: {name}",
    "Generated on: {dt:%Y-%m-%d %H:%M}": "Fecha de generación: {dt:%Y-%m-%d %H:%M}",
    "File: {name}": "Archivo: {name}",
    "Graphs": "Gráficos",
    "Metrics": "Métricas",
    "Metric": "Métrica",
    "Value": "Valor",
    "Duration": "Duración",
    "Global RMS": "RMS global",
    "Mean frequency (MNF)": "Frecuencia media (MNF)",
    "Median frequency (MDF)": "Frecuencia mediana (MDF)",
    "Fatigue evidence": "Evidencia de fatiga",
    "Configuration used": "Configuración utilizada",
    "Parameter": "Parámetro",
    "Sampling rate": "Frecuencia de muestreo",
    "Channel": "Canal",
    "Band-pass": "Paso-banda",
    "Notch (mains)": "Notch (red)",
    "Envelope (low-pass)": "Envolvente (paso-bajo)",
    "RMS window": "Ventana RMS",
    "Device": "Dispositivo",
    "not stored in the EDF": "no almacenado en el EDF",
    "generated {dt:%Y-%m-%d %H:%M}": "generado {dt:%Y-%m-%d %H:%M}",
    "page {n}": "página {n}",
}
