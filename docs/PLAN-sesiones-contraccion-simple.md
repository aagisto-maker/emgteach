# Plan · sesiones guiadas en «Contracción de un músculo»

**Estado: solo plan.** No se ha tocado ningún código. Leído en modo solo
lectura el 24 de octubre de 2026: emgteach en `main` `0c38423` (3.9.1),
ecgteach `origin/main` `6105696` y eegteach `origin/main` `acee200`. Responde
al encargo «sesiones guiadas en Contracción de un músculo · fase 1: plan» del
24 de octubre, punto por punto (a–g). Se distingue lo **comprobado** en el
código (con fichero y línea) de lo que es **inferencia**, que va marcado así.
Los guiones del §4 son una **propuesta**: duraciones, escalones y textos
están para que Ángel los ajuste.

Las líneas citadas son las de `0c38423`; cualquier PR que se fusione antes las
desplaza.

**Aprobado el 24 de octubre con las decisiones del §10**, que mandan sobre lo
que diga el resto del plan: las contracciones sucesivas **no** se hacen como
sesión (§4.3 queda como registro de lo que se propuso y por qué se descartó),
la fatiga gana una variante intermitente y el §4.3 lleva una corrección de
fisiología.

---

## 0. Resumen

- **No se porta `GuidedSessionDialog`** de ecg/eeg (§2.1). Es un `QDialog`
  aparte que escribe las marcas con el texto traducido de la fase; en
  emgteach el alumno ya recibe las indicaciones en el `MvcOverlay` sobre las
  gráficas, con la barra de % CVM a la vista y retransmitido al móvil, y las
  marcas son códigos ASCII. **Lo que sí se porta tal cual es `cue.py`** (el
  tono) y la idea del **destello** del panel de instrucción, que en emgteach
  no existe: hoy ninguna fase suena ni destella (comprobado, §1.3).
- **El encaje es el flujo automático que ya tienen las otras dos prácticas**
  (§2.2): la sesión se elige **antes** de grabar, en un desplegable junto a
  «Calibrar CVM» que solo se ve en «Contracción de un músculo» y no añade
  altura; «Iniciar grabación» hace calibración (si la sesión la pide),
  `PREP start`, `REC start`, las fases, y la grabación **se detiene sola** al
  acabar, como en el par y en cinemática. Con «Ninguna» (lo que hay al abrir)
  todo sigue igual: la grabación libre es la norma.
- **Lo nuevo vive fuera de la pestaña**: un módulo sin Qt (`sessions.py`:
  guiones, marcas y su lector) y un `SessionRunner` (QObject con el reloj) que
  pide a la pestaña lo que ya sabe hacer (overlay, marca, difusión, sujeto
  simulado). La pestaña gana ≤ 200 líneas (§6). No hace falta hacer antes
  el encargo E; sí conviene no repetir su defecto.
- **Marcas:** tres familias ASCII, `GRAD`, `RHYTHM`, `HOLD`, con la gramática
  de `CAL start ch=1 rep=1` (§4.4). Distinguibles de las manuales (que son
  texto traducido) y de las de fase (`CAL`, `WARMUP`, `PREP`, `REC`).
- **Acelerómetro en «Contracciones sucesivas»: no** (§4.3). En esta práctica
  no se adquiere (un canal; `_USES_ACC[MODE_SINGLE] = False`,
  `modes.py:77`) y con Arduino + MyoWare no existe; y, sobre todo, si el
  ritmo lo marca la aplicación la velocidad del movimiento la fija el
  metrónomo, no el músculo. Se propone el experimento solo con EMG y un
  objetivo docente que el EMG sí enseña: la relación ritmo–amplitud y la
  **relajación incompleta** entre contracciones al acelerar el ritmo. La
  variante con acelerómetro queda como extensión en Cinemática.
- **Orden y coste** (§7): cimientos + gradación (2 PR, ~4 jornadas), fatiga
  (1 PR, ~1.5), sucesivas (1 PR, ~1.5), versión 3.10.0 con manual y banco
  (~1). Cada PR deja la aplicación entregable.

---

## 1. Lo que hay ya (comprobado)

### 1.1 En emgteach, en la adquisición

| Qué | Dónde | Sirve para |
|---|---|---|
| Marcas de fase ASCII `CAL start/end ch= rep=`, `WARMUP start`, `PREP start`, `REC start` | `phases.py:104–135`; se escriben con `_write_phase_marker` (`acquisition.py:3927`) → `worker.add_marker` (`workers/acquisition.py:255`), sellado con `n_samples_total/fs` (exacto a la muestra, no al reloj de la interfaz) | La misma vía para las marcas nuevas |
| Flujo automático de sesión: `_mvc_flow_pending`/`_fv_flow_pending` armados en `_iniciar_grabacion` (2474–2518), disparados en el primer bloque de `_on_data_ready` (2606–2640); calibración → `_mvc_enter_prep` (`PREP start`, 3954) → `_prep_tick` (`REC start`, 3978) → en el par `_guia_maniobras`, en cinemática `_lanzar_estudio_fv` (3996–4004) | `acquisition.py` | El tercer brazo: en «Contracción de un músculo» → la sesión elegida |
| `PREP`/`REC` **solo se escriben en el flujo automático** (`_mvc_flow_auto`, 4423–4433); «Calibrar CVM» a mano, el caso actual de esta práctica, no los escribe | comprobado | La sesión tiene que ser flujo automático para heredarlos |
| `_parar_al_terminar_sesion` (4938–4958): `_conservar_panel`, 5 s de panel final, `_detener_grabacion` | lo llaman `_guia_fin` y `_fv_finish_all` | El final de la sesión. Su docstring (4946–4948), `DECISIONS.md:58–61` y `CHANGELOG.md:75` dicen que «the one-muscle practical has no guided end»: hay que revisarlos |
| Cancelar con Esc: `_btn_cancelar_guia` (1395–1401) y `_cancelar_guiado` (4455–4488) | | El mismo botón y la misma tecla |
| `MvcOverlay` (`gui/widgets/mvc_overlay.py`, 718 líneas): `show_ready` (cuenta atrás), `show_contract` (barra de ventana + barra de esfuerzo con pico), `show_relax`, `show_phase` (fase con barra de mantenimiento y barras con zona objetivo), `show_done`, mapa de pasos `set_steps`/`mark_step` | 341–443, 167–252 | Toda la presentación de las fases; es transparente al ratón y se coloca sobre las gráficas (4991) |
| Difusión al móvil: `_bcast_calib(active, phase, title, sub, count, secs, progress, effort)` → `{"t":"calib"}` (3215–3224); el móvil pinta `ready`, `contract`, `rest`, `warmup|prep` y el resto como «done» (`web/dashboard.html:222–243`) | | Las indicaciones en el móvil, con una rama nueva por fase |
| Sujeto simulado: `worker.instruct(ch, level, repeat_s=)` (`workers/acquisition.py:244`) → `_SyntheticSubject.instruct` (`devices/bitalino_sim.py:148`): nivel mantenido o una contracción de ~1 s cada `repeat_s` | lo usa el asistente CVM (`_pedir_al_sujeto`, 3895–3925) | Las pruebas: el sujeto hace lo que la fase pide |
| Repaso al detener: `_mostrar_registro` sombrea `phase_spans(parse_phase_markers(...))` (2920–2958) | | Añadir los tramos de la sesión al sombreado |
| El guion `Cue`/`cue_script` del ensayo F‑V (`fv_rehearsal.py:70–139`): lista de señales con `phase, seconds, start, end`, sin Qt, y un diálogo que la recorre con su reloj (`fv_rehearsal_dialog.py`, `_tick` 420, `_cue_at` 386, `_drive_overlay` 444) | | El modelo de guion para los tres experimentos |

Lo que **no** hay: tono, destello (grep de `QSound|beep|winsound|flash|blink`
en `src/`: nada; `app.py:871` solo habla del parpadeo de la barra de tareas),
ni ninguna máquina de estados reutilizable: CVM (`_mvc_tick`, 3635–3743),
preparación (`_prep_tick`), coactivación (`_coact_tick`) y F‑V (`_fv_tick`,
4723–4831) son cuatro `QTimer` de 100 ms escritos a mano dentro de la
pestaña.

### 1.2 En emgteach, en el análisis

