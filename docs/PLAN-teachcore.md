# Plan · teachcore, el paquete común de emgteach, ecgteach y eegteach

**Estado: solo plan.** No se ha tocado ningún repositorio para hacerlo. Las tres
copias se han leído de `origin/main` el 14 de octubre de 2026: emgteach
`bd87cb1`, ecgteach `17e0808` y eegteach `b46c52c`. Responde al encargo
«teachcore · plan» del 14 de octubre, punto por punto. Se distingue lo
**comprobado** en el código de lo que es **inferencia**, que va marcado así.

Para comparar se han normalizado los nombres de paquete (`emgteach`,
`ecgteach`, `eegteach` → `XXteach`) y de señal (`EMG`, `ECG`, `EEG` → `XX`).
Las cifras de «líneas distintas» cuentan las líneas `+`/`−` de un diff
unificado de las copias normalizadas.

---

## 0. Resumen

- **De los once módulos candidatos, solo cuatro se pueden mover tal cual:**
  `difusion.py`, `devices/factory.py`, `devices/arduino.py` y, entre
  ecgteach y eegteach, casi todos los demás. emgteach diverge en casi todo,
  y en dos casos (`help_button.py`, `bitalino_sim.py`) las copias no son
  versiones de un mismo módulo sino diseños distintos.
- **La mayor parte del trabajo no es mover ficheros, sino decidir en cada
  diferencia** cuál de las copias es la buena (§1) y abrir unos pocos puntos
  de inyección: la ganancia y la unidad del sensor, el generador de la placa
  simulada, el traductor, el nombre de la aplicación y la página de la
  difusión.
- **Recomendación:** hacerlo, pero en dos tiempos.
  - **Primero, un núcleo sin Qt:** devices, `difusion`, `crash`, `recovery`
    y el protocolo de la placa simulada.
  - **Después, lo de interfaz:** `broadcast`, `logger` y `help_button`.

  emgteach entra la última, como dice el encargo, y no antes de su 3.9.0.
  §8 da los riesgos y la opción de no hacerlo.

---

## 1. Módulo a módulo: diferencias reales y veredicto

| Módulo | Líneas emg / ecg / eeg | ecg ↔ eeg | ecg/eeg ↔ emg | Veredicto |
|---|---|---|---|---|
| `difusion.py` | 89 / 89 / 89 | 0 | 0 | **idéntico** |
| `devices/factory.py` | 97 / 97 / 97 | 0 | 0 | **idéntico** (solo nombres de paquete) |
| `devices/arduino.py` | 258 / 258 / 258 | 0 | 2 | **solo de nombre** (un comentario) |
| `devices/base.py` | 158 / 145 / 145 | 0 | 71 | **comportamiento (API)** con emg |
| `devices/bitalino.py` | 890 / 929 / 932 | 13 | 289 | **comportamiento**, también entre ecg y eeg |
| `devices/bitalino_sim.py` | 337 / 383 / 372 | 237 | 362 | protocolo idéntico, **señal distinta** (§2) |
| `broadcast.py` | 463 / 429 / 429 | 0 | 104 | **comportamiento** con emg |
| `crash.py` | 145 / 141 / 141 | 0 | 16 | **comportamiento** con emg |
| `recovery.py` | 234 / 237 / 237 | 10 (solo docstrings) | 41 | **comportamiento** con emg |
| `gui/widgets/logger.py` | 48 / 39 / 39 | 0 | 13 | **comportamiento** con emg |
| `gui/widgets/help_button.py` | 97 / 31 / 31 | 0 | 112 | **dos componentes distintos** |

### 1.1 `difusion.py`: idéntico

Es el mismo fichero en las tres apps. El CHANGELOG de ecgteach lo da como
«the same module as emgteach 3.7.2», y eegteach lo copió de ecgteach. Es el
primer candidato y el más fácil.

### 1.2 `devices/factory.py`: idéntico

Exporta `BACKEND_BITALINO`, `BACKEND_ARDUINO`, `DeviceBuilder`, `_REGISTRY`,
`register_device`, `available_backends` y `create_device(backend_id,
**kwargs)`, que pasa los kwargs sin tocarlos. `devices/__init__.py` también es
igual en las tres. Las pruebas de las tres apps usan `_REGISTRY`, así que el
paquete debe seguir exponiéndolo.

### 1.3 `devices/arduino.py`: solo de nombre

La única diferencia es un comentario. En emgteach, la línea 107 dice
«(see _raw_to_mv)», un método que Arduino no tiene; en ecg y eeg dice «(see
read)» desde el 14 de octubre (`c2fbda5` y `231ab1a`). **Copia buena:
ecg/eeg.** En las tres, la conversión es fija en mV con `_GAIN = 200.0`
(MyoWare) y no admite ganancia ni unidad.

### 1.4 `devices/base.py`: ecg y eeg idénticos; con emg, diferencias de API

1. **`quantisation_step`** (propiedad, 0.0 por defecto). Solo está en
   ecg/eeg, que la usan en `diagnostics.py` y en la pestaña de adquisición
   (el `lsb=` del monitor de calidad). En eegteach, `test_sensor_gain.py`
   exige ese 0.0 por defecto. emgteach no la usa.
2. **`lost_frames` y `crc_errors`** (0 por defecto). En ecg/eeg están en la
   clase base. En emgteach solo las tiene `BitalinoDevice`, y el worker las
   lee con `getattr(…, 0)`.
