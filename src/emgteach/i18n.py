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
    # --- muscle labels (acquisition) ---
    "Agonist — e.g. FCR": "Agonista, p. ej. FCR",
    "Antagonist — e.g. ECR": "Antagonista, p. ej. ECR",
    "Agonist": "Agonista",
    "Antagonist": "Antagonista",
    # --- acquisition: output path, test identifier, k ---
    "Output path and file:": "Ruta y archivo de salida:",
    "Test identifier:": "Identificador de prueba:",
    "Test identifier: {code}": "Identificador de prueba: {code}",
    "Device: BITalino": "Dispositivo: BITalino",
    "Co-activation\nindex": "Índice de\ncoactivación",
    "mean % MVC": "% CVM medio",
    # --- el dispositivo, según la práctica ---
    "a BITalino over Bluetooth": "un BITalino por Bluetooth",
    "either of two sensors: a BITalino over Bluetooth or an Arduino + "
    "MyoWare 2.0 over USB":
        "cualquiera de dos sensores: un BITalino por Bluetooth o un Arduino + "
        "MyoWare 2.0 por USB",
    "The electrical activity of a muscle is recorded and turned into "
    "measurements that can be interpreted. The application works with "
    "{sensors}.\n\nFor a short walkthrough of the application, press Yes.":
        "Se registra la actividad eléctrica de un músculo y se convierte en "
        "medidas que se pueden interpretar. La aplicación funciona con "
        "{sensors}.\n\nPara un recorrido breve por la aplicación, pulse Sí.",
    "This practical is recorded with the BITalino over Bluetooth, which is "
    "the device that gives two channels.":
        "Esta práctica se registra con el BITalino por Bluetooth, que es el "
        "dispositivo que da dos canales.",
    "This practical is recorded with the BITalino over Bluetooth, which is "
    "the device that carries the accelerometer.":
        "Esta práctica se registra con el BITalino por Bluetooth, que es el "
        "dispositivo que lleva el acelerómetro.",
    "Switch the board on and connect the electrodes: the positive and the "
    "negative go on the midline of the muscle, the reference on a neutral "
    "point, over a bone if possible.":
        "Encienda la placa y conecte los electrodos: el positivo y el "
        "negativo van sobre la línea media del músculo, la referencia en un "
        "punto neutro, sobre un hueso si es posible.",
    "The application supports two devices: the BITalino over Bluetooth and "
    "the Arduino + MyoWare 2.0 over USB. Only the single-muscle practical "
    "can use the Arduino; the other two need the BITalino's second channel "
    "or its accelerometer, so they fix it and the selector does not appear.":
        "La aplicación admite dos dispositivos: el BITalino por Bluetooth y "
        "el Arduino + MyoWare 2.0 por USB. Solo la práctica de un músculo "
        "puede usar el Arduino; las otras dos necesitan el segundo canal del "
        "BITalino o su acelerómetro, así que lo fijan y el selector no "
        "aparece.",
    # --- calibration wizard: brief maximal efforts ---
    " (brief {i}/{n})": " (breve {i}/{n})",
    "One short, maximal effort when the count reaches 0 — against something "
    "that cannot move, such as the underside of the table, not against a "
    "hand.":
        "Un solo esfuerzo máximo y breve cuando la cuenta llegue a 0, contra "
        "algo que no se pueda mover —el canto inferior de la mesa, por "
        "ejemplo—, no contra una mano.",
    "Maximum, short and hard — {label}{rep}":
        "¡Máximo, breve y fuerte! — {label}{rep}",
    "Make a single, brief muscle contraction (a twitch) with the greatest "
    "force you can.":
        "Haga una contracción o sacudida muscular simple (breve) con la máxima "
        "fuerza posible.",
    "Make a single, brief contraction of {label} with the greatest force you "
    "can{rep}":
        "Haga una contracción o sacudida muscular simple (breve) de {label} con "
        "la máxima fuerza posible{rep}",
    "e.g. bench 3, attempt 2": "p. ej. mesa 3, intento 2",
    "Goes into the EDF header and the report. One student, a pair, a bench "
    "or a repeat — whatever tells this recording apart.":
        "Va a la cabecera del EDF y al informe. Un alumno, una pareja, una "
        "mesa o una repetición: lo que distinga este registro.",
    "threshold = rest + k × noise (3 is usual)":
        "umbral = reposo + k × ruido (lo habitual es 3)",
    "Type the name of each muscle in its box, following the order of the "
    "board's channels (Muscle 1 is the one recorded on A1).":
        "Escriba el nombre de cada músculo en su casilla, siguiendo el orden "
        "de los canales de la placa (Músculo 1 es el que se registra por A1).",
    # --- fatigue panel with both muscles ---
    "{muscle}: MDF per window": "{muscle}: MDF por ventana",
    "{muscle}: trend": "{muscle}: tendencia",
    # --- analysis row: fragments count, panel chips ---
    "1 fragment selected": "1 fragmento seleccionado",
    "{n} fragments selected": "{n} fragmentos seleccionados",
    "The chips at the end of that line choose which panels are drawn; hover "
    "over «Panels:» for what each one shows.":
        "Las casillas al final de esa línea eligen qué paneles se dibujan; "
        "pase el ratón por «Paneles:» para ver qué muestra cada uno.",
    # --- per-contraction table ---
    "{n} contractions found; see the table.":
        "{n} contracciones encontradas; véase la tabla.",
    "The contraction table could not be built: {err}":
        "No se pudo construir la tabla de contracciones: {err}",
    "Contractions": "Contracciones",
    "RMS (mV)": "RMS (mV)",
    "Peak (% MVC)": "Pico (% CVM)",
    "EMD (ms)": "EMD (ms)",
    "{n} contractions": "{n} contracciones",
    "mean electromechanical delay {ms:.0f} ms":
        "retraso electromecánico medio {ms:.0f} ms",
    "Each row is one contraction the application found on its own, the same "
    "ones the fragment editor proposes. With two muscles, the row belongs to "
    "the one that led it; «Co-activation» means both worked at once, and the "
    "numbers are the stronger one's.":
        "Cada fila es una contracción que la aplicación ha encontrado por sí "
        "misma, las mismas que propone el editor de fragmentos. Con dos "
        "músculos, la fila es del que la lideró; «Coactivación» significa "
        "que los dos trabajaron a la vez, y los números son los del más "
        "fuerte.",
    "RMS": "RMS",
    "mean amplitude of the filtered signal over the contraction. Rest is a "
    "few hundredths of a millivolt; a firm effort with surface electrodes is "
    "usually 0.1–1 mV, and depends on the electrodes and the skin, which is "
    "why % MVC exists.":
        "amplitud media de la señal filtrada durante la contracción. El "
        "reposo son unas centésimas de milivoltio; un esfuerzo firme con "
        "electrodos de superficie suele estar entre 0,1 y 1 mV, y depende de "
        "los electrodos y de la piel: por eso existe el % CVM.",
    "the strongest {w:.1f} s of the contraction, as a share of the maximum. "
    "A task effort is usually 20–80 %; above 100 % (in red) the calibration "
    "was not a maximum.":
        "el tramo de {w:.1f} s más fuerte de la contracción, como porcentaje "
        "del máximo. Un esfuerzo de tarea suele estar entre el 20 y el 80 %; "
        "por encima del 100 % (en rojo) la calibración no fue un máximo.",
    "MDF": "MDF",
    "median frequency of the spectrum. Typically 60–150 Hz for surface EMG "
    "of limb muscles; it falls along a sustained effort as the muscle "
    "fatigues. Not shown for contractions shorter than a quarter of a second.":
        "frecuencia mediana del espectro. Típicamente 60–150 Hz en EMG de "
        "superficie de músculos de las extremidades; baja a lo largo de un "
        "esfuerzo sostenido a medida que el músculo se fatiga. No se muestra "
        "en contracciones de menos de un cuarto de segundo.",
    "EMD": "EMD",
    "electromechanical delay, from the electrical onset to the start of the "
    "movement measured by the accelerometer on the limb. Usually 30–100 ms "
    "in healthy adults: the time the muscle takes to take up its slack and "
    "build force.":
        "retraso electromecánico, desde el inicio eléctrico hasta el comienzo "
        "del movimiento medido por el acelerómetro en la extremidad. "
        "Habitualmente 30–100 ms en adultos sanos: el tiempo que tarda el "
        "músculo en tensar sus elementos elásticos y generar fuerza.",
    # --- spectrum before/after the filter, ranges on the cards ---
    "After the filter": "Después del filtro",
    "Before the filter (raw)": "Antes del filtro (bruto)",
    "Electromechanical delay: {ms:.0f} ms (mean of {n})":
        "Retraso electromecánico: {ms:.0f} ms (media de {n})",
    "usual 80–170 Hz": "habitual 80–170 Hz",
    "usual 60–150 Hz": "habitual 60–150 Hz",
    "a task effort is usually 20–80 %": "un esfuerzo de tarea suele ser 20–80 %",
    "rest ≈ 0.01 mV · effort 0.1–1 mV": "reposo ≈ 0,01 mV · esfuerzo 0,1–1 mV",
    # --- «?» texts per box (help_texts.py) ---
    "Choose the device and the port it appears on; on a laboratory computer "
    "this is set once and kept. The test identifier written here goes into "
    "the recording's header and the report.":
        "Elija el dispositivo y el puerto en el que aparece; en un ordenador "
        "de laboratorio esto se fija una vez y se conserva. El identificador "
        "de prueba que se escribe aquí va a la cabecera del registro y al "
        "informe.",
    "The guided force-velocity study": "El estudio fuerza-velocidad guiado",
    "A muscle shortens more slowly the heavier the load it moves, and the "
    "power it delivers is greatest at intermediate loads. «Guided F-V…» runs "
    "the procedure that measures this: it asks for the plan (the loads in "
    "order, how many lifts of each, the seconds of preparation), starts the "
    "recording if it was not running, takes an isometric maximum without load "
    "as the reference, and then prompts one quick lift per repetition, marking "
    "each in the file with its load. The force-velocity study in the Analysis "
    "tab reads those marks and draws the load-velocity, force-velocity, power "
    "and recruitment curves.":
        "Un músculo se acorta más despacio cuanto mayor es la carga que mueve, "
        "y la potencia que entrega es máxima con cargas intermedias. «F-V "
        "guiada…» dirige el procedimiento que lo mide: pide el plan (las "
        "cargas en orden, cuántas elevaciones de cada una, los segundos de "
        "preparación), inicia la grabación si no estaba en marcha, toma un "
        "máximo isométrico sin carga como referencia y después avisa de una "
        "elevación rápida por repetición, marcando cada una en el archivo con "
        "su carga. El estudio fuerza-velocidad de la pestaña Análisis lee esas "
        "marcas y dibuja las curvas carga-velocidad, fuerza-velocidad, "
        "potencia y reclutamiento.",
    "«Rehearse…» runs the same prompts with a synthetic signal and no "
    "hardware, to learn the procedure before anyone holds a weight.":
        "«Ensayar…» recorre los mismos avisos con una señal sintética y sin "
        "hardware, para aprender el procedimiento antes de que nadie sostenga "
        "un peso.",
    "In the practicals that need a reference, the session asks for the "
    "maximal contraction first and the task afterwards, and writes both into "
    "one file.":
        "En las prácticas que necesitan referencia, la sesión pide primero la "
        "contracción máxima y después la tarea, y escribe las dos en un solo "
        "archivo.",
    "The live signal": "La señal en directo",
    "The upper trace is the raw signal: the sum of the action potentials of "
    "the fibres under the electrodes, in millivolts. The lower one is its "
    "envelope — the raw signal rectified and smoothed — which follows how "
    "hard the muscle is working and is what the load bars and the analysis "
    "are built on.":
        "El trazo superior es la señal en bruto: la suma de los potenciales de "
        "acción de las fibras bajo los electrodos, en milivoltios. El inferior "
        "es su envolvente, la señal rectificada y suavizada, que sigue cuánto "
        "trabaja el músculo y es sobre lo que se construyen las barras de "
        "carga y el análisis.",
    "Three sustained maximal efforts are recorded, then three brief maximal "
    "squeezes: a held contraction shows a peak at its start and then a "
    "plateau, and a brief squeeze reaches that peak alone. The reference is "
    "the strongest 0.2 s across all six, so it is a maximum the task cannot "
    "exceed; a repetition that came out weak can be discarded afterwards in "
    "the analysis.":
        "Se graban tres esfuerzos máximos mantenidos y después tres "
        "sacudidas máximas breves: una contracción mantenida muestra un pico "
        "al inicio y luego una meseta, y una sacudida breve alcanza ese pico "
        "sin más. La referencia es el tramo de 0,2 s más fuerte de las seis "
        "repeticiones, de modo que es un máximo que la tarea no puede "
        "superar; una repetición que salió floja puede descartarse después "
        "en el análisis.",
    "Opening a recording": "Abrir un registro",
    "Open a recording and it is analysed on its own; the channel to study is "
    "the muscle's name from the file. The two buttons underneath are for "
    "afterwards: «Calibration repetitions…» chooses which maximal efforts fix "
    "the reference, and «Select fragments…» limits the analysis to some of "
    "the contractions. Neither is needed to read a clean recording.":
        "Abra un registro y se analiza solo; el canal a estudiar es el nombre "
        "del músculo que trae el archivo. Los dos botones de debajo son para "
        "después: «Repeticiones de la calibración…» elige qué esfuerzos "
        "máximos fijan la referencia, y «Seleccionar fragmentos…» limita el "
        "análisis a algunas contracciones. Ninguno hace falta para leer un "
        "registro limpio.",
    "Reading the numbers": "Leer los números",
    "Each card is one figure for the whole analysed span, with its usual "
    "range in grey where one can be given: those ranges are orientative "
    "values for surface EMG in healthy adults, not limits. The task maximum "
    "says how far the effort went against the calibrated maximum; well above "
    "100 % means the calibration was not maximal. The table beside gives the "
    "same figures contraction by contraction.":
        "Cada ficha es una cifra para todo el tramo analizado, con su rango "
        "habitual en gris cuando se puede dar uno: esos rangos son valores "
        "orientativos para EMG de superficie en adultos sanos, no límites. "
        "El máximo de la tarea dice hasta dónde llegó el esfuerzo respecto "
        "al máximo calibrado; muy por encima del 100 % significa que la "
        "calibración no fue máxima. La tabla de al lado da las mismas cifras "
        "contracción a contracción.",
    # --- the five-step tour (tour.py) ---
    "Everything else follows from this. Each mode records what that "
    "practical needs — one muscle, an agonist/antagonist pair, or a "
    "muscle plus the accelerometer — and the rest of the interface "
    "offers only the measurements that make sense for it. The "
    "coloured band beside it is the level: basic, intermediate or "
    "advanced.":
        "Todo lo demás sale de aquí. Cada modo registra lo que esa práctica "
        "necesita (un músculo, un par agonista/antagonista, o un músculo más "
        "el acelerómetro) y el resto de la interfaz ofrece solo las medidas "
        "que tienen sentido para ella. La banda de color de al lado es el "
        "nivel: básico, intermedio o avanzado.",
    "This practical names its channel itself, so there is nothing to "
    "type.":
        "Esta práctica pone nombre a su canal por sí misma, así que no hay "
        "nada que escribir.",
    "Press record. The session asks first for a maximal contraction "
    "— the reference every measurement is expressed against — and "
    "then for the task. Both go into one file, so nothing has to be "
    "matched up afterwards. Watch the live trace: at rest it should "
    "be a flat line with only baseline noise. A signal that never "
    "returns to baseline usually means a loose electrode, not a "
    "tonic muscle. Each contraction onset is marked on its own.":
        "Pulse grabar. La sesión pide primero una contracción máxima (la "
        "referencia respecto a la que se expresa cada medida) y después la "
        "tarea. Las dos van a un solo archivo, así que no hay que emparejar "
        "nada después. Observe el trazo en directo: en reposo debe ser una "
        "línea plana con solo el ruido basal. Una señal que nunca vuelve a la "
        "línea base suele ser un electrodo suelto, no un músculo tónico. El "
        "inicio de cada contracción se marca solo.",
    "There are two possibilities: on the muscle it allows the "
    "mechanomyogram (MMG) to be measured, which runs in parallel "
    "with the electrical signal; on the moving segment of the "
    "joint it allows the movement, and the parameters associated "
    "with it, to be measured — including the delay between the "
    "muscle firing and the limb moving.":
        "Hay dos posibilidades: sobre el músculo permite medir el "
        "mecanomiograma (MMG), que corre en paralelo con la señal eléctrica; "
        "sobre el segmento móvil de la articulación permite medir el "
        "movimiento y los parámetros asociados a él, incluido el retraso "
        "entre que el músculo se activa y la extremidad se mueve.",
    "The force-velocity experiment, and its rehearsal":
        "El experimento fuerza-velocidad, y su ensayo",
    "The step-by-step wizard guides you through the contractions "
    "with different loads: with a greater load the velocity is "
    "lower, and that inverse relation is the force-velocity "
    "curve. As it is the longest procedure in the application, a "
    "simulation is provided as a rehearsal, so that what is "
    "going to be done live is understood first.":
        "El asistente paso a paso guía las contracciones con distintas "
        "cargas: con más carga la velocidad es menor, y esa relación inversa "
        "es la curva fuerza-velocidad. Como es el procedimiento más largo de "
        "la aplicación, se ofrece una simulación como ensayo, para entender "
        "primero lo que se va a hacer en vivo.",
    "The recording is analysed as soon as it is opened. Both muscles were "
    "calibrated while recording, so the two envelopes are overlaid in % MVC "
    "— the only form in which two different muscles compare at all, since "
    "each one's millivolts depend on its own electrodes and skin. In a clean "
    "movement the agonist activates while the antagonist stays nearly "
    "silent; simultaneous activation is co-activation, which holds the joint "
    "rigid and is typical of an unpractised or uncertain movement. The table "
    "below the panels gives one row per contraction, and which muscle led it.":
        "El registro se analiza en cuanto se abre. Los dos músculos se "
        "calibraron al grabar, así que las dos envolventes se superponen en "
        "% CVM, la única forma en que dos músculos distintos se pueden "
        "comparar, porque los milivoltios de cada uno dependen de sus "
        "electrodos y de su piel. En un movimiento limpio el agonista se "
        "activa mientras el antagonista queda casi en silencio; la "
        "activación simultánea es coactivación, que deja rígida la "
        "articulación y es típica de un movimiento poco practicado o "
        "inseguro. La tabla bajo los paneles da una fila por contracción, y "
        "qué músculo la lideró.",
    "The recording is analysed as soon as it is opened. The study "
    "builds the load-velocity, force-velocity and power curves "
    "from a recording where several known loads were lifted, and "
    "relates them to the EMG amplitude — that is, to how many "
    "motor units had to be recruited for each load. The panels "
    "also show the movement against the EMG and the delay "
    "between the two.":
        "El registro se analiza en cuanto se abre. El estudio construye las "
        "curvas carga-velocidad, fuerza-velocidad y potencia a partir de un "
        "registro en el que se levantaron varias cargas conocidas, y las "
        "relaciona con la amplitud del EMG, es decir, con cuántas unidades "
        "motoras hubo que reclutar para cada carga. Los paneles muestran "
        "también el movimiento frente al EMG y el retraso entre ambos.",
    "What the analysis shows": "Qué muestra el análisis",
    "The recording is analysed as soon as it is opened. Raw signal: what the "
    "contracting fibres produce. Normalised envelope: how activation changes "
    "over time, which is what is compared between efforts. Spectrum: how the "
    "activity is distributed across frequencies — as a sustained contraction "
    "fatigues the muscle, the median frequency (MDF) falls. The cards under "
    "the panels carry the numbers with their usual ranges, and the table "
    "beside them gives one row per contraction.":
        "El registro se analiza en cuanto se abre. Señal en bruto: lo que "
        "producen las fibras que se contraen. Envolvente normalizada: cómo "
        "cambia la activación con el tiempo, que es lo que se compara entre "
        "esfuerzos. Espectro: cómo se reparte la actividad entre "
        "frecuencias; a medida que una contracción sostenida fatiga el "
        "músculo, la frecuencia mediana (MDF) baja. Las fichas bajo los "
        "paneles llevan los números con sus rangos habituales, y la tabla de "
        "al lado da una fila por contracción.",
    # --- analysis summary cards, task maximum, fatigue help ---
    "MDF slope": "Pendiente de la MDF",
    "Task maximum": "Máximo de la tarea",
    "MVC": "CVM",
    "Close": "Cerrar",
    "not a maximum": "no fue un máximo",
    "Highest sustained level ({w:.1f} s) of the task, as % of the maximal "
    "contraction. Well above 100 % means the calibration was not a maximum.":
        "Nivel más alto sostenido ({w:.1f} s) durante la tarea, en % de la "
        "contracción máxima. Muy por encima del 100 % significa que la "
        "calibración no fue un máximo.",
    "Detected (MDF −{decline:.1f} %)": "Detectada (MDF −{decline:.1f} %)",
    "Not detected (MDF stable or rising)": "No detectada (MDF estable o en aumento)",
    "Not conclusive (trend does not fit, R²={r2:.2f})":
        "No concluyente (la tendencia no ajusta, R²={r2:.2f})",
    "The task went well past the reference: the calibration did not capture "
    "a maximum, so every % MVC here is too high in the same proportion. "
    "Calibrate again, against something that cannot move.":
        "La tarea superó con mucho la referencia: la calibración no recogió "
        "un máximo, así que todos los % CVM de aquí están inflados en la "
        "misma proporción. Vuelva a calibrar contra algo que no pueda moverse.",
    "As a muscle fatigues, its action potentials slow down and the EMG "
    "spectrum shifts towards lower frequencies. The median frequency (MDF) "
    "is the frequency that splits the spectrum in two halves of equal "
    "power; it is the standard measure of that shift.":
        "Cuando un músculo se fatiga, sus potenciales de acción se vuelven "
        "más lentos y el espectro del EMG se desplaza hacia frecuencias más "
        "bajas. La frecuencia mediana (MDF) es la que divide el espectro en "
        "dos mitades de igual potencia; es la medida habitual de ese "
        "desplazamiento.",
    "The application computes the MDF on successive windows and fits a "
    "straight line to it over time. The verdict follows that line:":
        "La aplicación calcula la MDF en ventanas sucesivas y ajusta una "
        "recta a su evolución en el tiempo. El veredicto sale de esa recta:",
    "<b>Detected</b>: the MDF falls clearly and the line fits the data "
    "(high R²).":
        "<b>Detectada</b>: la MDF baja con claridad y la recta ajusta bien "
        "los datos (R² alto).",
    "<b>Not detected</b>: the MDF stays flat or rises.":
        "<b>No detectada</b>: la MDF se mantiene o sube.",
    "<b>Not conclusive</b>: the line does not fit (low R²). This is usual "
    "with short or intermittent contractions; the recording does not "
    "answer the question, which is not the same as answering “no”.":
        "<b>No concluyente</b>: la recta no ajusta (R² bajo). Es lo habitual "
        "con contracciones cortas o intermitentes; el registro no responde a "
        "la pregunta, que no es lo mismo que responder «no».",
    "Fatigue is only meaningful on a sustained contraction of some tens of "
    "seconds. On a series of short contractions the verdict says nothing "
    "about the muscle.":
        "La fatiga solo tiene sentido en una contracción sostenida de varias "
        "decenas de segundos. En una serie de contracciones cortas el "
        "veredicto no dice nada del músculo.",
    "Open a recording, or record one in Acquisition: it is analysed on its own.":
        "Abra un registro, o grabe uno en Adquisición: se analiza solo.",
    "Open a recording with calibration, or record one in Acquisition: the "
    "reference is computed on its own.":
        "Abra un registro con calibración, o grabe uno en Adquisición: la "
        "referencia se calcula sola.",
    # --- session report: calibration section ---
    "Calibration (maximal voluntary contraction)":
        "Calibración (contracción voluntaria máxima)",
    "Reference": "Referencia",
    "Source": "Procedencia",
    "{pct:.0f} % MVC (sustained {w:.1f} s)": "{pct:.0f} % CVM (sostenido {w:.1f} s)",
    "The task exceeds the reference by a wide margin: the calibration did "
    "not capture a maximum, so every percentage in this report is too high "
    "in the same proportion. Calibrate again with a genuinely maximal "
    "contraction, against something that cannot move.":
        "La tarea supera la referencia con mucho margen: la calibración no "
        "recogió un máximo, así que todos los porcentajes de este informe "
        "están inflados en la misma proporción. Vuelva a calibrar con una "
        "contracción realmente máxima, contra algo que no pueda moverse.",
    "Repetition": "Repetición",
    "Other muscle during it": "El otro músculo mientras tanto",
    "Channel {n}": "Canal {n}",
    "discarded": "descartada",
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
    # -- EDF+ identification header: what did not fit, said out loud --
    "Warning — the EDF+ header shares {budget} characters between equipment, "
    "supervisor and protocol. Equipment shortened from \"{was}\" to \"{now}\" "
    "so the protocol \"{protocol}\" is saved whole.":
        "Aviso — la cabecera EDF+ reparte {budget} caracteres entre equipo, "
        "supervisor y protocolo. Se ha acortado el equipo de «{was}» a "
        "«{now}» para guardar entero el protocolo «{protocol}».",
    "Warning — supervisor shortened to \"{now}\" so the protocol "
    "\"{protocol}\" is saved whole.":
        "Aviso — se ha acortado el supervisor a «{now}» para guardar entero "
        "el protocolo «{protocol}».",
    "Warning — the protocol is {length} characters and the EDF+ header has "
    "room for {budget}; it will be saved cut short as \"{kept}\". Shorten it "
    "to keep it whole.":
        "Aviso — el protocolo tiene {length} caracteres y en la cabecera "
        "EDF+ caben {budget}; se guardará recortado como «{kept}». Acórtelo "
        "para conservarlo entero.",
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
    "Time given for each loaded lift — a quick concentric movement, "
    "not a hold.":
        "Tiempo para cada levantamiento con carga: un movimiento concéntrico "
        "rápido, no un mantenimiento.",
    "Enter at least two positive loads (kg), separated by spaces.":
        "Introducir al menos dos cargas positivas (kg), separadas por espacios.",
    "List the known loads (kg) the subject will lift, lightest to "
    "heaviest. Recording calibrates the maximum first and then cues a "
    "quick lift for each load ('Lift!' → 'Relax!', no hold), marking "
    "each one so the force-velocity study reads the loads "
    "automatically.":
        "Indique las cargas conocidas (kg) que levantará el sujeto, de menor a "
        "mayor. Al grabar se calibra primero el máximo y después se pide un "
        "levantamiento rápido por cada carga («¡Levante!» → «¡Relaje!», sin "
        "mantener), marcando cada uno para que el estudio fuerza-velocidad lea "
        "las cargas automáticamente.",
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
    "Fatigue": "Fatiga",
    # The fragment editor's suggested manoeuvres (EMG_PROFILE.marker_presets).
    # They reach tr() as a variable, so the literal scan cannot see them;
    # test_i18n guards them by name instead.
    "Flexion": "Flexión",
    "Extension": "Extensión",
    "Grip": "Presa",
    # The ECG profile's own presets. Never translated because nothing scanned
    # them; the guard on marker_presets found them the moment it was written.
    "Rest": "Reposo",
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
    "Marker added: t={t:.1f} s — {label}": "Marca añadida: t={t:.1f} s — {label}",
    "Recording finished. File: {path}": "Grabación finalizada. Archivo: {path}",
    "No data from the device — connection not established.":
        "Sin datos del dispositivo — conexión no establecida.",
    "No data from the device for {s:.1f} s — forcing disconnection.":
        "Sin datos del dispositivo durante {s:.1f} s — forzando desconexión.",
    # -- live muscle-load monitor --
    "Muscle load (live MVC)": "Carga muscular (CVM en vivo)",
    "Calibrate MVC": "Calibrar CVM",
    "Calibration failed (no signal).": "Calibración fallida (sin señal).",
    # -- guided MVC-calibration wizard --
    "Guided MVC calibration: contract each muscle in turn at maximum "
    "when prompted; sets the reference for the live load monitor.":
        "Calibración CVM guiada: contraiga cada músculo por turnos al máximo "
        "cuando se le indique; fija la referencia del monitor de carga en vivo.",
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
    "This panel needs a recording with two muscles.":
        "Este panel necesita un registro con dos músculos.",
    "2nd channel «{name}» overlaid.": "2º canal «{name}» superpuesto.",
    "Could not analyse the 2nd channel «{name}»: {err}":
        "No se pudo analizar el 2º canal «{name}»: {err}",
    "Envelope cutoff frequency (Hz):": "Frec. corte envolvente (Hz):",
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
    "Widen the time window (×2)": "Ampliar ventana temporal (×2)",
    "Narrow the time window (÷2)": "Reducir ventana temporal (÷2)",
    "Analysis summary": "Resumen del análisis",
    "Start:": "Inicio:",
    "Duration:": "Duración:",
    "File:": "Archivo:",
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

    # --- MVC worker / GUI ---
    "Signal loaded — {fs:.0f} Hz — {dur:.1f} s — units: {units}":
        "Señal cargada — {fs:.0f} Hz — {dur:.1f} s — unidades: {units}",
    "Processing test signal (notch → band-pass → envelope)…":
        "Procesando señal de prueba (notch → paso-banda → envolvente)…",
    # -- procedencia de la referencia de CVM (phases.py) --
    "calibration in this recording": "calibración de este registro",
    "calibration in this recording (1 repetition)":
        "calibración de este registro (1 repetición)",
    "calibration in this recording ({n} repetitions)":
        "calibración de este registro ({n} repeticiones)",
    "calibration as recorded (repetitions not stored)":
        "calibración tal como se grabó (no se guardaron las repeticiones)",
    "no calibration": "sin calibración",
    "The maximal contraction every % MVC on this recording is measured against, and where it came from.":
        "La contracción máxima contra la que se mide cada % de CVM de este registro, y de dónde sale.",
    "Muscle load computed over {n} selected fragment(s) ({d:.2f} s of {full:.2f} s).":
        "Carga muscular calculada sobre {n} fragmento(s) seleccionado(s) ({d:.2f} s de {full:.2f} s).",
    "Choose which parts of the recording the muscle load is measured over — leave out the calibration and any pause. The MVC reference is not affected: it comes from the calibration, wherever in the file that is.":
        "Elija sobre qué partes del registro se mide la carga muscular: deje fuera la calibración y las pausas. La referencia de CVM no se ve afectada, sale de la calibración esté donde esté en el fichero.",
    "Mean normalised activation: {value:.1f} % MVC":
        "Activación media normalizada: {value:.1f} % CVM",
    "MVC normalisation parameters": "Parámetros de normalización CVM",
    "Test EDF:": "EDF de prueba:",
    "Select the EDF file to normalise…": "Seleccionar el archivo EDF a normalizar…",
    "Compute MVC": "Calcular CVM",
    "MVC reference:": "CVM referencia:",
    "Mean activation:": "Activación media:",
    "1. Filtered and rectified EMG signal": "1. Señal EMG filtrada y rectificada",
    "Amplitude ({units})": "Amplitud ({units})",
    "MVC ref: {value:.4f} {units}": "CVM ref: {value:.4f} {units}",
    "2. Envelope and MVC reference amplitude": "2. Envolvente y amplitud de referencia CVM",
    "3. EMG signal normalised to MVC (% MVC)": "3. Señal EMG normalizada al CVM (% CVM)",
    "% MVC": "% CVM",
    "Activation (% MVC)": "Activación (% CVM)",
    "100 % MVC": "100 % CVM",
    "Select test EDF": "Seleccionar EDF de prueba",
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
    "Live signal quality: saturation or a flat (disconnected) signal.":
        "Calidad de señal en vivo: saturación o señal plana (desconectada).",
    # -- analysis tab (region / fragments / CSV) --
    "Export CSV": "Exportar CSV",
    "Analyse only a region:": "Analizar solo una región:",
    "Restrict every metric (spectrum, RMS, fatigue) to the time window below instead of the whole recording.":
        "Restringe todas las métricas (espectro, RMS, fatiga) a la ventana temporal de "
        "abajo en lugar del registro completo.",
    "Select fragments…": "Seleccionar fragmentos…",
    'Student code:': 'Código de alumno/a:',
    "Basic level": "Nivel básico",
    "Intermediate level": "Nivel intermedio",
    "Advanced level": "Nivel avanzado",
    "Muscle": "Músculo",
    'Save tuned EDF…': 'Guardar EDF afinado…',
    'Write a new recording carrying the current selection: the calibration repetitions kept and the fragments of the task. The original is never touched, and the new file says where it came from.': 'Escribe un registro nuevo con la selección vigente: las repeticiones de calibración conservadas y los fragmentos de la tarea. El original no se toca nunca, y el fichero nuevo dice de dónde viene.',
    'Save tuned recording': 'Guardar el registro afinado',
    'The tuned recording cannot replace the one it comes from: tuning discards signal, so its source has to stay.': 'El registro afinado no puede sustituir a aquel del que sale: afinar descarta señal, así que su origen tiene que quedarse.',
    'Could not write the tuned recording: {err}': 'No se pudo escribir el registro afinado: {err}',
    'Tuned recording saved: {name} — {kept}/{total} calibration repetition(s), {secs:.1f} s of {full:.1f} s of the task. The original is untouched.': 'Registro afinado guardado: {name} — {kept}/{total} repetición(es) de calibración, {secs:.1f} s de {full:.1f} s de la tarea. El original queda intacto.',
    'The most recent onsets detected. They all travel in the EDF.': 'Los últimos inicios detectados. Todos viajan dentro del EDF.',
    'Marks are put on by themselves': 'Las marcas se ponen solas',
    'With this ticked the application timestamps each contraction onset as it finds it — the threshold is the resting level plus k standard deviations, and k is the knob beside it. The marks travel inside the EDF, so each effort can be found again during the analysis. Unticked, nothing is written: marking by hand during a recording asks the operator to keep up with a signal that does not wait.': "Con esto marcado, la aplicación anota el instante de cada inicio de "
        "contracción según lo encuentra: el umbral es el nivel de reposo más "
        "k desviaciones típicas, y k es el mando de al lado. Las marcas "
        "viajan dentro del EDF, así que cada esfuerzo se vuelve a encontrar "
        "en el análisis. Sin marcar, no se escribe ninguna: marcar a mano "
        "durante un registro es pedirle al operador que siga el ritmo de una "
        "señal que no espera.",
    '2. Envelope (no calibration in this recording)': '2. Envolvente (este registro no trae calibración)',
    '3. Signal as % MVC — not available': '3. Señal en % CVM — no disponible',
    'Muscle load computed over the recording phase ({d:.2f} s of {full:.2f} s); the calibration and the pause are outside it.': 'Carga muscular calculada sobre la fase de registro ({d:.2f} s de {full:.2f} s); la calibración y la pausa quedan fuera.',
    'MVC reference amplitude: {value:.4f} {units}': 'Amplitud de referencia de CVM: {value:.4f} {units}',
    'This recording carries no calibration, so there is no maximum to express it as a percentage of: no % MVC and no muscle-load analysis. The signal and its envelope do not depend on a reference and are drawn as usual.': 'Este registro no trae calibración, así que no hay un máximo del que expresar porcentajes: ni % CVM ni análisis de carga muscular. La señal y su envolvente no dependen de una referencia y se dibujan como siempre.',
    'This recording marks its own calibration (1 repetition); the reference is recomputed from it.': 'Este registro marca su propia calibración (1 repetición); la referencia se recalcula a partir de ella.',
    'This recording marks its own calibration ({n} repetitions); the reference is recomputed from it.': 'Este registro marca su propia calibración ({n} repeticiones); la referencia se recalcula a partir de ella.',
    'This recording carries a calibration recorded with it ({n} channel(s)).': 'Este registro trae una calibración grabada con él ({n} canal(es)).',
    'No calibration': 'Sin calibración',
    'This recording has no maximal effort in it, so there is no maximum to express the signal as a percentage of: no % MVC and no muscle-load analysis. The signal and its envelope are drawn as usual. Record the session again with the guided flow, which calibrates without stopping the recording.': "Este registro no lleva dentro ningún esfuerzo máximo, así que no "
        "hay un máximo del que expresar porcentajes: ni % CVM ni análisis de "
        "carga muscular. La señal y su envolvente se dibujan como siempre. "
        "Vuelva a grabar la sesión con el flujo guiado, que calibra sin "
        "parar el registro.",
    'none': 'ninguna',
    'Reference from:': 'Referencia tomada de:',
    'Muscle load needs a maximum to be a percentage of, and this recording carries no calibration. Record the session again with the guided flow, which calibrates without stopping the recording.': "La carga muscular necesita un máximo del que ser porcentaje, y este "
        "registro no trae calibración. Vuelva a grabar la sesión con el "
        "flujo guiado, que calibra sin parar el registro.",
    'The recording could not be shown for review: {err}': 'No se pudo mostrar el registro para revisarlo: {err}',
    'Recording just finished (review)': 'Registro recién terminado (revisión)',
    'Envelope of the recording (review)': 'Envolvente del registro (revisión)',
    'Reviewing the recording: {dur:.1f} s. Drag to scroll, wheel to zoom. It goes back to live on the next recording.': "Revisando el registro: {dur:.1f} s. Arrastre para desplazarse y use "
        "la rueda para acercar. Vuelve a la vista en vivo con el siguiente "
        "registro.",
    'warm-up': 'calentamiento',
    'calibration': 'calibración',
    'get ready': 'preparación',
    'recording': 'registro',
    '⚠ «{name}» reaches {peak:.0f} % MVC, and spends {share:.0f} % of the recording above {limit:.0f} %. The calibration did not capture a maximum — the task beat it — so every percentage here is too high.': '⚠ «{name}» llega al {peak:.0f} % de la CVM, y pasa el {share:.0f} % del registro por encima del {limit:.0f} %. La calibración no capturó un máximo —la tarea lo superó—, así que todos los porcentajes de aquí salen inflados.',
    'Analyse the recording first: what each maximal effort was worth is measured from the signal, not stored in the file.': "Analice primero el registro: lo que valió cada esfuerzo máximo se "
        "mide sobre la señal, no viene guardado en el fichero.",
    'This recording carries no calibration. Only sessions recorded with the guided flow mark their maximal efforts.': 'Este registro no trae calibración. Solo las sesiones grabadas con el flujo guiado marcan sus esfuerzos máximos.',
    'This recording carries no calibration spans, so the repetition list stays off. Only sessions recorded with the guided flow have them.': 'Este registro no trae tramos de calibración, así que la lista de repeticiones queda apagada. Solo las sesiones grabadas con el flujo guiado los llevan.',
    '{name}: 1 repetition': '{name}: 1 repetición',
    '{name}: {n} repetitions': '{name}: {n} repeticiones',
    'Calibration in the file — {detail}. The repetition list is available.': 'Calibración en el fichero: {detail}. La lista de repeticiones está disponible.',
    'Calibration repetitions…': 'Repeticiones de la calibración…',
    'Keep or discard the maximal efforts the reference is computed from. Discarding one moves the reference and every % MVC with it — which is what makes a weak repetition worth spotting.': 'Conservar o descartar los esfuerzos máximos con los que se calcula la referencia. Descartar uno mueve la referencia y con ella todos los % CVM: por eso merece la pena localizar una repetición floja.',
    '1 repetition discarded': '1 repetición descartada',
    '{n} repetitions discarded': '{n} repeticiones descartadas',
    'Calibration repetitions': 'Repeticiones de la calibración',
    'Each maximal effort the wizard recorded. Unticking one leaves it out of the reference — and out of every % MVC computed from it.': 'Cada esfuerzo máximo que registró el asistente. Al desmarcar uno queda fuera de la referencia, y por tanto de todos los % CVM que se calculan con ella.',
    'rep {n}': 'rep. {n}',
    '{pct:.0f} % of the best': '{pct:.0f} % de la mejor',
    'other muscle at {pct:.0f} %': 'el otro músculo al {pct:.0f} %',
    "What the other channel reached during this effort, as a share of its own reference. Some of it is the antagonist steadying the joint and some is this muscle's own signal conducted through the tissue; neither can be separated from two bipolar channels, and around 20 % is normal.": 'Lo que alcanzó el otro canal durante este esfuerzo, como porcentaje de su propia referencia. Una parte es el antagonista estabilizando la articulación y otra es la señal de este mismo músculo conducida por el tejido; con dos canales bipolares no se pueden separar, y en torno al 20 % es normal.',
    'Keep at least one repetition: a channel with none is not a calibration with a smaller reference, it is no calibration.': "Conserve al menos una repetición: un canal sin ninguna no es una "
        "calibración con una referencia menor, es no haber calibrado.",
    'unchanged': 'sin cambios',
    'was {before:.4f} mV, {pct:+.0f} %': 'antes {before:.4f} mV, {pct:+.0f} %',
    'Reference with this selection: {value:.4f} mV — {change}': 'Referencia con esta selección: {value:.4f} mV — {change}',
    "Open the assisted editor to keep the significant fragments and discard the rest. Takes precedence over the region above.":
        "Abre el editor asistido para conservar los fragmentos significativos y descartar "
        "el resto. Tiene prioridad sobre la región de arriba.",
    "Cancel": "Cancelar",
    "CSV files (*.csv)": "Archivos CSV (*.csv)",
    "from": "desde",
    "to": "hasta",
    "Cancelling analysis…": "Cancelando análisis…",
    "CSV exported to: {path}": "CSV exportado a: {path}",
    "Could not open the fragment editor: {error}":
        "No se pudo abrir el editor de fragmentos: {error}",
    "CSV export error: {error}": "Error al exportar CSV: {error}",
    "Cancelling…": "Cancelando…",
    # -- fragment-selection widget --
    "Select analysis fragments": "Seleccionar fragmentos de análisis",
    "Envelope low-pass cut-off (Hz): lower = smoother envelope.":
        "Frecuencia de corte del paso-bajo de la envolvente (Hz): menor = envolvente más suave.",
    "Start over": "Empezar de nuevo",
    "Discard the changes and go back to what the app proposed.": "Descarta los cambios y vuelve a la propuesta de la aplicación.",
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
    "band": "banda",
    "envelope": "envolvente",
    "Whole recording will be analysed.": "Se analizará el registro completo.",
    "{n} fragment(s) — {d:.2f} s of {full:.1f} s": "{n} fragmento(s) — {d:.2f} s de {full:.1f} s",

    # ── Recording modes and fine controls ──────────────────────────────
    "Single-muscle contraction": "Contracción de un músculo",
    "Agonist / antagonist contraction": "Contracción agonista / antagonista",
    "Muscle kinematics": "Cinemática muscular",
    "Practical the app is set up for":
        "Práctica para la que la aplicación está configurada",
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
    'Choose "Single-muscle contraction" or "Muscle kinematics" at the top of '
    "the window, or open a two-channel recording.":
        "Elija «Contracción de un músculo» o «Cinemática muscular» en la parte "
        "superior de la ventana, o abra un registro con dos canales.",

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
    "The maximum is recorded inside the session: when the recording starts, "
    "the app asks for a maximal effort of each muscle and writes it into the "
    "same file, before the task. That is the reference; nothing else has to "
    "be chosen here.":
        "El máximo se registra dentro de la propia sesión: al iniciar la "
        "grabación, la aplicación pide un esfuerzo máximo de cada músculo y lo "
        "escribe en el mismo fichero, antes de la tarea. Esa es la referencia; "
        "aquí no hay que elegir nada más.",
    "A recording with no calibration inside it cannot be normalised: without "
    "a maximum there is no percentage, and this tab says so rather than "
    "dividing the signal by itself.":
        "Un registro sin calibración dentro no se puede normalizar: sin un "
        "máximo no hay porcentaje, y esta pestaña lo dice en vez de dividir "
        "la señal por sí misma.",
    "I understand, continue": "Entendido, continuar",

    # ── MVC reference picker ───────────────────────────────────────────
    # ── Auto-normalisation confirmation ────────────────────────────────

    # ── Auto-normalisation marking (screen and report) ─────────────────
    # ── Guided tour: chrome ────────────────────────────────────────────
    "Guide": "Guía",
    "Tour of the application and its measurements":
        "Recorrido por la aplicación y sus medidas",
    "Skip": "Saltar",
    "Back": "Atrás",
    "Next": "Siguiente",
    "Finish": "Terminar",
    "Step {i} of {n}": "Paso {i} de {n}",
    "Stop the recording before starting the guide":
        "Detenga la grabación antes de iniciar la guía",

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
    'Get ready to record': 'Prepárese para grabar',
    'Warm up first': 'Caliente primero',
    'Warming up: {n}': 'Calentando: {n}',
    'Two or three easy contractions of each muscle. The first maximal effort of a session is never the strongest one.':
        "Dos o tres contracciones suaves de cada músculo. El primer esfuerzo "
        "máximo de una sesión nunca es el más fuerte.",
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
    '{muscles}: this is not a maximum. Calibrate again against a resistance the joint cannot move.': "{muscles}: esto no es un máximo. Calibre de nuevo contra una "
        "resistencia que la articulación no pueda mover.",
    '⚠ «{name}»: the recording starts with the muscle already active, so no resting baseline could be measured and contraction onsets were not detected. Record a couple of quiet seconds before the first contraction.': '⚠ «{name}»: el registro empieza con el músculo ya activo, así que no se pudo medir una línea base de reposo y no se han detectado inicios de contracción. Grabe un par de segundos en reposo antes de la primera contracción.',
    '⚠ «{muscle}»: the calibration reached {ref:.3f} mV, only {ratio:.1f}× its resting level. That is not a maximal contraction — every % MVC from now on will be too high by that factor. Calibrate again.': '⚠ «{muscle}»: la calibración llegó a {ref:.3f} mV, solo {ratio:.1f}× su nivel de reposo. Eso no es una contracción máxima: a partir de ahora todos los % de CVM saldrán altos por ese mismo factor. Calibre de nuevo.',
    'These values are not real % MVC: the calibration did not capture a maximum. Calibrate again with a genuinely maximal contraction.': "Estos valores no son % de CVM reales: la calibración no recogió un "
        "máximo. Calibre de nuevo con una contracción verdaderamente máxima.",
    'No contraction detected in «{name}»: it never left its baseline.': 'No se detecta contracción en «{name}»: no sale de su línea base.',
    'Channel separation — while «{muscle}» was at maximum, «{other}» reached {pct:.0f} % of its own reference.': 'Separación entre canales: mientras «{muscle}» estaba al máximo, «{other}» llegó al {pct:.0f} % de su propia referencia.',
    '{other} at {pct:.0f} % during {muscle}': '{other} al {pct:.0f} % durante {muscle}',
    'Channels not separated': 'Canales sin separar',
    '{pairs}. Move the electrode pairs further apart, over the belly of each muscle, and support the forearm.': '{pairs}. Separe más los dos pares de electrodos, cada uno sobre el vientre de su músculo, y apoye el antebrazo.',
    'Co-activation (Falconer-Winter)': 'Coactivación (Falconer-Winter)',
    'Co-activation index': 'Índice de coactivación',
    'Mean activation (% MVC)': 'Activación media (% CVM)',
    'not reported — {name} below {floor:.0f} % MVC': 'no se informa — {name} por debajo del {floor:.0f} % de CVM',
    "not reported — no MVC reference for one of the channels": "no se informa — falta la referencia de CVM en uno de los canales",
    'not reported — window too short': 'no se informa — ventana demasiado corta',
    'not reported — no activation above rest': 'no se informa — sin activación por encima del reposo',
    "Whole recording — accept the fragments for one value per window": "Registro completo — acepte los fragmentos para tener un valor por "
        "ventana",
    'Window': 'Ventana',
    '9. Overlaid envelopes (agonist/antagonist), % MVC': '9. Envolventes superpuestas (agonista/antagonista), % CVM',
    'Millivolts are not comparable between two muscles. Calibrate MVC while recording to compare them.': 'Los milivoltios no son comparables entre dos músculos. Calibre la CVM mientras graba para poder compararlos.',
    'Connecting the sensor': 'Conexión del sensor',
    'How to place the accelerometer': 'Cómo situar el acelerómetro',
    'Following the recording remotely': 'Seguimiento del registro de forma remota',
    'Every member of the group making the recording can watch the trace on their own mobile device. This is done by scanning the QR code the application generates.': "Cada miembro del grupo que hace el registro puede ver el trazado en "
        "su propio móvil. Basta con escanear el código QR que genera la "
        "aplicación.",
    'Calibrating the contraction': 'Calibración de la contracción',
    'A maximal voluntary contraction is asked for, and it becomes the reference against which the live load bars and the measurements are expressed, making contractions easier to compare.': 'Se solicita una contracción voluntaria máxima que será la referencia respecto a la que se representan las barras de carga en vivo y las medidas, facilitando la comparación entre contracciones.',
    'The basic panels': 'Paneles básicos',
    'Raw signal: the signal from the set of fibres that are contracting. Normalised envelope: shows how activation changes over time, which is what is compared between efforts. Power spectrum: how the muscle activity is distributed across the different frequencies recorded.': 'Señal en bruto: señal del conjunto de las fibras que se están contrayendo. Envolvente normalizada: muestra cómo cambia la activación en el tiempo, que es lo que se compara entre esfuerzos. Espectro de potencia: cómo se reparte la actividad muscular entre las diferentes frecuencias registradas.',
    "Choose the practical first": "Elegir primero la práctica",
    "Show this guide next time": "Mostrar la guía la próxima vez",
    "Start recording and ask for the contraction. Watch the live trace: at "
    "rest it should be a flat line with only baseline noise. A signal that "
    "never returns to baseline usually means a loose electrode or a poor "
    "contact, not a tonic muscle.":
        "Se inicia el registro y se pide la contracción. Conviene vigilar el trazado en vivo: "
        "en reposo debe ser una línea plana con solo ruido de base. Una señal "
        "que nunca vuelve a la línea de base suele indicar un electrodo suelto "
        "o mal contacto, no un músculo tónico.",
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
    "Why normalise at all": "Por qué normalizar",
    "Muscle load": "Carga muscular",

    # ── Tutorial: texto revisado por el autor (22-ago-2026) ──────────
    'Quick guide':
        'Guía rápida',
    'Devices the application supports':
        'Dispositivos soportados por la aplicación',
    'The recording can be made with either of two devices: BITalino (Bluetooth) or Arduino (USB).':
        'El registro se puede hacer con uno cualquiera de dos dispositivos: BITalino (Bluetooth) o Arduino (USB).',
    'Recording':
        'Registro',
    'A raw amplitude cannot be compared between two people, or between two sessions of the same person: it depends on the electrodes, the skin and the fat beneath it. Expressing every value as a percentage of the maximal contraction cancels all of that out, because the two amplitudes share the same electrodes and the same skin: what is left is how hard the muscle is working. The maximum is inside the recording: the session calibrates without stopping, so nothing else has to be chosen here.':
        'Una amplitud bruta no se puede comparar entre dos personas, ni entre dos sesiones de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. Expresar cada valor como porcentaje de la contracción máxima cancela todo eso, porque las dos amplitudes comparten los mismos electrodos y la misma piel: lo que queda es cuánto está trabajando el músculo. El máximo está dentro del registro: la sesión calibra sin parar, así que aquí no hay nada más que elegir.',
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

    # ── Ensayo del asistente F-V (fv_rehearsal_dialog.py) ─────────
    'Rehearse…': 'Ensayar…',
    "It emulates the entire guided procedure with the same warnings, in the "
    "same order, with a synthetic record. Each step is explained and ends "
    "with the simulated force-velocity study.":
        "Emula todo el procedimiento guiado con los mismos avisos, en el mismo "
        "orden, con un registro sintético. Se explica cada paso y termina con "
        "el estudio fuerza-velocidad simulado.",
    "Rehearsal — guided force-velocity acquisition":
        "Ensayo — adquisición guiada fuerza-velocidad",
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
    'maximum': "máximo",
    '{kg:g} kg': '{kg:g} kg',
    'Get ready — the maximum comes first, with no weight.': "Prepárese: primero el máximo, sin peso.",
    'A sustained maximum, held for a few seconds.': "Un máximo sostenido, mantenido unos segundos.",
    'Recovery, and the first weight is set up.': 'Recuperación, y se prepara el primer peso.',
    'Prepare {kg:g} kg — take the weight and the starting position.': 'Prepare {kg:g} kg: coja el peso y sitúese en la posición de partida.',
    'Lift {kg:g} kg — one quick movement, not a hold.': 'Levante {kg:g} kg: un movimiento rápido, no un mantenimiento.',
    'Relax, and change the weight.': 'Relaje, y cambie el peso.',
    'Recorded — the loads are already in the file.': 'Registrado: las cargas ya están en el archivo.',
    'The maximum is recorded before any load: it is the 100 % the other contractions are read against. Doing it first also keeps it clear of the fatigue the loads are about to cause.': "El máximo se registra antes que ninguna carga: es el 100 % con el "
        "que se leen las demás contracciones. Hacerlo primero lo mantiene "
        "además libre de la fatiga que van a producir las cargas.",
    'Held, because a true maximum takes about a second to reach. It is isometric — nothing moves, so the accelerometer stays flat here. This contraction sets the amplitude reference, not a velocity.': "Se mantiene porque alcanzar un máximo de verdad lleva alrededor de "
        "un segundo. Es isométrica: no se mueve nada, así que aquí el "
        "acelerómetro permanece plano. Esta contracción fija la referencia "
        "de amplitud, no una velocidad.",
    'Longer than the pauses between loads: the subject has just given a maximum, and the first load should not be lifted tired.': "Más larga que las pausas entre cargas: el sujeto acaba de hacer un "
        "máximo, y la primera carga no debe levantarse ya cansado.",
    'Nothing is being recorded as a repetition yet. The countdown is there so the load is handed over and the position taken without hurrying.': 'Todavía no se registra nada como repetición. La cuenta atrás está para entregar la carga y tomar la posición sin prisas.',
    'The study reads the shortening velocity from the accelerometer, and a slow or held contraction has none. As this cue appears the application writes a marker into the file with the load — which is why the study can fill the load column by itself.': 'El estudio lee del acelerómetro la velocidad de acortamiento, y una contracción lenta o mantenida no la tiene. Al aparecer este aviso la aplicación escribe en el archivo una marca con la carga: por eso el estudio puede rellenar solo la columna de cargas.',
    'Short on purpose: long enough to change the load, not long enough to lose the thread. If more than one repetition per load was asked for, this is where it goes back for another.': 'Corta a propósito: lo justo para cambiar la carga, no tanto como para perder el hilo. Si se pidió más de una repetición por carga, aquí es donde vuelve a por otra.',
    'Stop the recording and open the force-velocity study in the Analysis tab. Nothing has to be typed: every window carries its load.': 'Detenga la grabación y abra el estudio fuerza-velocidad en la pestaña de análisis. No hay que teclear nada: cada ventana lleva su carga.',

    "page {n}": "página {n}",
    'Add a row for a contraction the app did not find.': 'Añade una fila para una contracción que la aplicación no encontró.',
    'Delete the selected row.': 'Borra la fila seleccionada.',
    'An analysis is already running; wait for it to finish.': 'Ya hay un análisis en marcha; espere a que termine.',
    'A calculation is already running; wait for it to finish.': 'Ya hay un cálculo en marcha; espere a que termine.',
    'Unexpected error': 'Error inesperado',
    'The application hit an error it did not expect. What you were doing may not have been saved.\n\nThe details have been written to:\n{path}\n\nSend that file on, with a note of what you were doing at the time.': 'La aplicación ha encontrado un error que no esperaba. Puede que lo que estaba haciendo no se haya guardado.\n\nLos detalles se han escrito en:\n{path}\n\nEnvíe ese fichero, indicando qué estaba haciendo en ese momento.',
    'The application hit an error it did not expect, and could not write the details to a file.': 'La aplicación ha encontrado un error que no esperaba, y no ha podido escribir los detalles en un fichero.',
    'What it measures': 'Qué mide',
    'Of all the activity in the two muscles, how much of it was shared — how much they worked at the same time. 0 % means one worked and the other did not; 100 % means both did the same thing throughout.': 'De toda la actividad de los dos músculos, qué parte fue compartida: cuánto trabajaron a la vez. 0 % significa que uno trabajó y el otro no; 100 %, que los dos hicieron lo mismo todo el rato.',
    'Why one row per window': 'Por qué una fila por ventana',
    'The index compares the shape of the two envelopes, so it only means something over a stretch in which one thing was being done. Over a whole recording that mixes rest, flexion and grip it still produces a number, and that number is not a measurement of anything.': 'El índice compara la forma de las dos envolventes, así que solo significa algo en un tramo en el que se estaba haciendo una cosa. Sobre un registro entero que mezcla reposo, flexión y presa sigue saliendo un número, y ese número no mide nada.',
    'Where the windows come from': 'De dónde salen las ventanas',
    'From «{button}», at the top of this tab. Each row of that dialogue has a name, which the app fills in itself with the muscle that led the contraction. Consecutive rows with the same name become one window here — six flexions in a row give one row in this table, not six.': 'Del botón «{button}», arriba en esta misma pestaña. Cada fila de ese cuadro lleva un nombre, que la aplicación rellena sola con el músculo que llevó esa contracción. Las filas seguidas con el mismo nombre se juntan aquí en una sola ventana: seis flexiones seguidas dan una fila en esta tabla, no seis.',
    'If it says «whole recording»': 'Si pone «registro completo»',
    'Then no window has a name: either the fragment editor has not been opened, or the names were cleared. Open it and accept what it proposes.': 'Entonces ninguna ventana tiene nombre: o no se ha abierto el cuadro de fragmentos, o se han borrado los nombres. Ábralo y acepte lo que propone.',
    'Whole recording: with no named windows this number does not measure anything. Open «{button}» and accept what it proposes.': 'Registro completo: sin ventanas con nombre este número no mide nada. Abra «{button}» y acepte lo que propone.',
    'Running the first analysis…': 'Haciendo el primer análisis…',
    'Running the first computation…': 'Haciendo el primer cálculo…',
    'Folder:': 'Carpeta:',
    'Co-activation': 'Coactivación',
    'More panels…': 'Más paneles…',
    'The rectified signal smoothed with a 5 Hz low-pass filter, computed as the samples arrive: it follows the level of activation.': 'La señal rectificada y suavizada con un filtro paso-bajo de 5 Hz, calculada según llegan las muestras: sigue el nivel de activación.',
    'Next: «{button}». It decides which maximal efforts set the reference, and every % MVC below is measured against it — so it goes before choosing the fragments.': 'Siguiente: «{button}». Decide qué esfuerzos máximos fijan la referencia, y todos los % CVM de abajo se miden contra ella, así que va antes de elegir los fragmentos.',
    'Next: «{button}», to drop any contraction that did not come out well. Press «Use these fragments» even if you change nothing: that is what applies them.': 'Siguiente: «{button}», para quitar las contracciones que no salieran bien. Pulse «Usar estos fragmentos» aunque no cambie nada: es lo que las aplica.',
    'The «Muscle» column says which of the two led each contraction; the app fills it in by comparing them. Change it if you disagree. Consecutive rows with the same name become a single window of the co-activation table, so a run of flexions is measured as one.': 'La columna «Músculo» dice cuál de los dos llevó cada contracción; la aplicación la rellena comparándolos. Cámbiela si no está de acuerdo. Las filas seguidas con el mismo nombre pasan a ser una sola ventana de la tabla de coactivación, de modo que una serie de flexiones se mide como una.',
    'Which muscle led this contraction. The app works it out by comparing the two; change it if you disagree, or empty it to leave the contraction out of the co-activation table.': 'Qué músculo llevó esta contracción. La aplicación lo deduce comparándolos; cámbielo si no está de acuerdo, o déjelo vacío para que la contracción no entre en la tabla de coactivación.',
    'Re-run the analysis with the settings changed since the last one. It lights up only when there is something to redo: opening a file analyses it, and the two editors re-analyse when you accept them.': 'Vuelve a hacer el análisis con los ajustes que hayan cambiado desde el anterior. Solo se enciende cuando hay algo que rehacer: abrir un fichero lo analiza, y los dos editores reanalizan al aceptarlos.',
    # --- fragment editor with live adjustment, and the two summary charts ---
    'Each row is one contraction found in the recording. Uncheck the ones not worth analysing — a movement done wrong, a tug on the cable — and only the rest is analysed, joined up as if recorded in one go. Press «Use these fragments» even if you change nothing: that is what applies them.': 'Cada fila es una contracción encontrada en el registro. Desmarque las que no merezca la pena analizar (un movimiento mal hecho, un tirón del cable) y se analiza solo el resto, unido como si se hubiera registrado de una vez. Pulse «Usar estos fragmentos» aunque no cambie nada: es lo que los aplica.',
    'Adjust the proposal': 'Ajustar la propuesta',
    'Sensitivity': 'Sensibilidad',
    'lower finds more contractions; higher, fewer': 'más baja encuentra más contracciones; más alta, menos',
    'Co-activation when the weaker muscle exceeds': 'Coactivación cuando el músculo menor supera el',
    '% of the stronger': '% del mayor',
    'Fine adjustment': 'Ajuste fino',
    'Minimum duration (s)': 'Duración mínima (s)',
    'Join gaps shorter than (s)': 'Unir huecos menores de (s)',
    'Split between contractions': 'Separación entre contracciones',
    'lower splits a series more readily; higher keeps it together': 'más baja separa una serie con más facilidad; más alta la mantiene unida',
    'Reset': 'Restablecer',
    'Moving a setting rebuilds the proposal; rows edited by hand are replaced.': 'Al mover un ajuste se rehace la propuesta; las filas editadas a mano se sustituyen.',
    'Click a shaded stretch to keep or drop it.': 'Pulse sobre un tramo sombreado para conservarlo o descartarlo.',
    'activity threshold': 'umbral de actividad',
    'Table': 'Tabla',
    'Chart': 'Gráfico',
    'Contraction': 'Contracción',
    'Mean activation (% MVC) · index (%)': 'Activación media (% CVM) · índice (%)',
    'not reported': 'no se informa',
    # --- the contraction chart as two panels: the series and its relation ---
    'Amplitude against MDF (JASA)': 'Amplitud frente a MDF (JASA)',
    'Who leads each contraction': 'Quién lleva cada contracción',
    'fatigue': 'fatiga',
    'more force': 'más fuerza',
    'less force': 'menos fuerza',
    'recovery': 'recuperación',
    '{name} leads': 'lidera {name}',
    'The relation needs at least two contractions with an MDF.':
        'La relación necesita al menos dos contracciones con MDF.',
    'No contractions': 'Sin contracciones',
    'Co-activation index (%)': 'Índice de coactivación (%)',
    '(1 repetition)': '(1 repetición)',
    'How to read the chart': 'Cómo leer el gráfico',
    'One line per window, its seconds on the right. A purple bar is the index, '
    'with the number in it. A gold block means the index is not reported, and '
    'the small square beside it is the colour of the muscle that worked alone — '
    'in a clean flexion or extension that is the correct answer, not a fault. No '
    'square at all is a rest. The two mean activations are in the table.':
        'Una línea por ventana, con sus segundos a la derecha. Una barra morada es '
        'el índice, con el número dentro. Un bloque dorado quiere decir que el '
        'índice no se informa, y el cuadradito de al lado lleva el color del músculo '
        'que trabajó solo: en una flexión o una extensión limpias esa es la '
        'respuesta correcta, no un fallo. Sin cuadradito, es un reposo. Las dos '
        'activaciones medias están en la tabla.',
    '({n} repetitions)': '({n} repeticiones)',
    '(as recorded)': '(tal como se grabó)',
    'Relation': 'Relación',
    'Series': 'Serie',
    'Category': 'Categoría',
    'Who leads': 'Quién lidera',
    'By load': 'Por carga',
    'One view at a time; the numbers behind them are the last.':
        'Una vista cada vez; los números que hay detrás son la última.',
    'The chart, or the numbers behind it.': 'El gráfico, o los números que hay detrás.',
    'Mean per category, and each contraction': 'Media por categoría, y cada contracción',
    'Who leads, and by how much': 'Quién lidera, y por cuánto',
    'only {name}': 'solo {name}',
    'equal': 'iguales',
    'floor 5 %': 'suelo 5 %',
    'Amplitude by load': 'Amplitud por carga',
    'EMD by load': 'EMD por carga',
    'Velocity by load': 'Velocidad por carga',
    '1 · Rehearse…': '1 · Ensayar…',
    '2 · F-V parameters…': '2 · Parámetros de la F-V…',
    'F-V parameters…': 'Parámetros de la F-V…',
    "Optional, and it needs no hardware: it plays the whole procedure over a "
    "synthetic recording, with the same prompts in the same order, and ends "
    "in the force-velocity study. Skip it if you know the procedure.":
        "Opcional, y no necesita hardware: recorre todo el procedimiento sobre "
        "un registro sintético, con los mismos avisos y en el mismo orden, y "
        "termina en el estudio fuerza-velocidad. Sáltelo si ya conoce el "
        "procedimiento.",
    "Next: «{button}». The loads in order and the lifts per load. Nothing "
    "starts there; it is kept for the recording.":
        "Ahora: «{button}». Las cargas en orden y los levantamientos por "
        "carga. Ahí no empieza nada; se guarda para la grabación.",
    "Next: «{button}». It asks for the file name, calibrates the maximum, and "
    "then cues each load in turn. Esc stops the guidance at any point.":
        "Ahora: «{button}». Pide el nombre del archivo, calibra el máximo y "
        "después va pidiendo cada carga. Esc interrumpe la guía en cualquier "
        "momento.",
    "Next: «{button}». It writes a new recording with the repetitions and the "
    "fragments you have just chosen, so reopening it gives these same "
    "numbers. The original is not touched.":
        "Ahora: «{button}». Escribe un registro nuevo con las repeticiones y "
        "los fragmentos que acaba de elegir, de modo que al reabrirlo dé estos "
        "mismos números. El original no se toca.",
    "Tuned the recording in Analysis? Open the «_tuned» file here with "
    "«Browse…» and press «Compute MVC»: it carries the repetitions and the "
    "fragments that were chosen there.":
        "¿Ha afinado el registro en Análisis? Abra aquí el archivo «_tuned» "
        "con «Explorar…» y pulse «Calcular CVM»: lleva las repeticiones y los "
        "fragmentos que se eligieron allí.",
    'Optional: to learn the procedure before anyone holds a weight. Skip it if you know it.':
        'Opcional: para entender el procedimiento antes de que nadie sostenga un peso. Sáltelo si ya lo conoce.',
    'The loads in order, the lifts per load and the seconds of preparation. Kept for the '
    'recording; nothing starts here.':
        'Las cargas en orden, los levantamientos por carga y los segundos de preparación. '
        'Se guardan para la grabación; aquí no empieza nada.',
    '3 · Start recording: the maximum is calibrated first, then each load is cued.':
        '3 · Iniciar grabación: primero se calibra el máximo y después se va pidiendo cada carga.',
    'No force-velocity plan: set the loads in «F-V parameters…» first.':
        'No hay plan de fuerza-velocidad: fije antes las cargas en «Parámetros de la F-V…».',
    'Recording to {file}.': 'Grabando en {file}.',
    'First the calibration of the maximum; then the force-velocity study: {plan}.':
        'Primero la calibración del máximo; después el estudio fuerza-velocidad: {plan}.',
    'The maximum is already calibrated; the force-velocity study starts now: {plan}.':
        'El máximo ya está calibrado; el estudio fuerza-velocidad empieza ahora: {plan}.',
    'Force-velocity study: {n} loads, {r} lifts each, lightest first.':
        'Estudio fuerza-velocidad: {n} cargas, {r} levantamientos por carga, de menor a mayor.',
    'Now the force-velocity study': 'Ahora, el estudio fuerza-velocidad',
    '{n} loads, {r} lifts each, lightest first. Set up the first load.':
        '{n} cargas, {r} levantamientos por carga, de menor a mayor. Prepare la primera carga.',
    'The force-velocity study, step by step': 'El estudio fuerza-velocidad, paso a paso',
    'A muscle shortens more slowly the heavier the load it moves, and the power it delivers '
    'is greatest at intermediate loads. This box is the sequence that measures it. Three '
    'steps, and only the first two are here.\n\n'
    'First, «Rehearse…», which is optional and needs no hardware: it plays the whole '
    'procedure over a synthetic recording, with the same prompts in the same order, and ends '
    'in the force-velocity study itself. It is worth one run before anyone holds a weight; '
    'skip it once you know the procedure.\n\n'
    'Second, «F-V parameters…»: the loads in order, the lifts per load, the seconds to '
    'prepare each one and the seconds of the lift. Nothing starts there — the plan is kept '
    'for the recording.\n\n'
    'Third, «Start recording», in the box to the left. It runs the whole session on its own: '
    'it asks for the file name, calibrates the maximum first (a warm-up and three brief '
    'maximal efforts against something that cannot move), announces the study, and then cues '
    'one quick lift for each repetition of each load, marking every one in the file with its '
    'load. There is no isometric maximum without load in between: the calibration was that. '
    '«Cancel guide (Esc)» stops the guidance at any moment and the recording goes on.\n\n'
    'In the Analysis tab the contraction table then holds one row per lift, and the '
    'force-velocity study reads those rows to draw the load-velocity, force-velocity, power '
    'and recruitment curves.':
        'Un músculo se acorta más despacio cuanto mayor es la carga que mueve, y la potencia '
        'que entrega es máxima con cargas intermedias. Esta caja es la secuencia que lo mide. '
        'Son tres pasos, y aquí solo están los dos primeros.\n\n'
        'Primero, «Ensayar…», que es opcional y no necesita hardware: recorre el procedimiento '
        'entero sobre un registro sintético, con los mismos avisos y en el mismo orden, y '
        'termina en el propio estudio fuerza-velocidad. Merece una pasada antes de que nadie '
        'sostenga un peso; sáltelo cuando ya conozca el procedimiento.\n\n'
        'Segundo, «Parámetros de la F-V…»: las cargas en orden, los levantamientos por carga, '
        'los segundos para preparar cada una y los segundos de levantamiento. Ahí no empieza '
        'nada: el plan se guarda para la grabación.\n\n'
        'Tercero, «Iniciar grabación», en la caja de la izquierda. Lleva la sesión entera '
        'sola: pide el nombre del archivo, calibra primero el máximo (un calentamiento y tres '
        'esfuerzos máximos breves contra algo que no se pueda mover), anuncia el estudio y '
        'después va pidiendo un levantamiento rápido por cada repetición de cada carga, '
        'marcando cada uno en el archivo con su carga. No hay máximo isométrico en vacío entre '
        'medias: la calibración ya lo fue. «Cancelar guía (Esc)» detiene la guía en cualquier '
        'momento y la grabación sigue.\n\n'
        'En la pestaña de Análisis la tabla de contracciones trae entonces una fila por '
        'levantamiento, y el estudio fuerza-velocidad lee esas filas para dibujar las curvas '
        'carga-velocidad, fuerza-velocidad, potencia y reclutamiento.',
    'Each point is a contraction, numbered and joined in order; a drift towards the top '
    'left — more amplitude, less frequency — is fatigue.':
        'Cada punto es una contracción, numeradas y unidas en orden; una deriva hacia arriba '
        'a la izquierda (más amplitud, menos frecuencia) es fatiga.',
    'The rows are those of the contraction table: to change them, edit the '
    'fragments in the Analysis tab.':
        'Las filas son las de la tabla de contracciones: para cambiarlas, edite los '
        'fragmentos en la pestaña de Análisis.',
    'Nothing measured for this.': 'No hay medida de esto.',
    'Muscle on A1 · accelerometer on A2': 'Músculo en A1 · acelerómetro en A2',
    'Muscle — e.g. biceps': 'Músculo — p. ej. bíceps',
    'Cancel guide (Esc)': 'Cancelar guía (Esc)',
    'Stop the guided procedure now; the recording goes on.':
        'Detiene ahora el procedimiento guiado; la grabación sigue.',
    'Calibration cancelled; the recording goes on.':
        'Calibración cancelada; la grabación sigue.',
    'Force-velocity acquisition cancelled; the recording goes on.':
        'Adquisición fuerza-velocidad cancelada; la grabación sigue.',
    'MDF by load': 'MDF por carga',
    'This view needs two muscles.': 'Esta vista necesita dos músculos.',
    'The box shows one view at a time, chosen on its title line. «Relation» is the '
    'panel a conclusion is read off: amplitude against MDF with one muscle, where a '
    'drift towards more amplitude and less frequency is fatigue; one muscle against '
    'the other with two, where a flexion lies on one axis, an extension on the other '
    'and a grip in the co-activation wedge. «Category» groups the contractions by who '
    'led them, with each muscle\'s mean; «Who leads» is one bar per contraction, to '
    'the right when the first muscle led and to the left when the second did, with '
    'the band where both count as co-activation. «Series» follows the contractions '
    'in order with the fitted trend; «By load» groups them by the load of the guided '
    'acquisition. «Table» is the numbers behind them all.':
        'El cuadro enseña una vista cada vez, elegida en su línea de título. «Relación» '
        'es el panel del que se saca la conclusión: la amplitud frente a la MDF con un '
        'músculo, donde una deriva hacia más amplitud y menos frecuencia es fatiga; un '
        'músculo frente al otro con dos, donde una flexión cae sobre un eje, una '
        'extensión sobre el otro y una presa en la cuña de coactivación. «Categoría» '
        'agrupa las contracciones según quién las llevó, con la media de cada músculo; '
        '«Quién lidera» es una barra por contracción, hacia la derecha cuando llevó el '
        'primer músculo y hacia la izquierda cuando llevó el segundo, con la banda en la '
        'que los dos cuentan como coactivación. «Serie» sigue las contracciones en orden '
        'con la recta de tendencia; «Por carga» las agrupa por la carga de la '
        'adquisición guiada. «Tabla» son los números que hay detrás de todas.',
    'This view needs the load markers of the guided force-velocity acquisition.':
        'Esta vista necesita los marcadores de carga de la adquisición fuerza-velocidad guiada.',
    '{name} {slope:+.1f} %/contr.': '{name} {slope:+.1f} %/contr.',
    '{name} {slope:+.2f} mV/contr.': '{name} {slope:+.2f} mV/contr.',
    'MDF {slope:+.1f} Hz/contr.': 'MDF {slope:+.1f} Hz/contr.',
}
