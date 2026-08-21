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
    "EMG envelope (electrical)": "Envolvente EMG (eléctrica)",
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
        "Desmarque cualquier contracción que no sea claramente válida y pulse "
        "Redibujar. Las repeticiones de la misma carga se promedian. La "
        "velocidad está en unidades arbitrarias (el acelerómetro no está "
        "calibrado); la fuerza es la carga introducida.",
    "⚠ The accelerometer barely moved (flat / pinned at a rail), so "
    "the velocities are ~0. Put it on the moving segment, oriented "
    "so its resting value sits mid-range (not at ±1 g), and lift "
    "quickly.":
        "⚠ El acelerómetro apenas se movió (plano / pegado a un extremo), así "
        "que las velocidades son ~0. Colóquelo en el segmento móvil, orientado "
        "para que en reposo quede a media escala (no en ±1 g), y levante "
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
        "girar el acelerómetro. Conecte el BITalino primero, y no lo use "
        "mientras graba.",
    "Find the accelerometer channel": "Buscar el canal del acelerómetro",
    "Reading all six analogue inputs. Tilt the accelerometer slowly "
    "through 90° in each direction: the channel whose range grows the "
    "most is where the accelerometer is wired. A4 is the one emgteach "
    "uses for the ACC.":
        "Leyendo las seis entradas analógicas. Gire el acelerómetro despacio "
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
        "→ El acelerómetro está en {ch}, no en A4. Cambie su conector al "
        "puerto A4 (o dígamelo y hago el canal del ACC seleccionable).",
    "Tilt the sensor 90°… no channel clearly responds yet.":
        "Gire el sensor 90°… ningún canal responde claramente aún.",
    "Could not read the BITalino: {err}":
        "No se pudo leer el BITalino: {err}",
    "Use this channel for the ACC": "Usar este canal para el ACC",
    "ACC ch:": "Canal ACC:",
    "Analogue input the accelerometer is connected to (default A4). "
    "Use \"Find ACC channel…\" if unsure.":
        "Entrada analógica a la que está conectado el acelerómetro (por "
        "defecto A4). Use «Buscar canal del ACC…» si no está seguro.",
    "Accelerometer set to A{n}.": "Acelerómetro fijado en A{n}.",
    "Channels: EMG on {emg}, accelerometer on A{acc}.":
        "Canales: EMG en {emg}, acelerómetro en A{acc}.",
    "Tick at least two valid repetitions with a load (kg) entered, "
    "then press Redraw.":
        "Marque al menos dos repeticiones válidas con una carga (kg) "
        "introducida y pulse Redibujar.",
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
        "Active el acelerómetro y conecte el BITalino primero.",
    "List the known loads (kg) the subject will lift, lightest to "
    "heaviest. The wizard guides one short recording per load and marks "
    "each with its load, so the force-velocity study reads them "
    "automatically.":
        "Indique las cargas conocidas (kg) que levantará el sujeto, de menor a "
        "mayor. El asistente guía un registro corto por carga y marca cada una "
        "con su carga, para que el estudio fuerza-velocidad las lea "
        "automáticamente.",
    "Loads (kg):": "Cargas (kg):",
    "e.g.  2, 4, 6, 8": "p. ej.  2, 4, 6, 8",
    "Separate loads with commas or spaces; use a dot for decimals "
    "(e.g. 7.5).":
        "Separe las cargas con comas o espacios; use el punto para decimales "
        "(p. ej. 7.5).",
    "⚠ The accelerometer is set to the muscle. For force-velocity "
    "put it on the moving segment (set the placement to \"on the "
    "moving segment\"), or the velocity will be near zero.":
        "⚠ El acelerómetro está en el músculo. Para fuerza-velocidad póngalo en "
        "el segmento móvil (ponga la colocación en «en el segmento móvil»), o la "
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
        "Introduzca al menos dos cargas positivas (kg), separadas por espacios.",
    "List the known loads (kg) the subject will lift, lightest to "
    "heaviest. The wizard first guides an MVC maximum (no load), then "
    "for each load cues a quick lift ('Lift!' → 'Relax!', no hold), "
    "marking each so the force-velocity study reads the loads "
    "automatically.":
        "Indique las cargas conocidas (kg) que levantará el sujeto, de menor a "
        "mayor. El asistente guía primero una CVM máxima (sin carga) y luego, "
        "para cada carga, indica un levantamiento rápido («¡Levanta!» → "
        "«¡Relaja!», sin mantener), marcando cada uno para que el estudio "
        "fuerza-velocidad lea las cargas automáticamente.",
    # Config label next to the guided-F-V button (reps · loads).
    "{reps}× · loads: {loads} kg": "{reps}× · cargas: {loads} kg",
    "(loads not set)": "(cargas sin definir)",
    # Guided-F-V wizard prompts (MVC maximum first, then per-load contractions).
    "Get ready — maximum contraction (no load)":
        "Prepárate — contracción máxima (sin carga)",
    "Contract at maximum when it reaches 0":
        "Contraiga al máximo al llegar a 0",
    "Get ready — maximum (no load): {n}":
        "Prepárate — máxima (sin carga): {n}",
    "Contract at maximum! (no load)": "¡Contraiga al máximo! (sin carga)",
    "Contract at maximum! ({s:.0f} s)": "¡Contraiga al máximo! ({s:.0f} s)",
    "Relax — now the loads, lightest first":
        "Relaja — ahora las cargas, de menor a mayor",
    "Relax — the loads come next…": "Relaja — ahora vienen las cargas…",
    " (load {i}/{n}, rep {r}/{rn})": " (carga {i}/{n}, rep {r}/{rn})",
    "Prepare {kg:g} kg{prog}": "Prepara {kg:g} kg{prog}",
    "Prepare {kg:g} kg{prog}: {n}": "Prepara {kg:g} kg{prog}: {n}",
    "Lift {kg:g} kg when it reaches 0":
        "Levanta {kg:g} kg al llegar a 0",
    "Lift {kg:g} kg!": "¡Levanta {kg:g} kg!",
    "Lift {kg:g} kg — then relax": "Levanta {kg:g} kg — luego relaja",
    "Relax — another rep of {kg:g} kg":
        "Relaja — otra repetición de {kg:g} kg",
    "Relax — change to {kg:g} kg": "Relaja — cambia a {kg:g} kg",
    "F-V: MVC reference {ref:.2f} mV.":
        "F-V: referencia CVM {ref:.2f} mV.",
    "Force-velocity: contraction with {kg:g} kg.":
        "Fuerza-velocidad: contracción con {kg:g} kg.",
    "Loads recorded": "Cargas grabadas",
    "{n} loads marked.\nStop recording, then open the "
    "Force-velocity study.":
        "{n} cargas marcadas.\nDetenga la grabación y abra el estudio "
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
    "Broadcast to phones (classroom mode)": "Difundir a móviles (modo aula)",
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
        "Modo aula activado — los alumnos pueden seguir en {url}",
    "Could not start classroom mode (port busy?).":
        "No se pudo iniciar el modo aula (¿puerto ocupado?).",
    "Classroom mode off.": "Modo aula desactivado.",
    "Classroom mode off — previous follower links are now invalid.":
        "Modo aula desactivado — los enlaces anteriores ya no son válidos.",
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
        "puerto COM concreto (p. ej. COM5), o déjelo vacío para autodetectar. Empareje "
        "antes el BITalino en la configuración Bluetooth de Windows. No se usa PyBluez.",
    "Select a COM port for the Arduino before connecting.":
        "Seleccione un puerto COM para el Arduino antes de conectar.",
    "Device configured: {desc}. Press 'Start recording'.":
        "Dispositivo configurado: {desc}. Pulse 'Iniciar grabación'.",
    "Device disconnected.": "Dispositivo desconectado.",
    "Press M to quickly add a marker with the selected label.":
        "Pulse M para marcar rápidamente con la etiqueta seleccionada.",
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
        "Grabe unos segundos de contracción máxima para fijar la referencia "
        "CVM del monitor de carga en vivo.",
    "Calibrate the MVC to start monitoring.":
        "Calibra el CVM para empezar a monitorizar.",
    "Calibrating… contract at maximum for {s:.0f} s.":
        "Calibrando… contraiga al máximo durante {s:.0f} s.",
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
    "Get ready — {label}{rep}: {n}": "Prepárate — {label}{rep}: {n}",
    "Get ready — {label}{rep}": "Prepárate — {label}{rep}",
    "Maximum contraction when it reaches 0": "Contracción máxima al llegar a 0",
    "Contract {label} at maximum!{rep}": "¡Contraiga {label} al máximo!{rep}",
    "Next muscle: {label}": "Siguiente músculo: {label}",
    "Get ready for the next repetition": "Prepárate para la siguiente repetición",
    "MVC ready": "CVM listo",
    "{summary}\nYou can start recording.": "{summary}\nYa puede empezar a grabar.",
    "Calibration failed": "Calibración fallida",
    "No signal — check the electrodes.": "Sin señal — revise los electrodos.",
    "Contract {label} as hard as you can!  ({s:.0f} s)  "
    "peak {pk:.2f} mV":
        "¡Contraiga {label} todo lo que pueda!  ({s:.0f} s)  pico {pk:.2f} mV",
    "Relax…": "Relaja…",
    "Relax": "Relaja",
    "Effort {pct:.0f} %": "Esfuerzo {pct:.0f} %",
    "Push as hard as you can until it reaches 0":
        "Empuje todo lo que pueda hasta llegar a 0",
    "MVC ready — {summary}. You can start recording.":
        "CVM listo — {summary}. Ya puede empezar a grabar.",
    "MVC calibrated: {summary}": "CVM calibrado: {summary}",
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
        "Borre todo y empiece de cero (p. ej. un nuevo alumno)",
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
    "Fatigue trend detected (MDF decreases over time).":
        "Tendencia de fatiga detectada (la MDF desciende con el tiempo).",
    "No fatigue (MDF increases or stays stable).":
        "Sin fatiga (la MDF aumenta o se mantiene estable).",
    "MDF trend undefined (signal too short or constant).":
        "Tendencia de MDF indeterminada (señal demasiado corta o constante).",
    "Analysis parameters": "Parámetros de análisis",
    "EDF file:": "Archivo EDF:",
    "Select an EDF file…": "Seleccione un archivo EDF…",
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
        "(revise el contacto del electrodo o la ganancia).",
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
        "pulse «Calcular CVM» tras cambiarlo.",
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
    "Tick the graphs to add to the report:": "Marque los gráficos que se añadirán al informe:",
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
    "Select the EDF file to normalise…": "Seleccione el archivo EDF a normalizar…",
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
        "del ADC durante tramos ≥ 10 ms. Revise el contacto del electrodo y la ganancia.",
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
        "emparejados. Empareje el dispositivo en la configuración Bluetooth del "
        "sistema y enciéndalo.",
    "No BITalino was found on the Bluetooth COM ports. Pair the "
    "BITalino in the operating system's Bluetooth settings and switch "
    "it on, or enter its MAC address or COM port explicitly.":
        "No se encontró ningún BITalino en los puertos COM Bluetooth. Empareje el "
        "BITalino en la configuración Bluetooth del sistema y enciéndalo, o "
        "introduzca su dirección MAC o su puerto COM explícitamente.",
    "The device on {port} did not identify itself as a "
    "BITalino. Check that the BITalino is paired and "
    "switched on.":
        "El dispositivo en {port} no se identificó como un BITalino. "
        "Compruebe que el BITalino está emparejado y encendido.",
    "Unsupported BITalino sampling rate {fs} Hz. "
    "Use one of 1, 10, 100 or 1000.":
        "Frecuencia de muestreo {fs} Hz no soportada por el BITalino. "
        "Use 1, 10, 100 o 1000.",
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
    "Flat signal — check electrode contact": "Señal plana — revise el contacto del electrodo",
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
    "e.g. Isometric contraction 30 s": "p. ej. Contracción isométrica 30 s",
    "Live signal quality: saturation or a flat (disconnected) signal.":
        "Calidad de señal en vivo: saturación o señal plana (desconectada).",
    "Markers recorded so far. Select one and press Delete to remove it.":
        "Marcadores registrados hasta ahora. Seleccione uno y pulse Supr para eliminarlo.",
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
        "Abra el editor asistido para conservar los fragmentos significativos y descartar "
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
        "Vuelva a ejecutar la propuesta automática de fragmentos con los parámetros de arriba.",
    "Add fragment": "Añadir fragmento",
    "Remove selected": "Quitar seleccionado",
    "Whole recording": "Registro completo",
    # Segment "reason" codes shown in the fragment table.
    "activity": "actividad",
    "manual": "manual",
    "Clear the selection and analyse everything.": "Borre la selección y analice todo.",
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
        "con toda la fuerza que pueda. Registre primero la referencia, con los "
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
        "Obligatorio en este nivel de interfaz: seleccione un registro de "
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
        "Use esta opción solo para ver la forma de la señal.",
    "Choose a reference recording": "Elegir registro de referencia",
    "Continue without reference": "Continuar sin referencia",

    # ── Auto-normalisation marking (screen and report) ─────────────────
    "auto (not a real %MVC)": "automática (no es %CVM real)",
    "Muscle-load analysis requires an MVC reference recording. Select one to "
    "interpret these values as muscle load limits.":
        "El análisis de carga muscular requiere un registro de referencia CVM. "
        "Seleccione uno para interpretar estos valores como límites de carga "
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
    "A quick guide?": "¿Una guía rápida?",
    "This is a teaching application: it records the electrical activity of a "
    "muscle and turns it into measurements you can interpret. It works with "
    "either of two sensors — a BITalino over Bluetooth, or an Arduino + "
    "MyoWare 2.0 over USB — and behaves the same way with both.\n\nWould you "
    "like a short walkthrough of what each control does and what it means "
    "physiologically? It takes a couple of minutes, and you can reopen it "
    "later with the \"Guide\" button.":
        "Esta es una aplicación docente: registra la actividad eléctrica de un "
        "músculo y la convierte en medidas que se pueden interpretar. Funciona "
        "con cualquiera de dos sensores —un BITalino por Bluetooth o un "
        "Arduino + MyoWare 2.0 por USB— y se comporta igual con ambos.\n\n"
        "¿Quiere un recorrido breve por lo que hace cada control y por su "
        "significado fisiológico? Lleva un par de minutos, y puede volver a "
        "abrirlo cuando quiera con el botón «Guía».",
    "Stop the recording before starting the guide.":
        "Detenga el registro antes de iniciar la guía.",

    # ── Guided tour: teaching content (BORRADOR, pendiente de revisión) ─
    "Choose the practical first": "Elija primero la práctica",
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
    "interest, classroom broadcast — are shared by all three modes and stay "
    "out of the way until you tick this.":
        "Los controles finos —frecuencias de corte, umbrales de fatiga, región "
        "de interés, modo aula— son comunes a los tres modos y no estorban "
        "hasta que marque esta casilla.",
    "Two devices, one application": "Dos dispositivos, una aplicación",
    "The recording can be made with either of two interchangeable front ends: "
    "a BITalino over Bluetooth, or an Arduino RedBoard Plus with a MyoWare "
    "2.0 sensor over USB, whose firmware ships with the application.\n\n"
    "Which one is in use is a technical setting, made once by whoever "
    "prepares the laboratory: it sits with the connection details under "
    "\"Advanced options\". Nothing after that point changes — recording, "
    "analysis and file format are identical either way — so it is not "
    "something you need to touch during a practical, and a class can run on "
    "whatever hardware it has.":
        "El registro se puede hacer con cualquiera de dos frontales "
        "intercambiables: un BITalino por Bluetooth, o un Arduino RedBoard "
        "Plus con un sensor MyoWare 2.0 por USB, cuyo firmware se distribuye "
        "con la aplicación.\n\nCuál de los dos se usa es un ajuste técnico, "
        "que hace una sola vez quien prepara el laboratorio: está junto a los "
        "datos de conexión, en «Opciones avanzadas». Nada de lo que viene "
        "después cambia —registro, análisis y formato de fichero son "
        "idénticos con cualquiera de los dos—, así que no es algo que haya "
        "que tocar durante una práctica, y una clase puede funcionar con el "
        "material del que disponga.",
    "Offer this guide next time": "Ofrecer esta guía la próxima vez",
    "Connect the sensor": "Conecte el sensor",
    "With a BITalino, pair it in the operating system first; with the "
    "Arduino, just plug in the USB cable. Either way the surface electrodes "
    "go on the belly of the muscle, in line with the fibres, with the "
    "reference on a bony point that does not contract.":
        "Con un BITalino, empareje primero en el sistema operativo; con el "
        "Arduino, basta con enchufar el cable USB. En ambos casos los "
        "electrodos de superficie van sobre el vientre del músculo, en la "
        "dirección de las fibras, con la referencia en un punto óseo que no se "
        "contraiga.",
    "Name the muscle": "Nombre el músculo",
    "This name is written into the EDF file as the channel label, so the "
    "recording still says which muscle it was months later. Use the "
    "anatomical name.":
        "Este nombre se escribe en el fichero EDF como etiqueta del canal, de "
        "modo que el registro sigue diciendo qué músculo era meses después. "
        "Use el nombre anatómico.",
    "Where the accelerometer goes": "Dónde va el acelerómetro",
    "On the muscle it measures mechanomyogram (MMG): the transverse bulging "
    "of the fibres as they shorten, that is, the mechanical counterpart of "
    "the electrical signal. On the moving segment it measures the movement "
    "itself — its acceleration, and from that velocity and tremor.":
        "Sobre el músculo mide el mecanomiograma (MMG): el abombamiento "
        "transversal de las fibras al acortarse, es decir, la contrapartida "
        "mecánica de la señal eléctrica. Sobre el segmento móvil mide el "
        "movimiento mismo: su aceleración, y a partir de ella la velocidad y "
        "el temblor.",
    "Record": "Registre",
    "Start recording and ask for the contraction. Watch the live trace: at "
    "rest it should be a flat line with only baseline noise. A signal that "
    "never returns to baseline usually means a loose electrode or a poor "
    "contact, not a tonic muscle.":
        "Inicie el registro y pida la contracción. Vigile el trazado en vivo: "
        "en reposo debe ser una línea plana con solo ruido de base. Una señal "
        "que nunca vuelve a la línea de base suele indicar un electrodo suelto "
        "o mal contacto, no un músculo tónico.",
    "Let the class follow along": "Deje que la clase siga el registro",
    "This serves a read-only live view over the local network, so the rest of "
    "the group can watch the trace on their own phones while one person wears "
    "the electrodes. Nobody installs anything: they open a link, or scan the "
    "QR code.\n\nIt is worth more than it sounds. A single sensor is usually "
    "all a teaching laboratory has, and this is what turns one recording into "
    "something the whole class reads at the same time.":
        "Esto sirve una vista en vivo de solo lectura por la red local, de modo "
        "que el resto del grupo puede ver el trazado en su propio móvil "
        "mientras una persona lleva los electrodos. Nadie instala nada: abren "
        "un enlace, o escanean el código QR.\n\nVale más de lo que parece. Un "
        "laboratorio docente suele tener un único sensor, y esto es lo que "
        "convierte un solo registro en algo que lee toda la clase a la vez.",
    "Mark what happens": "Marque lo que ocurre",
    "Press MARK to timestamp an event — the start of an effort, a change of "
    "load, the moment the subject reports fatigue. The marks travel inside "
    "the EDF and let you find each phase again during the analysis.":
        "Pulse MARCA para poner una marca temporal en un suceso: el inicio de "
        "un esfuerzo, un cambio de carga, el momento en que el sujeto refiere "
        "fatiga. Las marcas viajan dentro del EDF y permiten reencontrar cada "
        "fase durante el análisis.",
    "Guided force-velocity": "Fuerza-velocidad guiada",
    "This wizard walks through one contraction per load. With increasing "
    "loads the shortening velocity falls: that inverse relation is the "
    "force-velocity curve, and the product of the two gives the power, which "
    "peaks at intermediate loads.":
        "Este asistente guía una contracción por cada carga. Al aumentar la "
        "carga cae la velocidad de acortamiento: esa relación inversa es la "
        "curva fuerza-velocidad, y el producto de ambas da la potencia, que es "
        "máxima con cargas intermedias.",
    "Calibrate the maximum": "Calibre el máximo",
    "A maximal voluntary contraction recorded now becomes the reference the "
    "live load bars are expressed against. Without it the amplitude is in "
    "millivolts, which says as much about the electrodes and the skin as "
    "about the muscle.":
        "Una contracción voluntaria máxima registrada ahora pasa a ser la "
        "referencia respecto a la que se expresan las barras de carga en vivo. "
        "Sin ella la amplitud está en milivoltios, que dice tanto de los "
        "electrodos y de la piel como del músculo.",
    "The three basic panels": "Los tres paneles básicos",
    "Raw signal: the interference pattern of the motor units firing. "
    "Normalised envelope: how activation changes over time, which is what you "
    "compare between efforts. Power spectrum: how that activity is "
    "distributed in frequency.":
        "Señal en bruto: el patrón de interferencia de las unidades motoras al "
        "descargar. Envolvente normalizada: cómo cambia la activación en el "
        "tiempo, que es lo que se compara entre esfuerzos. Espectro de "
        "potencia: cómo se reparte esa actividad en frecuencia.",
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
    "With two channels the envelopes can be overlaid. In a clean movement the "
    "agonist activates while the antagonist stays nearly silent; simultaneous "
    "activation is co-contraction, which stiffens the joint and is typical of "
    "an unpractised or uncertain movement.":
        "Con dos canales se pueden superponer las envolventes. En un "
        "movimiento limpio el agonista se activa mientras el antagonista "
        "permanece casi silente; la activación simultánea es co-contracción, "
        "que rigidiza la articulación y es típica de un movimiento poco "
        "entrenado o inseguro.",
    # (the "Force-velocity study" caption itself is defined with the Analysis
    # tab strings above; only the tour's explanation of it belongs here)
    "Builds the load-velocity, force-velocity and power curves from a "
    "recording where several known loads were lifted, and relates them to the "
    "EMG amplitude — that is, to how much the muscle had to be recruited for "
    "each load.":
        "Construye las curvas carga-velocidad, fuerza-velocidad y potencia a "
        "partir de un registro en el que se levantaron varias cargas "
        "conocidas, y las relaciona con la amplitud EMG, es decir, con cuánto "
        "hubo que reclutar el músculo para cada carga.",
    "Take the results away": "Llévese los resultados",
    "The report gathers the figures and the metrics into a PDF, and the CSV "
    "export holds the numbers behind them for anyone who wants to work on "
    "them elsewhere.":
        "El informe reúne las figuras y las métricas en un PDF, y la "
        "exportación CSV guarda los números que hay detrás para quien quiera "
        "trabajarlos en otro sitio.",
    "Why normalise at all": "Por qué normalizar",
    "A raw amplitude cannot be compared between two people, or between two "
    "sessions of the same person: it depends on the electrodes, the skin and "
    "the fat beneath it. Expressing every value as a percentage of the "
    "maximal contraction removes all of that and leaves the muscle.":
        "Una amplitud bruta no se puede comparar entre dos personas, ni entre "
        "dos sesiones de la misma persona: depende de los electrodos, de la "
        "piel y de la grasa que hay debajo. Expresar cada valor como "
        "porcentaje de la contracción máxima elimina todo eso y deja el "
        "músculo.",
    "Muscle load": "Carga muscular",
    "Once the signal is in % MVC, the distribution of load over time can be "
    "read against the Jonsson limits: the static level (P10) is the load that "
    "is almost never released, and it is the one most associated with "
    "sustained-effort discomfort.":
        "Una vez la señal está en % CVM, la distribución de la carga en el "
        "tiempo se puede leer frente a los límites de Jonsson: el nivel "
        "estático (P10) es la carga que casi nunca se suelta, y es la más "
        "asociada a las molestias por esfuerzo mantenido.",

    "page {n}": "página {n}",
}
