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
    "Restore default address ({addr})": "Restaurar dirección por defecto ({addr})",
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
    "Save EDF recording as…": "Guardar grabación EDF como…",
    "BITalino MAC address (recommended — stable on every PC), or an "
    "explicit COM port (e.g. COM5), or leave empty to autodetect. Pair "
    "the BITalino in Windows Bluetooth settings first. No PyBluez is used.":
        "Dirección MAC del BITalino (recomendado — estable en cualquier PC), o un "
        "puerto COM concreto (p. ej. COM5), o déjalo vacío para autodetectar. Empareja "
        "antes el BITalino en la configuración Bluetooth de Windows. No se usa PyBluez.",
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
    # -- live muscle-load monitor --
    "Muscle load (live MVC)": "Carga muscular (CVM en vivo)",
    "Calibrate MVC": "Calibrar CVM",
    "Record a few seconds of maximum contraction to set the MVC "
    "reference for the live load monitor.":
        "Graba unos segundos de contracción máxima para fijar la referencia "
        "CVM del monitor de carga en vivo.",
    "Calibrate the MVC to start monitoring.":
        "Calibra el CVM para empezar a monitorizar.",
    "Calibrating… contract at maximum for {s:.0f} s.":
        "Calibrando… contrae al máximo durante {s:.0f} s.",
    "MVC calibrated. Monitoring load.": "CVM calibrado. Monitorizando carga.",
    "MVC calibrated for live load monitoring.":
        "CVM calibrado para el monitor de carga en vivo.",
    "Calibration failed (no signal).": "Calibración fallida (sin señal).",
    "static {st:.0f} · median {md:.0f} · peak {pk:.0f} %":
        "estático {st:.0f} · mediano {md:.0f} · pico {pk:.0f} %",
    "not calibrated": "sin calibrar",
    "Warning": "Aviso",
    "Danger": "Peligro",
    "Load (% MVC) where the warning (tiredness) zone starts.":
        "Carga (% CVM) en la que empieza la zona de aviso (cansancio).",
    "Load (% MVC) where the danger (fatigue) zone starts.":
        "Carga (% CVM) en la que empieza la zona de peligro (fatiga).",

    # -- new-session reset (tab-bar corner) --
    "New session": "Nueva sesión",
    "Clear everything and start over (e.g. a new student)":
        "Borra todo y empieza de cero (p. ej. un nuevo alumno)",
    "Stop the recording before starting a new session.":
        "Detén la grabación antes de iniciar una nueva sesión.",
    "Clear everything and start a new session?\n\n"
    "This clears the on-screen data, markers, log, calibration and "
    "the loaded analysis. The EDF files already saved on disk are "
    "not deleted.":
        "¿Borrar todo e iniciar una nueva sesión?\n\n"
        "Se borran los datos en pantalla, los marcadores, el registro, la "
        "calibración y el análisis cargado. Los archivos EDF ya guardados en "
        "disco no se eliminan.",
    "New session started.": "Nueva sesión iniciada.",

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
    "1A. Raw": "1A. En bruto",
    "2. Env. norm.": "2. Env. norm.",
    "3. PSD": "3. PSD",
    "4. Filt.+rect.": "4. Filtr.+rect.",
    "5. Env. vs RMS": "5. Env. vs RMS",
    "6. RMS/window": "6. RMS/ventana",
    "7. MDF/time": "7. MDF/tiempo",
    "8. RMS vs MDF": "8. RMS vs MDF",
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
    "1A. Raw signal": "1A. Señal en bruto",
    "2. Normalised envelope": "2. Envolvente normalizada",
    "3. PSD with MNF/MDF": "3. PSD con MNF/MDF",
    "4. Filtered + rectified": "4. Filtrada + rectificada",
    "5. Envelope vs RMS": "5. Envolvente vs RMS",
    "6. RMS per window": "6. RMS por ventana",
    "7. MDF vs time (fatigue)": "7. MDF vs tiempo (fatiga)",
    "1A. Raw EMG signal": "1A. Señal EMG en bruto",
    "Filtered EMG (20-450 Hz)": "EMG filtrado (20-450 Hz)",
    "4. Filtered + rectified EMG signal": "4. Señal EMG filtrada + rectificada",
    "Rectified EMG": "EMG rectificado",
    "LP envelope (zero-phase)": "Envolvente LP (fase cero)",
    "RMS envelope": "Envolvente RMS",
    "5. EMG signal envelope": "5. Envolvente de la señal EMG",
    "Normalised envelope (max=1)": "Envolvente normalizada (max=1)",
    "2. Envelope normalised to maximum": "2. Envolvente normalizada al máximo",
    "Normalised amplitude (0-1)": "Amplitud normalizada (0-1)",
    "3. Power spectral density (PSD)": "3. Densidad espectral de potencia (PSD)",
    "Frequency (Hz)": "Frecuencia (Hz)",
    "RMS per 1 s window": "RMS por ventana de 1 s",
    "6. RMS amplitude over time": "6. Amplitud RMS en el tiempo",
    "Median frequency per window": "Frecuencia mediana por ventana",
    "Trend (degree-2 polynomial)": "Tendencia (polinomio grado 2)",
    "7. Fatigue trend: median frequency vs. time\n"
    "   (a decrease indicates muscle fatigue)":
        "7. Tendencia de fatiga: frecuencia mediana vs. tiempo\n"
        "   (un descenso indica fatiga muscular)",
    "Degree-2 polynomial fit": "Ajuste polinómico grado 2",
    "8. Amplitude (force) vs median frequency (fatigue)":
        "8. Relación amplitud (fuerza) vs frecuencia mediana (fatiga)",
    "Select EDF file": "Seleccionar archivo EDF",
    "EDF files (*.edf *.EDF)": "Archivos EDF (*.edf *.EDF)",
    "Save figure": "Guardar figura",
    "PNG images (*.png)": "Imágenes PNG (*.png)",
    "Save PDF report": "Guardar informe PDF",
    "PDF documents (*.pdf)": "Documentos PDF (*.pdf)",
    "Figure saved to: {path}": "Figura guardada en: {path}",
    "Report graphs": "Gráficos del informe",
    "Tick the graphs to add to the report:": "Marca los gráficos que se añadirán al informe:",
    "Time range to plot (s):": "Tramo temporal a dibujar (s):",
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
    "Muscle-load distribution (APDF, Jonsson)":
        "Distribución de carga muscular (APDF, Jonsson)",
    "Normalisation and muscle load": "Normalización y carga muscular",
    "Muscle load (Jonsson APDF)": "Carga muscular (APDF de Jonsson)",
    "Static (P10):": "Estático (P10):",
    "Median (P50):": "Mediano (P50):",
    "Peak (P90):": "Pico (P90):",
    "MVC normalisation and muscle-load report":
        "Informe de normalización CVM y carga muscular",
    "exceeds limit": "supera el límite",
    "within limit": "dentro del límite",
    "Normal range:": "Rango normal:",
    "near-continuous background load": "carga casi continua (de fondo)",
    "typical working load": "carga de trabajo típica",
    "recurrent high-effort load": "esfuerzos altos recurrentes",
    "average activation over the task": "activación media durante la tarea",
    "Report time range": "Rango temporal del informe",

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
    "A BITalino connection is already active. Close it before opening another.":
        "Ya hay una conexión BITalino activa. Ciérrala antes de abrir otra.",
    "The BITalino device is not open.": "El dispositivo BITalino no está abierto.",
    "Could not open the BITalino port {port}: {err}. If the port is "
    "busy or access is denied, switch the BITalino off and on to reset "
    "the Bluetooth link, then retry.":
        "No se pudo abrir el puerto del BITalino {port}: {err}. Si el puerto está "
        "ocupado o el acceso está denegado, apaga y enciende el BITalino para "
        "reiniciar el enlace Bluetooth y reintenta.",
    "BITalino {mac} was not found among the paired Bluetooth COM "
    "ports. Pair it in the operating system's Bluetooth settings "
    "and switch it on.":
        "No se encontró el BITalino {mac} entre los puertos COM Bluetooth "
        "emparejados. Empareja el dispositivo en la configuración Bluetooth del "
        "sistema y enciéndelo.",
    "No BITalino was found on the Bluetooth COM ports. Pair the "
    "BITalino in the operating system's Bluetooth settings and switch "
    "it on, or enter its MAC address or COM port explicitly.":
        "No se encontró ningún BITalino en los puertos COM Bluetooth. Empareja el "
        "BITalino en la configuración Bluetooth del sistema y enciéndelo, o "
        "introduce su dirección MAC o su puerto COM explícitamente.",
    "The device on {port} did not identify itself as a "
    "BITalino. Check that the BITalino is paired and "
    "switched on.":
        "El dispositivo en {port} no se identificó como un BITalino. "
        "Comprueba que el BITalino está emparejado y encendido.",
    "Unsupported BITalino sampling rate {fs} Hz. "
    "Use one of 1, 10, 100 or 1000.":
        "Frecuencia de muestreo {fs} Hz no soportada por el BITalino. "
        "Usa 1, 10, 100 o 1000.",
    "Invalid BITalino channel list; channels must be in 0..5.":
        "Lista de canales del BITalino no válida; deben estar en 0..5.",
    "Timeout while reading from the BITalino — connection lost.":
        "Tiempo de espera agotado al leer del BITalino — conexión perdida.",
    "Corrupted BITalino frame (CRC mismatch) — connection lost.":
        "Trama del BITalino corrupta (error de CRC) — conexión perdida.",

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
    "7. Fatigue: median frequency (MDF) vs time":
        "7. Fatiga: frecuencia mediana (MDF) vs tiempo",
    "8. Amplitude (RMS) vs median frequency (MDF)":
        "8. Amplitud (RMS) vs frecuencia mediana (MDF)",
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

    # --- fragment editor / CSV export / new UI (v1.1.x) ---
    # -- DSP live signal-quality diagnostics --
    "Signal OK": "Señal correcta",
    "Flat signal — check electrode contact": "Señal plana — revisa el contacto del electrodo",
    "Saturation: {pct:.0f}% at rails — lower gain":
        "Saturación: {pct:.0f}% en los extremos — baja la ganancia",
    # -- CSV export (exports.py) --
    "undetermined": "indeterminada",
    "fatigue (MDF decreasing)": "fatiga (MDF decreciente)",
    "no fatigue (MDF stable/increasing)": "sin fatiga (MDF estable/creciente)",
    "whole recording": "registro completo",
    "File": "Archivo",
    "Sampling rate (Hz)": "Frecuencia de muestreo (Hz)",
    "Analysed window": "Ventana analizada",
    "Duration (s)": "Duración (s)",
    "Global RMS (mV)": "RMS global (mV)",
    "MNF (Hz)": "MNF (Hz)",
    "MDF (Hz)": "MDF (Hz)",
    "MDF slope (Hz/s)": "Pendiente MDF (Hz/s)",
    "MDF slope (Hz/min)": "Pendiente MDF (Hz/min)",
    "MDF R2": "R² de MDF",
    "MDF decline (%)": "Descenso MDF (%)",
    "{n} fragments: {list} s": "{n} fragmentos: {list} s",
    "{a:.2f}-{b:.2f} s of {d:.1f} s": "{a:.2f}-{b:.2f} s de {d:.1f} s",
    "Per-segment metrics": "Métricas por segmento",
    # -- fatigue verdicts (reports.py / workers) --
    "Yes — MDF falls {slope:+.2f} Hz/s ({decline:.1f}% decline, R²={r2:.2f})":
        "Sí — la MDF desciende {slope:+.2f} Hz/s ({decline:.1f}% de descenso, R²={r2:.2f})",
    "No — MDF stable or rising ({slope:+.2f} Hz/s, R²={r2:.2f})":
        "No — MDF estable o en aumento ({slope:+.2f} Hz/s, R²={r2:.2f})",
    "Analysed fragments": "Fragmentos analizados",
    "Protocol: {p}": "Protocolo: {p}",
    "{n} fragments ({d:.2f} s of {full:.1f} s): {list} s":
        "{n} fragmentos ({d:.2f} s de {full:.1f} s): {list} s",
    "Fitting MDF-vs-time regression…": "Ajustando la regresión MDF-tiempo…",
    "The selected region ({a:.2f}-{b:.2f} s) is shorter than the 1 s minimum required for analysis.":
        "La región seleccionada ({a:.2f}-{b:.2f} s) es más corta que el mínimo de 1 s "
        "requerido para el análisis.",
    "The selected fragments total {t:.2f} s, below the 1 s minimum required for analysis.":
        "Los fragmentos seleccionados suman {t:.2f} s, por debajo del mínimo de 1 s "
        "requerido para el análisis.",
    "Fatigue trend: MDF slope {slope:.3f} Hz/s ({decline:.1f}% decline, R²={r2:.2f}).":
        "Tendencia de fatiga: pendiente MDF {slope:.3f} Hz/s ({decline:.1f}% de descenso, "
        "R²={r2:.2f}).",
    "Region of interest: {a:.2f}-{b:.2f} s ({d:.2f} s).":
        "Región de interés: {a:.2f}-{b:.2f} s ({d:.2f} s).",
    "Analysing {n} selected fragments ({d:.2f} s of {full:.2f} s).":
        "Analizando {n} fragmentos seleccionados ({d:.2f} s de {full:.2f} s).",
    "No fatigue: MDF slope {slope:+.3f} Hz/s (R²={r2:.2f}).":
        "Sin fatiga: pendiente MDF {slope:+.3f} Hz/s (R²={r2:.2f}).",
    # -- acquisition tab (protocol / markers) --
    "Name": "Nombre",
    "e.g. Isometric biceps 30 s": "p. ej. Bíceps isométrico 30 s",
    "Live signal quality: saturation or a flat (disconnected) signal.":
        "Calidad de señal en vivo: saturación o señal plana (desconectada).",
    "Markers recorded so far. Select one and press Delete to remove it.":
        "Marcadores registrados hasta ahora. Selecciona uno y pulsa Supr para eliminarlo.",
    "Delete": "Eliminar",
    "Delete the selected marker.": "Elimina el marcador seleccionado.",
    "Protocol:": "Protocolo:",
    "Marker deleted: t={t:.1f} s — {label}": "Marcador eliminado: t={t:.1f} s — {label}",
    # -- analysis tab (region / fragments / CSV) --
    "Export CSV": "Exportar CSV",
    "Analyse only a region:": "Analizar solo una región:",
    "Restrict every metric (spectrum, RMS, fatigue) to the time window below instead of the whole recording.":
        "Restringe todas las métricas (espectro, RMS, fatiga) a la ventana temporal de "
        "abajo en lugar del registro completo.",
    "Select fragments…": "Seleccionar fragmentos…",
    "Open the assisted editor to keep the significant fragments and discard the rest. Takes precedence over the region above.":
        "Abre el editor asistido para conservar los fragmentos significativos y descartar "
        "el resto. Tiene prioridad sobre la región de arriba.",
    "Cancel": "Cancelar",
    "CSV files (*.csv)": "Archivos CSV (*.csv)",
    "from": "desde",
    "to": "hasta",
    "Cancelling analysis…": "Cancelando análisis…",
    "Fatigue: DETECTED (MDF −{decline:.1f}%)": "Fatiga: DETECTADA (MDF −{decline:.1f}%)",
    "CSV exported to: {path}": "CSV exportado a: {path}",
    "{n} fragment(s) selected ({d:.1f} s)": "{n} fragmento(s) seleccionado(s) ({d:.1f} s)",
    "Could not open the fragment editor: {error}":
        "No se pudo abrir el editor de fragmentos: {error}",
    "CSV export error: {error}": "Error al exportar CSV: {error}",
    "Cancelling…": "Cancelando…",
    # -- fragment-selection widget --
    "Select analysis fragments": "Seleccionar fragmentos de análisis",
    "The app suggests the informative fragments (active periods). Adjust, add or remove them; only the checked fragments are analysed. You decide the final selection.":
        "La app sugiere los fragmentos informativos (periodos activos). Ajústalos, "
        "añádelos o quítalos; solo se analizan los fragmentos marcados. Tú decides la "
        "selección final.",
    "Band-pass low cut-off (Hz).": "Frecuencia de corte baja del paso-banda (Hz).",
    "Band-pass high cut-off (Hz).": "Frecuencia de corte alta del paso-banda (Hz).",
    "Mains-notch frequency (Hz), usually 50 or 60.":
        "Frecuencia del notch de red (Hz), normalmente 50 o 60.",
    "Envelope low-pass cut-off (Hz): lower = smoother envelope.":
        "Frecuencia de corte del paso-bajo de la envolvente (Hz): menor = envolvente más suave.",
    "Threshold in robust standard deviations above the resting baseline. Lower = more sensitive (keeps weaker activity).":
        "Umbral en desviaciones típicas robustas sobre la línea base de reposo. "
        "Menor = más sensible (conserva actividad más débil).",
    "Shortest fragment kept; briefer active periods are discarded.":
        "Fragmento más corto que se conserva; los periodos activos más breves se descartan.",
    "Active periods separated by less than this are merged into one.":
        "Los periodos activos separados por menos de esto se fusionan en uno.",
    "Auto-suggest": "Auto-sugerir",
    "Re-run the automatic fragment proposal with the parameters above.":
        "Vuelve a ejecutar la propuesta automática de fragmentos con los parámetros de arriba.",
    "Add fragment": "Añadir fragmento",
    "Remove selected": "Quitar seleccionado",
    "Whole recording": "Registro completo",
    "Clear the selection and analyse everything.": "Borra la selección y analiza todo.",
    "Use these fragments": "Usar estos fragmentos",
    "Keep": "Conservar",
    "Start (s)": "Inicio (s)",
    "End (s)": "Fin (s)",
    "Reason": "Motivo",
    "Envelope filter (Hz):": "Filtro de envolvente (Hz):",
    "band": "banda",
    "notch": "notch",
    "envelope": "envolvente",
    "Detection:": "Detección:",
    "sensitivity k": "sensibilidad k",
    "min. duration": "duración mín.",
    "merge gap": "hueco de fusión",
    "Whole recording will be analysed.": "Se analizará el registro completo.",
    "{n} fragment(s) — {d:.2f} s of {full:.1f} s": "{n} fragmento(s) — {d:.2f} s de {full:.1f} s",

    "page {n}": "página {n}",
}