3. **`instruct(channel_index, level, *, repeat_s=None)`**. Solo está en
   emgteach, como método concreto que no hace nada. Es por donde la
   calibración de CVM manda órdenes a la placa simulada. Lo usan el worker,
   la pestaña y unas 26 pruebas.

**Copia buena: la base de ecg/eeg más `instruct` de emgteach** (sin acción
por defecto). Ninguna de las dos copias contiene a la otra, y las cuatro
adiciones no obligan a cambiar ningún backend existente. `force_close` es
abstracto en las tres.

### 1.5 `devices/bitalino.py`: diferencias de comportamiento, también entre ecg y eeg

**Entre ecg y eeg hay una diferencia real.** La normalización la esconde,
porque los tres nombres de sensor pasan a `XX`:

- **Ganancia por defecto si no se da `sensor_gain`:** en ecgteach es
  `SENSOR_GAINS["EMG"]` (1009); en eegteach, `SENSOR_GAINS["EEG"]` (40 000),
  desde `f1eff3e` (21 de agosto, «stop the EEG path falling back to the EMG
  gain»).
- La prueba de ecgteach `test_default_device_stays_on_the_emg_lineage`
  **exige** 1009 y mV por defecto. El ECG solo sale bien porque la pestaña y
  el diagnóstico pasan `**profile.device_kwargs()`.

**Entre ecg/eeg y emgteach:**

1. **Conversión a unidades físicas.**
   - emgteach: `_GAIN_EMG = 1009.0` fijo, siempre en mV, con `_raw_to_mv` y
     `raw_to_mv`.
   - ecg/eeg: `SENSOR_GAINS = {"EMG": 1009, "ECG": 1100, "EEG": 40000}`,
     `_UNIT_SCALE`, `__init__(…, sensor_gain=None, unit="mV")` con
     validación, `_raw_to_unit(raw, slot)` (la resolución depende de la
     ranura de la trama), y las propiedades `quantisation_step`,
     `sensor_gain` y `unit`.
   - Con ganancia 1009 y unidad mV, las dos conversiones dan lo mismo
     (inferencia por la fórmula).
2. **`instruct()`**: solo emgteach lo tiene. Reenvía la orden al puerto
   simulado; con una placa real no hace nada.
3. **Placa simulada.**
   - ecg/eeg eligen un modelo por la dirección («simulada alfa»…), el nombre
     del dispositivo es «BITalino (<modelo>)», y una dirección que no nombra
     ningún modelo da un error.
   - emgteach tiene un solo modelo y el nombre fijo «BITalino (simulated)»,
     que llega a la cabecera del EDF.
4. **Solo de nombre:**
   - `_abandonar`/`_comprobar_abandono` en emgteach y
     `_abandoned`/`_check_abandoned` en ecg/eeg (nadie de fuera los usa);
   - docstrings, por ejemplo el de `adc_max_for_slot` en emgteach, que dice
     algo de ecgteach que ya no es cierto desde el 29 de septiembre.
5. **Iguales en las tres:**
   - la resincronización confirmada por la trama siguiente;
   - `lost_frames`/`crc_errors`;
   - el ACC escalado según su ranura;
   - `force_close` sin bloqueo;
   - el `write_timeout` de 2 s;
   - los reintentos ante el error 1168 de Windows.

**Copia buena: ecg/eeg**, más `instruct()` de emgteach, y **sin ganancia por
defecto ligada a una señal**. El paquete común no debe saber de ECG, EEG ni
EMG: cada app pasa su `sensor_gain` y su `unit` desde el perfil
(`profile.device_kwargs()`), como ya hacen ecg/eeg. Para emgteach eso
significa crear el dispositivo con `sensor_gain=1009, unit="mV"`. Hoy no lo
hace: lo crea sin argumentos en `gui/tabs/acquisition.py` y en
`diagnostics.py`. La prueba de ecgteach que exige el 1009 por defecto
tendría que cambiar.

**Lo que emgteach usa de su API propia y habría que adaptar:**

- `acquisition.py:1863`: `getattr(clase, "_GAIN_EMG", None) or clase._GAIN`
  para la escala del panel. La revisión del 13 de octubre (encargo E) ya
  proponía un método público tipo `full_scale_mv()`.
- `test_arreglos_pantalla.py`, que lee `BitalinoDevice._GAIN_EMG`.
- `raw_to_mv`, que ya se quitó de ecg/eeg y que en emgteach solo usan sus
  pruebas.

### 1.6 `broadcast.py`: ecg y eeg idénticos; emgteach con más

**El protocolo, igual en las tres:**
- `lan_ipv4` y `hay_red_utilizable`;
- el servidor HTTP, con la página para cualquier ruta, las descargas
  registradas y el token `?k=`;
- `BroadcastServer`: puertos de `difusion.py`, token, sustitución de
  `{{WS_PORT}}` y `{{LANG}}`, contador de seguidores, `register_download`,
  `failed_port`;
- la lógica de **«el que llega tarde»**: se reenvían el último `config` y la
  última oferta de cada descarga, que se olvidan con una configuración
  nueva, al empezar a grabar y al parar.

**Lo que solo tiene emgteach:**
1. El **reenvío de `results`** (`_last_results`) con las mismas reglas de
   olvido. Es de la 3.8.0, por el banco M10 del 12 de octubre.
2. **`frames_for_a_new_follower()`**, el mismo comportamiento escrito como
   método y probado aparte.