| Qué | Dónde | Sirve para |
|---|---|---|
| El worker lee `CAL/WARMUP/PREP/REC`, `MVC ref` y `FV load=` y los **quita** de las marcas que se dibujan (`workers/analysis.py:437–450`) | | Las marcas nuevas tienen que quitarse ahí también, o saldrán como marcas del alumno en todos los paneles |
| Tramo analizado por defecto: `SessionPhases.rec_span` (`phases.py:213–241`): `REC start`, o el fin de la última `CAL`, o 1 s antes de la primera carga F‑V | | El tramo de la sesión |
| **Una fila por marcador**: en cinemática, sin fragmentos, las filas de la tabla de contracciones salen de `_ventanas_de_carga` a partir de los `FV load` (`workers/analysis.py:353–363, 1234`) y `contraction_table(segments=…)` las recorta al esfuerzo (`contractions.py:125, 301–308`) | | Gradación: una fila por escalón. Sucesivas: una por contracción |
| `Contraction` (`contractions.py:53–95`): `rms_mv` (RMS de la filtrada), `peak_pct` (pico de la envolvente en % CVM; `None` sin CVM), `mdf_hz`, `velocity_au`, `emd_ms` | | Las cifras de cada escalón y de cada contracción |
| Gráfico de contracciones `draw_contraction_chart(view=…)` (`charts.py:87`): `relation`, `series` (puntos por contracción en orden, recta de tendencia si ≥ 4, MDF en eje gemelo con su pendiente, 318), `category`, `dominance`, `load` (puntos + media por carga, 264), `table` | | `series` ya sirve para las sucesivas. **No hay barras**: hace falta una vista `steps` |
| Fatiga por ventanas: `compute_segments` (`dsp.py:392`: `t_seg`, `rms_seg`, `mdf_seg`), `active_segments`, `fit_mdf_vs_time` (`slope`, `slope_per_min`, `r_squared`, `pct_decline`, `linear_fitted`), `fatigue_verdict` (`fatigue.py:57–206`); panel 6 (RMS/ventana), 7 (MDF/tiempo), 8 (RMS vs MDF); fichas del resumen (`analysis.py:2168–2205`) | | La fatiga entera. **No hay «tiempo hasta caer X %»** |
| En «Contracción de un músculo» solo se ofrecen los paneles 1, 2 y 3 (`_panel_is_offered`, `analysis.py:3415–3449`); 6, 7 y 8 están tras «Más paneles…» | | La fatiga debe ofrecer el 7 (y el 6) sin pasar por ahí |
| Informe: `build_session_report` (`reports.py:606–871`) con `_seccion_contracciones` (470–537) como patrón: `_render_chart` + `_styled_table` (anchos ≤ 17 cm, `TABLE_WIDTH_CM`) | | Una `_seccion_sesion` con el mismo patrón |
| Móvil tras el análisis: `{"t":"results"}` con `mnf, mdf, mdf_slope, rms, iemg, duration, fatigue` (`analysis.py:2108`) y el PDF por `{"t":"download"}` | | Añadir el resumen de la sesión |
| Las pruebas de GUI con la placa simulada: `tab`/`recording`, `_until`, `_start`/`_stop` (`tests/test_marcas_manuales.py:168–207`); el ensayo F‑V prueba la máquina de estados real con los mismos números que el guion (`tests/test_fv_rehearsal.py:99–138`) | | El patrón de las pruebas (§8) |

### 1.3 En ecgteach y eegteach (lo que se pide portar)

- **`gui/widgets/guided_session.py`** (ecg 504 líneas, eeg 486): un
  `QDialog` con intro, línea de paso, panel de instrucción grande,
  `QProgressBar`, panel de «qué esperar», botones Iniciar / Siguiente fase /
  Parar, casilla «Tono en cada cambio de fase» (recordada en `QSettings`) y
  un registro de fases. Reloj `QTimer` de 250 ms; **lead‑in** de 10 s que no
  marca nada (`PREPARE_S`, porque el movimiento de soltar el ratón caía en la
  línea de base); en cada fase emite `marker_requested(tr(step.label))`,
  destella el panel 900 ms (`_FLASH_MS`) y suena `beep()`; al terminar emite
  la marca de fin (`SESSION_END` o la propia de cada sesión) y
  `session_completed`; Esc y cerrar = parar. Las dos copias son el mismo
  fichero salvo el metrónomo respiratorio (ecg) y los motivos del Berger
  (eeg): comprobado con `diff` normalizando el nombre del paquete.
- **`sessions.py`** (ecg, 266 líneas, sin Qt): `SessionPhase(key, label,
  instruction, duration_s, expectation, cycle_s, cycle_texts)` y las tres
  secuencias (`LEADS`, `BREATHING`, `ORTHOSTATIC`). Las subclases del diálogo
  (`session_dialogs.py`, 83 líneas) solo ponen `SEQUENCE`, `TITLE`, `INTRO`
  y la marca de fin.
- **Las marcas son el texto traducido de la fase** («Paced breathing 6/min»
  o su español), y el análisis las reconoce contra todas las traducciones
  (`markers.py:41–48`, `manoeuvres.py:75–98`). Es lo contrario de lo que pide
  el encargo (códigos ASCII como `CAL`/`REC`), y es una de las razones para
  no portar el diálogo tal cual.
- **`cue.py`** (ecg 372 líneas; eeg igual más los motivos del Berger): WAV
  sintetizado en memoria (880 Hz, 120 ms, volumen 0.35, 250 ms de silencio
  delante para despertar la tarjeta), `winsound.PlaySound` en un hilo propio
  con cerrojo y regla de tono atascado; fuera de Windows, `QApplication.beep`.
  Motivos `phase`, `end` (dos notas descendentes), `abort` (220 Hz, 750 ms).
  `set_tone_report` para que la pestaña anote en su log si el tono sonó. Todo
  el porqué está en sus comentarios (banco de 5 de octubre de 2026).
- **Dónde se ofrece en ecgteach**: una caja «Sesión guiada» con un
  desplegable («Ninguna» al abrir) y dos etiquetas con las fases y «lo que
  viene» (`acquisition.py:1199–1243`); la sesión se elige **antes** de grabar
  (banco de 5 de octubre: abierta a mitad de grabación heredaba el juego de
  derivaciones de la prueba anterior), arranca **con el primer bloque de
  datos** (1310–1330; antes marcaba las fases a t = 0 s), y la grabación se
  detiene al completarse (`_on_session_completed`, 1332–1337).
- **Pruebas**: el diálogo se prueba con `prepare_s=0` llamando a
  `_advance_step()` y `_on_tick()` directamente
  (`tests/test_gui_session_dialogs.py`); la pestaña, con una subclase cuyas
  fases duran 0.3 s inyectada con `monkeypatch` en el registro de sesiones y
  `_until(lambda: not tab.is_recording(), 8.0)`
  (`tests/test_sessions_need_data.py:158–176`).

---

## 2. Cómo se encaja (punto a)

### 2.1 Portar el diálogo o reutilizar lo de emgteach: reutilizar, y portar solo el tono

Razones, por orden de peso:

1. **El alumno de esta práctica mira la pantalla y la barra de % CVM.** La
   gradación es *apretar hasta la marca de la barra*; un `QDialog` encima de
   la ventana la tapa, y el overlay ya está diseñado para convivir con ella
   (está sobre las gráficas, no sobre el panel de carga, `4991`). En ecg/eeg
   el diálogo existe porque el sujeto está tumbado o con los ojos cerrados y
   no hay nada que mirar.
2. **Las indicaciones ya llegan al móvil** por el frame `calib`; el diálogo
   de ecg no retransmite nada (comprobado: en ecgteach solo salen `config`,
   `status`, `data`, `marker`).
3. **Las marcas**: el encargo quiere códigos ASCII; el diálogo escribe texto
   traducido. Portarlo y luego cambiarle las marcas es portar la mitad.
4. **Coherencia con las otras dos prácticas**: el par y cinemática ya guían
   con overlay, Esc y parada automática. Un tercer estilo en la tercera
   práctica sería lo raro.

Lo que **sí** se lleva de ecg/eeg:

- **`cue.py` entero**, sin cambios de lógica (solo el nombre del paquete y
  el texto del docstring sobre el BITalino, que en EMG vale igual: el zumbador
  de la placa mete un transitorio en la alimentación y vibra sobre los
  electrodos). Pasa a ser la tercera copia idéntica: **anotar en
  `PLAN-teachcore.md`** como candidato del núcleo sin Qt.
- **El destello**: 900 ms de resaltado del panel de instrucción en cada
  cambio de fase, junto con el tono y en el mismo sitio del código (regla de
  `_start_flash` en ecg: un cambio de fase es un evento y se anuncia en un
  solo lugar). En emgteach va en `MvcOverlay`: un método `flash()` que
  cambia el borde/fondo del marco 900 ms con un `QTimer` de un disparo.
- **El lead‑in que no marca nada**: ya existe, es `PREP` (5 s), y aquí además
  queda registrado como fase.
- **La casilla «Tono en cada cambio de fase»** recordada en `QSettings`, el
  tono al marcarla y al abrir (la lección de la sesión perdida en eeg): en
  emgteach, en el desplegable de la sesión no cabe; propuesta: en la caja
  «Carga muscular» no (altura); en el **menú/caja de ajustes avanzados** o,
  mejor, **sin casilla**: el tono siempre, con `DEFAULT_ENABLED = True` como
  en ecg 0.4.0, y el informe del tono en el log de eventos
  (`set_tone_report`). *Decisión de Ángel.*

### 2.2 La arquitectura propuesta

```
sessions.py (sin Qt)                 gui/session_runner.py (QObject)        gui/tabs/acquisition.py
──────────────────────               ─────────────────────────────────      ────────────────────────
SessionPhase(key, kind, seconds,     SessionRunner(script, *, tick_ms)     desplegable «Sesión guiada»
  target_pct, title, text, level)      QTimer 100 ms, elapsed, index         _session_flow_pending
gradation_script(...)                  signals:                              _lanzar_sesion(): crea el runner,
rhythm_script(...)                       marker(str)      ──────────────►    conecta: marker → _write_phase_marker
hold_script(...)                         cue(phase, title, sub, secs,        cue    → _mvc_overlay.show_* + flash
  → list[SessionPhase] con start/end           progress, effort)              + beep() + _bcast_calib
*_marker(...) / parse_session_markers    instruct(level, repeat_s)           instruct → _pedir_al_sujeto
is_session_marker / GuidedSession        finished(completed: bool)           finished → _parar_al_terminar_sesion
session_spans(...)                     skip(), cancel()                      Esc → runner.cancel()
```

