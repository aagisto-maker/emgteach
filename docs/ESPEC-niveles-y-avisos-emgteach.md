# emgteach: niveles de interfaz y avisos de uso avanzado

Especificación de implementación. Escrita el 20 de agosto de 2026 sobre el código
de `src/emgteach` tal como está en el disco de Angel. Todas las líneas citadas se han comprobado
en ese código; si el fichero cambia, hay que localizar el control por nombre de variable, no por
número de línea.

Origen: el Reviewer 2 de *Advances in Physiology Education* escribió que el artículo suscitaba más
preguntas que una idea clara de la implementación. La respuesta no es explicar más la interfaz
actual, es que la interfaz pida menos de entrada.

---

## 1. Tres problemas distintos, no uno

Al revisar la interfaz aparecen tres cosas que conviene no mezclar, porque cada una pide una
solución diferente.

**a) Densidad.** La pestaña de adquisición tiene 24 controles interactivos y la de análisis 14 más
12 casillas de paneles. Un profesor de fisiología general que solo quiere registrar un bíceps ve
selección de dispositivo, dirección MAC, puerto serie, número de canales, acelerómetro con su
colocación y su canal analógico, diagnóstico de canal, modo aula, detección automática de inicio
con umbral en k·SD, fuerza-velocidad guiada y umbrales de fatiga. De todo eso, para grabar hacen
falta cinco controles.

**b) Conceptos que se dan por sabidos.** La pestaña de normalización CVM no define en ningún sitio
qué es una contracción voluntaria máxima. La sigla aparece en el título de la pestaña, en dos
selectores de fichero, en el botón de calcular y en los ejes de las gráficas, y nunca se expande
salvo en el docstring del módulo, que el usuario no ve. Es justo lo que preguntó el Reviewer 1
sobre el botón *Calibrate MVC*.

**c) Un resultado que puede salir mal en silencio.** Esto es lo serio y lo trato aparte, en el
apartado 3.

La distinción que propongo, y que rige toda la especificación: **la densidad se arregla ocultando,
no advirtiendo**. Un aviso cada vez que alguien toca una opción avanzada se lee las dos primeras
veces y se acepta sin leer a partir de la tercera, y además castiga al usuario competente. Los
avisos hay que gastarlos donde el usuario va a obtener un resultado equivocado sin enterarse.

---

## 2. Nivel de interfaz: básico y completo

### 2.1 Mecanismo

Clave nueva en `QSettings`: `app/ui_level`, valor `"basic"` (por defecto en instalación nueva) o
`"full"`. Vive en el mismo `QSettings("Bioinstrumentacion", "EMGApp")` que ya usa la app
(`gui/app.py:261`).

Selector en la esquina de la barra de pestañas, junto al idioma y al botón `?`
(`gui/app.py:162-169`): un `QComboBox` con `tr("Basic")` / `tr("Full")`. A diferencia del idioma,
el cambio de nivel **se aplica en caliente**, sin reiniciar: cada pestaña expone un método
`apply_ui_level(level: str)` que hace `setVisible(...)` sobre los contenedores afectados.

Ocultar, no deshabilitar. Un control gris sigue ocupando espacio y sigue generando la pregunta
«¿y esto qué es?».

### 2.2 Qué se oculta en modo básico

**Pestaña Acquisition** (`gui/tabs/acquisition.py`)

| Se oculta | Variable | Línea |
|---|---|---|
| Selector de dispositivo | `_combo_device_type` | 369 |
| MAC / puerto serie y sus botones | `_stack_conn` (contiene `_widget_mac` 379 y `_widget_arduino` 404) | 417 |
| Número de canales | `_combo_n_channels` | 447 |
| Bloque acelerómetro completo | `_chk_acc` 474, `_combo_acc_place` 488, `_combo_acc_channel` 502, `_btn_acc_diag` 520 | |
| Modo aula y sus accesorios | `_chk_aula` 565, `_btn_copy_url` 575, `_btn_aula_qr` 586 | |
| Detección automática de inicio | `_chk_auto` 688, `_spin_k` 701 | |
| Fuerza-velocidad guiada | `_btn_fv_guided` 1833, `_lbl_fv_config` 1846 | |
| Best of 3 | `_chk_mvc_best3` | 1822 |
| Umbrales de aviso y peligro | `_spin_warning` 1864, `_spin_danger` 1882 | |