3. Una **demo** propia (`python -m emgteach.broadcast`) con envolventes,
   zonas de carga 40/70 y la calibración. La de ecg/eeg dibuja latidos; en
   eegteach es un resto de la copia (inferencia).

**Detalles de cada app** dentro de la parte común: el import de `difusion` y
de `i18n.get_language`, el nombre del servidor WebSocket y la ruta de
`dashboard.html`.

**Copia buena: la de emgteach, parametrizada.**
- `BroadcastServer(app_name, dashboard_path, http_port, ws_port, *,
  language=…, sticky_kinds=("results",))`.
- `sticky_kinds` generaliza `_last_results`. En ecg/eeg no cambia nada,
  porque nunca emiten `results`.
- La demo sale del paquete: cada app conserva un `XXteach/broadcast.py` fino
  con su demo.

**`web/dashboard.html` se queda en cada app.** ecg y eeg tienen la misma
página (182 líneas); la de emgteach (327) añade calibración, zonas de carga y
resultados. El servidor común recibe su ruta.

### 1.7 `crash.py`: ecg y eeg idénticos; dos diferencias con emgteach

1. **`install_crash_log()` solo es idempotente en emgteach.** Allí lo llaman
   el lanzador y la aplicación, y sin la guarda cada fallo se escribiría dos
   veces. En ecg/eeg se llama una vez.
2. **`_hay_alguien_delante()`.** ecg/eeg preguntan si la instancia es una
   `QApplication`; emgteach solo si hay instancia. Con un `QCoreApplication`,
   emgteach llega al mismo resultado, pero por una excepción que se recoge.
   eegteach anotó en su CHANGELOG que esta era la última diferencia de
   lógica entre las copias.

**Copia buena: la unión.** La guarda de emgteach (con un atributo genérico,
`_teachcore_crash_log`) más el `isinstance` de ecg/eeg. El nombre y la
versión de la app en la cabecera del registro pasan a ser parámetros de
`install_crash_log(app_name, version, tr=…)`.

### 1.8 `recovery.py`: ecg y eeg iguales salvo ejemplos; dos diferencias con emgteach

- El fichero lateral y el sufijo son iguales en las tres: `.marcas.txt` y
  `_recuperado`.
- **`write_sidecar_header()`** (`# ecgteach marks for <nombre>…`) solo está
  en ecg/eeg. emgteach escribe las marcas sin cabecera. Los dos formatos son
  compatibles, porque `read_sidecar` ignora las líneas con `#`.
  - Detalle de ecgteach: al reescribir el lateral tras borrar una marca, la
    cabecera nombra el propio `.marcas.txt` en vez del EDF. Es cosmético,
    pero se arrastraría.
- **El EDF recuperado lleva «RECOVERED from …» en su cabecera** solo en
  emgteach (`patient_additional`). En ecg/eeg, `RecordingMetadata` no tiene
  ese campo, y lo que dice que el fichero está recuperado es su nombre.
- `recovery.py` importa `BufferedEdfWriter`, `ChannelInfo` y
  `RecordingMetadata` de `<app>.io`, que el encargo deja **fuera** del
  paquete.

**Copia buena: ecg/eeg** (con la cabecera del lateral, corrigiendo el
detalle), más un gancho para los metadatos del recuperado.

**Problema (comprobado):** mientras `io.py` sea de cada app, `recovery.py`
no puede ser común sin recibir el escritor EDF por parámetro. Propuesta:
`recover(edf, sidecar, out, *, writer_factory, metadata_hook)`. O bien
dejar `recovery.py` fuera de la primera tanda (§6).

### 1.9 `gui/widgets/logger.py`: una diferencia de comportamiento

- ecg/eeg: el registro tiene un **techo** de tres líneas (`setMaximumHeight`).
- emgteach: tiene un **suelo** de tres líneas y ocupa la altura de su caja
  (`setMinimumHeight` más `Ignored`). Lo explica el CHANGELOG de emgteach
  3.0.0: un registro con veinte mensajes enseñaba los tres últimos en una
  esquina de un rectángulo vacío.

**Copia buena: emgteach.** Al cambiarlo en ecg/eeg hay que comprobar en
pantalla que ninguna caja contaba con el techo (inferencia).

### 1.10 `gui/widgets/help_button.py`: dos componentes distintos

- **ecg/eeg:** una función `help_button(text, title, parent)`. Es un «?» que
  el que la llama pone en su layout, y abre un `QMessageBox`.
- **emgteach:** la clase `HelpButton` con `add_help(box, key)`.
  - Se ancla a la esquina de un `QGroupBox` y se recoloca al cambiar de
    tamaño.
  - Toma título y cuerpo de `emgteach.gui.help_texts` por clave, de modo que
    una clave que no existe falla al arrancar y no con un clic.
  - Si hay **coach**, abre el panel del coach sobre la caja; si no, un
    `QMessageBox`.
  - `coach` y `help_texts` no existen en ecg/eeg.

**Veredicto: no son versiones de un mismo módulo.** Propuesta (inferencia):
un `HelpButton(box, title, body, *, presenter=None)` común, donde el
presentador por defecto es un `QMessageBox` y emgteach inyecta el del coach.
La función `help_button(...)` de ecg/eeg queda como fachada. `help_texts` y
`coach` siguen siendo de emgteach. **Es el candidato que menos gana**:
moverlo puede esperar.

### 1.11 Lo que el paquete tiene que exponer