- **`sessions.py`**: los tres guiones como funciones con los segundos por
  parámetro (como `cue_script`), las marcas (`*_marker`) y su lector
  (`parse_session_markers` → `GuidedSession(kind, version, start_s, end_s,
  spans: tuple[SessionSpan, ...])`, `is_session_marker`), y
  `session_spans()` para el sombreado del repaso y del análisis. Es el
  equivalente de `phases.py` para las sesiones y se prueba sin Qt.
- **`SessionRunner`**: un reloj y un índice, nada más. Recibe el guion, va
  emitiendo lo que toca y no conoce la pestaña ni el overlay (se le conectan
  slots). Con `tick_ms` y las duraciones por parámetro se prueba con un reloj
  falso en milisegundos, como `test_fv_rehearsal.py` prueba `_fv_tick`.
- **La pestaña** añade: el desplegable (§3), el armado en
  `_iniciar_grabacion` (una línea junto a `_mvc_flow_pending`), el tercer brazo
  tras `REC start` en `_prep_tick` (3996–4004), `_lanzar_sesion` (~40 líneas
  de conexiones), el brazo de la sesión en `_cancelar_guiado`, y el nombre de
  fichero (como el par y cinemática llevan el suyo: `_SESSIONS[...][2]` en
  ecg; en emgteach la función de nombres está en `acquisition.py:453–588`).
  Estimación: **150–200 líneas**, ninguna máquina de estados nueva dentro.
- **Calibración**: la sesión declara si la quiere (`needs_mvc`). Gradación:
  sí (los escalones son % de la barra); fatiga: sí, opcional (para decir
  «máximo» en % CVM y para la barra de esfuerzo; sin ella el experimento
  sigue valiendo); sucesivas: no. Si la pide, el flujo es exactamente el del
  par: `_iniciar_calibracion(auto_flow=True)` → `PREP` → `REC` → sesión. Si
  no, propuesta: `PREP` → `REC` → sesión (sin `WARMUP` ni `CAL`), lo que
  exige que `_mvc_enter_prep` pueda arrancar sin calibración previa
  (comprobado: hoy solo lo llama `_mvc_finish_all`, 4432; qué estado
  presupone se mira al implementar).
- **Sujeto simulado**: el runner emite `instruct(level, repeat_s)` en cada
  fase (nivel del escalón; 1.0 en la máxima; `repeat_s` del ritmo en las
  sucesivas) y la pestaña lo pasa como ya hace el asistente CVM. Con placa
  real no hace nada (`workers/acquisition.py:244`).

### 2.3 Qué falta (resumen)

Sin Qt: `sessions.py` (guiones, marcas, lector, tramos), `cue.py`,
`time_to_decline` en `fatigue.py`, vista `steps` (barras) en `charts.py`,
las filas por fase en el worker de análisis, la sección del informe.
Con Qt: `SessionRunner`, `MvcOverlay.flash`, el desplegable y sus ~200
líneas en la pestaña, la oferta de paneles por sesión y las fichas nuevas
en la pestaña de análisis, la rama del móvil en `dashboard.html`.
Documentación: manual (§7.1), guion de prácticas (1b y 1c pasan a hacerse
con la sesión; nuevo 1e para las sucesivas), chuleta, `help_texts.py`,
`i18n.py`, CHANGELOG, notas de versión.

---

## 3. Dónde se ofrece y cómo convive con la grabación libre (punto b)

**Propuesta:** un desplegable «Sesión guiada» en la **fila superior del panel
«Carga muscular»** (`_build_load_panel`, `fila_sup` 3241–3323), a la derecha
de «Calibrar CVM». Comprobado: en «Contracción de un músculo» esa fila solo
tiene «Calibrar CVM» y un `addStretch(0)` (3322), porque `_box_fv_guided`
(3274–3316) está oculto; hay sitio horizontal de sobra y **no se añade ninguna
fila**. Visible solo en `MODE_SINGLE`, con el mismo patrón que
`_box_fv_guided.setVisible(uses_acc)` en `apply_mode` (5582–5583).

- Opciones: «Ninguna» (siempre al abrir la pestaña, como en ecg: una sesión
  heredada de la prueba anterior es lo que tropezó en su banco),
  «Gradación», «Contracciones sucesivas», «Contracción máxima mantenida».
- El tooltip del desplegable lista las fases y la duración total; el mapa de
  pasos del overlay (`set_steps`) las muestra durante la sesión. No hay
  etiquetas nuevas bajo el desplegable (en ecg las hay y ganan altura).
- **Antes de grabar, no durante**: la sesión se elige y «Iniciar grabación»
  la ejecuta cuando llega el primer bloque. Es lo que ecg aprendió en el
  banco del 5 de octubre y lo que ya hacen el par y cinemática. El
  desplegable se desactiva mientras se graba.
- **Convivencia con la grabación libre**: con «Ninguna», `_iniciar_grabacion`
  no arma nada y todo es como en 3.9.1 (incluido «Calibrar CVM» a mano a
  mitad de grabación). Durante una sesión siguen funcionando el auto‑inicio
  (`Onset (auto)`), la marca manual (M) y la difusión. **Esc** cancela la
  sesión: se escribe la marca de fin de la familia y **la grabación sigue
  libre** hasta «Detener», que es lo que ya hacen la calibración, la tarea
  del par y el F‑V (comprobado: `_cancelar_guiado`, 4455–4488, anota
  «…cancelled; the recording goes on» en los tres casos). Así una sesión
  abortada no pierde lo grabado.
- **Al completarse** la sesión, la grabación se detiene sola por
  `_parar_al_terminar_sesion`, con los 5 s de panel «Sesión completada: la
  grabación se detiene» (texto a propuesta en §4), y el repaso
  `_mostrar_registro` sombrea los tramos de la sesión además de los de
  calibración.
- Alternativa descartada: un botón «Sesión guiada…» con un diálogo de
  elección. Es un clic más y la misma altura; solo ganaría si hubiera que
  explicar cada experimento con un párrafo, y para eso está el botón de
  ayuda de la caja y el manual.

---

## 4. Los guiones (punto c), como propuesta

Convenciones comunes: textos en «usted», infinitivo en botones, punto
decimal; el tono (880 Hz, 120 ms) y el destello en **cada cambio de fase**,
el motivo de fin (dos notas descendentes) al completar y el de aborto (220 Hz,
750 ms) si la aplicación cancela por sí misma (p. ej. el puerto se cae); con
Esc, nada (quien pulsa Esc ya lo sabe). Antes de cada sesión: `PREP start`
(5 s, «Prepárese…», como hoy) y `REC start`. Las fases de reposo no llevan
marca propia: son los huecos entre marcas, como el descanso entre `CAL`.
Los tiempos de las marcas son los del worker (muestra exacta); el reloj del
runner solo decide *cuándo pedirlas*, con ±100 ms.

### 4.1 Gradación (`GRAD`)

Objetivo: la envolvente crece con la fuerza, de forma monótona y no lineal
(ejercicio 1b del guion, que hoy se hace a ojo con la barra).

| # | Fase | s | Texto en pantalla (y móvil) | Overlay | Marca |
|---|---|---|---|---|---|
| 0 | Reposo inicial | 5 | «Reposo. Deje la mano suelta sobre la mesa.» | `show_relax` | — |
| 1 | Escalón 1 | 4 | «Apriete el puño hasta el **20 %** de la barra y manténgalo.» | `show_phase` con `zone=(15, 25)` y barra de esfuerzo | `GRAD step start k=1 pct=20` / `GRAD step end k=1` |
| — | Reposo | 6 | «Suelte. Reposo.» | `show_relax` | — |
| 2 | Escalón 2 | 4 | «… **40 %** …» | ídem, `zone=(35, 45)` | `GRAD step start k=2 pct=40` / `… end k=2` |
| 3 | Escalón 3 | 4 | «… **60 %** …» | | `k=3 pct=60` |
| 4 | Escalón 4 | 4 | «… **80 %** …» | | `k=4 pct=80` |
| 5 | Escalón 5 | 4 | «Apriete **al máximo**.» | `zone=(90, 100)` | `k=5 pct=100` |
| — | Reposo final | 5 | «Suelte. Fin de la gradación: la grabación se detiene sola.» | `show_done` | `GRAD end` |

Total 55 s (más calentamiento, calibración y 5 s de `PREP`). Marca de
cabecera al empezar: `GRAD start steps=5 v=1`. Cinco escalones y no cuatro
porque con cuatro (25/50/75/100) la curva tiene tres intervalos; con cinco se
ve la concavidad. **Sin CVM calibrada** (si Ángel quiere permitirlo): los
mismos tiempos con niveles verbales («muy suave», «suave», «medio», «fuerte»,
«máximo»), `pct=0` en la marca y el overlay sin zona; el resultado sale en mV.
*Propuesta: exigir la calibración en esta sesión*, porque sin barra el alumno
no puede graduar y la tabla en mV no se compara entre compañeros.

### 4.2 Contracción máxima mantenida (`HOLD`)

Objetivo: la caída de la MDF (y lo que haga el RMS) al sostener un máximo.
**Nota**: el ejercicio 1c del guion pide hoy un **50 %** de la barra durante
30–60 s; el encargo pide **máxima**. Con esfuerzo máximo la MDF cae más
deprisa y 30 s suelen bastar para que la recta ajuste; al 50 % hacen falta
60 s o más y en algunos sujetos sigue saliendo «no concluyente». Propuesta:
**máxima, 30 s**, con 45 s como alternativa en el desplegable o en ajustes
(*decisión de Ángel*), y actualizar 1c en el guion.

