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
    "Surface EMG acquisition": "Adquisición de EMG de superficie",
    "Acquisition": "Adquisición",
    "Analysis": "Análisis",
    "MVC normalisation": "Normalización CVM",
    "Interface language": "Idioma de la interfaz",
    "About EMG Bioinstrumentation": "Acerca de EMG Bioinstrumentación",
    "Language": "Idioma",
    "The language change will take effect when you restart the application.":
        "El cambio de idioma se aplicará al reiniciar la aplicación.",
    "Version": "Versión",
    "Physiology Department, Complutense University of Madrid":
        "Departamento de Fisiología, Universidad Complutense de Madrid",

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
    # -- classroom broadcast (followers on phones) --
    # -- accelerometer (ACC) --
    "ACC": "ACC",
    "Accelerometer (normalised g)": "Acelerómetro (g normalizado)",
    "Also record the BITalino accelerometer (A4) in its own plot and "
    "EDF channel. Useful to relate muscle activation to movement, "
    "flag motion artefacts, or show tremor. BITalino only.":
        "Registra también el acelerómetro del BITalino (A4) en su propia "
        "gráfica y canal EDF. Útil para relacionar la activación muscular con "
        "el movimiento, señalar artefactos de movimiento o mostrar el temblor. "
        "Solo BITalino.",
    "on the muscle (MMG)": "en el músculo (MMG)",
    "on the moving segment (tremor)": "en el segmento móvil (temblor)",
    "Where the accelerometer is stuck — sets which ACC analyses apply.":
        "Dónde se pega el acelerómetro — determina qué análisis de ACC aplican.",
    "10. EMG vs MMG (electrical vs mechanical)":
        "10. EMG vs MMG (eléctrico vs mecánico)",
    "11. Tremor (accelerometer FFT)": "11. Temblor (FFT del acelerómetro)",
    "10. EMG vs MMG": "10. EMG vs MMG",
    "11. Tremor": "11. Temblor",
    "11. Tremor — accelerometer spectrum":
        "11. Temblor — espectro del acelerómetro",
    "Electrical (EMG) vs mechanical (MMG, from the accelerometer on "
    "the muscle) envelope — needs an accelerometer channel.":
        "Envolvente eléctrica (EMG) vs mecánica (MMG, del acelerómetro sobre "
        "el músculo) — requiere un canal de acelerómetro.",
    "Frequency spectrum of the accelerometer with the tremor peak "
    "(physiological ~8-12 Hz) — needs an accelerometer channel.":
        "Espectro de frecuencia del acelerómetro con el pico de temblor "
        "(fisiológico ~8-12 Hz) — requiere un canal de acelerómetro.",
    "EMG — {ch} (electrical)": "EMG — {ch} (eléctrico)",
    "MMG is paired with «{ch}» — the muscle carrying the accelerometer.":
        "El MMG se empareja con «{ch}» — el músculo que lleva el acelerómetro.",
    "MMG envelope (mechanical)": "Envolvente MMG (mecánica)",
    "EMG (mV)": "EMG (mV)",
    "MMG (g)": "MMG (g)",
    "No accelerometer channel in this recording.":
        "Este registro no tiene canal de acelerómetro.",
    "Peak: {hz:.1f} Hz": "Pico: {hz:.1f} Hz",
    "Accelerometer «{name}» — tremor peak {hz:.1f} Hz.":
        "Acelerómetro «{name}» — pico de temblor {hz:.1f} Hz.",
    "Could not analyse the accelerometer «{name}»: {err}":
        "No se pudo analizar el acelerómetro «{name}»: {err}",
    # -- force-velocity study --
    "Force-velocity study…": "Estudio fuerza-velocidad…",
    "Force-velocity study": "Estudio fuerza-velocidad",
    "Build the load-velocity, force-velocity, power and recruitment "
    "curves from one recording where several known loads were "
    "lifted. Needs an accelerometer channel.":
        "Construye las curvas carga-velocidad, fuerza-velocidad, potencia y "
        "reclutamiento a partir de un registro en el que se levantaron varias "
        "cargas conocidas. Requiere un canal de acelerómetro.",
    "Could not open the force-velocity study: {error}":
        "No se pudo abrir el estudio fuerza-velocidad: {error}",
    "Repetitions (one per contraction):":
        "Repeticiones (una por contracción):",
    "Use": "Usar",
    "Rep": "Rep",
    "Load (kg)": "Carga (kg)",
    "Velocity (a.u.)": "Velocidad (u.a.)",
    "Untick any contraction that is clearly not valid, then Redraw. "
    "Repetitions at the same load are averaged. Velocity is in "
    "arbitrary units (the accelerometer is uncalibrated); force is the "
    "entered load.":
        "Desmarcar cualquier contracción que no sea claramente válida y pulsar "
        "Redibujar. Las repeticiones de la misma carga se promedian. La "
        "velocidad está en unidades arbitrarias (el acelerómetro no está "
        "calibrado); la fuerza es la carga introducida.",
    "⚠ The accelerometer barely moved (flat / pinned at a rail), so "
    "the velocities are ~0. Put it on the moving segment, oriented "
    "so its resting value sits mid-range (not at ±1 g), and lift "
    "quickly.":
        "⚠ El acelerómetro apenas se movió (plano / pegado a un extremo), así "
        "que las velocidades son ~0. Colocarlo en el segmento móvil, orientado "
        "para que en reposo quede a media escala (no en ±1 g), y levantar "
        "rápido.",
    "No repetitions detected in this recording.":
        "No se detectaron repeticiones en este registro.",
    "No velocity — accelerometer flat\n(see the warning)":
        "Sin velocidad — acelerómetro plano\n(ver el aviso)",
    # Analogue-channel diagnostic (find where the accelerometer is wired).
    "Find ACC channel…": "Buscar canal del ACC…",
    "Read all six analogue inputs live to see which one responds when "
    "you tilt the accelerometer. Connect the BITalino first, and do "
    "not run it while recording.":
        "Lee las seis entradas analógicas en vivo para ver cuál responde al "
        "girar el acelerómetro. Conectar el BITalino primero, y no usarlo "
        "mientras se graba.",
    "Find the accelerometer channel": "Buscar el canal del acelerómetro",
    "Reading all six analogue inputs. Tilt the accelerometer slowly "
    "through 90° in each direction: the channel whose range grows the "
    "most is where the accelerometer is wired. A4 is the one emgteach "
    "uses for the ACC.":
        "Leyendo las seis entradas analógicas. Girar el acelerómetro despacio "
        "90° en cada dirección: el canal cuyo rango más crece es donde está "
        "conectado el acelerómetro. A4 es el que emgteach usa para el ACC.",
    "Value (raw)": "Valor (crudo)",
    "Range": "Rango",
    "Movement": "Movimiento",
    "Reset ranges": "Reiniciar rangos",
    "✓ The accelerometer responds on A4 — as expected.":
        "✓ El acelerómetro responde en A4 — como debe ser.",
    "→ The accelerometer is on {ch}, not A4. Move its plug to "
    "the A4 port (or tell me and I make the ACC channel "
    "selectable).":
        "→ El acelerómetro está en {ch}, no en A4. Cambiar su conector al "
        "puerto A4 (o indicarlo y hago el canal del ACC seleccionable).",
    "Tilt the sensor 90°… no channel clearly responds yet.":
        "Girar el sensor 90°… ningún canal responde claramente aún.",
    "Could not read the BITalino: {err}":
        "No se pudo leer el BITalino: {err}",
    "Use this channel for the ACC": "Usar este canal para el ACC",
    "ACC ch:": "Canal ACC:",
    "Analogue input the accelerometer is connected to (default A4). "
    "Use \"Find ACC channel…\" if unsure.":
        "Entrada analógica a la que está conectado el acelerómetro (por "
        "defecto A4). Usar «Buscar canal del ACC…» en caso de duda.",
    "Accelerometer set to A{n}.": "Acelerómetro fijado en A{n}.",
    "Channels: EMG on {emg}, accelerometer on A{acc}.":
        "Canales: EMG en {emg}, acelerómetro en A{acc}.",
    "Tick at least two valid repetitions with a load (kg) entered, "
    "then press Redraw.":
        "Marcar al menos dos repeticiones válidas con una carga (kg) "
        "introducida y pulsar Redibujar.",
    "Load-velocity": "Carga-velocidad",
    "Force-velocity (normalised)": "Fuerza-velocidad (normalizada)",
    "Force (fraction of max)": "Fuerza (fracción del máximo)",
    "Velocity (fraction of max)": "Velocidad (fracción del máximo)",
    "Power (load × velocity)": "Potencia (carga × velocidad)",
    "Power (a.u.)": "Potencia (u.a.)",
    "Recruitment (load vs EMG)": "Reclutamiento (carga vs EMG)",
    "EMG amplitude (mV)": "Amplitud EMG (mV)",
    # Guided force-velocity acquisition wizard.
    "Guided F-V…": "F-V guiada…",
    "Guided force-velocity acquisition": "Adquisición fuerza-velocidad guiada",
    "Guided force-velocity acquisition: an MVC maximum first (no "
    "load), then a discrete 'contract with this load' prompt for "
    "every repetition of every load. Starts the recording for you "
    "and marks each contraction with its load so the force-velocity "
    "study reads them directly. Enable the accelerometer and connect "
    "the BITalino first.":
        "Adquisición fuerza-velocidad guiada: primero una CVM máxima (sin "
        "carga) y luego un aviso «contraiga con esta carga» para cada repetición "
        "de cada carga. Inicia la grabación por usted y marca cada contracción con "
        "su carga, para que el estudio fuerza-velocidad las lea directamente. "
        "Activar el acelerómetro y conectar el BITalino primero.",
    "Loads (kg):": "Cargas (kg):",
    "e.g.  2, 4, 6, 8": "p. ej.  2, 4, 6, 8",
    "Separate loads with commas or spaces; use a dot for decimals "
    "(e.g. 7.5).":
        "Separar las cargas con comas o espacios; usar el punto para decimales "
        "(p. ej. 7.5).",
    "⚠ The accelerometer is set to the muscle. For force-velocity "
    "put it on the moving segment (set the placement to \"on the "
    "moving segment\"), or the velocity will be near zero.":
        "⚠ El acelerómetro está en el músculo. Para fuerza-velocidad ponerlo en "
        "el segmento móvil (poner la colocación en «en el segmento móvil»), o la "
        "velocidad será casi cero.",
    "Contractions per load:": "Contracciones por carga:",
    "Contractions to perform at each load. The wizard prompts one at a "
    "time; keep it low (1-3) so fatigue does not bias the heavier loads.":
        "Contracciones a realizar en cada carga. El asistente las pide de una en "
        "una; mantenlo bajo (1-3) para que la fatiga no sesgue las cargas más "
        "pesadas.",
    "Prepare time:": "Tiempo de preparación:",
    "Countdown to prepare before each contraction.":
        "Cuenta atrás para prepararte antes de cada contracción.",
    "Lift time:": "Tiempo de levantamiento:",
    "Time given for each loaded lift — a quick concentric movement, not "
    "a hold (the MVC maximum is held separately).":
        "Tiempo para cada levantamiento con carga — un movimiento concéntrico "
        "rápido, no un mantenimiento (la CVM máxima se mantiene aparte).",
    "Enter at least two positive loads (kg), separated by spaces.":
        "Introducir al menos dos cargas positivas (kg), separadas por espacios.",
    "List the known loads (kg) the subject will lift, lightest to "
    "heaviest. The wizard first guides an MVC maximum (no load), then "
    "for each load cues a quick lift ('Lift!' → 'Relax!', no hold), "
    "marking each so the force-velocity study reads the loads "
    "automatically.":
        "Indicar las cargas conocidas (kg) que levantará el sujeto, de menor a "
        "mayor. El asistente guía primero una CVM máxima (sin carga) y luego, "
        "para cada carga, indica un levantamiento rápido («¡Levante!» → "
        "«¡Relaje!», sin mantener), marcando cada uno para que el estudio "
        "fuerza-velocidad lea las cargas automáticamente.",
    # Config label next to the guided-F-V button (reps · loads).
    "{reps}× · loads: {loads} kg": "{reps}× · cargas: {loads} kg",
    "(loads not set)": "(cargas sin definir)",
    # Guided-F-V wizard prompts (MVC maximum first, then per-load contractions).
    "Get ready — maximum contraction (no load)":
        "Prepárese — contracción máxima (sin carga)",
    "Contract at maximum when the count reaches 0":
        "Contraiga al máximo cuando la cuenta llegue a 0",
    "Get ready — maximum (no load): {n}":
        "Prepárese — máxima (sin carga): {n}",
    "Contract at maximum! (no load)": "¡Contraiga al máximo! (sin carga)",
    "Contract at maximum! ({s:.0f} s)": "¡Contraiga al máximo! ({s:.0f} s)",
    "Relax — now the loads, lightest first":
        "Relaje — ahora las cargas, de menor a mayor",
    "Relax — the loads come next…": "Relaje — ahora vienen las cargas…",
    " (load {i}/{n}, rep {r}/{rn})": " (carga {i}/{n}, rep {r}/{rn})",
    "Prepare {kg:g} kg{prog}": "Prepare {kg:g} kg{prog}",
    "Prepare {kg:g} kg{prog}: {n}": "Prepare {kg:g} kg{prog}: {n}",
    "Lift {kg:g} kg when the count reaches 0":
        "Levante {kg:g} kg cuando la cuenta llegue a 0",
    "Lift {kg:g} kg!": "¡Levante {kg:g} kg!",
    "Lift {kg:g} kg — then relax": "Levante {kg:g} kg — luego relaje",
    "Relax — another rep of {kg:g} kg":
        "Relaje — otra repetición de {kg:g} kg",
    "Relax — change to {kg:g} kg": "Relaje — cambie a {kg:g} kg",
    "F-V: MVC reference {ref:.2f} mV.":
        "F-V: referencia CVM {ref:.2f} mV.",
    "Force-velocity: contraction with {kg:g} kg.":
        "Fuerza-velocidad: contracción con {kg:g} kg.",
    "Loads recorded": "Cargas grabadas",
    "{n} loads marked.\nStop recording, then open the "
    "Force-velocity study.":
        "{n} cargas marcadas.\nDetener la grabación y abrir el estudio "
        "fuerza-velocidad.",
    "Force-velocity: {n} loads recorded. Stop recording, then open "
    "the Force-velocity study in the Analysis tab.":
        "Fuerza-velocidad: {n} cargas grabadas. Detenga la grabación y abra el "
        "estudio fuerza-velocidad en la pestaña Análisis.",
    "Force-velocity acquisition finished: {n} loads.":
        "Adquisición fuerza-velocidad terminada: {n} cargas.",
    # Movement-vs-EMG analysis panel (accelerometer on the moving segment).
    "Movement (limb kinematics)": "Movimiento (cinemática del segmento)",
    "Movement (a.u.)": "Movimiento (u.a.)",
    "12. Movement vs EMG (limb kinematics)":
        "12. Movimiento vs EMG (cinemática del segmento)",
    "Movement from the accelerometer on the moving segment — follows "
    "«{ch}» (arbitrary units).":
        "Movimiento del acelerómetro en el segmento móvil — sigue a «{ch}» "
        "(unidades arbitrarias).",
    "Serve a read-only live view over the local network so students "
    "can follow on their phone/tablet browser (no install). One "
    "device drives the BITalino; the others just watch.":
        "Sirve una vista en vivo de solo lectura por la red local para que los "
        "alumnos sigan la sesión desde el navegador de su móvil/tablet (sin "
        "instalar nada). Un dispositivo maneja el BITalino; los demás solo miran.",
    "Students open:  {url}": "Los alumnos abren:  {url}",
    "Students open:  {url}   ·   {n} following":
        "Los alumnos abren:  {url}   ·   {n} siguiendo",
    "Classroom mode on — students can follow at {url}":
        "Modo seguimiento en móviles activado — los alumnos pueden seguir en {url}",
    "Could not start classroom mode (port busy?).":
        "No se pudo iniciar el modo seguimiento en móviles (¿puerto ocupado?).",
    "Classroom mode off — previous follower links are now invalid.":
        "Modo seguimiento en móviles desactivado — los enlaces anteriores ya no son válidos.",
    "Copy link": "Copiar enlace",
    "Copied ✓": "Copiado ✓",
    "Copy the follower link to the clipboard, e.g. to email it to "
    "the students. The link only works for this session: stopping "
    "the broadcast invalidates it.":
        "Copia el enlace para los alumnos al portapapeles, p. ej. para "
        "enviarlo por correo. El enlace solo vale para esta sesión: al "
        "desactivar la difusión queda invalidado.",
    "Follower link copied to the clipboard.":
        "Enlace para los alumnos copiado al portapapeles.",
    "QR": "QR",
    "Show a QR code students can scan to open the follower page.":
        "Muestra un código QR que los alumnos escanean para abrir la página de seguimiento.",
    "QR code unavailable (the 'segno' library is missing).":
        "Código QR no disponible (falta la librería 'segno').",
    "Scan to follow the session": "Escanea para seguir la sesión",
    "Point the phone camera at the code (same Wi-Fi network).":
        "Apunta la cámara del móvil al código (misma red Wi-Fi).",
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
    "Zoom in (vertical) — accelerometer":
        "Ampliar (vertical) — acelerómetro",
    "Zoom out (vertical) — accelerometer":
        "Reducir (vertical) — acelerómetro",
    # Vertical-zoom sidebar button letters (raw/filtered/envelope initials).
    # "F" and "E" are identical in both languages and fall through to the key.
    "R": "B",
    "Raw EMG signal (mV)": "Señal EMG en bruto (mV)",
    "Envelope (5 Hz low-pass filter, causal with continuous state)":
        "Envolvente (filtro paso-bajo 5 Hz, causal con estado continuo)",
    "Select destination folder": "Seleccionar carpeta de destino",
    "Save EDF recording as…": "Guardar grabación EDF como…",
    "BITalino MAC address (recommended — stable on every PC), or an "
    "explicit COM port (e.g. COM5), or leave empty to autodetect. Pair "
    "the BITalino in Windows Bluetooth settings first. No PyBluez is used.":
        "Dirección MAC del BITalino (recomendado — estable en cualquier PC), o un "
        "puerto COM concreto (p. ej. COM5), o dejarlo vacío para autodetectar. Hay que emparejar "
        "antes el BITalino en la configuración Bluetooth de Windows. No se usa PyBluez.",
    "Select a COM port for the Arduino before connecting.":
        "Seleccionar un puerto COM para el Arduino antes de conectar.",
    "Device configured: {desc}. Press 'Start recording'.":
        "Dispositivo configurado: {desc}. Ya se puede pulsar «Iniciar grabación».",
    "Device disconnected.": "Dispositivo desconectado.",
    "Press M to quickly add a marker with the selected label.":
        "Pulsar M para marcar rápidamente con la etiqueta seleccionada.",
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
    "Calibrate the MVC to start monitoring.":
        "Calibra el CVM para empezar a monitorizar.",
    "MVC calibrated. Monitoring load.": "CVM calibrado. Monitorizando carga.",
    "MVC calibrated for live load monitoring.":
        "CVM calibrado para el monitor de carga en vivo.",
    "Calibration failed (no signal).": "Calibración fallida (sin señal).",
    # -- guided MVC-calibration wizard --
    "Guided MVC calibration: contract each muscle in turn at maximum "
    "when prompted; sets the reference for the live load monitor.":
        "Calibración CVM guiada: contraiga cada músculo por turnos al máximo "
        "cuando se le indique; fija la referencia del monitor de carga en vivo.",
    "Best of 3": "Mejor de 3",
    "Repeat each muscle 3 times and keep the strongest contraction "
    "(more reliable). Otherwise a single contraction per muscle.":
        "Repita cada músculo 3 veces y conserve la contracción más fuerte "
        "(más fiable). Si no, una sola contracción por músculo.",
    "Muscle {n}": "Músculo {n}",
    " (rep {i}/{n})": " (rep {i}/{n})",
    "Get ready — {label}{rep}: {n}": "Prepárese — {label}{rep}: {n}",
    "Get ready — {label}{rep}": "Prepárese — {label}{rep}",
    "Contract {label} at maximum!{rep}": "¡Contraiga {label} al máximo!{rep}",
    "Next muscle: {label}": "Siguiente músculo: {label}",
    "Get ready for the next repetition": "Prepárese para la siguiente repetición",
    "MVC ready": "CVM listo",
    "{summary}\nYou can start recording.": "{summary}\nYa se puede empezar a grabar.",
    "Calibration failed": "Calibración fallida",
    "No signal — check the electrodes.": "Sin señal — conviene revisar los electrodos.",
    "Contract {label} as hard as you can!  ({s:.0f} s)  "
    "peak {pk:.2f} mV":
        "¡Contraiga {label} todo lo que pueda!  ({s:.0f} s)  pico {pk:.2f} mV",
    "Relax…": "Relaje…",
    "Relax": "Relaje",
    "Effort {pct:.0f} %": "Esfuerzo {pct:.0f} %",
    "Contract as hard as you can until the count reaches 0":
        "Contraiga al máximo hasta que la cuenta llegue a 0",
    "MVC ready — {summary}. You can start recording.":
        "CVM listo — {summary}. Ya se puede empezar a grabar.",
    "MVC calibrated: {summary}": "CVM calibrado: {summary}",
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
        "Borra todo y vuelve al estado inicial (p. ej. un nuevo alumno)",
    "Stop the recording before starting a new session.":
        "Detenga la grabación antes de iniciar una nueva sesión.",
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
    "No fatigue (MDF increases or stays stable).":
        "Sin fatiga (la MDF aumenta o se mantiene estable).",
    "Analysis parameters": "Parámetros de análisis",
    "EDF file:": "Archivo EDF:",
    "Select an EDF file…": "Seleccionar un archivo EDF…",
    "Browse…": "Explorar…",
    "Analyse": "Analizar",
    "Save figure (PNG)": "Guardar figura (PNG)",
    "Generate PDF report": "Generar informe PDF",
    "EMG channel:": "Canal EMG:",
    "Channel «{ch}»: flat — no signal (electrode not connected?).":
        "Canal «{ch}»: plano — sin señal (¿electrodo sin conectar?).",
    "Channel «{ch}»: saturated — the trace is pinned at the rails "
    "(check the electrode contact or the gain).":
        "Canal «{ch}»: saturado — la traza está pegada al tope "
        "(conviene revisar el contacto del electrodo o la ganancia).",
    "Channel «{ch}»: weak signal (low amplitude).":
        "Canal «{ch}»: señal débil (amplitud baja).",
    "EMG channel to analyse. Every panel and the report use only "
    "this channel. Filled with the file's channels (EMG1/EMG2) when "
    "you select it.":
        "Canal EMG a analizar. Todos los paneles y el informe usan solo este "
        "canal. Se rellena con los canales del archivo (EMG1/EMG2) al "
        "seleccionarlo.",
    "Compare channels:": "Comparar canales:",
    "Overlay the envelope of the two channels (agonist/antagonist). "
    "The partner channel is set automatically to the other one. "
    "Only available for two-channel recordings.":
        "Superpone la envolvente de los dos canales (agonista/antagonista). "
        "El canal pareja se fija automáticamente al otro. Solo disponible en "
        "registros de dos canales.",
    "Partner channel (chosen automatically).":
        "Canal pareja (elegido automáticamente).",
    "EMG channel to normalise (EMG1/EMG2 for two-channel files; "
    "disabled when there is only one). The whole normalisation uses "
    "this channel — press \"Compute MVC\" after changing it.":
        "Canal EMG a normalizar (EMG1/EMG2 en archivos de dos canales; "
        "desactivado si solo hay uno). Toda la normalización usa este canal; "
        "pulsar «Calcular CVM» tras cambiarlo.",
    "9. Overlaid envelopes (agonist/antagonist)":
        "9. Envolventes superpuestas (agonista/antagonista)",
    "9. Env. overlay": "9. Env. superp.",
    "Both channels' envelopes overlaid — agonist/antagonist "
    "coordination (needs a 2nd channel).":
        "Envolventes de ambos canales superpuestas — coordinación "
        "agonista/antagonista (requiere un 2º canal).",
    "Enable “Compare 2nd channel” to overlay the antagonist.":
        "Active «Comparar 2º canal» para superponer el antagonista.",
    "2nd channel «{name}» overlaid.": "2º canal «{name}» superpuesto.",
    "Could not analyse the 2nd channel «{name}»: {err}":
        "No se pudo analizar el 2º canal «{name}»: {err}",
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
    "Integral of the rectified EMG — total muscle activation.":
        "Integral de la EMG rectificada — activación muscular total.",
    # --- didactic tooltips (panels, summary metrics, APDF) ---
    "Raw EMG signal, unfiltered.": "Señal EMG cruda, sin filtrar.",
    "Envelope normalised to its maximum (0-1): the activation time course.":
        "Envolvente normalizada a su máximo (0-1): el curso temporal de la activación.",
    "Power spectrum; MNF and MDF summarise its frequency content.":
        "Espectro de potencia; MNF y MDF resumen su contenido en frecuencia.",
    "Band-pass filtered (20-450 Hz) and rectified signal.":
        "Señal filtrada paso-banda (20-450 Hz) y rectificada.",
    "Linear envelope vs the RMS envelope of the signal.":
        "Envolvente lineal frente a la envolvente RMS de la señal.",
    "RMS amplitude per window: how the intensity evolves.":
        "Amplitud RMS por ventana: cómo evoluciona la intensidad.",
    "Median frequency over time; a fall indicates fatigue.":
        "Frecuencia mediana en el tiempo; su descenso indica fatiga.",
    "Amplitude-frequency relation (force vs fatigue).":
        "Relación amplitud-frecuencia (fuerza frente a fatiga).",
    "Mean spectral frequency; tends to fall with fatigue.":
        "Frecuencia media del espectro; tiende a bajar con la fatiga.",
    "Frequency that splits the spectrum into two equal-power halves; "
    "falls with fatigue.":
        "Frecuencia que divide el espectro en dos mitades de igual potencia; "
        "baja con la fatiga.",
    "Fatigue indicator from the MDF trend over time.":
        "Indicador de fatiga a partir de la tendencia de la MDF en el tiempo.",
    "Slope of MDF over time (Hz/s); negative = fatigue.":
        "Pendiente de la MDF en el tiempo (Hz/s); negativa = fatiga.",
    "Global RMS amplitude: mean intensity of the activation.":
        "Amplitud RMS global: intensidad media de la activación.",
    "Analysed signal duration.": "Duración de la señal analizada.",
    "Analysed EDF file.": "Archivo EDF analizado.",
    "Out of normal range": "Fuera del rango normal",
    "<p>Amplitude Probability Distribution Function (Jonsson): "
    "the % of time the muscle stays below each load level (% MVC). "
    "The static (P10), median (P50) and peak (P90) levels gauge "
    "overload risk.</p>":
        "<p>Función de distribución de probabilidad de amplitud (Jonsson): "
        "el % del tiempo que el músculo permanece por debajo de cada nivel "
        "de carga (% CVM). Los niveles estático (P10), mediano (P50) y pico "
        "(P90) valoran el riesgo de sobrecarga.</p>",
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
    "Tick the graphs to add to the report:": "Marcar los gráficos que se añadirán al informe:",
    "Time range to plot (s):": "Tramo temporal a dibujar (s):",
    "PDF report generated: {path}": "Informe PDF generado: {path}",
    "Error generating the PDF report: {error}": "Error al generar el informe PDF: {error}",
    "Amplitude (mV)": "Amplitud (mV)",
    "Time (s)": "Tiempo (s)",
    # Progress bar + fatigue summary (analysis tab).
    "Ready": "Listo",
    "Analysing…  %p%": "Analizando…  %p%",
    "Fatigue: not conclusive (trend does not fit, R²={r2:.2f})":
        "Fatiga: no concluyente (la tendencia no ajusta, R²={r2:.2f})",
    "Fatigue: Not detected (MDF stable or increasing)":
        "Fatiga: No detectada (MDF estable o crece)",

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
    "calibration recorded in this file": "calibración grabada en este mismo fichero",
    # -- procedencia de la referencia de CVM (phases.py) --
    "calibration in this recording": "calibración de este registro",
    "calibration in this recording ({n} repetition(s))":
        "calibración de este registro ({n} repetición/ones)",
    "calibration as recorded (repetitions not stored)":
        "calibración tal como se grabó (no se guardaron las repeticiones)",
    "no calibration": "sin calibración",
    "MVC:": "CVM:",
    "The maximal contraction every % MVC on this recording is measured against, and where it came from.":
        "La contracción máxima contra la que se mide cada % de CVM de este registro, y de dónde sale.",
    "MVC reference read from the file's own calibration: {value:.4f} {units}.":
        "Referencia de CVM leída de la calibración del propio fichero: {value:.4f} {units}.",
    "This recording carries its own MVC calibration ({n} channel(s)) — no reference file needed.":
        "Este registro lleva su propia calibración de CVM ({n} canal(es)): no hace falta fichero de referencia.",
    "Not needed — this recording carries its own calibration…":
        "No hace falta: este registro lleva su propia calibración…",
    "Muscle load computed over {n} selected fragment(s) ({d:.2f} s of {full:.2f} s).":
        "Carga muscular calculada sobre {n} fragmento(s) seleccionado(s) ({d:.2f} s de {full:.2f} s).",
    "Choose which parts of the recording the muscle load is measured over — leave out the calibration and any pause. The MVC reference is not affected: it comes from the calibration, wherever in the file that is.":
        "Elija sobre qué partes del registro se mide la carga muscular: deje fuera la calibración y las pausas. La referencia de CVM no se ve afectada, sale de la calibración esté donde esté en el fichero.",
    "MVC reference amplitude: {value:.4f} {units} ({source})":
        "Amplitud CVM de referencia: {value:.4f} {units} ({source})",
    "Mean normalised activation: {value:.1f} % MVC":
        "Activación media normalizada: {value:.1f} % CVM",
    "MVC normalisation parameters": "Parámetros de normalización CVM",
    "Test EDF:": "EDF de prueba:",
    "Select the EDF file to normalise…": "Seleccionar el archivo EDF a normalizar…",
    "MVC reference EDF (optional):": "EDF de referencia CVM (opcional):",
    "Leave empty for auto-normalisation…": "Dejar vacío para auto-normalización…",
    "Remove": "Quitar",
    "EMG channel of the EDF to normalise. Filled with the channels "
    "of the test file when you select it.":
        "Canal EMG del EDF a normalizar. Se rellena con los canales "
        "del archivo de prueba al seleccionarlo.",
    "Compute MVC": "Calcular CVM",
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
    "Static": "Estático",
    "Median": "Mediano",
    "Peak": "Pico",
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
        "del ADC durante tramos ≥ 10 ms. Conviene revisar el contacto del electrodo y la ganancia.",
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
        "Ya hay una conexión BITalino activa. Ciérrela antes de abrir otra.",
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
        "emparejados. Hay que emparejar el dispositivo en la configuración Bluetooth "
        "del sistema y encenderlo.",
    "No BITalino was found on the Bluetooth COM ports. Pair the "
    "BITalino in the operating system's Bluetooth settings and switch "
    "it on, or enter its MAC address or COM port explicitly.":
        "No se encontró ningún BITalino en los puertos COM Bluetooth. Hay que emparejar "
        "el BITalino en la configuración Bluetooth del sistema y encenderlo, o "
        "introducir su dirección MAC o su puerto COM explícitamente.",
    "The device on {port} did not identify itself as a "
    "BITalino. Check that the BITalino is paired and "
    "switched on.":
        "El dispositivo en {port} no se identificó como un BITalino. "
        "Conviene comprobar que el BITalino está emparejado y encendido.",
    "Unsupported BITalino sampling rate {fs} Hz. "
    "Use one of 1, 10, 100 or 1000.":
        "Frecuencia de muestreo {fs} Hz no soportada por el BITalino. "
        "Usar 1, 10, 100 o 1000.",
    "Invalid BITalino channel list; channels must be in 0..5.":
        "Lista de canales del BITalino no válida; deben estar en 0..5.",
    "Timeout while reading from the BITalino — connection lost.":
        "Tiempo de espera agotado al leer del BITalino — conexión perdida.",
    "Corrupted BITalino frame (CRC mismatch) — connection lost.":
        "Trama del BITalino corrupta (error de CRC) — conexión perdida.",

    # --- PDF report ---
    "Not conclusive — the trend does not fit ({slope:+.2f} Hz/s, R²={r2:.2f}). Fatigue needs a contraction held long enough for the trend to show.":
        "No concluyente: la tendencia no ajusta ({slope:+.2f} Hz/s, R²={r2:.2f}). La fatiga necesita una contracción mantenida el tiempo suficiente para que la tendencia se vea.",
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
    "Flat signal — check electrode contact": "Señal plana — conviene revisar el contacto del electrodo",
    "Saturation: {pct:.0f}% at rails — lower gain":
        "Saturación: {pct:.0f}% en los extremos — baja la ganancia",
    # -- CSV export (exports.py) --
    "not conclusive (the MDF trend does not fit)": "no concluyente (la tendencia de MDF no ajusta)",
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
    "MDF trend fitted over {n} of {total} segments (the rest were below the contraction threshold).":
        "Tendencia de MDF ajustada sobre {n} de {total} segmentos (el resto quedaba por debajo del umbral de contracción).",
    "MDF trend not conclusive: slope {slope:+.3f} Hz/s but R²={r2:.2f} over {n} segment(s). Fatigue needs a contraction held long enough for the trend to show.":
        "Tendencia de MDF no concluyente: pendiente {slope:+.3f} Hz/s pero R²={r2:.2f} sobre {n} segmento(s). La fatiga necesita una contracción mantenida el tiempo suficiente para que la tendencia se vea.",
    "No fatigue: MDF slope {slope:+.3f} Hz/s (R²={r2:.2f}).":
        "Sin fatiga: pendiente MDF {slope:+.3f} Hz/s (R²={r2:.2f}).",
    # -- acquisition tab (protocol / markers) --
    "Name": "Nombre",
    "e.g. Isometric contraction 30 s": "p. ej. Contracción isométrica 30 s",
    "Live signal quality: saturation or a flat (disconnected) signal.":
        "Calidad de señal en vivo: saturación o señal plana (desconectada).",
    "Markers recorded so far. Select one and press Delete to remove it.":
        "Marcadores registrados hasta ahora. Seleccionar uno y pulsar Supr para eliminarlo.",
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
        "La app sugiere los fragmentos informativos (periodos activos). Se pueden "
        "ajustar, añadir o quitar; solo se analizan los fragmentos marcados. La "
        "selección final la decide el alumno.",
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
    # Segment "reason" codes shown in the fragment table.
    "activity": "actividad",
    "manual": "manual",
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

    # ── Recording modes and fine controls ──────────────────────────────
    "Single-muscle contraction": "Contracción de un músculo",
    "Agonist / antagonist contraction": "Contracción agonista / antagonista",
    "Muscle kinematics": "Cinemática muscular",
    "Which practical the app is set up for":
        "Práctica para la que está configurada la aplicación",
    "Advanced options": "Opciones avanzadas",
    "Show the fine controls shared by every mode":
        "Muestra los controles finos comunes a todos los modos",
    "One-off setup": "Solo la primera vez",
    "How many EMG sensors are being recorded.":
        "Cuántos sensores de EMG se están registrando.",
    "Accelerometer:": "Acelerómetro:",
    "Compared with:": "Comparado con:",

    # ── Recording that does not match the mode ─────────────────────────
    "The recording does not match the mode": "El registro no concuerda con el modo",
    "This recording has {n} EMG channel(s), and the agonist / antagonist "
    "mode needs two.":
        "Este registro tiene {n} canal(es) de EMG, y el modo agonista / "
        "antagonista necesita dos.",
    "Choose \"Single-muscle contraction\" or \"Muscle kinematics\" at the top "
    "of the window, or open a recording made with two channels.":
        "Elija «Contracción de un músculo» o «Cinemática muscular» en la parte "
        "superior de la ventana, o abra un registro hecho con dos canales.",

    # ── MVC entry screen ───────────────────────────────────────────────
    "Normalising to maximum voluntary contraction (MVC)":
        "Normalización a la contracción voluntaria máxima (CVM)",
    "A raw EMG amplitude cannot be compared between two people, or between "
    "two sessions of the same person: it depends on the electrodes, the skin "
    "and the fat layer beneath it. Normalisation solves this by expressing "
    "every value as a percentage of the amplitude that muscle reaches during "
    "a maximal effort.":
        "La amplitud bruta de una señal EMG no se puede comparar entre dos "
        "personas, ni entre dos sesiones de la misma persona: depende de los "
        "electrodos, de la piel y de la grasa que hay debajo. La normalización "
        "resuelve esto expresando cada valor como porcentaje de la amplitud "
        "que ese músculo alcanza en un esfuerzo máximo.",
    "To do that you need two recordings: the one you want to study, and a "
    "short reference recording in which the subject contracts the muscle as "
    "hard as possible. Record the reference first, with the electrodes in the "
    "same position, and do not remove them in between.":
        "Para ello hacen falta dos registros: el que se quiere estudiar y un "
        "registro corto de referencia en el que el sujeto contrae el músculo "
        "con toda la fuerza que pueda. Se registra primero la referencia, con los "
        "electrodos en la misma posición, y no los retire entre uno y otro.",
    "Without a reference recording this tab can still work, but the "
    "percentages it produces are not percentages of MVC and the muscle-load "
    "limits do not apply to them.":
        "Sin registro de referencia esta pestaña funciona igualmente, pero los "
        "porcentajes que produce no son porcentajes de CVM y los límites de "
        "carga muscular no se les pueden aplicar.",
    "I understand, continue": "Entendido, continuar",

    # ── MVC reference picker ───────────────────────────────────────────
    "MVC reference EDF:": "EDF de referencia CVM:",
    "Required at this interface level — select a reference recording…":
        "Obligatorio en este nivel de interfaz: seleccionar un registro de "
        "referencia…",

    # ── Auto-normalisation confirmation ────────────────────────────────
    "No MVC reference recording selected":
        "No se ha seleccionado registro de referencia CVM",
    "The signal will be normalised to the 95th percentile of itself. The "
    "values will be shown as \"% MVC\", but they are not percentages of "
    "maximum voluntary contraction, and the Jonsson muscle-load limits (P10, "
    "P50, P90) do not apply: a sustained contraction will exceed them by "
    "construction.":
        "La señal se normalizará al percentil 95 de sí misma. Los valores "
        "aparecerán como «% CVM», pero no son porcentajes de contracción "
        "voluntaria máxima, y los límites de carga muscular de Jonsson (P10, "
        "P50, P90) no se les pueden aplicar: una contracción mantenida los "
        "supera por construcción.",
    "Use this only to see the shape of the signal.":
        "Usar esta opción solo para ver la forma de la señal.",
    "Choose a reference recording": "Elegir registro de referencia",
    "Continue without reference": "Continuar sin referencia",

    # ── Auto-normalisation marking (screen and report) ─────────────────
    "auto (not a real %MVC)": "automática (no es %CVM real)",
    "Muscle-load analysis requires an MVC reference recording. Select one to "
    "interpret these values as muscle load limits.":
        "El análisis de carga muscular requiere un registro de referencia CVM. "
        "Hay que seleccionar uno para interpretar estos valores como límites de carga "
        "muscular.",
    " (auto-normalised, not %MVC)": " (auto-normalizada, no es %CVM)",

    # ── Guided tour: chrome ────────────────────────────────────────────
    "Guide": "Guía",
    "Walk through the app and what it measures":
        "Recorrido por la aplicación y por lo que mide",
    "Skip": "Saltar",
    "Back": "Atrás",
    "Next": "Siguiente",
    "Finish": "Terminar",
    "Step {i} of {n}": "Paso {i} de {n}",
    "Stop the recording before starting the guide.":
        "Hay que detener el registro antes de iniciar la guía.",

    # ── Guided tour: teaching content (texto del autor; el resto, borrador) ─
    # -- la sesión en dos fases (phases.py / acquisition.py) --
    'Starting the session — the calibration begins as soon as the signal arrives.':
        'Empieza la sesión: la calibración arranca en cuanto llegue la señal.',
    'This practical calibrates first: waiting for the signal to start the session.':
        'Esta práctica calibra primero: esperando la señal para empezar la sesión.',
    'The calibration needs a recording in progress.':
        'La calibración necesita una grabación en marcha.',
    'Another guided procedure is already running.':
        'Ya hay otro procedimiento guiado en marcha.',
    "Calibration started as the session's opening phase.":
        'Calibración iniciada como fase de apertura de la sesión.',
    'Calibration started on its own.': 'Calibración iniciada por su cuenta.',
    'The session could not start the calibration on its own. Press «Calibrate MVC» when you are ready — the phases will be written just the same.':
        'La sesión no ha podido arrancar la calibración por su cuenta. Pulse «Calibrar CVM» cuando esté listo: las fases se escriben igual.',
    'Session flow: practical={mode}, {n} channel(s), references={refs} → calibrate first: {yes}.':
        'Flujo de sesión: práctica={mode}, {n} canal(es), referencias={refs} → calibrar primero: {yes}.',
    'No recording': 'Sin registro',
    'Reference needed': 'Falta la referencia',
    'Get ready to record': 'Prepárese para grabar',
    'Warm up first': 'Caliente primero',
    'Warming up: {n}': 'Calentando: {n}',
    'Two or three easy contractions of each muscle. The first maximal effort of a session is never the strongest one.':
        'Dos o tres contracciones suaves de cada músculo. La primera máxima de una sesión nunca es la más fuerte.',
    'The recording ended before the preparation phase could start, so this file has no recording phase marked.':
        'El registro terminó antes de que pudiera empezar la fase de preparación, así que este fichero no lleva marcada la fase de registro.',
    'Get ready to record: {n}': 'Prepárese para grabar: {n}',
    'The recording starts when the count reaches 0. The calibration is already saved.':
        'El registro empieza cuando la cuenta llegue a 0. La calibración ya está guardada.',
    'Recording — the calibration is behind you.':
        'Grabando: la calibración ya queda atrás.',
    'Recording phase started. Everything before this point — the calibration and this pause — stays out of the analysis.':
        'Empieza la fase de registro. Todo lo anterior —la calibración y esta pausa— queda fuera del análisis.',
    'Push as hard as you can when the count reaches 0 — against something that cannot move, such as the underside of the table, not against a hand':
        'Empuje todo lo que pueda cuando la cuenta llegue a 0, contra algo que no se pueda mover —el canto inferior de la mesa, por ejemplo—, no contra una mano',
    "The reference has to be made against something that cannot move — the underside of a table, a fixed bar — with the joint held still. Not a hand, and least of all the subject's own other hand: a hand yields, and holding oneself splits the effort between two limbs, which produces less force than either would alone. This is the force-velocity relationship at work: whatever the muscle is allowed to shorten against, it shortens faster and therefore develops less force, so it recruits fewer motor units. A maximum performed in mid-air is submaximal by construction, and every percentage that follows comes out too high in the same proportion.":
        'La referencia hay que hacerla contra algo que no se pueda mover —el canto inferior de una mesa, una barra fija— y con la articulación quieta. No contra una mano, y menos aún contra la otra mano del propio sujeto: una mano cede, y sujetarse uno mismo reparte el esfuerzo entre dos miembros, que juntos dan menos fuerza que cualquiera de los dos por separado. Es la relación fuerza-velocidad en acción: contra lo que el músculo pueda acortarse, se acorta más deprisa y por tanto desarrolla menos fuerza, así que recluta menos unidades motoras. Una máxima hecha en el aire es submáxima por construcción, y todos los porcentajes posteriores salen altos en la misma proporción.',
    'Calibration too weak': 'Calibración demasiado floja',
    '{muscles}: this is not a maximum. Calibrate again against a resistance the joint cannot move.': '{muscles}: esto no es una máxima. Calibre de nuevo contra una resistencia que la articulación no pueda mover.',
    "% of this recording's own maximum": '% del máximo del propio registro',
    'Distribution of effort over time': 'Reparto del esfuerzo en el tiempo',
    '⚠ «{name}»: the recording starts with the muscle already active, so no resting baseline could be measured and contraction onsets were not detected. Record a couple of quiet seconds before the first contraction.': '⚠ «{name}»: el registro empieza con el músculo ya activo, así que no se pudo medir una línea base de reposo y no se han detectado inicios de contracción. Grabe un par de segundos en reposo antes de la primera contracción.',
    '⚠ «{muscle}»: the calibration reached {ref:.3f} mV, only {ratio:.1f}× its resting level. That is not a maximal contraction — every % MVC from now on will be too high by that factor. Calibrate again.': '⚠ «{muscle}»: la calibración llegó a {ref:.3f} mV, solo {ratio:.1f}× su nivel de reposo. Eso no es una contracción máxima: a partir de ahora todos los % de CVM saldrán altos por ese mismo factor. Calibre de nuevo.',
    '⚠ «{name}» is above {limit:.0f} % MVC for {share:.0f} % of the recording, peaking at {peak:.0f} %. The calibration did not capture a maximum, so every percentage here is too high.': '⚠ «{name}» está por encima del {limit:.0f} % de CVM durante el {share:.0f} % del registro, con un pico del {peak:.0f} %. La calibración no captó una máxima, así que todos los porcentajes de aquí salen altos.',
    'These values are not real % MVC: the calibration did not capture a maximum. Calibrate again with a genuinely maximal contraction.': 'Estos valores no son % de CVM reales: la calibración no captó una máxima. Calibre de nuevo con una contracción verdaderamente máxima.',
    'No contraction detected in «{name}»: it never left its baseline.': 'No se detecta contracción en «{name}»: no sale de su línea base.',
    'Channel separation — while «{muscle}» was at maximum, «{other}» reached {pct:.0f} % of its own reference.': 'Separación entre canales: mientras «{muscle}» estaba al máximo, «{other}» llegó al {pct:.0f} % de su propia referencia.',
    '{other} at {pct:.0f} % during {muscle}': '{other} al {pct:.0f} % durante {muscle}',
    'Channels not separated': 'Canales sin separar',
    '{pairs}. Move the electrode pairs further apart, over the belly of each muscle, and support the forearm.': '{pairs}. Separe más los dos pares de electrodos, cada uno sobre el vientre de su músculo, y apoye el antebrazo.',
    'Co-activation (Falconer-Winter)': 'Coactivación (Falconer-Winter)',
    'Co-activation index': 'Índice de coactivación',
    'Mean activation (% MVC)': 'Activación media (% CVM)',
    'not reported — {name} below {floor:.0f} % MVC': 'no se informa — {name} por debajo del {floor:.0f} % de CVM',
    'not reported — no MVC reference for both channels': 'no se informa — falta referencia de CVM en algún canal',
    'not reported — window too short': 'no se informa — ventana demasiado corta',
    'not reported — no activation above rest': 'no se informa — sin activación por encima del reposo',
    'Whole recording — mark the phases for a meaningful value': 'Registro completo — marque las fases para obtener un valor con sentido',
    'Window': 'Ventana',
    "Calibrate the MVC of both muscles while recording and the two envelopes are overlaid in % MVC — the only form in which two different muscles compare at all, since each one's millivolts depend on its own electrodes and on the skin and fat beneath them. Without that reference the panel stays in millivolts and says so. In a clean movement the agonist activates while the antagonist stays nearly silent; simultaneous activation is co-contraction, which holds the joint rigid and is typical of an unpractised or uncertain movement.": 'Calibre la CVM de los dos músculos mientras graba y las dos envolventes se superponen en % CVM, que es la única forma en que dos músculos distintos se comparan: los milivoltios de cada uno dependen de sus electrodos y de la piel y la grasa que hay debajo. Sin esa referencia el panel se queda en milivoltios y lo advierte. En un movimiento limpio el agonista se activa mientras el antagonista permanece casi silente; la activación simultánea es co-contracción, que mantiene rígida la articulación y es típica de un movimiento poco entrenado o inseguro.',
    '9. Overlaid envelopes (agonist/antagonist), % MVC': '9. Envolventes superpuestas (agonista/antagonista), % CVM',
    '9. Env. overlay (% MVC)': '9. Env. superp. (% CVM)',
    'Millivolts are not comparable between two muscles. Calibrate MVC while recording to compare them.': 'Los milivoltios no son comparables entre dos músculos. Calibre la CVM mientras graba para poder compararlos.',
    'Complexity level': 'Nivel de complejidad',
    'The coloured band shows the subjective level of complexity of the analysis: basic, intermediate or advanced. There is also a free analysis that gives control over the fine settings.': 'La banda coloreada indica el nivel subjetivo de complejidad del análisis: básico, intermedio o avanzado. Hay un análisis libre que permite controlar los ajustes finos.',
    'Connecting the sensor': 'Conexión del sensor',
    'The board has to be switched on and the electrodes connected: the positive and the negative go on the midline of the muscle, while the reference goes on a neutral point, over a bone if possible.': 'La placa tiene que estar encendida y los electrodos conectados: el positivo y el negativo se sitúan sobre la línea media del músculo, mientras que el de referencia se coloca en un punto neutro, a ser posible sobre un hueso.',
    'How to place the accelerometer': 'Cómo situar el acelerómetro',
    'There are two possibilities: on the muscle it allows the mechanomyogram (MMG) to be measured, which runs in parallel with the electrical signal; on the moving segment of the joint it allows the movement, and the parameters associated with it, to be measured.': 'Hay dos posibilidades: sobre el músculo permite la medida del mecanomiograma (MMG), que irá en paralelo con la señal eléctrica; sobre el segmento móvil de la articulación permite medir el movimiento y los parámetros asociados a éste.',
    'Following the recording remotely': 'Seguimiento del registro de forma remota',
    'Every member of the group making the recording can watch the trace on their own mobile device. This is done by scanning the QR code the application generates.': 'Cada miembro del grupo que está realizando el registro puede ver el trazado en su dispositivo móvil. Este procedimiento se lleva a cabo capturando el código QR que genera la aplicación.',
    'Wizard for the force-velocity experiment': 'Asistente para el experimento de fuerza-velocidad',
    'The step-by-step wizard guides you through the contractions with different loads. With a greater load the velocity is expected to be lower, and this defines an inverse relation which is the force-velocity curve. The product of the two gives the power, which is maximal at intermediate loads.': 'El asistente paso a paso va guiando por las contracciones con diferentes cargas. Con mayor carga se espera que la velocidad sea menor y define una relación inversa que es la curva fuerza-velocidad. El producto de ambas proporciona la potencia, que es máxima con cargas intermedias.',
    'Rehearsal of the force-velocity experiment': 'Ensayo del experimento fuerza-velocidad',
    'As this is the longest and most complex procedure in the application, a simulation is provided as a rehearsal, so that what is going to be done live is better understood. It can be followed step by step or watched as an animation, and it can also be replayed to see it better.': 'Dado que es el procedimiento más largo y complejo de la aplicación se proporciona una simulación a modo de ensayo para comprender mejor lo que se va a hacer en vivo. Se puede ir paso a paso o ver como una animación y también se puede repetir para verlo mejor.',
    'Calibrating the contraction': 'Calibración de la contracción',
    'A maximal voluntary contraction is asked for, and it becomes the reference against which the live load bars and the measurements are expressed, making contractions easier to compare.': 'Se solicita una contracción voluntaria máxima que será la referencia respecto a la que se representan las barras de carga en vivo y las medidas, facilitando la comparación entre contracciones.',
    'The basic panels': 'Paneles básicos',
    'Raw signal: the signal from the set of fibres that are contracting. Normalised envelope: shows how activation changes over time, which is what is compared between efforts. Power spectrum: how the muscle activity is distributed across the different frequencies recorded.': 'Señal en bruto: señal del conjunto de las fibras que se están contrayendo. Envolvente normalizada: muestra cómo cambia la activación en el tiempo, que es lo que se compara entre esfuerzos. Espectro de potencia: cómo se reparte la actividad muscular entre las diferentes frecuencias registradas.',
    "Choose the practical first": "Elegir primero la práctica",
    "Everything else follows from this. Each mode records what that practical "
    "needs — one muscle, an agonist/antagonist pair, or a muscle plus the "
    "accelerometer — and the rest of the interface offers only the "
    "measurements that make sense for it.":
        "Todo lo demás se deriva de esto. Cada modo registra lo que esa "
        "práctica necesita —un músculo, una pareja agonista/antagonista, o un "
        "músculo más el acelerómetro— y el resto de la interfaz ofrece solo "
        "las medidas que tienen sentido para ella.",
    "Everything else is optional": "Lo demás es opcional",
    "The fine controls — filter cut-offs, fatigue thresholds, region of "
    "interest — are shared by all three modes and stay out of the way until "
    "this is ticked.":
        "Los controles finos —frecuencias de corte, umbrales de fatiga, región "
        "de interés— son comunes a los tres modos y no estorban hasta que se "
        "marca esta casilla.",
    "Offer this guide next time": "Ofrecer esta guía la próxima vez",
    "Start recording and ask for the contraction. Watch the live trace: at "
    "rest it should be a flat line with only baseline noise. A signal that "
    "never returns to baseline usually means a loose electrode or a poor "
    "contact, not a tonic muscle.":
        "Se inicia el registro y se pide la contracción. Conviene vigilar el trazado en vivo: "
        "en reposo debe ser una línea plana con solo ruido de base. Una señal "
        "que nunca vuelve a la línea de base suele indicar un electrodo suelto "
        "o mal contacto, no un músculo tónico.",
    "Mark what happens": "Marcar lo que ocurre",
    "Press MARK to timestamp an event — the start of an effort, a change of "
    "load, the moment the subject reports fatigue. The marks travel inside "
    "the EDF, so each phase can be found again during the analysis.":
        "Pulsar MARCA para poner una marca temporal en un suceso: el inicio de "
        "un esfuerzo, un cambio de carga, el momento en que el sujeto refiere "
        "fatiga. Las marcas viajan dentro del EDF y permiten reencontrar cada "
        "fase durante el análisis.",
    "Fatigue lives in the spectrum": "La fatiga está en el espectro",
    "As a sustained contraction fatigues the muscle, the conduction velocity "
    "of the fibres falls and the spectrum shifts towards low frequencies: the "
    "median frequency (MDF) drops while the amplitude often rises, because "
    "more motor units are recruited to hold the same force.":
        "A medida que una contracción mantenida fatiga al músculo, la "
        "velocidad de conducción de las fibras disminuye y el espectro se "
        "desplaza hacia frecuencias bajas: la frecuencia mediana (MDF) baja "
        "mientras la amplitud a menudo sube, porque se reclutan más unidades "
        "motoras para sostener la misma fuerza.",
    "Agonist and antagonist": "Agonista y antagonista",
    # (the "Force-velocity study" caption itself is defined with the Analysis
    # tab strings above; only the tour's explanation of it belongs here)
    "Builds the load-velocity, force-velocity and power curves from a "
    "recording where several known loads were lifted, and relates them to the "
    "EMG amplitude — that is, to how many motor units had to be recruited for "
    "each load.":
        "Construye las curvas carga-velocidad, fuerza-velocidad y potencia a "
        "partir de un registro en el que se levantaron varias cargas "
        "conocidas, y las relaciona con la amplitud EMG, es decir, con cuántas "
        "unidades motoras hubo que reclutar para cada carga.",
    "Why normalise at all": "Por qué normalizar",
    "Muscle load": "Carga muscular",

    # ── Tutorial: texto revisado por el autor (22-ago-2026) ──────────
    'Quick guide':
        'Guía rápida',
    'The electrical activity of a muscle is recorded and turned into measurements that can be interpreted. The application works with either of two sensors: a BITalino over Bluetooth or an Arduino + MyoWare 2.0 over USB.\n\nFor a short walkthrough of the application, press Yes.':
        'Se registra la actividad eléctrica de un músculo y se convierte en medidas que se pueden interpretar. Funciona con cualquiera de dos sensores: un BITalino por Bluetooth o un Arduino + MyoWare 2.0 por USB.\n\nPara un recorrido breve por la aplicación, pulsar Sí.',
    'Devices the application supports':
        'Dispositivos soportados por la aplicación',
    'The recording can be made with either of two devices: BITalino (Bluetooth) or Arduino (USB).':
        'El registro se puede hacer con uno cualquiera de dos dispositivos: BITalino (Bluetooth) o Arduino (USB).',
    'Assign the labels':
        'Asignar etiquetas',
    'This name is written into the EDF file as the channel label, so the recording keeps the muscle and the channel identified. The anatomical name is the one to use.':
        'Este nombre se escribe en el fichero EDF como etiqueta del canal, de modo que el registro mantiene la identificación del músculo y del canal. Conviene usar el nombre anatómico.',
    'Recording':
        'Registro',
    'Download the results: report and data':
        'Descargar resultados: informe y datos',
    "The report gathers the figures and the metrics into a PDF document. The CSV export saves the recording's data.":
        'El informe reúne las figuras y las métricas en un documento PDF. Exportar CSV permite guardar los datos del registro.',
    'A raw amplitude cannot be compared between two people, or between two sessions of the same person: it depends on the electrodes, the skin and the fat beneath it. Expressing every value as a percentage of the maximal contraction cancels all of that out, because the two amplitudes share the same electrodes and the same skin: what is left is how hard the muscle is working.':
        'Una amplitud bruta no se puede comparar entre dos personas, ni entre dos sesiones de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. Expresar cada valor como porcentaje de la contracción máxima cancela todo eso, porque las dos amplitudes comparten los mismos electrodos y la misma piel: lo que queda es cuánto está trabajando el músculo.',
    'Once the signal is in % MVC, the distribution of load over time can be read against the Jonsson limits: the static level (P10) is the load the muscle stays above 90 % of the time, the background tension it hardly ever lets go of, and the level most associated with sustained-effort discomfort.':
        'Una vez la señal está en % CVM, la distribución de la carga en el tiempo se puede leer frente a los límites de Jonsson: el nivel estático (P10) es la carga que el músculo supera el 90 % del tiempo, la tensión de fondo que casi nunca llega a relajar, y el nivel más asociado a las molestias por esfuerzo mantenido.',
    'Broadcast to phones (in the laboratory)':
        'Difundir a móviles (en laboratorio)',

    # Iniciales de los botones de zoom vertical y la etiqueta de error.
    # Coinciden en los dos idiomas —Envolvente, Acelerómetro, Error—, pero se
    # declaran igualmente: sin entrada propia funcionaban por casualidad, al
    # devolver tr() la clave inglesa. Su hermana «R» sí se traduce (Raw ->
    # Bruto), que es lo que delató el hueco.
    "E": "E",
    "A": "A",
    "Error:": "Error:",

    # Por qué no se puede pulsar «Calcular CVM» todavía.
    "Select the recording to normalise.":
        "Seleccionar el registro que se va a normalizar.",
    "A reference recording is required to express the signal as % MVC and to "
    "read it against the Jonsson limits. Tick \"Advanced options\" to "
    "normalise without one.":
        "Hace falta un registro de referencia para expresar la señal en % CVM "
        "y poder leerla frente a los límites de Jonsson. Marcar «Opciones "
        "avanzadas» para normalizar sin él.",

    # Selección de paneles de la pestaña CVM.
    "Panels:": "Paneles:",
    "1. Filtered and rectified": "1. Filtrada y rectificada",
    "2. Envelope and MVC": "2. Envolvente y CVM",
    "3. Normalised (% MVC)": "3. Normalizada (% CVM)",

    # Elegir músculo cuando el registro trae dos y la práctica estudia uno.
    "Which muscle is being analysed?": "¿Qué músculo se analiza?",
    "This recording has two muscles. This practical studies one at a time, so "
    "every panel, metric and report will be about the channel chosen here.":
        "Este registro tiene dos músculos. Esta práctica estudia uno cada vez, "
        "así que todos los paneles, medidas e informes se referirán al canal "
        "que se elija aquí.",
    "Analysing {muscle}.": "Se analiza {muscle}.",
    "Which muscle is being normalised?": "¿Qué músculo se normaliza?",
    "This recording has two muscles. Normalisation is about one of them: the "
    "reference amplitude, the load distribution and the report will all be "
    "about the channel chosen here.":
        "Este registro tiene dos músculos. La normalización es de uno de ellos: "
        "la amplitud de referencia, la distribución de carga y el informe se "
        "referirán al canal que se elija aquí.",
    "Normalising {muscle}.": "Se normaliza {muscle}.",

    # Cuarto modo y franja de complejidad.
    "Free analysis": "Análisis libre",
    "Basic analysis — direct measurements":
        "Análisis básico — medidas directas",
    "Intermediate analysis — comparison between muscles":
        "Análisis intermedio — comparación entre músculos",
    "Advanced analysis — derived quantities":
        "Análisis avanzado — magnitudes derivadas",
    "Free analysis — every control, no guidance":
        "Análisis libre — todos los controles, sin guía",

    # Panel del bruto del segundo músculo, y el paso del tour sobre la franja.
    "1B. Raw signal — 2nd muscle": "1B. Señal en bruto — 2º músculo",
    "1B. Raw (2nd)": "1B. Bruto (2º)",
    "1B. Raw EMG signal — {muscle}": "1B. Señal EMG en bruto — {muscle}",
    "Raw EMG signal of the second muscle, unfiltered (needs a 2nd channel).":
        "Señal EMG en bruto del segundo músculo, sin filtrar (necesita un 2º canal).",

    # El registro viaja entre pestañas.
    "Recording loaded for analysis: {path}":
        "Registro cargado para análisis: {path}",
    "Recording loaded to normalise: {path}":
        "Registro cargado para normalizar: {path}",

    # Normalizar frente al propio registro, ofrecido con su advertencia.
    "Use this recording": "Usar este registro",
    "Normalise against this recording itself?":
        "¿Normalizar frente al propio registro?",
    "The signal will be divided by the 95th percentile of itself, so the "
    "strongest moment of this recording becomes 100 % — whatever the muscle "
    "can really do. Two recordings normalised this way cannot be compared "
    "with each other, and the Jonsson load limits do not apply: a sustained "
    "contraction exceeds them by construction.\n\nWhat does survive is the "
    "shape over time: when the muscle worked harder and when it let go.":
        "La señal se dividirá por el percentil 95 de sí misma, así que el "
        "momento más fuerte de este registro pasa a ser el 100 % —sea cual sea "
        "lo que el músculo pueda dar de verdad—. Dos registros normalizados "
        "así no se pueden comparar entre sí, y los límites de carga de Jonsson "
        "no se aplican: una contracción sostenida los supera por "
        "construcción.\n\nLo que sí se conserva es la forma en el tiempo: "
        "cuándo trabajó más el músculo y cuándo aflojó.",
    "Use it, showing the shape only": "Usarlo, solo para ver la forma",
    "Normalising against the recording itself — shape only, not % MVC.":
        "Normalizando frente al propio registro: solo la forma, no % CVM.",
    "A reference recording is required to express the signal as % MVC and to "
    "read it against the Jonsson limits.":
        "Hace falta un registro de referencia para expresar la señal en % CVM "
        "y poder leerla frente a los límites de Jonsson.",

    # ── Ensayo del asistente F-V (fv_rehearsal_dialog.py) ─────────
    'During the recording this panel appears over the plots, at this size:': 'Durante la grabación este panel aparece sobre las gráficas, con este tamaño:',
    'Rehearse…': 'Ensayar…',
    'Play the whole guided procedure with no hardware: the same prompts in the same order over a synthetic recording, with an explanation of each step, ending in the force-velocity study.': 'Reproduce todo el procedimiento guiado sin hardware: los mismos avisos, en el mismo orden, sobre un registro sintético, con una explicación de cada paso y terminando en el estudio fuerza-velocidad.',
    'Rehearsal — guided force-velocity acquisition': 'Ensayo — adquisición guiada fuerza-velocidad',
    'No hardware and no subject: the prompts, in the order and at the speed the wizard will show them. Loads: {loads} kg.': 'Sin hardware y sin sujeto: los avisos, en el orden y a la velocidad con que los mostrará el asistente. Cargas: {loads} kg.',
    'Play': 'Reproducir',
    'Pause': 'Pausa',
    'Next step': 'Paso siguiente',
    'Restart': 'Reiniciar',
    'Speed:': 'Velocidad:',
    '×1 is the real duration of the protocol; the faster settings are for reviewing the sequence.': '×1 es la duración real del protocolo; las velocidades mayores sirven para repasar la secuencia.',
    'Open the study…': 'Abrir el estudio…',
    "Opens the real force-velocity study on the rehearsal's recording.": 'Abre el estudio fuerza-velocidad real sobre el registro del ensayo.',
    'Force-velocity study — rehearsal recording': 'Estudio fuerza-velocidad — registro del ensayo',
    'maximum': 'máxima',
    '{kg:g} kg': '{kg:g} kg',
    'Get ready — the maximum comes first, with no weight.': 'Prepárese: primero la máxima, sin peso.',
    'A sustained maximum, held for a few seconds.': 'Una máxima sostenida, mantenida unos segundos.',
    'Recovery, and the first weight is set up.': 'Recuperación, y se prepara el primer peso.',
    'Prepare {kg:g} kg — take the weight and the starting position.': 'Prepare {kg:g} kg: coja el peso y sitúese en la posición de partida.',
    'Lift {kg:g} kg — one quick movement, not a hold.': 'Levante {kg:g} kg: un movimiento rápido, no un mantenimiento.',
    'Relax, and change the weight.': 'Relaje, y cambie el peso.',
    'Recorded — the loads are already in the file.': 'Registrado: las cargas ya están en el archivo.',
    'The maximum is recorded before any load: it is the 100 % the other contractions are read against. Doing it first also keeps it clear of the fatigue the loads are about to cause.': 'La máxima se registra antes que ninguna carga: es el 100 % con el que se leen las demás contracciones. Hacerla primero la mantiene además libre de la fatiga que van a producir las cargas.',
    'Held, because a true maximum takes about a second to reach. It is isometric — nothing moves, so the accelerometer stays flat here. This contraction sets the amplitude reference, not a velocity.': 'Se mantiene porque alcanzar la máxima verdadera lleva alrededor de un segundo. Es isométrica: no se mueve nada, así que aquí el acelerómetro permanece plano. Esta contracción fija la referencia de amplitud, no una velocidad.',
    'Longer than the pauses between loads: the subject has just given a maximum, and the first load should not be lifted tired.': 'Más larga que las pausas entre cargas: el sujeto acaba de dar una máxima, y la primera carga no debe levantarse ya cansado.',
    'Nothing is being recorded as a repetition yet. The countdown is there so the load is handed over and the position taken without hurrying.': 'Todavía no se registra nada como repetición. La cuenta atrás está para entregar la carga y tomar la posición sin prisas.',
    'The study reads the shortening velocity from the accelerometer, and a slow or held contraction has none. As this cue appears the application writes a marker into the file with the load — which is why the study can fill the load column by itself.': 'El estudio lee del acelerómetro la velocidad de acortamiento, y una contracción lenta o mantenida no la tiene. Al aparecer este aviso la aplicación escribe en el archivo una marca con la carga: por eso el estudio puede rellenar solo la columna de cargas.',
    'Short on purpose: long enough to change the load, not long enough to lose the thread. If more than one repetition per load was asked for, this is where it goes back for another.': 'Corta a propósito: lo justo para cambiar la carga, no tanto como para perder el hilo. Si se pidió más de una repetición por carga, aquí es donde vuelve a por otra.',
    'Stop the recording and open the force-velocity study in the Analysis tab. Nothing has to be typed: every window carries its load.': 'Detenga la grabación y abra el estudio fuerza-velocidad en la pestaña de análisis. No hay que teclear nada: cada ventana lleva su carga.',

    # ── Mapa del recorrido (gui/mapa.py) ──────────────────────────
    'connect · label · record': 'conectar · etiquetar · grabar',
    'mark events': 'marcar sucesos',
    'panels follow the practical': 'los paneles siguen a la práctica',
    'window · fragments': 'ventana · fragmentos',
    'signal as % of the maximum': 'la señal en % de la máxima',
    'muscle load (Jonsson)': 'carga muscular (Jonsson)',
    'F-V wizard': 'Asistente fuerza-velocidad',
    'one contraction per load,': 'una contracción por carga,',
    'marked with its weight': 'marcada con su peso',
    'F-V study': 'Estudio fuerza-velocidad',
    'load-velocity · power': 'carga-velocidad · potencia',
    'recruitment': 'reclutamiento',
    'Reference recording': 'Grabación de referencia',
    'the maximal effort, unloaded': 'el esfuerzo máximo, sin carga',
    'Two muscles?': '¿Dos músculos?',
    'asks which, once': 'pregunta cuál, una vez',
    'A reference?': '¿Hay referencia?',
    'if not, offers this one': 'si no, ofrece este registro',
    'goes by itself': 'va solo',
    'goes by itself, with the chosen muscle': 'va solo, con el músculo elegido',
    'loads': 'cargas',
    'another pass, same tab': 'otra pasada, misma pestaña',
    'it is the 100 %': 'es el 100 %',
    'The recording travels from left to right': 'El registro avanza de izquierda a derecha',

    # ── Diálogo del mapa ──────────────────────────────────────────
    'Map': 'Mapa',
    'Where you are in the process': 'Dónde estás en el proceso',
    'Where you are': 'Dónde estás',
    '{practical} — the lit path is the one this practical uses.': '{practical} — el camino iluminado es el que usa esta práctica.',
    'The map for this practical has not been generated.': 'El mapa de esta práctica no está generado.',

    "page {n}": "página {n}",
}