- **Fábrica:** `BACKEND_*`, `available_backends`, `create_device`,
  `register_device` y `_REGISTRY`.
- **`AcquisitionDevice`:**
  - abstractos: `fs`, `name`, `open`, `read`, `close`, `force_close`;
  - con valor por defecto: `quantisation_step`, `lost_frames`, `crc_errors`
    e `instruct`.
- **`BitalinoDevice`:**
  - constructor `(port, fs, channels, acc, acc_channel, sensor_gain, unit,
    simulator=…)`;
  - propiedades `sensor_gain`, `unit`, `quantisation_step`, `lost_frames`,
    `crc_errors`, `firmware_version` e `is_simulated`;
  - los internos que tocan las pruebas: `_resolve_port`, `_crc_ok`,
    `_extract_channel`, `_opening_serial`, `_bluetooth_ports`…
- **`ArduinoDevice`**, tal cual.

---

## 2. `bitalino_sim.py`: protocolo común y generador de cada app

**Comprobado.** El protocolo es idéntico línea a línea en las tres:
- `SIMULATED_PORT`, `VERSION_REPLY`, `_VCC`, `_ADC_MAX` y `_FS_BY_CODE`;
- `frame_size`, `crc4` y `encode_frame`;
- `SimulatedBitalinoPort`:
  - `write` y `_command` (parar, versión, frecuencia y arranque con la
    máscara de canales);
  - `_fill`, con la temporización por `perf_counter`, el tope de 2000
    tramas, el `>>4` de las ranuras 5 y 6 y la secuencia de 4 bits;
  - `in_waiting`, `read` (bloqueante y liberado por `close`),
    `reset_input_buffer`, `flush` y `close`.

Las diferencias son tres:
- el **constructor**: `acc_channel` en emgteach, `model` en ecg/eeg;
- la **llamada al generador**: emgteach pasa también `fs`, porque el
  acelerómetro va con retraso;
- **`instruct`**: solo emgteach lo tiene.

La señal es de cada app:

| | Generador | Ganancia y unidad | Modelos | Particularidades |
|---|---|---|---|---|
| emg | `_SyntheticSubject` | 1009, mV | uno | ciclo de 12 s (flexión, extensión, prensión); acelerómetro con retraso y temblor; **obedece a la calibración** (`instruct`) |
| ecg | `_SyntheticHeart` | 1100, mV | seis (normal, arritmia sinusal, ejes, bradi, taqui) | P-QRS-T; II = I + III; respiración |
| eeg | `_SyntheticEEG` | 40 000, µV | dos (alfa reactiva, plana) | alfa de 10 Hz que se bloquea con los ojos abiertos; fondo 1/f **con estado** (pide tiempos en orden) |

**Cómo separarlo:**

- **En `teachcore.devices.bitalino_sim`:**
  - las constantes y `frame_size`, `crc4` y `encode_frame`;
  - `physical_to_adc(x, gain, unit_scale)`, que sustituye a `mv_to_adc` y
    `uv_to_adc`;
  - las direcciones al estilo de ecg/eeg: «simulada», «simulado» o
    «simulated» más palabras clave;
  - `resolve_model(address, models)` y `model_list_message(…)`;
  - `SimulatedBitalinoPort(generator, timeout=5.0)`, sin cambios en el
    protocolo. `instruct` lo reenvía al generador si este lo tiene.
- **Interfaz del generador:**

  ```python
  class SignalGenerator(Protocol):
      def sample(self, t: float, fs: float, channels: list[int]) -> list[int]:
          """Códigos ADC de 10 bits de los canales activos, en orden.
          Se llama con t creciente dentro de una grabación."""
      # opcional
      def instruct(self, channel_index: int, level: float | None, *,
                   repeat_s: float | None = None) -> None: ...
  ```

  Se adopta la firma de emgteach, con `fs`; ecg y eeg la ignoran. El orden
  creciente de `t` queda documentado, porque eegteach lo necesita.
- **Registro de la app:** `BitalinoDevice(..., simulator=SimulatorSpec(models,
  factory, name))`.
  - `factory(model, acc_channel, seed)` devuelve el generador.
  - `name(model)` da «BITalino (…)», para que emgteach conserve exactamente
    «BITalino (simulated)» en la cabecera del EDF.
- **Queda en cada app** su `SimulatedModel`, `MODELS`, constantes de señal y
  generador. En emgteach: `CYCLE_S`, `_CYCLE`, `_SyntheticSubject` y
  `g_to_adc`.

**Cambios que conlleva para emgteach (inferencia):**
- aceptaría «simulado» y la forma por palabras;
- «simulada xyz» pasaría de no ser simulada a dar un error que lista los
  modelos.

Hay que decidirlo y probarlo.

---

## 3. Las cadenas `tr()` de esos módulos

**Recuento (comprobado):**

| Módulo | emg | ecg | eeg |
|---|---|---|---|
| `devices/bitalino.py` | 12 | 12 | 12 |
| `recovery.py` | 10 | 10 | 10 |
| `devices/arduino.py` | 4 | 4 | 4 |
| `crash.py` | 3 | 3 | 3 |
| `gui/widgets/logger.py` | 1 | 1 | 1 |
| `devices/bitalino_sim.py` | 0 | 1 | 1 |
| `gui/widgets/help_button.py` | 0 | 1 | 1 |
| `base.py`, `factory.py`, `broadcast.py`, `difusion.py` | 0 | 0 | 0 |
| **Llamadas** | **30** | **32** | **32** |