| # | Fase | s | Texto | Overlay | Marca |
|---|---|---|---|---|---|
| 0 | Reposo | 5 | «Reposo. Antebrazo apoyado, puño cerrado sin apretar.» | `show_relax` | — |
| 1 | Cuenta atrás | 3 | «A la cuenta, apriete al máximo.» | `show_ready` (3, 2, 1) | — |
| 2 | Esfuerzo | 30 | «Apriete **al máximo** y manténgalo. **Respire**; no retenga el aire. Si nota dolor, suelte.» | `show_contract` con barra de tiempo y barra de esfuerzo (pico) | `HOLD start secs=30 v=1` al empezar la fase / `HOLD end` |
| 3 | Reposo | 10 | «Suelte. Deje la mano caer. Fin: la grabación se detiene sola.» | `show_done` | — |

Seguridad: isométrico contra la mesa, sin carga en la mano, 30 s con tope en
45; el texto manda respirar (Valsalva) y soltar si duele; en el manual, la
advertencia para quien tenga hipertensión o lesión del antebrazo (no en la
aplicación: no es un dispositivo médico y el guion ya lleva este tipo de
notas). La `CAL` previa (tres sacudidas máximas) sirve de calentamiento y da
la referencia para la barra; la sesión no la exige.

### 4.3 Contracciones sucesivas (`RHYTHM`)

**Sobre el acelerómetro (lo que pide evaluar el encargo).** Veredicto: **no
sirve aquí como medida mecánica**, por tres razones, de la más fuerte a la
menos:

1. **Si el ritmo lo marca la aplicación, la velocidad la fija el
   metrónomo.** Con una carga fija y un recorrido fijo, el tiempo de cada
   contracción lo dicta el tono; la velocidad media de cada repetición es
   recorrido/tiempo y la de pico, para un movimiento de una pieza, es
   proporcional. Lo único libre es *cuánto EMG hace falta* para cumplir el
   ritmo. Una tendencia en la velocidad no diría nada del músculo: diría que
   el alumno dejó de seguir el ritmo (recorrido más corto o retraso). Para
   que la velocidad fuera la variable dependiente habría que pedir «lo más
   rápido que pueda», y entonces el experimento es el de fuerza‑velocidad,
   que ya existe en Cinemática.
2. **En esta práctica no se adquiere** (un canal, `modes.py:72, 77`; el
   análisis nunca pasa `acc_channel` en `MODE_SINGLE`, `analysis.py:1688–1690,
   3447`) y con **Arduino + MyoWare**, que esta práctica admite
   (`_combo_device_type`, 5561), no existe. Habilitarlo sería convertir la
   práctica básica en la avanzada.
3. **Sin calibrar y en unidades arbitrarias** (`force_velocity.py:19–22,
   235`): solo valen comparaciones relativas dentro de la misma serie, y con
   el ACC en el segmento (`ACC (limb)`), no sobre el músculo. La dispersión
   repetición a repetición de la velocidad de pico en un curl con 2 kg es,
   *inferencia* a partir del banco del ensayo F‑V y del informe
   `investigacion_acelerometro_emg.md` (§«Lo que NO conviene afirmar»), de
   decenas de por ciento: una tendencia solo se vería si fuera grande, y por
   (1) no hay motivo para que lo sea.

Lo que el ACC **sí** daría, si algún día se quiere la variante en Cinemática:
el recuento y la duración de cada movimiento (cadencia: ¿siguió el ritmo?),
el retraso electromecánico por repetición (`emd_ms`, que la tabla ya
calcula con el ACC en el segmento) y un indicio de relajación incompleta
mecánica (el segmento no vuelve a la posición de partida). Propuesta: el
mismo guion `RHYTHM` ejecutable en Cinemática con «carga fija 2 kg» en una
fase posterior, sin prometer una curva de velocidad.

**El experimento solo con EMG**, isométrico contra la mesa, puño cerrado
(sin carga en la mano; si Ángel prefiere una mancuerna fija, 2 kg y curl de
antebrazo, con el mismo guion). Objetivo docente: *relación ritmo–amplitud*
—qué le pasa al pico de cada contracción y a la MDF cuando el ritmo se acelera—
y la **relajación incompleta**: al acelerar, la envolvente no vuelve al reposo
entre contracciones (el «nivel de reposo» entre pulsos sube), y se mide en el
mismo registro.

> **Corregido el 24 de octubre** (la primera versión decía «correlato EMG de
> la suma temporal», y es un error): la suma temporal es mecánica, la fusión
> de las sacudidas en la fuerza; el EMG refleja la descarga de las
> motoneuronas. Que la envolvente no vuelva a reposo entre pulsos rápidos se
> debe sobre todo a que la relajación voluntaria no se completa, y podría
> deberse también a la constante de tiempo del filtro de la envolvente, que
> el §10.3 cuantifica: con el filtro de la aplicación es despreciable a 3,
> 2 y 1.5 s.

| # | Fase | s | Texto | Overlay | Marca |
|---|---|---|---|---|---|
| 0 | Reposo | 5 | «Reposo.» | `show_relax` | `RHYTHM start blocks=3 v=1` |
| 1 | Bloque 1: 8 contracciones, una cada **3 s** (1 s apretar, 2 s soltar) | 24 | «Al tono, apriete **fuerte** un segundo y suelte. Una cada tres segundos.» | `show_phase` con el pulso; tono en cada contracción | `RHYTHM block start k=1 period=3 reps=8`; por contracción `RHYTHM rep start k=1 n=3` / `RHYTHM rep end k=1 n=3`; `RHYTHM block end k=1` |
| — | Reposo | 10 | «Suelte. Reposo.» | | — |
| 2 | Bloque 2: 8 × cada **2 s** (1/1) | 16 | «Ahora una cada dos segundos.» | | `k=2 period=2 reps=8` |
| — | Reposo | 10 | | | |
| 3 | Bloque 3: 10 × cada **1 s** (0.5/0.5) | 10 | «Ahora una por segundo, cortas.» | | `k=3 period=1 reps=10` |
| — | Reposo final | 10 | «Suelte. Fin de las sucesivas: la grabación se detiene sola.» | `show_done` | `RHYTHM end` |

Total 85 s. El tono por contracción es el motivo `phase` (120 ms); en el
bloque 3 suena cada segundo, por encima de los 250 ms de silencio previo
que `cue.py` necesita (banco de ecg: cada 4 s se oía, cada 12 s no). Las
marcas por contracción permiten *una fila por contracción* sin depender del
detector, que en el bloque 3 (0.5 s) fusionaría pulsos
(`merge_gap_s=0.3`, `min_duration_s=0.5` en `contraction_table`). **Decisión
de Ángel**: los tres ritmos (3/2/1 s) y si el bloque 3 es demasiado rápido
para un alumno sin práctica (alternativa: 3/2/1.5 s).

### 4.4 La gramática de las marcas

```
<FAMILIA> start <k=v…> v=1        cabecera de la sesión (versión del guion)
<FAMILIA> <fase> start <k=v…>     abre una fase medida
<FAMILIA> <fase> end <k=v…>       la cierra
<FAMILIA> end                     fin de la sesión (completada o cancelada)
```

con `FAMILIA ∈ {GRAD, RHYTHM, HOLD}`, mayúsculas ASCII, `k=v` sin espacios
y los números con punto decimal (`period=1.5`). Igual que `CAL start ch=1
rep=1`: el lector es una expresión regular por familia, insensible a
mayúsculas, y una fase abierta sin cierre se descarta (grabación detenida a
mitad), como hace `parse_phase_markers` (`phases.py:244–292`). `v=1` en la
cabecera permite cambiar un guion sin romper la lectura de los registros
antiguos. Se distinguen de las manuales (texto traducido, `is_manual_mark`)
y de las de fase (`is_phase_marker`) sin ambigüedad; `is_session_marker`
las reconoce y el worker de análisis las quita de las que dibuja (§1.2).
En la lista de últimas marcas de la pestaña aparecen como aparecen hoy las
`CAL` (*inferencia*: no he comprobado si `_on_marker_added` las filtra).

---

## 5. Qué muestra el análisis, qué va al informe y al móvil (punto d)

**Detección**: `parse_session_markers` en el worker (junto a
`parse_phase_markers`, `workers/analysis.py:437`) → `result["session"]`
(`kind`, `version`, tramos). El tramo analizado por defecto pasa a ser el de
la sesión cuando la hay (`rec_span` con una precedencia más, delante de
`REC start`), así la calibración queda fuera sin tocar los fragmentos. El
editor de fragmentos sigue disponible.

### 5.1 Gradación

- **Filas de la tabla de contracciones = escalones** (el patrón de
  `_ventanas_de_carga` con `GRAD step`), recortadas al esfuerzo como hoy.
  Columna «#» pasa a «Escalón» con el objetivo («1 · 20 %»). RMS (mV), pico
  (% CVM) y MDF ya están.
- **Gráfico**: vista nueva `steps` en `draw_contraction_chart`: barras de
  RMS (mV) o de pico (% CVM) por escalón, con el objetivo como línea
  punteada en la barra cuando hay CVM. Se ofrece por defecto en esta sesión.
- **Fichas**: «Escalones: 5 de 5», «Monótona: sí/no» (cada escalón mayor que
  el anterior), «Cociente 100/20 %».
- **Informe**: sección «Sesión guiada: gradación» con la tabla de escalones
  y el gráfico de barras (`_seccion_sesion`, patrón de
  `_seccion_contracciones`). Las secciones generales siguen igual.