Queda visible: conectar, grabar, carpeta de destino, etiquetas de canal, alumno y protocolo,
marcadores, gráficas y sus controles de escala, y el botón `Calibrate MVC` con su barra de carga.

El dispositivo y el puerto no desaparecen del programa: en modo básico se usan los últimos valores
guardados en `adquisicion/device_type` y `adquisicion/port`. La primera vez que se abre la
aplicación no hay valores guardados, así que hace falta una excepción: **si `adquisicion/port` está
vacío, el bloque de conexión se muestra aunque el nivel sea básico**, con una etiqueta que diga que
solo hay que hacerlo una vez. Sin esa excepción, un usuario nuevo en modo básico no puede conectar
nada y la aplicación parece rota.

**Pestaña Analysis** (`gui/tabs/analysis.py`)

| Se oculta | Variable | Línea |
|---|---|---|
| Frecuencia de corte de la envolvente | `_spin_fenv` | 287 |
| Comparación de canales | `_chk_compare2` 269, `_combo_canal2` 279 | |
| Región de interés | `_chk_roi` 319, `_spin_roi_start` 328, `_spin_roi_end` 337 | |
| Selección de fragmentos | `_btn_fragmentos` 349, `_lbl_fragmentos` 359 | |
| Estudio fuerza-velocidad | `_btn_fv` | 235 |
| Paneles 4 a 12 de la caja «Panels to show» | casillas del bucle | 429-438 |

En modo básico la caja «Panels to show» se queda con tres casillas: `1A. Raw`, `2. Env. norm.` y
`3. PSD`, que son las tres que ya vienen marcadas por defecto (`_DEFAULT_PANELS = (0, 3, 4)`,
línea 90). El resumen numérico (MNF, MDF, pendiente, iEMG) se mantiene visible: es resultado, no
control, y es contenido docente.

**Pestaña MVC** (`gui/tabs/mvc.py`)

En modo básico se oculta `_spin_fenv` (línea 178). El resto de la pestaña se trata en el apartado 3.

### 2.3 Cómo se cuenta esto en el artículo

Una frase basta: la aplicación arranca en modo básico, con los controles imprescindibles para
registrar y analizar, y un selector permite pasar a modo completo cuando el profesor quiere usar
las medidas avanzadas. Eso convierte la v2.0 de problema en argumento.

---

## 3. La pestaña CVM

### 3.1 Lo que encontré

Cuando el usuario deja vacío el campo *MVC reference EDF (optional)*, la aplicación **no avisa de
nada**: normaliza la señal por el percentil 95 de sí misma (`workers/mvc.py:162-165`, etiquetado
como `auto (percentile 95 of the test signal)`) y sigue adelante. El resultado se expresa en «%
MVC» y alimenta el análisis de carga muscular APDF de Jonsson, que compara P10, P50 y P90 con los
límites de 5 %, 14 % y 70 % de CVM (`profiles.py:114-116`) y pinta en rojo lo que los excede
(`gui/tabs/mvc.py:74`, `_metric_html` 389-401).

El problema es de construcción. Si la referencia es el percentil 95 de la propia señal, el P90 de
esa señal queda por debajo pero muy cerca del 100 %, porque P90 ≤ P95 siempre. Basta que el
cociente P90/P95 supere 0,7 para que la carga pico se marque como fuera de rango. Lo he
comprobado numéricamente con envolventes sintéticas de distinto ciclo de trabajo:

| Registro | P10 | P50 | P90 | Veredicto que da la app |
|---|---|---|---|---|
| Contracción sostenida 60 s | 64,9 | 80,2 | 95,7 | los tres en rojo |
| Contracción intermitente, 50 % del tiempo | 2,2 | 19,2 | 94,4 | P50 y P90 en rojo |
| Contracción intermitente, 20 % del tiempo | 2,3 | 2,9 | 91,0 | P90 en rojo |
| Contracciones breves, 10 % del tiempo | 2,5 | 3,1 | 8,2 | todo normal |