Son **34 claves distintas** en total:
- **28 comunes** a las tres:
  - **16 con la misma traducción**;
  - **12 con traducciones distintas**;
- **1** que solo comparten ecg y eeg;
- **5** propias de una sola app: la descripción de la recuperación, con el
  nombre de la app, y la lista de modelos simulados de cada una.

**Las 16 iguales:**
- `The connection attempt was given up before the board answered.`
- `Invalid BITalino channel list; channels must be in 0..5.`
- `The Arduino device is not open.`
- `The serial port is already open.`
- `The Arduino on {port} did not reply READY within {timeout:.0f} s.`
- `Unexpected error`
- `Error:`
- las nueve de `recovery.py`:
  - la ayuda de sus argumentos (el `.edf` sin cerrar, dónde escribir, el
    lateral `.marcas.txt`);
  - los mensajes de cabecera ilegible, de fichero demasiado corto y de
    fichero sin registros completos;
  - «{n} records in the header, {m} on disk»;
  - «{n} marks already in the file, {m} in the side-car»;
  - «Recovered: {path} — {seconds:.0f} s, {n} marks».

**Las 12 que difieren** (emgteach frente a ecg/eeg):

| Clave (abreviada) | emgteach | ecg / eeg |
|---|---|---|
| `The BITalino device is not open.` | «El dispositivo BITalino no está abierto.» | «La placa BITalino no está abierta.» |
| `A BITalino connection is already active…` | «…Ciérrela antes de abrir otra.» | «…con la placa BITalino… Hay que cerrarla…» |
| `The device on {port} did not identify itself…` | «…que la placa está emparejada…» | «…que la placa BITalino está emparejada…» |
| `BITalino {mac} was not found among the paired…` | «…emparejar el dispositivo… y encenderlo» | ecg «la placa… encenderla»; eeg «la placa… encenderlo» (concordancia mal) |
| `No BITalino was found on the Bluetooth COM ports…` | «…la placa… encenderlo» | ecg «…encenderla»; eeg «…encenderlo» |
| `Could not open the BITalino port {port}…` | «…apague y encienda la placa…» | «…la placa BITalino…» |
| `Unsupported BITalino sampling rate {fs} Hz…` | «no soportada… Usar…» | ecg «no admitida… Use…»; eeg «no soportada… Use…» |
| `Timeout while reading from the BITalino — …` | raya «—» | guion «-» |
| `Corrupted BITalino frames (CRC mismatch) — …` | «(error de CRC) —» | «(fallo de CRC) -» |
| `Timeout while reading from the Arduino — …` | raya «—» | guion «-» |
| `The application hit an error it did not expect, and could not write…` | «archivo» | «fichero» |
| `The application hit an error it did not expect. … written to:` | «archivo» | «fichero» (dos veces) |

Las versiones de emgteach («El dispositivo BITalino…», «Usar…») **harían
fallar** las pruebas de estilo de ecg/eeg:
`test_the_bitalino_is_a_board_and_feminine_in_spanish` y
`test_an_instruction_is_not_an_infinitive`.

**Cómo se traducen: dos opciones.**

- **Catálogo propio en teachcore** (`teachcore/i18n.py` con su `_ES`):
  - el paquete es autosuficiente;
  - sus pruebas de i18n van con él;
  - la app solo le dice el idioma.
- **Traductor inyectado por la app al arrancar**
  (`teachcore.set_translator(tr)`):
  - cada app sigue teniendo todas las cadenas en su `_ES`;
  - las pruebas «toda clave tiene español» y «toda entrada del catálogo se
    usa» siguen viendo todo en un sitio;
  - pero cada app tiene que copiar 30 claves del paquete en su catálogo, y
    cualquier clave nueva de teachcore obliga a tocar las tres apps.

**Preferencia: catálogo propio.** El paquete tiene que poder probarse solo, y
estas 34 cadenas son del paquete, no de la app; con ellas en tres catálogos
volvemos a tener tres copias. El idioma se sigue pasando:
`teachcore.i18n.set_language(lang)`, que la app llama junto al suyo, o un
`get_language` inyectado. Para el texto con el nombre de la app, una clave
con `{app}`.

**Consecuencias en las pruebas de cada app:**
- `_tr_keys()` dejará de ver esas cadenas, lo cual es correcto.
- La prueba de emgteach `test_every_catalogue_entry_is_still_used` fallará
  por las 30 entradas que se van de su `_ES`. Hay que borrarlas del
  catálogo al migrar.
- La lista blanca de f-strings de eegteach pierde cinco entradas.

**El catálogo común parte de la redacción de ecgteach**, que cumple todas
las reglas de estilo, y hay que decidir tres cosas:
- «encenderla» en vez de «encenderlo» (eegteach está mal);
- raya «—» o guion «-»;
- «archivo» o «fichero».

Las pruebas de estilo de ecg/eeg (placa femenina, punto decimal, no
infinitivo, sin tuteo) se copian a teachcore sobre su catálogo.

---

## 4. Las pruebas: cuáles se mueven y cuáles se quedan

**Se mueven a teachcore, en su mayoría:**