- **Móvil**: en vivo, `calib` con `phase="step"`, `count="40 %"`, `progress`
  y `effort` (rama nueva en `setCalib`; hoy una fase desconocida se pinta
  como «done»); tras el análisis, `results` gana `session={"kind":"grad",
  "rows":[{"k":1,"pct":20,"rms":…,"peak":…},…]}` y el móvil lo lista bajo
  las cifras que ya muestra.

### 5.2 Contracción máxima mantenida

- **Tramo = la fase `HOLD`**, de serie; un solo fragmento, así `t_seg` no
  es tiempo concatenado (§1.2).
- **Paneles 7 (MDF/tiempo) y 6 (RMS/ventana) ofrecidos y marcados por
  defecto** en esta sesión (`_panel_is_offered` + marcados iniciales por
  sesión), además de 1, 2 y 3.
- **Fichas**: las que hay (pendiente Hz/s, R², veredicto, caída %) y dos
  nuevas: «MDF primeros 5 s / últimos 5 s» y **«Tiempo hasta −10 %»** (y
  −20 %): primera ventana cuya MDF queda por debajo del (1 − X) de la
  mediana de las tres primeras ventanas activas; «no alcanzado» si no
  ocurre. Función `time_to_decline(t_seg, mdf_seg, active, pct)` en
  `fatigue.py`, sin Qt.
- **Informe**: sección «Sesión guiada: contracción máxima mantenida» con la
  tabla (MDF y RMS en los primeros y últimos 5 s, pendiente, R², veredicto,
  tiempos a −10/−20 %) y los paneles 6 y 7 (ya se renderizan panel a panel).
- **Móvil**: `calib` con `phase="contract"` (ya existe: `secs`, `progress`,
  `effort`); `results` ya lleva `mdf_slope` y `fatigue`; añadir
  `session={"kind":"hold","t10":…,"pct_decline":…}`.

### 5.3 Contracciones sucesivas

- **Filas = contracciones marcadas** (`RHYTHM rep`), en orden, con el bloque
  en la columna «Músculo» reaprovechada o una columna «Bloque» (ancho: hay
  2.8 cm libres en el PDF cuando no hay segundo músculo, §1.2).
- **Gráfico**: la vista `series` que ya existe (pico por contracción en
  orden, tendencia, MDF en eje gemelo), con **separadores verticales por
  bloque** y, nuevo, la línea del **nivel de reposo entre contracciones**
  (mediana de la envolvente en cada hueco entre `rep end` y el siguiente
  `rep start`), que es lo que enseña la relajación incompleta.
- **Fichas**: por bloque, «pico medio», «MDF media», «reposo entre
  contracciones (% CVM o mV)».
- **Informe**: sección con la tabla por bloque (ritmo, n, pico medio, MDF
  media, reposo entre contracciones) y el gráfico `series`.
- **Móvil**: `calib` con `phase="rhythm"`, `count` = «3 / 8», tono en el
  propio ordenador (el móvil no suena: no hay API de audio sin gesto del
  usuario y no merece la pena); `results.session` con las filas por bloque.

---

## 6. Relación con el encargo E (punto e)

Comprobado: en el repositorio **no hay ningún documento del encargo E** sobre
partir `AcquisitionTab`; la única mención a «encargo E» (`PLAN-teachcore.md:
153`) es sobre `full_scale_mv()`. Lo que sí hay son 5679 líneas con cuatro
máquinas de estados a mano (§1.1) y la constancia en `DECISIONS.md:566–626`
de que se eligió no mover ficheros.

**Recomendación: no hacer E antes, pero no repetir su defecto.** Lo que
engorda la pestaña no es un botón, son las máquinas de estados dentro de ella
(CVM ≈ 1070 líneas, 3422–4489; F‑V ≈ 500, 4490–4986). Este encargo pone la
suya **fuera** desde el primer día (`SessionRunner` + `sessions.py`, §2.2) y
la pestaña solo conecta señales: ≤ 200 líneas, con la cota comprobable en la
PR (`wc -l` antes y después). Eso es, de hecho, el primer paso de E en la
dirección correcta y a coste cero.

Si Ángel quiere adelantar una parte de E, la única que **paga** aquí es
pequeña y opcional (~1 jornada): mover el asistente F‑V a un `SessionRunner`
con su `cue_script`, que ya existe sin Qt. Demostraría el runner sobre un
flujo real antes de confiarle los tres experimentos y quitaría ~400 líneas
de la pestaña. No es necesario para entregar la gradación. El resto de E
(CVM, par, repaso, difusión) queda para después, con las sesiones como primer
cliente del patrón.

---

## 7. Fases, coste, riesgos y orden (punto f)

Unidad: jornadas de trabajo con la placa simulada; el banco con la placa real
va aparte en cada versión. Cada PR deja la aplicación entregable y pasa la
CI (incluido el recuento de pruebas del README).

| Fase | PR | Contenido | Coste |
|---|---|---|---|
| **0 · Cimientos** | 1 | `sessions.py` (tres guiones, marcas, lector, tramos), `cue.py`, `MvcOverlay.flash`, `SessionRunner`, desplegable + armado + brazo tras `REC` + cancelación + parada, filtro en el worker de análisis, sombreado del repaso, nombre de fichero, `i18n`. Pruebas sin Qt de guiones y lector; runner con reloj falso; una prueba de GUI por experimento (marcas en el EDF, §8). | ~2 jornadas |
| **1 · Gradación** | 1 | Filas por escalón, vista `steps`, fichas, sección del informe, móvil (rama `step` + `results.session`), manual/guion 1b/chuleta/ayuda. Pruebas con la placa simulada (§8). | ~2 jornadas |
| **2 · Fatiga** | 1 | Tramo = `HOLD`, paneles 6/7 por defecto, `time_to_decline`, fichas, sección, móvil, guion 1c actualizado. Pruebas con EDF sintético de MDF decreciente. | ~1.5 jornadas |
| **3 · Sucesivas** | 1 | Filas por contracción, bloques, nivel de reposo, `series` con separadores, fichas, sección, móvil, guion 1e nuevo. | ~1.5 jornadas |
| **4 · Versión 3.10.0** | 1 + etiqueta | CHANGELOG, notas de versión, README, manual, informe Sourcebook; banco con la placa real (tono en el PC del laboratorio, 125 %); `PLAN-teachcore.md` anota `cue.py`. | ~1 jornada |

La fase 0 puede ir en la misma PR que la 1 si se prefiere una sola entrega
con la gradación de punta a punta (~4 jornadas); separadas, la 0 se revisa
sin ruido de análisis. Versión **3.10.0**, no 3.9.x: añade funciones y
anotaciones nuevas al EDF (los registros antiguos se leen igual: una
grabación sin marcas de sesión es una grabación libre).

**Riesgos y qué se hace con cada uno**

- *El tono solo está probado en Windows* (`winsound`); en Linux/CI cae a
  `QApplication.beep`. Las pruebas portadas de ecg prueban `render_tone` y la
  lógica del cerrojo, no el sonido; el banco de la 3.10.0 debe oír las tres
  sesiones en el PC del laboratorio (lección del 5 de octubre: los tonos
  intermedios no sonaban sin los 250 ms de silencio).
- *Una fase máxima de 30 s puede no dar «fatiga detectada»* en todos los
  sujetos. Es un resultado legítimo (el veredicto ya contempla «no
  concluyente») y el guion lo explica; el tiempo a −10 % da una cifra aunque
  la recta no ajuste. Si en el banco sale no concluyente a menudo, subir a
  45 s.
- *Seguridad del esfuerzo máximo*: texto que manda respirar y soltar si
  duele, 45 s de tope, advertencia en el manual (§4.2).
- *`_mvc_enter_prep` sin calibración previa* (sucesivas, y fatiga sin CVM):
  solo lo llama `_mvc_finish_all` (4432); hay que ver qué estado presupone.
  Si no arranca limpio, el runner escribe `PREP`/`REC` él mismo con las
  mismas funciones de `phases.py`.
- *Tres decisiones vigentes que hay que cambiar*: «the one-muscle practical
  has no guided end» en `DECISIONS.md:58–61`, `CHANGELOG.md:75` y el
  docstring de `_parar_al_terminar_sesion`. Se anotan en `DECISIONS.md` con
  la fecha del encargo.
- *El bloque 3 de las sucesivas (una por segundo)*: puede ser demasiado
  rápido para seguirlo; el banco lo dirá y los períodos son parámetros del
  guion.
- *El detector de contracciones no se usa para las filas de las sesiones*:
  se usan las marcas. Así una sesión no depende de `k` ni del umbral, y los
  `Onset (auto)` que sigan escribiéndose no cambian nada.
- *Altura a 125 %*: el desplegable va en una fila que ya existe; se comprueba
  en el banco como se comprobó «Marcar (M)».
- *Dos idiomas*: todos los textos pasan por `tr()` y entran en `_ES`; el
  `test_i18n` los exige. Las marcas no se traducen.

---

## 8. Pruebas previstas (punto g)

En el estilo de la suite (nombres que cuentan qué se comprueba; fixtures
`tab`/`recording`, `_until`, `_start`/`_stop` de `test_marcas_manuales.py`).
Los guiones aceptan los segundos por parámetro, así las pruebas de GUI usan
fases de 0.3–0.5 s como hace ecg (`test_sessions_need_data.py:158–176`) y
`test_fv_rehearsal.py` con `_fv_tick`.

**Sin Qt (`tests/test_sesiones.py`)**

- Cada guion encaja sin huecos y su duración total es la suma (como
  `test_the_cues_tile_the_run_without_gaps`).