La primera fila es exactamente lo que hace un alumno en una práctica de contracción isométrica
mantenida. Sale todo en rojo, con aspecto de hallazgo fisiológico, y no significa nada: es el
método midiéndose a sí mismo. Y la cuarta fila enseña la otra cara, porque un registro casi todo
reposo pasa por normal.

Esto no es un fallo de programación, la auto-normalización está puesta a propósito y es útil para
ver la forma de la señal sin hardware de calibración. Lo que falta es que el usuario sepa que la
está usando y qué deja de ser válido cuando la usa.

### 3.2 Puerta de entrada de la pestaña

Aquí me aparto de lo que planteaste, y lo digo abiertamente. Un cuadro de diálogo que salte cada
vez que se pulsa la pestaña se convierte en un trámite: a la tercera vez nadie lo lee, y quien
usa la pestaña a diario acaba irritado. Lo que sí funciona es una **pantalla de entrada dentro de
la propia pestaña**, la primera vez de cada sesión.

Comportamiento: al entrar en la pestaña por primera vez en la sesión, en lugar del contenido
habitual se muestra un panel con el texto de abajo y un botón `tr("I understand, continue")`. Al
pulsarlo se revela la pestaña normal y no vuelve a aparecer hasta que se reinicie la aplicación o
se pulse «New session» (`gui/app.py:186`), que ya existe y sirve justamente para cambiar de
alumno. Sin casilla de «no volver a mostrar»: el objetivo es que cada alumno lo lea una vez.

Texto propuesto (inglés canónico, español debajo, ambos a `i18n.py`):

> **Normalising to maximum voluntary contraction (MVC)**
>
> A raw EMG amplitude cannot be compared between two people, or between two sessions of the same
> person: it depends on the electrodes, the skin and the fat layer beneath it. Normalisation solves
> this by expressing every value as a percentage of the amplitude that muscle reaches during a
> maximal effort.
>
> To do that you need two recordings: the one you want to study, and a short reference recording in
> which the subject contracts the muscle as hard as possible. Record the reference first, with the
> electrodes in the same position, and do not remove them in between.
>
> Without a reference recording this tab can still work, but the percentages it produces are not
> percentages of MVC and the muscle-load limits do not apply to them.

> **Normalización a la contracción voluntaria máxima (CVM)**
>
> La amplitud bruta de una señal EMG no se puede comparar entre dos personas, ni entre dos sesiones
> de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. La
> normalización resuelve esto expresando cada valor como porcentaje de la amplitud que ese músculo
> alcanza en un esfuerzo máximo.
>
> Para ello hacen falta dos registros: el que se quiere estudiar y un registro corto de referencia
> en el que el sujeto contrae el músculo con toda la fuerza que pueda. Registre primero la
> referencia, con los electrodos en la misma posición, y no los retire entre uno y otro.
>
> Sin registro de referencia esta pestaña funciona igualmente, pero los porcentajes que produce no
> son porcentajes de CVM y los límites de carga muscular no se les pueden aplicar.

### 3.3 La confirmación que sí hace falta

Momento: pulsar `_btn_calcular` («Compute MVC», línea 189) con `_edit_cvm_path` vacío. Aquí sí un
modal, porque es el instante en que se va a producir un número engañoso. `QMessageBox.question`
con dos botones explícitos, el seguro por defecto:

> **No MVC reference recording selected**
>
> The signal will be normalised to the 95th percentile of itself. The values will be shown as
> "% MVC", but they are not percentages of maximum voluntary contraction, and the Jonsson
> muscle-load limits (P10, P50, P90) do not apply: a sustained contraction will exceed them by
> construction.
>
> Use this only to see the shape of the signal.
>
> [Choose a reference recording] [Continue without reference]