| Prueba (nombre en cada app) | emg | ecg | eeg | Qué se mueve |
|---|---|---|---|---|
| `test_devices.py` | 69 | 66 | 66 | casi todo: ABC, Arduino, direcciones, BITalino básico, ranuras, watchdog, fábrica, rango físico. Con sus dobles `_FakeSerial`, `fake_serial_factory`, `_FakePortInfo` y `_BlockingFakeSerial`, y los codificadores de tramas |
| `test_difusion.py` | 5 | 5 | 5 | todo |
| `test_broadcast.py` | 12 | 12 | 12 | el servidor. Se quedan en la app la que mira el contenido de su `dashboard.html` y `test_student_view_carries_no_muscle_wording` (ecg/eeg) |
| `test_crash.py` | 16 | 16 | 16 | el registro y el gancho. Se quedan las de las pestañas (emg) y «el log lleva el nombre de esta app» y «la app lo instala antes de nada» (ecg/eeg) |
| `test_recuperacion.py` / `test_recovery.py` | 5 | 6 | 6 | las cuatro de módulo puro; las que usan el worker se quedan |
| `test_bitalino_simulada.py` (emg) y parte de `test_simulated_board.py` (ecg 15, eeg 17) | 8 | ≈8 | ≈8 | protocolo, CRC, direcciones y cierre que libera la lectura. Los modelos (Einthoven, alfa, el acelerómetro que sigue al músculo) se quedan |

**Se reparten:** dentro de `test_devices.py` hay pruebas ligadas a la
ganancia y la unidad de cada app.
- emgteach: `test_raw_to_mv_*`, `test_gain_is_divided_out` y
  `test_bitalino_full_scale_is_gain_corrected`.
- ecgteach: `test_bitalino_full_scale_matches_the_emg_datasheet`.
- eegteach: `test_bitalino_full_scale_follows_the_gain_it_is_given`.

Las de la ganancia de cada app se quedan en la app, como pruebas del perfil.

**Se quedan en la app:**
- `test_simulada_obedece.py` (emg), salvo quizá «el puerto lo reenvía»;
- `test_diagnostico.py`/`test_diagnostics.py`, `test_sensor_gain.py` y
  `test_workers.py` (con su `_FakeDevice`);
- la placa que no responde, el selector de placa, los fallos de guardado y
  la difusión desde la pestaña;
- `test_gui_app.py`, `test_manejo_en_aula.py` y las pruebas de pantalla de
  emgteach;
- las de «el móvil se lleva el informe».

`logger.py` y `help_button.py` no tienen pruebas propias en ninguna app:
teachcore tendría que escribirlas.

**Estimación (inferencia):** unas 90-100 pruebas por app pasan a teachcore,
que las ejecuta una sola vez. Los dobles pueden exportarse como
`teachcore.testing` si alguna app los sigue necesitando, por ejemplo
`_FakeSerial` en las pruebas del worker.

**Al mover pruebas de emgteach** cambia el número de pruebas, y
`test_readme.py::test_the_test_count_is_current` exige actualizar el README.

---

## 5. teachcore en el ejecutable, en la CI y en la atestación

### 5.1 PyInstaller

- **El código entra solo.** PyInstaller sigue los imports estáticos hasta
  `site-packages`, también los que están dentro de funciones. Los candidatos
  no tienen imports dinámicos.
- **Los datos no entran solos.** Si teachcore llevara ficheros que no son
  Python (un catálogo en JSON, una página), hay dos opciones:
  - añadir `collect_data_files("teachcore")` en cada `.spec`;
  - mejor, que teachcore traiga su propio *hook* de PyInstaller (punto de
    entrada `pyinstaller40`), y así los `.spec` no cambian.

  Con el catálogo en Python y el `dashboard.html` en cada app, como se
  propone, **no hay datos que añadir**.
- **El ejecutable del diagnóstico excluye Qt**, entre otros. Lo vigilan
  `test_the_diagnostic_runs_without_what_its_executable_leaves_out` (las
  tres) y `test_import_ecgteach_loads_nothing_heavy` (ecg).
  - Por eso `teachcore/__init__.py` y `teachcore.devices` **no pueden
    importar** `broadcast`, `logger` ni `help_button`, que cargan PySide6.
  - Las dependencias de teachcore se separan:
    - base: numpy y pyserial;
    - extra `[qt]`: PySide6.
  - Una prueba en teachcore lo comprueba en un intérprete limpio, como la de
    `emgteach.fragments`.
- **El autotest de cada ejecutable** añade la versión de teachcore a su
  línea: `SELFTEST OK: emgteach 3.9.0 (teachcore 1.0.0, frozen=True)`.

### 5.2 Instalación desde git

- `pip install "teachcore @ git+https://github.com/aagisto-maker/teachcore@v1.0.0"`.
- Con hatchling, una dependencia con URL en `pyproject.toml` necesita
  `[tool.hatch.metadata] allow-direct-references = true`.
- PyPI no admitiría estas apps con esa dependencia. Hoy no se publican en
  PyPI, pero conviene saberlo.
- En emgteach, `packaging/requirements-exe.txt` se usa con `-c`, y pip no
  acepta URLs en un fichero de restricciones. teachcore se fija en el propio
  requisito (por etiqueta, o mejor por SHA del commit de la etiqueta), no en
  `-c`.
- **Si teachcore es privado** (ecgteach lo es), la CI necesita un token de
  lectura de ese repositorio: un secreto con un *fine-grained token* o una
  *deploy key*. El `GITHUB_TOKEN` de un repo no da acceso a otro. Si es
  público, no hace falta nada.

### 5.3 CI

- **Cada app instala teachcore como cualquier dependencia** en el paso
  `pip install -e ".[dev]"`. `pytest --cov=<app>` no medirá teachcore,
  y es lo correcto.