- Las marcas se escriben y se leen de vuelta: cinco escalones con su `pct`,
  tres bloques con sus repeticiones, un `HOLD` con sus segundos; una fase sin
  `end` se descarta; `v=1` se lee; mayúsculas/minúsculas; una marca manual
  («Fatiga», «Fatigue») y una `CAL` no son marcas de sesión y viceversa.
- `session_spans` devuelve los tramos ordenados y recortados al registro.
- `time_to_decline`: con una MDF que cae linealmente de 100 a 80 Hz en 30 s
  da 15 s a −10 % y «no alcanzado» a −30 %; con MDF plana, «no alcanzado».
- `cue.py`: las pruebas de `test_cue.py` de ecg (síntesis, motivos, cerrojo).

**El runner con reloj falso (`tests/test_session_runner.py`)**

- Con `tick_ms=100` y un guion de gradación de 0.5 s por fase, al avanzar el
  reloj a mano emite `marker` en el orden y los instantes del guion (±1 tick),
  `cue` en cada cambio de fase, `instruct(0.2)`, …, `instruct(1.0)` y
  `instruct(None)` en los reposos, y `finished(True)` al final; `cancel()`
  emite la marca de fin y `finished(False)`; `skip()` salta la fase.

**Con la placa simulada (`tests/test_sesion_gradacion.py`, etc., marcadas
`gui`)**

- *Las fases quedan marcadas en el EDF a su tiempo*: se elige «Gradación»,
  «Iniciar grabación», y al detenerse sola el EDF lleva `GRAD start`, cinco
  pares `step start/end` y `GRAD end`; cada `step start` cae a `t_anterior +
  reposo` con tolerancia de un bloque de la placa simulada (y lo mismo en
  `.eventos.txt`). Es la prueba de la fase 0, una por experimento.
- *El análisis saca las cifras*: la pestaña de análisis adopta el registro
  (`recording_saved` → `adopt_recording`) y, con el sujeto simulado
  instruido a 0.2 … 1.0, `result["contractions"]` tiene cinco filas con
  RMS estrictamente creciente y `result["session"].kind == "grad"`; el
  gráfico de barras se dibuja (`draw_contraction_chart(view="steps")` sin
  excepción) y el PDF contiene la tabla (`_pdf_text` de
  `test_informes_y_csv.py`).
- *Sucesivas*: con `instruct(level, repeat_s=period)` el sujeto hace las
  contracciones; el EDF lleva 8 + 8 + 10 pares `rep start/end` dentro de sus
  bloques; el análisis da 26 filas en orden y tres bloques con n correcto.
- *Fatiga*: el sujeto simulado no se fatiga (su MDF es la del ruido
  filtrado, constante), así que la prueba de GUI comprueba las marcas, que el
  tramo analizado es el `HOLD`, que el panel 7 está ofrecido y marcado y que
  el veredicto es «none» o «inconclusive»; las cifras (pendiente negativa,
  tiempo a −10 %) se prueban sobre un **EDF sintético** con MDF decreciente
  escrito como hace `write_rehearsal_edf` (ruido blanco filtrado con la banda
  bajando de 120 a 80 Hz). Opcional (~0.5 jornada): dar al sujeto simulado
  una fatiga (`instruct(..., fatigue_s=)`) para que la prueba de GUI vea la
  caída también.
- *Con «Ninguna» nada cambia*: `_iniciar_grabacion` no arma la sesión, no se
  escribe `PREP`/`REC` ni marca de sesión, «Calibrar CVM» a mano sigue
  funcionando (las pruebas de 3.9.x ya lo cubren; se añade la aserción
  negativa).
- *Esc a mitad*: se escribe `GRAD end`, la grabación sigue libre y el
  análisis lee los escalones completados.