> **No se ha seleccionado registro de referencia CVM**
>
> La señal se normalizará al percentil 95 de sí misma. Los valores aparecerán como «% CVM», pero no
> son porcentajes de contracción voluntaria máxima, y los límites de carga muscular de Jonsson
> (P10, P50, P90) no se les pueden aplicar: una contracción mantenida los supera por construcción.
>
> Use esta opción solo para ver la forma de la señal.
>
> [Elegir registro de referencia] [Continuar sin referencia]

«Elegir registro de referencia» llama directamente a `_seleccionar_edf_cvm` (línea 489), para que
el aviso resuelva el problema en vez de limitarse a describirlo.

### 3.4 Marcar el resultado, no solo el momento

Un aviso al empezar se olvida en cuanto aparecen las gráficas, y las gráficas son lo que el alumno
copia en su cuaderno. Cuando la fuente sea auto:

- `_d_source` (línea 376, texto en 598) en rojo `#cc0000`, con el texto
  `tr("auto (not a real %MVC)")` / «auto (no es %CVM real)».
- En el bloque APDF, sustituir los tres valores P10/P50/P90 por una línea que diga que el análisis
  de carga muscular requiere una referencia de CVM. Es preferible no dar el número a darlo con una
  nota al pie: el número se copia, la nota no.
- En el título del panel 3 y del lienzo APDF (`gui/tabs/mvc.py:673` y `725`), añadir el sufijo
  `tr(" (auto-normalised, not %MVC)")`, para que quede escrito en la figura que se guarda como PNG
  y en el PDF del informe.

Esto último importa más de lo que parece: la figura sale de la aplicación y viaja sola.

---

## 4. Un fallo de usabilidad que conviene arreglar de paso

El `LoggerWidget` es una única instancia creada en `gui/app.py:117` y compartida por las tres
pestañas, pero **solo se inserta en un layout, el de la pestaña Analysis** (`analysis.py:372`). La
de adquisición no lo necesita porque tiene su propio log local (`acquisition.py:317`, mostrado en
610). La pestaña MVC no tiene ninguno.

Consecuencia: en Qt un widget solo puede estar en un sitio, así que **todo lo que la pestaña MVC
escribe en el log es invisible mientras se está en ella**. Y entre esos mensajes están los avisos
de canal plano por electrodo desconectado y de canal saturado por mal contacto
(`mvc.py:474-486`), que es justo el error más común de un alumno. El aviso se emite, nadie lo ve,
y el análisis continúa sobre una señal inservible.

Arreglo mínimo: dar a la pestaña MVC su propio log local, igual que hace adquisición, y reflejar en
él los mensajes. Alternativa mejor si se quiere tocar poco: mover el log a un panel inferior fijo
del `QMainWindow`, visible desde las tres pestañas.

---

## 5. Qué de esto va al artículo

Tres cosas, y las tres responden a peticiones expresas de los revisores.

1. **Los niveles** responden al comentario de fondo del Reviewer 2. Una frase en la descripción de
   la herramienta y una captura del modo básico.
2. **La explicación de la CVM** responde a la pregunta del Reviewer 1 sobre el botón *Calibrate
   MVC*. El texto del apartado 3.2 sirve casi tal cual para el artículo.
3. **La auto-normalización** es material de primera para las dos secciones que el Sourcebook exige
   y que el Reviewer 2 pidió por su nombre: *troubleshooting* para el instructor y errores típicos
   del alumnado. «Todos los indicadores de carga salen en rojo» es un síntoma con una causa
   concreta y una solución concreta, y la tabla del apartado 3.1 explica por qué.

---

## 6. Decisión pendiente

En modo básico, ¿la pestaña de normalización CVM se muestra o se oculta?

Argumento para mostrarla: la normalización es el concepto que arregla casi todo lo que se enseña
mal de la EMG, y dejarla fuera del modo básico la convierte en material de especialista, que es lo
contrario de lo que se pretende.

Argumento para ocultarla: es la pestaña que más conocimiento previo exige, y en una primera
práctica de registro puede sobrar.

Mi recomendación es mostrarla, con la puerta de entrada del apartado 3.2 haciendo el trabajo de
enseñar. Pero la decisión es docente, no técnica, y es tuya.