- **teachcore tiene su propia CI**, con la misma matriz: Ubuntu y Windows,
  Python 3.10 a 3.12. Lleva ruff, mypy bloqueante, sus pruebas y la del
  import sin Qt.
- **Opcional: un trabajo programado en teachcore** que instale las tres apps
  contra su `main` y pase sus suites. Avisaría antes de etiquetar si un
  cambio rompe una app.

### 5.4 La atestación del ejecutable de emgteach

- La atestación cubre el `.exe` final, que lleva teachcore dentro, **pero no
  dice qué teachcore**. Para que quede trazado:
  1. fijar teachcore por SHA en `pyproject.toml`;
  2. que el autotest diga su versión (§5.1);
  3. que el borrador de la release añada «teachcore vX.Y.Z (sha)» junto al
     número de ejecución y el SHA-256.

  Con eso, desde la release se llega al commit exacto de teachcore.
- teachcore puede atestar sus propias etiquetas, pero no es necesario para
  lo anterior.

---

## 6. Orden de migración

El orden es el del encargo: eegteach, luego ecgteach y por último emgteach.
eegteach y ecgteach son casi iguales entre sí, así que la primera migración
fija el paquete y la segunda debería ser casi mecánica.

### Paso 0 · Crear teachcore 0.1.0 (sin ninguna app)

1. **Repositorio `aagisto-maker/teachcore`**, con la estructura de las apps
   (src/, hatchling, ruff, mypy, la misma CI) y el **núcleo sin Qt**:
   - `devices` (base, factory, arduino, bitalino);
   - el protocolo de `bitalino_sim`;
   - `difusion`;
   - `crash`, sin el aviso con ventana, que se inyecta;
   - `i18n` con su catálogo.

   La base es la copia de ecgteach, con las decisiones de §1:
   - `instruct` en la base y en BITalino;
   - sin ganancia por defecto;
   - la idempotencia de emgteach en `crash`;
   - el generador simulado por parámetro.
2. **Pruebas** movidas desde ecgteach (§4), más las del import sin Qt.
3. Etiqueta `v0.1.0`.

`recovery`, `broadcast`, `logger` y `help_button` **no entran todavía**: los
dos primeros dependen de `io.py` o de la página de cada app, y los dos
últimos son de interfaz y de los menos rentables.

### Paso 1 · eegteach → teachcore 0.1.x

**Pasos:**
1. Dependencia `teachcore @ git+…@v0.1.0`.
2. Borrar sus copias de `devices/` (salvo su generador simulado),
   `difusion.py` y `crash.py`. Los imports pasan a `teachcore`.
3. Su `bitalino_sim.py` queda solo con `SimulatedModel`, `MODELS` y
   `_SyntheticEEG` adaptado a `(t, fs, channels)`.
4. Perfil EEG con `device_kwargs()` explícito (40 000, µV), como ya tiene.
5. Quitar las cadenas que se van de su `_ES` y podar su lista blanca de
   f-strings.

**Pruebas que lo cubren:**
- la suite completa;
- `test_simulated_board.py` en su parte de modelos;
- `test_sensor_gain.py`;
- `test_diagnostics.py`, incluida la del ejecutable sin Qt;
- la placa que no responde;
- la difusión desde la pestaña.

**Banco con la placa:**
- el diagnóstico con la BITalino real;
- una grabación de cada protocolo, con ojos abiertos y cerrados;
- la amplitud en µV comparada con un registro anterior del mismo montaje;
- tirar del Bluetooth a media grabación (tramas perdidas y resincronización);
- «simulada alfa» y «simulada plana»;
- la difusión a un móvil, entrando antes y después.

### Paso 2 · ecgteach

**Pasos:** los mismos que en eegteach. Además:
- su prueba `test_default_device_stays_on_the_emg_lineage` cambia, porque ya
  no hay ganancia por defecto;
- sus seis modelos simulados se quedan en la app.

**Pruebas:** la suite, con `test_import_ecgteach_loads_nothing_heavy` y
`test_the_self_test_passes_from_source` como guardianes del ejecutable.

**Banco:**
- el diagnóstico;
- las tres derivaciones y la secuencia de derivaciones;
- comprobar que la amplitud del QRS no ha cambiado (1100, mV);
- los modelos simulados por nombre;
- la difusión.

### Paso 3 · emgteach (3.9.0 o 3.10.0)

Es el paso más grande, porque emgteach difiere en todo.

**Pasos:**
1. Crear el dispositivo con `sensor_gain=1009, unit="mV"` desde el perfil.
2. Sustituir `_GAIN_EMG` y `raw_to_mv` en la pestaña (`full_scale_mv()`) y en
   sus pruebas.
3. Su generador `_SyntheticSubject`, con `instruct`, se registra como
   simulador con nombre «BITalino (simulated)».
4. Decidir si acepta «simulado» y la forma por palabras.
5. Borrar 30 entradas de su `_ES`. Su redacción cambia a la del catálogo
   común en las 12 cadenas que difieren (§3).
6. `README` con el nuevo número de pruebas.

**Pruebas que lo cubren:**
- la suite completa;
- `test_simulada_obedece.py`, porque la calibración guía a la simulada;
- `test_bitalino_simulada.py`, la parte del acelerómetro;
- la placa que no responde;
- el archivo que desaparece;
- `test_arreglos_pantalla.py`, por la escala;
- la regresión de fragmentos (`test_fragmentos_sin_qt.py`, con el registro
  real), que no debe moverse ni una centésima.

