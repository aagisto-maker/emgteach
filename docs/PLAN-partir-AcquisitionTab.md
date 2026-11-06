# Plan para partir `AcquisitionTab` (encargo E) — 5 de noviembre de 2026

Sobre `main` en `99355fc` (3.10.1 publicada). Solo plan: sin rama, sin commits, sin editar nada.

**Estado.** Paso 0 fusionado el 5 de noviembre (#161). Paso 1, el aula, fusionado (#162; `gui/acquisition/broadcast.py`, `ClassroomBox`): 221 líneas fuera de la pestaña (6168 → 5947). Paso 2, la conexión, fusionado (#163; `gui/acquisition/connection.py`, `ConnectionBox`): 343 líneas fuera (5947 → 5604); se quedaron en la pestaña la espera del puerto, la escala del panel bruto y el aviso de difusion.txt. Paso 3, el trazado, fusionado (#167; `gui/acquisition/plots.py`, `LivePlots`): 1058 líneas fuera (5604 → 4546), con la escala del panel bruto que el paso 2 dejó (`follow_device`). La pieza recibe funciones que dan, cada vez que se usan, el perfil, el número de canales, si el acelerómetro está activo y los nombres de los canales, en vez de copias, como recibe el hilo la conexión: el trazado los leía en el momento, y así sigue (una copia del número de canales hizo fallar 16 pruebas de test_gui_session_phases). `FS`, `MAX_CHANNELS` y los colores de los canales siguen en la pestaña, que los usa en todas partes, y se dan a la pieza al construirla. Paso 4, el escenario, en su PR (`gui/acquisition/stage.py`, `FlowStage`): 54 líneas fuera (4547 → 4493). A diferencia de §2.4 se quedan en la pestaña colocar el panel guía (`_reposition_mvc_overlay`, que depende de la geometría de la pestaña y lo llama su `resizeEvent`) y parar la grabación al acabar una tarea guiada (`_parar_al_terminar_sesion`, que es de la grabación); irán con los flujos que los usan.

## 1. Lo que hay hoy

`src/emgteach/gui/tabs/acquisition.py`: **6168 líneas**, una clase con **178 métodos** (5520 líneas de métodos; las 632 primeras del archivo son el docstring, las importaciones, dos funciones del registro de eventos y unas 470 líneas de constantes con sus comentarios). Los dos métodos mayores son `_build_ui` (862 líneas) e `__init__` (312, con 109 atributos de estado); después, `_iniciar_grabacion` (247), `_mostrar_registro` (148), `_fv_tick` (115), `apply_mode` (115) y `_mvc_tick` (114).

He repartido los 178 métodos en piezas candidatas y he medido con un script, no a ojo, tres cosas: qué atributos escribe cada pieza que pertenezcan a otra, qué atributos ajenos solo lee, y qué métodos de otra pieza llama. El resultado que decide el plan:

- **Ninguna pieza escribe atributos de otra.** El estado ya está repartido por responsabilidad; lo que ata la clase es que todas leen lo mismo de la pestaña (`_mvc_ref`, `_n_channels`, `_online`, `_worker`, `_profile`, botones) y que todas **llaman a un mismo puñado de métodos de servicio** que viven en la calibración: `_pedir_al_sujeto`/`_soltar_al_sujeto`/`_instruct_device` (la placa simulada), `_reposition_mvc_overlay`, `_mvc_info` (el texto bajo las barras), `_write_phase_marker`, `_tono` (sesiones), `_bcast_calib` (aula) y `_parar_al_terminar_sesion` (núcleo).
- Los cuatro flujos guiados (calibración CVM, tarea del par, fuerza-velocidad y sesiones GRAD/HOLD/FAST) comparten ese patrón: una máquina de estados con temporizador que escribe en el panel superpuesto, pide algo al sujeto simulado, marca fases en el archivo, suena y difunde al aula. Las sesiones ya tienen el reloj fuera (`SessionRunner`, 24 oct); los otros tres lo llevan dentro.
- Las entregas entre flujos son pocas y están en tres sitios: `_iniciar_grabacion` arma `_mvc_flow_pending`, `_session_flow_pending` y `_fv_flow_pending`; `_on_data_ready` los dispara con el primer bloque; `_prep_tick` y `_mvc_finish_all` (calibración) lanzan sesión, estudio F-V o tarea del par. Eso es un **director de flujos** pequeño, y es trabajo del núcleo, no de la calibración.

Las cuatro piezas del encargo del 13 de octubre siguen valiendo, con dos cambios: la de «calidad y avisos» ya no da para una pieza (`_update_quality` son 16 líneas, y los avisos de señal débil y reposo alto son de las sesiones), y han entrado las sesiones guiadas. El marcado a mano y los fragmentos ya están fuera.

## 2. Las piezas

Carpeta nueva `src/emgteach/gui/acquisition/` (el nombre, a su elección). **La pestaña no se mueve**: sigue siendo `emgteach.gui.tabs.acquisition.AcquisitionTab`, porque 40 archivos de prueba la importan de ahí y 11 parchean nombres de ese módulo con `monkeypatch` (`getSaveFileName` ×12, `hay_red_utilizable` ×4, `create_device` ×3, `GUIDED_SESSIONS` ×8 entradas, `AcquisitionWorker`, `build_session_report`, `_documentos`). Un nombre que se mude de módulo deja de parchearse sin que nada avise: salvo `hay_red_utilizable`, que se va con el aula, todos esos nombres se quedan definidos y usados en `acquisition.py`.

Regla de comunicación, la que pide el encargo: cada pieza es un `QObject` o `QWidget` que **no guarda referencia a la pestaña**. Recibe en el constructor lo que posee y los servicios que necesita; la pestaña la llama con métodos públicos y se conecta a sus señales; lo que la pieza necesite saber de la pestaña (`n_channels`, referencias CVM, etiquetas) se lo pasa la pestaña en la llamada o en un `configure(...)`. Nada de `self._tab._x`.

Cifras: líneas que se mueven (cuerpo de métodos + su parte de `__init__`, `_build_ui`, `_build_load_panel` y constantes, redondeadas), y pruebas que las tocan (archivos / accesos a atributos privados de la pestaña).

### 2.1 Aula — `broadcast.py` · ≈240 líneas · 2 archivos / 14 accesos

`ClassroomBox(QGroupBox)`: la caja «Aula» de `_build_ui` (74 líneas) y `_on_toggle_broadcast`, `_vigilar_seguidores`, `_avisar_sin_seguidores`, `_copy_broadcast_url`, `_on_aula_qr`, `_make_qr_pixmap`, `_on_broadcast_clients`, `_bcast_config`, `_bcast_status`, `_bcast_live`, `_bcast_calib`; con `ESPERA_SEGUIDORES_MS` y `hay_red_utilizable`.
- Posee: `_chk_aula`, `_lbl_aula`, `_btn_copy_url`, `_btn_aula_qr`, `_timer_sin_seguidores`, el `BroadcastServer` que le pasa la pestaña.
- Pestaña → pieza: `config(labels, n_channels, mvc_ref, thresholds)`, `status(recording)`, `live(block, loads, danger)`, `calib(...)`.
- Pieza → pestaña: `message(str)` (para el registro de eventos). Nada más.
- Deja de leer: `_load_danger` (carga), `_mvc_ref`, `_n_channels`, `_online` → van en los argumentos.
- Pruebas: `test_manejo_en_aula.py` (86 pruebas) y una de `test_la_grabacion_nueva_olvida_el_informe.py`; los 4 parches de `hay_red_utilizable` cambian de módulo.
- Coste bajo, riesgo bajo. Cero dependencias hacia otras piezas.

### 2.2 Conexión — `connection.py` · ≈415 líneas · 15 archivos / 51 accesos

`ConnectionBox(QGroupBox)`: la caja del dispositivo de `_build_ui` (98 líneas) y `_default_address`, `report_ports_problem`, `_log_station_address`, `_reset_mac`, `_on_device_type_changed`, `_ajustar_rango_bruto_al_dispositivo`, `_refresh_ports`, `_toggle_conexion`, `_conectar`, `_desconectar`, `_marcar_si_no_respondio`, `_set_led`, `_conexion_sin_datos`, `_esperar_al_puerto`, `_puerto_liberado`, `_tras_aviso_conexion`, `_check_watchdog`; con `CONEXION_MAX_S`.
- Posee: `_combo_device_type`, `_edit_mac`, `_combo_port`, `_widget_mac/_widget_arduino`, `_stack_conn`, `_btn_conectar`, `_led`, `_led_idle_timer`, `_conexion_timer`, `_watchdog_timer`, `_aviso_conexion`, `_esperando_puerto`, `_placa_reiniciar`, `_sin_respuesta`, `_station_address`.
- Pestaña → pieza: `device_id()`, `address()`, `set_recording(bool)`, `first_block_arrived(worker)` (arranca el vigilante), `enable(bool)`.
- Pieza → pestaña: `ready_changed(bool)` (conectado/desconectado: hoy ese cambio refresca botones de F-V y de la guía desde dentro de `_conectar`, que es la única llamada de esta pieza hacia F, G, P y S), `device_type_changed(backend_id)`, `raw_scale_changed(mv)`, `status(str)`, `warning(str)`, `stop_requested()` (el vigilante), `retry_recording()` (tras «Reintentar»).
- Se quedan en la pestaña: `_lbl_estado` y `_btn_grabar` (los usa todo el mundo y 22+29 accesos de prueba).
- Pruebas: 15 archivos, pero 29 de los 51 accesos son el arranque de casi todas las pruebas de pestaña (`tab._edit_mac.setText("simulada"); tab._toggle_conexion()`): cambio mecánico a `tab.conexion._edit_mac…`, o un método público `tab.connect_to("simulada")` que lo haga, que es lo que yo propondría. Las que miran dentro: `test_la_placa_que_no_responde` (9), `test_cerrar_mientras_se_espera_el_puerto`, `test_apague_y_encienda_la_placa`, `test_direccion_del_puesto`. `tour.py` lee `adq._btn_conectar`.
- Coste medio, riesgo medio: tres temporizadores y la espera del puerto en Windows; `cleanup()` tiene que pararlos.

### 2.3 Trazado — `plots.py` · ≈1000 líneas · 18 archivos / 136 accesos

`LivePlots(QWidget)`: el bloque de las gráficas de `_build_ui` (258 líneas: los tres `PlotWidget`, las curvas, la barra de tiempo, la columna de escalas) y `_apply_channel_visibility`, `_update_legend`, `_is_stacked`, `_lane_half`, `_lane_baseline`, `_set_calib_ticks`, `_refresh_lane_label_texts`, `_apply_stacking_mode`, `_refresh_plots`, `_seguir_la_senal`, `_mostrar_registro`, `_px_por_segundo`, `_nombre_fase`, `_salir_revision`, `_apply_acc_range`, `_acc_zoom_step`, `_y_zoom`, `_reset_y_scales`, `_escala_envolvente_en_vivo`, `_autoscale_after_calibration`, `_on_tiempo_ampliar/_reducir`, `_on_combo_zoom_changed`, `_sync_combo_zoom`, `_update_ventana_label`, `_reset_all_scales`; con `MAX_POINTS`, `AUTOSCALE_*`, `ENV_SIGUE_*`, `_COLORES_FASE`.
- Posee: los plots, curvas y líneas de marcas, `_buf_raw/_buf_env/_buf_acc`, `_n_visible`, `_total_samples`, `_new_data`, `_render_timer`, `_y_ranges_init`, `_y_accum`, `_acc_zoom`, `_revisando`, `_revision_items`, `_marker_lines`.
- Pestaña → pieza: `set_channels(n, labels, colours)`, `set_stacked(bool)`, `set_raw_scale(mv)`, `append(raw, env, acc)` (desde `_on_data_ready`), `add_marker(t, label)`, `calibrated(refs, raw_peaks)` (el autoescalado), `show_recording(path, result)`, `leave_review()`, `reset()`.
- Pieza → pestaña: `review_left()`. Solo lee `_acc_enabled` y `_mvc_raw_peak` → argumentos.
- Única costura con otra pieza: `_mostrar_registro` llama a `_etiqueta_tramo` (tarea del par) para rotular los tramos de la revisión → la pestaña le pasa una función `label_for(span)`.
- Pruebas: 18 archivos, casi todos leyendo `_total_samples` (21), `_refresh_plots` (16), `_buf_*`, `_plot_raw/_plot_env` → `tab.plots._…`. Las que entran de verdad: `test_gui_acquisition`, `test_eje_de_tiempo`, `test_gui_session_review`, `test_la_vista_en_vivo_sigue`.
- Coste alto por tamaño, riesgo bajo por acoplamiento (es la pieza más limpia: cero escrituras ajenas, dos lecturas).

### 2.4 Escenario de los flujos guiados — `stage.py` · ≈120 líneas (unas 100 movidas) · nuevo

`FlowStage(QObject)`: los servicios que hoy llaman los cuatro flujos y que viven repartidos en calibración, sesiones y aula: `_instruct_device`, `_pedir_al_sujeto`, `_soltar_al_sujeto`, `_write_phase_marker`, `_tono`, `_reposition_mvc_overlay`, `_mvc_info`, `_bcast_calib` y `_parar_al_terminar_sesion`.
- Recibe: el `MvcOverlay` (**que se queda como widget de la pestaña**, porque 57 accesos de prueba usan `tab._mvc_overlay` y su posición depende de la geometría de la pestaña), la casilla del tono, la etiqueta de información, la caja del aula, y un `worker()` para marcas e instrucciones.
- Pestaña → pieza: `set_worker(worker | None)`, `set_channels(n)`.
- Pieza → pestaña: `stop_requested(reason)` (lo que hoy hace `_parar_al_terminar_sesion`), `tone(kind)` (para reemitir `_tono_informado`, que las pruebas escuchan en la pestaña).
- No cambia comportamiento. Es el paso que deja a sesiones, F-V y tarea del par sin llamadas hacia la calibración, y por eso va antes que ellas.
- Coste bajo, riesgo bajo-medio: es mecánico, pero lo toca todo.

### 2.5 Monitor de carga — `load_monitor.py` · ≈260 líneas · 14 archivos / 79 accesos

`LoadMonitorPanel(QGroupBox)`: de `_build_load_panel` las barras, lecturas P10/P50/P90, umbrales y «Calibrar CVM» (≈120 de sus 226 líneas; el resto es de sesiones y F-V, abajo) y `_set_thresholds_enabled`, `_on_thresholds_changed`, `_update_load_readout`, `_reset_load_monitor`, `_stop_load_monitor`, más la parte de `_process_load` que calcula la carga.
- Posee: `_load_bars`, `_load_rows`, `_load_name_labels`, `_load_readouts`, `_spin_warning/_spin_danger`, `_box_thr`, `_btn_calibrar`, `_load_timer`, `_online` (el `OnlineLoad`), `_load_warning/_load_danger`.
- Pestaña → pieza: `feed(env_block)`, `calibrated(refs)`, `set_channels(n, labels)`, `reset()`, `stop()`.
- Pieza → pestaña: `calibrate_requested()`, `danger_changed(bool)` (lo que lee el aula), `thresholds_changed(w, d)`.
- Lo que **no** se mueve: el reparto de `_process_load` (si está la calibración, alimenta `_mvc_feed`; si el estudio F-V, `_fv_mvc_feed`; si no, la carga) y `_stop_load_monitor` cancelando flujos. Eso es del director (2.10): hoy esta pieza llama a siete métodos de calibración, F-V y sesiones solo por ese reparto.
- Pruebas: 14 archivos, pero la mayoría solo pulsan `_btn_calibrar` o leen `_combo_sesion`/`_chk_tono`/`_btn_fv_guided` (que se van con sesiones y F-V); las de fondo son `test_rearme_en_rec_start` y `test_gui_acquisition` (umbrales).
- Coste medio, riesgo medio.

### 2.6 Sesiones guiadas — `sessions.py` · ≈345 líneas · 5 archivos / 33 accesos

`GuidedSessions(QObject)`: `_rellenar_sesiones`, `_sesion_elegida`, `_on_tono_cambiado`, `_on_tono`, `_lanzar_sesion`, `_sesion_fase`, `_revisar_reposo`, `_revisar_senal`, `_no_puedo_mas`, `_sesion_tick`, `_sesion_fin`, `_sesion_cerrar_panel`, `_estado_en_reposo`; y de `_build_load_panel` el desplegable y la casilla del tono (≈25 líneas).
- Posee: `_combo_sesion`, `_chk_tono`, `_btn_no_puedo`, `_session_runner`, `_session_script`, `_session_motivo`, `_sesion_reposo`, `_aviso_senal`, `_senal_revisada`, el diccionario `GUIDED_SESSIONS` (que `acquisition.py` sigue reexportando: las pruebas hacen `setitem` sobre `acq_mod.GUIDED_SESSIONS`, y como es el mismo objeto sigue valiendo).
- Pestaña → pieza: `chosen()`, `start(worker)`, `feed(env_level)`, `cancel(reason)`, `apply_mode(mode)`.
- Pieza → pestaña: `started(script)`, `finished(completed, reason)`, `rest_warning(str)`, `weak_signal(str)`. Deja de leer `_fv_active`/`_mvc_active` (lo sabe el director), `_carga_inst`/`_env_inst` (van en `feed`), `_placa_reiniciar`/`_sin_respuesta` (conexión → argumento de `start`).
- Pruebas: `test_fatiga_guiada` (37), `test_gradacion` (30), `test_contracciones_rapidas` (25), `test_sesion_guiada_en_la_pestana` (17): la mayoría graban con la placa simulada y no tocan internos; los que sí, `_session_runner` (12) y `_rellenar_sesiones` (5), cambio mecánico.
- Coste medio, riesgo medio: las pruebas de tiempo con la placa simulada son las que más sufren en la CI de Windows, aunque la lógica no cambie.

### 2.7 Fuerza-velocidad — `force_velocity.py` · ≈595 líneas · 8 archivos / 90 accesos

`FvStudy(QObject)` más `FvBox(QGroupBox)` (la caja «Estudio fuerza-velocidad» de `_build_load_panel`, ≈55 líneas): `_on_fv_params`, `_plan_fv_guardado`, `_lanzar_estudio_fv`, `_on_fv_rehearse`, `_fv_start`, `_fv_mapa`, `_fv_grupo`, `_fv_current_load`, `_fv_progress`, `_fv_info`, `_fv_mvc_feed`, `_fv_tick`, `_fv_compute_mvc`, `_fv_begin_contract`, `_fv_finish_contract`, `_fv_fila_de_esta_carga`, `_fv_finish_all`, `_soltar_panel`, `_fv_cerrar_mapa`, `_fv_cancel`, `_refresh_fv_config_label`, `_update_fv_button`; con las `FV_*`. Los controles del acelerómetro (`_on_acc_*`, `_apply_acc_placement_constraints`, la caja ACC) se quedan en la pestaña: son configuración del dispositivo, no del estudio.
- Posee: todo `_fv_*` (15 atributos), `_box_fv_guided`, `_btn_fv_guided`, `_btn_fv_rehearse`, `_lbl_fv_config`, `_fv_timer`.
- Pestaña → pieza: `plan()` (lo que hoy pregunta `_iniciar_grabacion`), `start(refs)`, `feed(env)`, `cancel()`, `apply_mode(mode, connected)`.
- Pieza → pestaña: `active_changed(bool)`, `finished()`, `loads_marked(...)`. Deja de leer `_mvc_active`, `_btn_calibrar`, `_lbl_load_info`, `_carga_inst`.
- Pruebas: `test_el_asistente_es_el_mismo` (21), `test_banco_septiembre` (19), `test_gui_acquisition` (14), `test_rearme_en_rec_start`, `test_la_sesion_guiada_termina`; `_fv_active` (18) y `_fv_phase` (11) → `tab.fv._active`. `tour.py` lee `adq._btn_fv_rehearse`.
- Coste medio-alto (`_fv_tick` 115 líneas), riesgo medio.

### 2.8 Tarea guiada del par — `pair_task.py` · ≈540 líneas · 5 archivos / 118 accesos

`PairTask(QObject)`: `_guia_mapa`, `_guia_maniobras`, `_maniobras_en_marcha`, `_pinta_maniobras`, `_rearmar_conteo_guiado`, `_guia_detecta`, `_guia_reposo`, `_paso_siguiente`, `_guia_coactivacion`, `_coact_tick`, `_guia_fin`, `_guia_cancelar`, `_actualizar_paso_guiado`, `_etiqueta_tramo`; con `MANIOBRA_*` y `COACT_*` (≈140 líneas, la mitad comentarios que explican el protocolo y que deben irse con ellas).
- Posee: `_guia_fase`, `_man_*` (6), `_coact_*` (4), `_paso_*`, `_btn_paso_hecho`, `_lbl_siguiente`.
- Pestaña → pieza: `show_map(phase, n, reps)`, `start_manoeuvres(labels)`, `feed(env_block)` (lo que hoy llama `_on_data_ready` a `_guia_detecta`), `cancel()`, `refresh_step(connected, recording)`.
- Pieza → pestaña: `finished()`, `step_changed(str, str, object)` (la pestaña lo reemite como `coach_step`, que es de la aplicación), `label_for(span)`.
- Costura con la calibración: `_guia_mapa("cal")` dibuja las casillas de la calibración en el panel; mientras la calibración siga en la pestaña la llama como `self._par.show_map("cal", …)`; al salir la calibración (2.9), las filas del mapa las calcula cada flujo y el escenario solo las pinta.
- Pruebas: `test_asistente_cuatro_cuadros` (39, la que entra a fondo: `_man_hechas` 21, `_guia_detecta` 15, `_man_grupo` 15), `test_el_asistente_es_el_mismo`, `test_la_sesion_guiada_termina`.
- Coste medio-alto, riesgo medio-alto: la detección de maniobras va bloque a bloque y `_coact_tick` lleva temporizador.

### 2.9 Calibración CVM — `calibration.py` · ≈785 líneas · 14 archivos / 228 accesos

`MvcCalibration(QObject)`: `_on_calibrar`, `_iniciar_calibracion`, `_mvc_label`, `_mvc_enter_warmup`, `_mvc_enter_ready`, `_mvc_tick`, `_mvc_rest_feed`, `_mvc_check_is_a_maximum`, `_mvc_feed`, `_mvc_finish_rep`, `_mvc_gesto`, `_ventana_cvm_s`, `_mvc_compute_muscle`, `_flow_needs_calibration`, `_mvc_enter_prep`, `_prep_tick`, `_write_mvc_ref_marker`, `_mvc_crosstalk`, `_mvc_finish_all`, `_mvc_cancel`; con `MVC_*` y `MVC_FLOW_MAX_TRIES`.
- Posee: `_mvc_*` (21 atributos menos `_mvc_ref`, `_mvc_overlay`, `_mvc_capture`, `_mvc_cross`, `_mvc_no_maximas`, que son resultado y se quedan en la pestaña), `_prep_*`, `_mvc_timer`, `_prep_timer`.
- Pestaña → pieza: `needs_calibration(mode, n, refs)`, `start(worker, labels, par)`, `feed(env)`, `rest_feed(env)`, `enter_prep()`, `cancel()`.
- Pieza → pestaña: `finished(refs, capture, cross, no_maximas)` (la pestaña guarda `_mvc_ref` y decide qué lanzar: hoy `_mvc_finish_all` lanza la tarea del par, el estudio F-V o la sesión él mismo), `prep_done()` (hoy `_prep_tick` lanza la sesión o el estudio F-V), `cancelled()`, `info(str)`.
- Va la última porque es a la que todos entregan y la que a todos lanza; con el escenario (2.4) y las otras tres fuera, sus llamadas hacia fuera se reducen a esas dos señales.
- Pruebas: `test_gui_session_phases` (39), `test_mvc_reference` (34), `test_calibracion_maxima` (18), `test_simulada_obedece` (15), `test_asistente_cuatro_cuadros`, `test_sesion_guiada_en_la_pestana`, `test_imagen_en_el_ejercicio`; `_iniciar_calibracion` (28), `_mvc_flow_pending` (20), `_mvc_phase` (17), `_mvc_tick` (13) → `tab.calibration._…`.
- Coste alto, riesgo alto por la superficie de pruebas, no por el código.

### 2.10 (opcional) Director de flujos — en la pestaña o `director.py` · ≈150 líneas

Lo que queda de orquestación en la pestaña tras 2.4-2.9: los tres `_flow_pending`, su disparo en el primer bloque de `_on_data_ready`, el reparto de `_process_load`, `_cancelar_guiado` y la parada al terminar. Puede quedarse en la pestaña como una sección clara o salir a `FlowDirector(QObject)` con `arm(mode, session, refs)`, `first_block()`, `feed(env)`, `cancel()`. Lo dejaría para cuando las piezas anteriores estén: entonces se ve solo.

### Lo que queda en la pestaña

≈1900-2100 líneas: `__init__`, la construcción de las cajas de configuración (canales, etiquetas, acelerómetro, control, marcas, registro: ≈430 líneas de `_build_ui`), `_iniciar_grabacion`, `_detener_grabacion`, `_on_data_ready` (que pasa a repartir bloques: `plots.append`, `load.feed`, `director.feed`), los slots del worker, el registro de eventos, `apply_mode`, `reset`, `cleanup`, `is_recording`, `_update_quality`, las marcas (`_on_marca_manual`, `_on_marker_added`) y el director. Si después se quiere más, lo siguiente que sale solo es «grabación» (`_iniciar/_detener_grabacion` + slots del worker + registro de eventos, ≈450 líneas), pero no lo propondría hasta ver la pestaña con las nueve piezas fuera.

## 3. Orden, con parada posible entre pasos

Cada paso es una rama y una PR; la suite en verde; la aplicación sin cambio visible (mismos widgets en los mismos sitios, solo cambia quién los construye). En cada paso: el módulo nuevo con sus pruebas directas (sin pestaña: se construye la pieza sola y se prueba por señales), las pruebas de pestaña que leían internos cambian mecánicamente `tab._x` → `tab.pieza._x` en la misma PR (**sin propiedades de reenvío**: mantendrían viva la interfaz de la clase-dios), y el recuento del README.

| Paso | Pieza | Líneas | Pruebas (archivos/accesos) | Riesgo | Por qué aquí |
|---|---|---|---|---|---|
| 0 | `full_scale_mv()` + `device_class()` (§4) | ≈40 | 1 / 2 | bajo | independiente; quita la lectura de privados |
| 1 | Aula | ≈240 | 2 / 14 | bajo | hoja: nadie depende de ella salvo el núcleo |
| 2 | Conexión | ≈415 | 15 / 51 | medio | hoja; iguales en ecg/eeg |
| 3 | Trazado | ≈1000 | 18 / 136 | bajo-medio | la más limpia; la más grande |
| 4 | Escenario | ≈120 | 3 / 20 | bajo-medio | desata los cuatro flujos de la calibración |
| 5 | Monitor de carga | ≈260 | 14 / 79 | medio | deja el reparto de bloques en el director |
| 6 | Sesiones guiadas | ≈345 | 5 / 33 | medio | ya tienen el reloj fuera |
| 7 | Fuerza-velocidad | ≈595 | 8 / 90 | medio | solo cinemática |
| 8 | Tarea del par | ≈540 | 5 / 118 | medio-alto | detección por bloques |
| 9 | Calibración CVM | ≈785 | 14 / 228 | alto (pruebas) | a la que todos entregan: la última |
| 10 | Director (opcional) | ≈150 | — | bajo | cuando se vea solo |

Se puede parar después de cualquier fila. Los pasos 1-3 ya se llevan ≈1650 líneas y dejan la pestaña en ≈4500 sin tocar ningún flujo; los pasos 4-9 son los que quitan la maraña.

Riesgos comunes a todos, y lo que los cubre:
- **Temporizadores que cambian de dueño** (conexión, calibración, F-V, coactivación): `cleanup()` de la pestaña debe llamar al `stop()` de cada pieza; `test_cerrar_mientras_se_espera_el_puerto` y `test_la_sesion_guiada_termina` lo vigilan.
- **Parches de módulo** (§2, cabecera): comprobados uno a uno en cada PR; solo `hay_red_utilizable` se muda.
- **`tour.py`** lee cinco atributos de la pestaña (`_par`, `_btn_grabar`, `_btn_conectar`, `_btn_fv_rehearse`, `_box_acc`) y `app.py` uno (`_edit_dir`): cambian en los pasos 2 y 7.
- **La ruta caliente**: `_on_data_ready` corre diez veces por segundo; cada pieza recibe su bloque por una llamada, sin copiar búferes (los búferes viven en el trazado).
- **Las pruebas de tiempo con la placa simulada** no cambian de lógica, pero son las que fallan en la CI de Windows cuando algo se retrasa: cada PR pasa la suite entera, no solo sus archivos.

## 4. `full_scale_mv()`: el método público

Hoy (`acquisition.py:1955-1983`) la pestaña importa `BitalinoDevice` y `ArduinoDevice` y lee `_GAIN_EMG`/`_GAIN` y `_V_REF` para escalar el panel bruto al cambiar el tipo de placa, **antes de que exista ningún dispositivo**. Por eso el método tiene que ser de clase, no de instancia: `physical_max` ya existe pero es una propiedad de instancia.

Propuesta, en `devices/base.py`:

```python
@classmethod
def full_scale_mv(cls, sensor_gain: float | None = None) -> float:
    """Half the input span referred to the electrodes, in mV: a signal
    lies in ±full_scale_mv(). The generic rail; a backend overrides it
    from its reference voltage and gain. Class-level because the GUI
    draws the raw panel to the device's scale when the device type is
    chosen, before any device is opened. *sensor_gain* lets a profile
    supply the gain of the sensor it describes; without it, the
    backend's default."""
    return 3.3

@property
def physical_min(self) -> float: return -self.full_scale_mv()
@property
def physical_max(self) -> float: return self.full_scale_mv()
```

- `BitalinoDevice.full_scale_mv`: `cls._V_REF / 2 * 1000 / (sensor_gain or cls._GAIN_EMG)`; `ArduinoDevice`: lo mismo con `_GAIN`. Las dos clases pierden sus `physical_min/max` propios (quedan los de la base, que delegan): una sola fuente para la escala del panel y para la cabecera del EDF. `channel_physical_ranges` no cambia.
- En `devices/factory.py`, `device_class(backend_id) -> type[AcquisitionDevice]` (el registro ya guarda las clases como constructores), para que la pestaña deje de importar `BitalinoDevice`/`ArduinoDevice`: `device_class(backend).full_scale_mv()` con el `ylim_raw` del perfil como respaldo si el backend no lo da.
- `tests/test_arreglos_pantalla.py:184,198` calculan hoy el esperado leyendo los privados; pasan a `BitalinoDevice.full_scale_mv()`, y una prueba nueva fija los dos valores (±1.635 y ±12.5 mV) y que `physical_max == full_scale_mv()`.
- El parámetro `sensor_gain` es para el paquete común del plan teachcore (§1.5): en ecg/eeg la ganancia es de instancia (viene del perfil, `device_kwargs()`), así que allí `physical_max` haría `self.full_scale_mv(self._sensor_gain)` y la firma sería la misma en los tres `base.py`. emgteach todavía no pasa `sensor_gain` al crear la placa; cuando lo haga, la pestaña llamará `full_scale_mv(sensor_gain=self._profile.sensor_gain)` sin tocar nada más.

## 5. ecgteach y eegteach

Sus pestañas tienen 2389 líneas / 81 métodos (ecg) y 2782 / 101 (eeg): dos veces y media menos, y sin los cuatro flujos guiados. Lo que les conviene, y lo que no:

- **Paso 0 (`full_scale_mv`)**: sí, con la misma firma, aunque su interfaz no lea privados: es lo que deja los tres `base.py` intercambiables para el paquete común. Allí el cambio es solo en `devices/`.
- **Aula, conexión y escalas/ventana de tiempo**: los métodos son los mismos con el mismo nombre en las tres (`_on_toggle_broadcast`…`_bcast_live`; `_wait_for_port`, `_port_released`, `_after_connection_warning`, `_check_watchdog`, `_set_led`, `_connection_without_data`; `_y_zoom`, `_reset_y_scales`, `_on_tiempo_*`, `_sync_combo_zoom`, `_update_ventana_label`, `_reset_all_scales`). Conviene hacerlo igual, **pero después de que emgteach pruebe la forma** (pasos 1-3): entonces es copiar el módulo y renombrar slots. No antes: a 2400 líneas no aprieta, y el beneficio es el paquete común, no la pestaña de cada una. La revisión del registro (`_mostrar_registro`) es solo de emgteach.
- **Escenario, calibración, par, F-V, sesiones GRAD/HOLD/FAST**: solo de emgteach. Las sesiones de ecg/eeg (fótica, atlas, Berger, neurofeedback, contacto) son diálogos propios y ya están fuera de la pestaña: nada que hacer.
- **Director**: no hace falta allí.

## 6. Qué no entra en este plan

- Cambiar comportamiento, textos o disposición: ninguno.
- Mover la pestaña de módulo ni tocar `app.py` más allá de los seis atributos del tour.
- El marcado a mano y los fragmentos, ya fuera.