- *Cierre de la ventana durante una sesión*: no deja timers vivos ni abre
  «Guardar como» (lección de #130/#131; `cleanup` para el runner).

Recuento: ~35–45 pruebas nuevas; el README y `.zenodo.json` se actualizan en
cada PR como manda `test_the_test_count_is_current`.

---

## 9. Decisiones que quedan para Ángel

1. Tono siempre (sin casilla) o casilla recordada como en ecg (§2.1).
2. Gradación: exigir CVM, o permitirla sin CVM con niveles verbales (§4.1).
3. Fatiga: máxima 30 s (propuesta) frente al 50 % de 30–60 s del guion 1c;
   tope de 45 s (§4.2).
4. Sucesivas: solo EMG isométrico (propuesta) o con mancuerna fija de 2 kg;
   los ritmos 3/2/1 s (§4.3).
5. Fases 0 y 1 en una PR o en dos (§7); si adelantar el F‑V al runner (§6).

---

## 10. Decisiones de Ángel (24 de octubre) y lo que cambian

1. **Tono**: casilla «Tono en cada cambio de fase» recordada entre
   sesiones (`QSettings`), activada por defecto, como en ecgteach.
2. **Gradación**: exige CVM calibrada; sin variante de niveles verbales.
3. **Fatiga**: contracción **máxima, 30 s**, tope 45 s; el ejercicio 1c del
   guion se actualiza. **Variante intermitente** dentro de la misma sesión
   (segunda opción del desplegable): contracción máxima **5 s / reposo 1 s,
   10 veces**, tono al empezar y al acabar cada contracción y cuenta atrás
   visible. Medida: **RMS de cada contracción** (no el pico, que es el
   arranque y no baja) y MDF por contracción, en tabla y barras. Pilotos de
   Ángel (24 de octubre, músculo ya cansado): con 5/1 s el RMS bajó de
   0.108 a 0.085 mV (−21 %), casi monótono en diez contracciones; con 5/2 s
   y 5/5 s la caída fue irregular. Se confirma en el banco con la app.
4. **Sucesivas: se quitan como sesión.** Piloto de Ángel con la placa real
   (24 de octubre): a 3, 2 y 1.5 s el pico de la envolvente no cambia
   (~0.20 mV) y vuelve a cero; solo un tren lo más rápido posible sube algo
   los picos y deja el suelo algo por encima de cero, y sin control de
   fuerza no es concluyente. Queda un **comentario al margen** en los
   manuales (es/en), en la práctica de contracción simple, prudente, con la
   cuantificación del filtro del §10.3.
5. **PR**: cimientos y gradación por separado; el paso del F‑V al runner,
   ahora no.

### 10.1 Orden de entrega (una rama y una PR por punto, sin fusionar)

0. El hallazgo de `_ofrecer_descargas`, aparte, con una prueba que falle sin
   el arreglo.
1. Cimientos: `sessions.py` sin Qt, `SessionRunner`, `cue.py`, desplegable,
   destello, marcas y lector.
2. Gradación: adquisición, análisis, PDF y móvil.
3. Fatiga: máxima mantenida y variante intermitente; el comentario de las
   contracciones seguidas en los manuales.
4. Versión 3.10.0 y banco.

Tras cada PR de la 2 y la 3, *Build Windows exe* a mano sobre la rama, con
su SHA-256, para probarla con la placa simulada antes de fusionar.

### 10.2 Las marcas, sin `RHYTHM`

Quedan dos familias: `GRAD` y `HOLD`. La variante intermitente es `HOLD`
con `mode=intermittent` en la cabecera y una fase por contracción:

```
HOLD start mode=sustained secs=30 v=1
HOLD end

HOLD start mode=intermittent reps=10 on=5 off=1 v=1
HOLD rep start n=1   …   HOLD rep end n=1
…
HOLD end
```

### 10.3 Cuánto sube el «nivel entre pulsos» solo por el filtro

Calculado el 24 de octubre con el filtro real de la envolvente (Butterworth
de orden 2 a 5 Hz, `design_lowpass`; `sosfiltfilt` en el análisis,
`dsp.py:298`, y causal en vivo, `dsp.py:228`), a 1000 Hz, sobre pulsos
ideales de actividad (rectangulares, y ruido gaussiano rectificado con el
mismo encendido), con reposo perfecto entre ellos. Nivel entre pulsos =
mediana de la envolvente en el hueco, en % del pico medio; promedio de seis
ciclos.

| Período | Encendido / hueco | Pulso ideal: análisis / en vivo | Ruido rectificado: análisis / en vivo | Reposo inicial |
|---|---|---|---|---|
| 3 s | 1 / 2 s | 0.0 % / 0.0 % | 1.8 % / 1.7 % | 1.8 % |
| 2 s | 1 / 1 s | 0.0 % / 0.0 % | 1.8 % / 1.7 % | 1.7 % |
| 1.5 s | 0.75 / 0.75 s | 0.0 % / 0.0 % | 1.8 % / 1.8 % | 1.8 % |
| 1.5 s | 0.5 / 1 s | 0.0 % / 0.0 % | 1.8 % / 1.8 % | 1.7 % |
| 1 s | 0.5 / 0.5 s | −0.1 % / 0.0 % | 1.6 % / 1.7 % | 1.8 % |
| 0.5 s | 0.25 / 0.25 s | 1.4 % / −0.3 % | 3.2 % / 1.5 % | 1.8 % |

**Conclusión: a 3, 2 y 1.5 s el filtro no sube nada el nivel entre pulsos**
(lo que queda es el propio nivel de reposo, igual que antes de empezar). Su
constante de tiempo es de unas decenas de milisegundos y el hueco más corto
de esos ritmos es de 0.75 s. Solo a dos o más contracciones por segundo
empieza a notarse (1.4 % en el análisis a 0.5 s). Así que, si en un registro
real el suelo entre pulsos sube a esos ritmos, **es del sujeto** (la
relajación que no se completa), no del procesado; no hace falta cambiar de
señal para medirlo. El cálculo está en el comentario al margen de los
manuales; el script, en la PR de la fatiga como prueba.

### 10.4 Anotado, sin implementar: la CVM por tren

Idea de Ángel (24 de octubre): tomar como referencia el **pico de un tren
de unas seis contracciones máximas rápidas**, para que el alumno no vea
contracciones por encima del 100 % CVM. Se mantiene la calibración actual.

- *A favor*: el tren se acerca más al pico que el alumno alcanza luego en la
  tarea, y el «más del 100 %» desaparece o se reduce, que en clase confunde.
- *Pegas*: no es la CVM de la literatura (isométrica sostenida, 3–5 s,
  con la ventana de pico que ya usa la aplicación), así que los % CVM
  dejarían de ser comparables con los rangos publicados (Jonsson, APDF) y
  con los registros hechos hasta ahora; el pico de un tren es más ruidoso
  (un único máximo instantáneo) y depende de la velocidad de cada alumno;
  y un tren de máximos rápidos cansa antes de la tarea.
- *Prueba comparativa necesaria antes de decidir*: los mismos sujetos, en
  orden alternado y con descanso, con **tres máximas aisladas** (la
  calibración actual) frente a **un tren de seis**; comparar la referencia
  (cociente tren/aisladas y su dispersión entre sujetos), la repetibilidad
  de cada una en dos días, y el % CVM que da cada una a la misma tarea
  (gradación y APDF). Si el tren da referencias sistemáticamente mayores y
  igual de repetibles, se podría ofrecer como alternativa marcada en el
  fichero (`MVC ref … method=train`), nunca sustituyendo a la actual.

---

## Hallazgo fuera del encargo

`_ofrecer_descargas` (`gui/tabs/analysis.py:2150`) pasa a
`build_session_report` los **índices de pantalla** de las casillas
(`enumerate(self._chk_paneles)`) en lugar de los `pid` (`_generar_informe`
sí los convierte, 2966, y el resto de la pestaña usa `self._panel_pids[i]`,
2448 y 3425). Como el orden de pantalla es 0, 3, 4, 1, 2, …, el PDF que
reciben los móviles lleva paneles equivocados: la casilla «2. Env. norm.»
sale como filtrada + rectificada. Comprobado en el código; no probado en la
aplicación. Arreglo de una línea, aparte de este plan.

## 11. Banco de la 3.10.0 con la placa real (26 de octubre)

Exe de la ejecución manual #133. Corregido en la rama `banco-3.10.0`: los
escalones, las contracciones intermitentes y el tren son la actividad dentro
de sus marcas seguida 1.5 s más allá de su final (§11.1); el registro afinado
conserva la sesión; la referencia de la gradación es la mayor entre la CVM y
el máximo de la sesión; y el tren no da veredicto de fatiga.

### 11.1 Pico frente a media (punto 4)

**Decisión de Ángel (26 de octubre): la propuesta A, solo en la gradación, y sin el punto 3** (la referencia = máx(CVM, sesión) se revierte: bajaba todos los escalones a la vez). Implementado: `sessions.GRAD_MVC_WINDOW_S`; si el escalón máximo pasa de la calibración, la vista y el informe lo dicen.

La CVM es **el pico de la envolvente** (`mvc_peak_window_s = 0`, desde la
3.2.0), y el «mantenido» de un escalón es **una media** sobre su meseta. Un
nivel medio no llega al pico de la misma envolvente aunque la intensidad sea
la misma: el pico es un máximo del ruido de la envolvente, no un nivel.
Medido con ruido gaussiano por los mismos filtros (20 repeticiones;
calibración de 1.5 s y contracción mantenida a la misma amplitud):

| | referencia = pico | referencia = mejor media de 0.5 s |
|---|---|---|
| mantenido / referencia, análisis (fase cero) | **87 %** | 95 % |
| barra en vivo (bloque de 100 ms / referencia en vivo) | **85 %** | 96 % |

Es decir: con la referencia en el pico, mantener exactamente la intensidad de
la calibración se lee como 85–87 %, y el «100 %» de la barra es inalcanzable
sosteniendo. Eso, más la parte del punto 1 (el reposo del principio dentro
del escalón), explica el 17/27/42/60/69 frente a 20/40/60/80/100. La envolvente
en vivo (causal, filtros de orden 2) sale un 10 % por encima de la del
análisis (fase cero) tanto en el pico como en la meseta, así que entre las dos
el cociente se compensa.

Propuesta, de menor a mayor alcance:

- **A (recomendada para la 3.10.0): solo en la gradación**, la CVM de la
  calibración que la abre y todo lo que la compara (la barra en vivo de los
  escalones, el mantenido, la referencia de la sesión del punto 3, la columna
  «Pico» de la tabla y el máximo de la tarea) con la **mejor media de 0.5 s**.
  Igual con igual, y las demás prácticas no cambian.
- **B: en toda la aplicación**, `mvc_peak_window_s = 0.5` por defecto. Todos
  los % CVM suben un ~9 % (pico/media de 0.5 s en una calibración breve), y se
  deshace la decisión de la 3.2.0 (referencia = punto más alto): un registro
  reanalizado daría otros porcentajes, lo que exige nota de versión.

### 11.2 Fatiga: fallos anotados, sin implementar (el protocolo va a cambiar)

Ángel probará bíceps con carga fija (codo a 90°, 3–5 kg, 60–90 s); en las tres
pruebas con el flexor del antebrazo la MDF quedó plana (pendientes ≤ ±0.2 Hz/s,
R² ≤ 0.07) y la RMS del máximo cayó a un tercio en 4–5 s y luego meseta
(pérdida de esfuerzo, no fatiga). Valen para cualquier protocolo:

7. **El resumen propio de la sesión mantenida no aparece** (MDF y RMS de
   inicio y final, segundos hasta −10 % de la MDF), solo el genérico.
   Hipótesis a comprobar: `result["hold"]` solo se calcula sin fragmentos
   elegidos (`not self._roi_segments` en `workers/analysis.py`); tras
   «Seleccionar fragmentos» queda en `None`. Si la sesión se paró antes de
   su marca de fin, también falta el tramo del esfuerzo.
8. **Una contracción sostenida se parte en trozos**: en
   `m_2026-10-26_10-17-16.edf` (una de ~60 s, grabación libre) la tabla da
   cinco (2.0, 3.5, 24.2, 36.5 y 47.0 s, varias de menos de 1 s). El
   detector (`selection.suggest_significant_segments`: umbral de k·DE sobre
   el reposo, prominencia 0.25 del pico, une huecos de menos de 0.3 s) corta
   cuando la meseta, a un tercio del pico inicial, cruza el umbral relativo.
   Necesita histéresis (umbral de salida por debajo del de entrada) o una
   duración mínima de reposo para cortar. **Comprobado en el archivo** (con
   permiso de Ángel): el reposo verdadero es de 0.004 mV y solo dura los
   primeros 2 s y los últimos 2 s; la meseta, a ~0.07 mV, ocupa 50 de los 63 s.
   El detector estima la línea de base sobre el 40 % más tranquilo de la
   envolvente y `resting_level` sobre su percentil 10 (0.050 mV), así que los
   dos toman **la meseta por reposo**: solo los picos que sobresalen de ella
   salen como contracciones. La raíz es la estimación del reposo cuando el
   reposo es corto; el arreglo, tomarlo del tramo tranquilo más largo (o de la
   pausa de preparación, como ya hace la tabla con `_cola_de_la_pausa`).
9. **«sin calibrar» en la barra tras una sesión que sí calibró**: cada
   grabación nueva vacía el monitor de carga (`_reset_load_monitor` al
   empezar a grabar, en `gui/tabs/acquisition.py`), así que una grabación
   libre después de la sesión calibrada no tiene CVM ni barra. Es la decisión
   de «cada registro se calibra a sí mismo» de la 3.8.0; si la grabación libre
   debe poder usar la CVM de la sesión anterior del mismo alumno, hay que
   decidir cuándo caduca (otro alumno, otro músculo, electrodos movidos).
   Comprobado en los archivos: la grabación libre `m_2026-10-26_10-17-16.edf`
   no lleva calibración ni anotación `MVC ref` (la de 0.4146 mV está en la
   gradación `m_graduales_2026-10-26_10-31-36.edf`, cuyo análisis sí la usa,
   recalculada de sus tres repeticiones: 0.397 mV), así que «sin calibrar» es
   lo que esa grabación tiene; lo que falta es poder llevar la CVM de la
   sesión anterior a la grabación libre.

### 11.3 Lo que dicen las grabaciones del banco (con permiso de Ángel)

Analizadas con el código de `main` (el exe #133) y con el de la rama:

- **Tren rápido** (`m_rapidas_2026-10-26_10-38-41.edf`): 28 contracciones con
  `main`, **30** con la rama; la última, a 10.36 s del aviso (la franja dura
  10 s). Ritmo 2.9/s; suelo entre contracciones un 9-10 % del pico, lo mismo
  que deja la medida sola: relajación completa.
- **Las dos grabaciones con la sesión de gradación**
  (`m_graduales_2026-10-26_10-25-29.edf` y `_10-31-36.edf`) **no son
  gradaciones, sino dos de las pruebas de fatiga** hechas con su barra (lo
  aclara la conversación del banco): un máximo sostenido de unos 47 s (la
  envolvente cae de 0.3 a 0.1 mV desde el primer escalón hasta el final) y un
  ~45 % de la CVM mantenido unos 36 s (estable en 0.17-0.20 mV entre los 47 y
  los 83 s, MDF plana). Por eso entre las franjas no hay reposo y el nivel no
  sube. **La gradación del informe del banco (17/27/42/60/69 % mantenido;
  33/60/68/81/127 % de pico) no está entre estos archivos**: hace falta su EDF
  para comprobar los puntos 1 y 3 con datos reales. Lo que sí muestran: con la
  rama, la regla de los tramos sigue la actividad (en la primera, el primer
  escalón empieza 0.9 s después de su aviso), y el registro afinado de la
  segunda a sus cinco contracciones se reabre con la sesión entera.
- **La gradación del banco** (`m_graduales_2026-10-26_09-48-16.edf`, con su
  `_tuned` hecho con el exe #133, que conserva las repeticiones 1 y 3 de la
  calibración: CVM 0.322 mV). Con `main` salen exactamente las cifras del
  informe: mantenido 17/27/42/60/69 %, picos 33/60/68/81/111 % y máximo de la
  tarea 127 %. El `_tuned` del #133 perdió las marcas de inicio de los cinco
  escalones (quedan solo los finales), así que se abre sin sesión: el punto 2,
  confirmado. Afinado con la rama, se reabre con sus cinco escalones.
  Mantenido (mV): 0.052, 0.087, 0.142, 0.196, 0.199, medido con la rama
  sobre la contracción (que empieza 0.7-1.0 s tras cada aviso). Según la
  referencia:

  | referencia | 20 | 40 | 60 | 80 | 100 |
  |---|---|---|---|---|---|
  | `main`: CVM pico (0.322), mantenido entre marcas | 17 | 27 | 42 | 60 | 69 |
  | rama (punto 3): máx(CVM, sesión) en pico (0.410) | 13 | 21 | 35 | 48 | 49 |
  | propuesta A: CVM mejor media de 0.5 s (0.241) | **22** | **36** | **59** | **81** | 83 |
  | A + punto 3: máx(CVM, sesión) en 0.5 s (0.306) | 17 | 29 | 46 | 64 | 65 |

  Medidos igual con igual (A), los cuatro primeros escalones son los pedidos:
  el sujeto siguió la barra. El escalón máximo sí pasó la calibración, con las
  dos medidas (pico 127 %, media de 0.5 s 127 %): la referencia de la sesión
  del punto 3 lo recoge, pero baja todos los demás a la vez. Hay que decidir
  si el punto 3 se queda con A o solo limita la columna «Pico».

## 12. La fatiga con carga fija (26 de octubre, tarde)

Ángel probó el bíceps con un peso fijo, el codo a 90° y unos 90 s, en una
grabación libre (`biceps_2026-10-26_12-21-27.edf`, abierta con su permiso).
Lo que mostró:

- **La MDF cae y el RMS no.** Del 2.º segundo tras empezar la actividad hasta
  que cae, la recta de la MDF va de 79 a 66 Hz (−17 %) con p ≈ 4·10⁻¹⁷ y un R²
  de solo 0.32; la MNF baja con ella; el RMS se queda en 0.09-0.10 mV
  (p = 0.09). La MDF cae un 10 % hacia los 22 s.
- **El R² no sirve de umbral.** El espectro de una ventana de 1 s tiene una
  dispersión propia grande: con un R² ≥ 0.30 como condición, una caída real
  quedaría en el límite. Lo que dice que la caída es real es la significación
  de la pendiente sobre 170 ventanas.
- **El reposo salió alto** (0.028 mV de mediana): contacto de los electrodos
  dudoso, aunque el espectro siga siendo legible.

Decisiones de Ángel («barra para final anticipado y lo demás que propones»):

1. **Una sola sesión de fatiga**, «Fatiga: bíceps con carga fija»: 5 s de
   reposo medido, 3 s de cuenta atrás para coger el peso, **90 s** sostenido
   (como mucho 180) y 5 s para dejarlo. Se quitan la contracción máxima
   mantenida y las contracciones intermitentes: con el flexor del antebrazo
   la MDF quedó plana y lo que cayó fue el esfuerzo (§11.2).
2. **La barra espaciadora termina el esfuerzo antes de tiempo** (y un botón
   «No puedo más (Espacio)»). La marca de su final lleva `early`; la sesión
   pasa al último reposo y las fases siguientes conservan su duración.
3. **Sin barra durante el esfuerzo**: la carga es fija, no un nivel que
   alcanzar.
4. **Veredicto**: fatiga si la pendiente de la MDF es significativa
   (p < 0.01) y su recta cae al menos un 10 %; no concluyente si no es
   significativa o hay menos de 10 ventanas.
5. **Tramo analizado**: de 2 s después de que empiece la actividad hasta que
   cae o termina la marca del esfuerzo.
6. **Vista propia**, «MDF en el tiempo»: MDF y MNF en ventanas de 1 s cada
   0.5 s, sus medias en 5 s, la recta, R², p, cambio, el momento del −10 % y el
   RMS en gris. Informe con la gráfica y la tabla; móviles con el cambio de MDF
   y RMS, R² y el −10 %.
7. **Textos**: la fatiga baja la frecuencia; la amplitud puede mantenerse o
   subir.
8. **Aviso de reposo alto**, por encima de 0.01 mV.
9. **El sujeto simulado se fatiga** mientras sostiene un nivel, para ensayar
   la sesión sin placa.

Correcciones de Ángel sobre la #146 (26 de octubre, tarde): la colocación del
bíceps dice desde qué extremo (1/3 desde la fosa del codo, SENIAM), y **con
fragmentos elegidos la vista de la carga sigue** (el punto 7 de §11.2): se lee
en el trozo más largo de la carga que conservan los fragmentos, y si ninguno
conserva 3 s, la vista y el informe lo avisan.

**El aviso de mala señal**, medido en los dos registros del bíceps (el bueno,
`biceps_2026-10-26_12-21-27.edf`, y el malo, `_12-13-27.edf`, abiertos con
permiso de Ángel):

| | bueno | malo |
|---|---|---|
| reposo (mediana de la envolvente) | 0.019 mV | 0.022 mV |
| 50 Hz en reposo | 0.0075 mV | 0.0081 mV |
| pico de 50 Hz / mediana del espectro, registro entero | 38× | 83× |
| pico de 50 Hz / mediana, solo el reposo | 126× | 44× |
| esfuerzo / reposo, tramo de la carga | 3.7 | 1.5 |
| esfuerzo / reposo, segundos 2 a 5 (en vivo) | 4.1 | 1.1 |
| fatiga | MDF −17 %, p 4·10⁻¹⁷ | MDF −1 %, p 0.54 |

El 50 Hz es el mismo en los dos: el pico del malo es mayor solo porque su EMG
es débil, y en el reposo la proporción se invierte. Lo que los separa es la
relación esfuerzo/reposo. Decisión de Ángel: **aviso de señal débil por debajo
de ×2** («Señal débil: el esfuerzo apenas supera el reposo (×1.5). Revise el
contacto de los electrodos o use un peso mayor.»), en vivo a los 5 s y en el
análisis; **reposo alto a 0.03 mV**, solo como comprobación gruesa; el pico de
50 Hz, fuera.

De §11.2 sigue abierto el 8 (el detector parte una contracción larga en trozos si el
reposo es corto; el tramo de la carga no depende de él, la tabla sí) y el 9.

## 13. Banco final de la 3.10.0 (exe #138, a465ddb)

**B1: con fragmentos elegidos, la vista «Escalones» mostraba 1 escalón.** Ángel
eligió cinco fragmentos, uno por escalón, cada uno ceñido a su contracción.
Reproducido con la gradación del banco de la mañana
(`m_graduales_2026-10-26_09-48-16.edf`): con fragmentos de la marca + 0.8 s al
final + 0.6 s salían **0 escalones**; con fragmentos que contienen las marcas,
los 5. La causa: un escalón solo contaba con sus dos marcas dentro de un mismo
fragmento (`guided.spans_in_analysis_time`), y el sujeto empieza unas décimas
después del aviso, así que un fragmento ceñido a la contracción deja fuera la
marca de inicio. Ahora cada tramo se mide en el fragmento que más lo cubre, sobre
la parte que conserva, si es al menos el 60 % de su duración marcada
(`guided.measured_windows`). Con esos fragmentos sale 22/36/59/79/82 %, como sin
ellos (22/36/59/81/83).

**Confirmado con los EDF de B1** (`biceps_graduales_2026-10-26_17-25-09.edf`
y su `_tuned`, abiertos con permiso de Ángel). Los cinco fragmentos, rehechos
desde el `_tuned` (sus 22.9 s y la posición de cada «Inicio (auto)»), empiezan
en 45.62, 56.09, 65.93, 75.68 y 85.58 s: los cuatro primeros, 0.1-0.6 s
después de su aviso; el quinto, 0.02 s antes del suyo, el único con su marca
dentro.

| | `main` (a465ddb) | con la corrección |
|---|---|---|
| original, sin fragmentos | 28 / 28 / 47 / 50 / 72 | igual |
| original, los 5 fragmentos | solo el 100 %: 72 | 31 / 28 / 47 / 50 / 72 |
| `_tuned`, reabierto | 31 / 28 / 47 / 50 / 72 | igual |

**La hipótesis del afinado pegado no se confirma**: el `_tuned` (escalones
pegados, el primero en `REC start`, 0.7-0.8 s entre uno y otro) se reabre con
sus cinco escalones también antes de la corrección; el fallo era solo el de
los fragmentos elegidos. El afinado no se cambia.