**Banco:**
- la lista completa de la versión, como la de la 3.8.0;
- en particular:
  - la calibración y la tarea con la placa real;
  - la escala del panel y el % CVM, que no deben cambiar;
  - el acelerómetro;
  - las tramas perdidas;
  - el diagnóstico;
  - «simulada» obedeciendo a la calibración.

**La release** sale por el procedimiento nuevo (PR #117): se prueba el
ejecutable de la ejecución manual y se publica ese.

### Paso 4 · teachcore 1.0 con lo de interfaz

1. `broadcast`, con `sticky_kinds`, la página por parámetro y la demo fuera.
2. `logger` (la versión de emgteach).
3. `recovery`, con el escritor EDF por parámetro.
4. Si compensa, `help_button` con su presentador inyectado.

Cada uno entra en las tres apps en el mismo orden. Se comprueba en el banco
la difusión con un móvil que entra tarde y la recuperación de un registro
cortado.

---

## 7. Versionado de teachcore y versión mínima en cada app

- **Versión semántica.**
  - **Mayor** cuando se rompe la API que usan las apps.
  - **Menor** cuando se añade algo.
  - **Parche** para correcciones.

  Mientras sea 0.x, una menor puede romper, y por eso cada app la fija
  exacta.
- **Cada app fija una etiqueta (o un SHA)** en `pyproject.toml`
  (`teachcore @ git+…@v0.2.0`). No basta una versión mínima, porque desde
  git pip no resuelve rangos. Subir teachcore en una app es una PR con su
  CI.
- **Versión mínima comprobada al arrancar y en las pruebas:**
  - `teachcore.__version__` y una constante en cada app,
    `TEACHCORE_MIN = (0, 2, 0)`;
  - una prueba de la app compara `importlib.metadata.version("teachcore")`
    con ese mínimo y **falla** si la instalada es más vieja (por ejemplo, un
    entorno de desarrollo sin actualizar);
  - al arrancar, la app comprueba lo mismo y, si no se cumple, dice qué
    versión tiene y cuál necesita, en vez de fallar más tarde con un
    `AttributeError`.
- **CHANGELOG de teachcore** con «qué cambia para las apps» en cada versión.
  Al subir teachcore, el CHANGELOG de cada app lo dice.

---

## 8. Riesgos, qué haría distinto y la opción de no hacerlo

**Riesgos:**

1. **Romper lo que funciona en el banco.** El controlador de la BITalino es
   lo más delicado de las tres apps: Bluetooth en Windows, errores 1168 y
   121, resincronización. Moverlo es cambiarlo, aunque sea a mejor.
   Mitigación:
   - el mismo código que hoy está en ecgteach;
   - las mismas pruebas, que se mueven con él;
   - un banco con la placa por app antes de su release.
2. **emgteach tiene un artículo que describe la 3.7.0** y una release
   cada pocas semanas. Migrarla obliga a reabrir el controlador y las
   cadenas. Mitigación: entra la última, en una versión propia, después del
   curso o entre prácticas.
3. **Dependencias por git:** el token si el repo es privado, `-c` sin URLs,
   hatchling con `allow-direct-references` y la imposibilidad de PyPI.
   Todo tiene arreglo, pero son piezas nuevas en el empaquetado y la CI.
4. **Más coordinación.** Un arreglo del controlador pasa a ser:
   1. una PR en teachcore;
   2. una etiqueta;
   3. tres PR que suben la versión.

   Son tres pasos donde hoy hay tres copias a mano, pero los pasos son
   visibles y probados, y las copias no.
5. **La traducción cambia en emgteach** en 12 mensajes (§3). Es poco, pero
   son textos que los alumnos ven.

**Qué haría distinto:**

- **Ir por partes, empezando por el núcleo sin Qt** (§6). No hacer los once
  módulos de una vez. `help_button` probablemente no compensa nunca.
- **Antes de crear el paquete, igualar las copias dentro de cada app**: que
  emgteach adopte la API de dispositivos de ecg/eeg (`sensor_gain`,
  `quantisation_step`, `lost_frames` en la base) y que ecg/eeg adopten
  `instruct`, la idempotencia de `crash` y el `logger` de emgteach. Son PR
  pequeñas, cada una con su banco. Cuando las copias sean iguales, el paso
  a teachcore es mover ficheros, sin decisiones a la vez.
- **Un vigilante barato entretanto** (era el encargo C): una prueba o
  script que compare las copias normalizadas y avise cuando diverjan. Con
  teachcore se descarta, pero si teachcore se retrasa, es lo que evita que
  las copias se separen más.

**La opción de no hacerlo:**

- Las tres apps funcionan.
- Las copias de ecg y eeg ya son iguales salvo la ganancia por defecto de
  `BitalinoDevice` y el generador de la placa simulada, que es de cada app. Lo que se mantiene a mano es sobre todo
  emgteach frente a las otras dos.
- Si en el horizonte del proyecto no hay una cuarta app ni muchos más
  cambios del controlador, igualar las copias y vigilarlas cuesta menos y
  arriesga menos que un paquete con su repositorio, su CI y su versionado.

**Recomendación:** igualar primero las copias (PR pequeñas por app); después
crear teachcore con el núcleo sin Qt, migrando eegteach y ecgteach; y
decidir lo de emgteach y lo de interfaz cuando eso haya pasado un banco.
