# emgteach — informe de estado para el artículo del Sourcebook

Escrito el 5 de septiembre de 2026 sobre `main`, después de publicar la versión
3.0.0, y actualizado a la **3.1.0** y a la **3.1.1** tras publicarlas, el 13 de
septiembre.
Responde a `PETICION-a-code-informe-Sourcebook.md` sección por sección.

Los textos de pantalla están **copiados literalmente** de
`src/emgteach/i18n.py` (inglés canónico y español), no parafraseados, y los
valores llevan el archivo y la línea donde están definidos. Un revisor que
descargue la aplicación puede comparar. Los bloques marcados como generados
los escribe `tools/informe_bloques.py` leyendo el código: se pueden volver a
producir cuando el código cambie.

Donde algo no está hecho o no lo sé, lo dice.

---

## 1. Versión y estado

| | |
|---|---|
| Rama | `main` |
| **Versión que describe el artículo** | `v3.1.1`, publicada el 13 de septiembre de 2026 |
| DOI de esa versión | 10.5281/zenodo.22734612 |
| DOI de concepto | 10.5281/zenodo.21002297 |
| Commit de la etiqueta | `aeb580d` |
| Pruebas en la etiqueta | **1074 recogidas, 1073 pasan y 1 se salta** |
| Versiones anteriores | `v3.1.0` (10.5281/zenodo.22733151, etiqueta en `927eeff`, 1064 pruebas) · `v3.0.0` (10.5281/zenodo.22365602, `155fb07`, 940 pruebas) |
| Análisis estático | `ruff check .` limpio |

Los bloques generados de este informe (apartados 4, 6 y 5.1, y el recorrido
guiado) se leen del **código de `main` en el momento de generarlos**. En esta
actualización `main` coincide con la etiqueta `v3.1.1` salvo en documentación
(este informe, `CITATION.cff`, el README y el CHANGELOG) y en el flujo que
compila el ejecutable de Windows, que no forma parte de la aplicación; así que
lo que dicen es lo que hace la versión publicada. Lo que cambió de la 3.1.0 a la 3.1.1 está en
el apartado 1.1, y de la 3.0.0 a la 3.1.0 en el 1.2.

La prueba que se salta es `tests/test_gui_mvc_overlay.py:161`: con la
tipografía de la plataforma de prueba el mensaje mide menos que el suelo del
propio panel, así que no puede provocar el crecimiento que esa prueba vigila.

La versión etiquetada para el depósito es **3.1.1**, y es la que describe el
artículo. Las publicaciones de GitHub no llevan ejecutable de Windows ya
compilado: un ejecutable de PyInstaller sin firmar hace saltar el antivirus al
descargarlo (un falso positivo conocido), así que la versión se distribuye como
código fuente (apartado 1.6). El ejecutable se sigue pudiendo compilar desde la
etiqueta con la receta de `packaging/`.

### 1.1 De la 3.1.0 a la 3.1.1

Un parche de una sola medida (PR #21). **La coactivación de una ventana con
nombre se lee sobre la fase de registro sin recortar.** Hasta la 3.1.0, elegir
fragmentos en la pestaña de Análisis los concatenaba, y la tabla de
coactivación se leía sobre esa señal concatenada. El índice resta a cada
músculo su nivel de reposo, el percentil 10 de la señal analizada, y una señal
hecha solo de contracciones no tiene reposo: su percentil 10 era lo más callado
que estuvo cada músculo *mientras trabajaba*. Para el antagonista, su propia
parte en la maniobra del otro; restarla castigaba a la señal pequeña, que es la
que la práctica enseña. En el registro de ejemplo, la fila que el editor
propone para la presa daba 58 % con el extensor en 6,3 % CVM; ahora da 75 % y
10,9 %.

Ahora las envolventes de los dos músculos se calculan una vez sobre la fase de
registro sin recortar, cada fragmento con nombre es una máscara sobre ellas, y
el reposo es el percentil 10 de la fase entera (`coactivation_by_fragments`,
`src/emgteach/coactivation.py`). **Es la definición que la tabla ya usaba sin
fragmentos** (apartado 5.6): con ella, las dos vías restan el mismo cero.
`tools/figura6.py` lee sus `--ventana` con la misma función, así que la figura
y la pestaña no pueden discrepar.

**Qué cambia en las cifras.** La herramienta tomaba antes el reposo de cada
ventana de la propia ventana; con la definición común sus medias se mueven hasta
0,3 % CVM y sus índices hasta 0,7 puntos (apartado 8.2). Con otras definiciones
razonables del reposo el índice se movería hasta dos puntos; está en el
apartado 9, punto 3.

**Qué comprueba la prueba** (`tests/test_coactivation_sin_recortar.py`): que las
tres maniobras del registro de ejemplo, elegidas en la pestaña como una fila
cada una, dan lo mismo que `figura6.py` a 10⁻⁶, con los valores fijados; y que
la fila que el editor propone para la presa conserva al extensor.

**Qué no cambia, a propósito.** El espectro, el RMS y la MDF por segmento, el
ajuste de fatiga y la tabla de contracciones siguen corriendo sobre los
fragmentos concatenados (apartado 9, punto 11). El EDF afinado es una
concatenación en disco y se lee como tal. Ninguna figura ni ningún control de
la interfaz cambia.

### 1.2 De la 3.0.0 a la 3.1.0

Son **39 commits** (29 sin contar las fusiones). La 3.1.0 no cambia el formato
del archivo ni los cálculos: los módulos que calculan (`coactivation.py`,
`phases.py`, `mvc.py`, `dsp.py`, `fatigue.py`, `contractions.py`,
`force_velocity.py`) son los de la 3.0.0 salvo en comentarios. Lo que cambia
es el manejo de la aplicación en el puesto de laboratorio, y **lo único que
puede mover resultados es la propuesta de filas del editor de fragmentos**:

- **La sensibilidad de detección se fija por práctica y forma parte del
  resultado.** En el par agonista/antagonista el editor de fragmentos abre en
  **k = 4,4**, el valor que da una fila por maniobra de la serie en los
  registros en que se probó; las otras dos prácticas siguen en 3,0. El
  análisis usa el mismo valor aunque no se abra el editor, y la k usada se
  escribe en la tabla «Configuración utilizada» del PDF y en la cabecera del
  CSV (apartado 5.5). Como las filas propuestas cambian con k, **las filas de
  un mismo registro del par, y las ventanas de coactivación que salen de
  ellas, pueden no coincidir con las que proponía la 3.0.0**. Las cifras del
  apartado 8 no dependen de esto: se calculan sobre ventanas dadas o sobre el
  tramo de registro completo.
- **El editor de fragmentos va por pasos** (apartado 3.1, paso 7): la
  sensibilidad con el recuento de marcadas frente a esperadas (seis flexiones,
  seis extensiones y una presa en el par), la revisión de cada contracción con
  «Mantener», «Eliminar» y «Dividir», y la aplicación. Los tramos que quedan
  bajo el umbral se dibujan punteados y se añaden con un clic, y una marca se
  puede arrastrar sobre la actividad de al lado; ninguna marca se pone a mano.
  Las filas se guardan en centésimas de segundo y separadas al menos una
  centésima: dos propuestas que se tocaban se unían antes del análisis, y el
  editor podía enseñar una contracción más de las que se analizaban. Esto
  también puede cambiar una fila respecto de la 3.0.0.
- **El recorrido guiado lleva imágenes** en el par: en el paso de conexión,
  dónde van los dos pares de electrodos y la referencia; en el de grabación,
  qué pide la calibración (apartado 3.3).
- **Una sola copia de la aplicación.** Un segundo arranque lleva al frente la
  ventana abierta en vez de abrir otra que compita por el puerto Bluetooth y
  por el registro, y el ejecutable muestra una imagen de carga desde el primer
  segundo.
- **Guardar no falla por una carpeta que ya no existe**: se crea, y si no se
  puede, el mensaje dice el archivo y la carpeta. Los registros van a
  Documentos mientras no se elija otra carpeta.
- **La envolvente en vivo sigue al pico** y vuelve poco a poco a la escala de
  las flechas; los móviles reciben el PDF antes que el CSV, y la emisión dice
  cuándo ningún móvil puede alcanzarla.
- **Capturas de pantalla** con F12 desde cualquier pestaña y un botón `Auto`
  que las hace solo, cada tres segundos y únicamente mientras se graba, con el
  nombre del registro al que pertenecen; el registro **se nombra con el
  identificador de prueba**; **«Guardar EDF afinado…» se ofrece en todas las
  prácticas** en cuanto hay fragmentos elegidos; y «Calibrar CVM» recupera su
  tamaño de botón en las dos prácticas sin caja de fuerza-velocidad. Las
  cuatro primeras se comprobaron sobre un registro completo: el archivo salió
  nombrado solo, el botón de guardar el afinado estaba donde tenía que estar y
  el registro de eventos anotó «32 automatic screenshots saved with the
  recording».
- **Una hoja por puesto** para imprimir y plastificar, con la práctica del
  par en un A4 apaisado (`docs/hoja-puesto/`).
- **Textos corregidos**: la ayuda de la calibración se escribe desde las
  constantes del asistente, y las guías ya no hablan de esfuerzos mantenidos
  de cuatro segundos.

### 1.3 Lo que trajo la 3.0.0 (desde el commit `7234b02`)

Son **97 commits**. Lo que cambió de cara al artículo:

- **La práctica es la configuración.** Tres prácticas (un músculo,
  agonista/antagonista, cinemática muscular) fijan el número de canales, el
  acelerómetro y lo que ofrece cada pestaña. Desaparecen de la interfaz el
  selector de canales, la casilla del acelerómetro y el modo de análisis libre.
- **La sesión es un archivo con sus fases marcadas dentro** (calentamiento,
  calibración, preparación, registro). Es la especificación
  `ESPEC-sesion-en-dos-fases.md`, implementada entera; apartado 2 de este
  informe.
- **La referencia de CVM viaja en el EDF** y se recalcula desde los tramos de
  calibración. Desaparece el archivo de referencia aparte y con él la
  auto-normalización en el análisis de carga muscular.
- **La referencia se mide sobre el mejor 0,2 s** y la calibración pide **tres
  esfuerzos máximos breves** por músculo. Las tres contracciones mantenidas de
  4 s que hubo en una versión intermedia se quitaron: medida en el pico, una
  sacudida da el mismo número.
- **Una fila por contracción** en el análisis, con retraso electromecánico
  donde hay acelerómetro; **índice de coactivación** de Falconer-Winter por
  ventana marcada y en % CVM; **estudio fuerza-velocidad** que lee esas filas.
- **Capa docente**: recorrido guiado, «?» en cada caja, estados vacíos que
  dicen qué hacer, y un cartel flotante que nombra el paso siguiente sobre el
  control que lo hace.
- **Registro de fallos**: las excepciones no capturadas se escriben en
  `emgteach-errores.log` en la carpeta del usuario.
- **Corrección de la ganancia del BITalino** en la conversión a milivoltios:
  la excursión completa es ±1,635 mV, no ±1,65 mV. Nada expresado como
  cociente cambia.

### 1.4 Dependencias

Declaradas en `pyproject.toml` y comprobadas en el entorno con el que se
generó este informe:

| Paquete | Declarado | Instalado aquí |
|---|---|---|
| Python | `>=3.10,<3.13` | 3.12.10 |
| PySide6 | `>=6.6,<7.0` | 6.11.2 |
| pyqtgraph | `>=0.13` | 0.14.0 |
| numpy | `==1.26.4` | 1.26.4 |
| scipy | `==1.13.1` | 1.13.1 |
| matplotlib | `==3.9.2` | 3.9.2 |
| pyedflib | `==0.1.42` | 0.1.42 |
| mne | `>=1.6,<2.0` | 1.12.1 |
| pyserial | `>=3.5` | 3.5 |
| reportlab | `>=4.0` | 4.5.1 |
| segno | `>=1.6` | 1.6.6 |

### 1.5 Plataformas probadas

La integración continua ejecuta la suite en **Ubuntu y Windows**, con
**Python 3.10, 3.11 y 3.12**: seis combinaciones, todas en verde para
`v3.1.1`. macOS no se prueba de forma automática. El hardware se ha probado
solo en Windows 11.

### 1.6 Instalación y arranque

Desde el código fuente:

```
git clone https://github.com/aagisto-maker/emgteach.git
cd emgteach
pip install -e ".[dev]"
emgteach
```

No hay ejecutable de Windows adjunto a la publicación (apartado 1). Quien lo
necesite lo compila desde la etiqueta con `packaging/emgteach.spec`
(instrucciones en `packaging/README.md`). El ejecutable acepta `--selftest`,
que construye la interfaz sin pantalla y escribe el resultado en
`emgteach_selftest.log`, a su lado.

---

## 2. Sesión en dos fases: qué se implementó

Referencia: `docs/ESPEC-sesion-en-dos-fases.md` y
`docs/ENMIENDAS-ESPEC-sesion-en-dos-fases.md` (copiadas al repositorio para
este informe; ver apartado 10). El orden de construcción que se siguió es el
**revisado del §5 de las enmiendas**, de ocho puntos.

| # | Punto | Estado |
|---|---|---|
| 1 | `phases.py`: anotaciones, parseadores y `mvc_reference()` | hecho |
| 2 | Escritura de las fases en la grabación, sin detener la adquisición | hecho |
| 3 | Lectura en Análisis: procedencia y deshabilitar con motivo | hecho |
| 4 | Lista de repeticiones con recálculo y columna de diafonía | hecho |
| 5 | Fragmentos con nombre en el tramo `REC` y ventanas de coactivación | hecho |
| 6 | Pestaña CVM: fuera el selector de referencia y la ruta auto de Jonsson | hecho |
| 7 | EDF afinado con trazabilidad y el código del alumno en la cabecera | hecho |
| 8 | Los dos puntos vivos del §8 de la especificación | hecho |

Del §8: la **última ventana de coactivación se cierra con el final de la
actividad detectada** (`_fin_de_la_actividad`, `coactivation.py`), y una
**ventana demasiado corta emite su fila con el motivo** en vez de
descartarse en silencio. El tercer punto, el suelo del índice, ya estaba
resuelto antes de la especificación (§3 de las enmiendas).

### 2.1 Desviaciones respecto de la especificación

Tres, todas deliberadas:

1. **El botón «Calibrar CVM» no desaparece** (el §6 de la especificación lo
   daba por eliminado en los modos que llevan la calibración dentro del flujo).
   Se conserva como vía de escape: si el flujo automático no consigue armar la
   calibración, el operador tiene que poder pedirla. En la práctica de
   cinemática sí está oculto, porque ahí el flujo la hace siempre.
2. **Se conserva el panel 2, «envolvente normalizada a su propio máximo»**. El
   §5 pedía eliminar «la auto-normalización del programa» y el §9 conservaba
   este panel: es la misma operación con otro nombre. Se aplica la redacción
   del §1.1 de las enmiendas: fuera la ruta auto **del análisis de carga
   muscular (Jonsson)**, por ninguna vía; el panel 2 se queda, honradamente
   etiquetado.
3. **Las medidas sin calibración se deshabilitan con su motivo, no se
   ocultan** (§1.2 de las enmiendas frente al §4.2 de la especificación).

Y una consecuencia declarada del §1.3 de las enmiendas: **la referencia
recalculada no coincide exactamente con la anotada**, porque la del asistente
sale de la envolvente en línea y la recalculada de `process_offline`, con
filtrado de fase cero. La discrepancia es de unidades de por ciento, está
documentada en el código y es esperada.

### 2.2 Anotaciones que se escriben en el EDF

Formato exacto y un ejemplo real de cada una, tomado de
`C:\Records\emg_2026-09-05_18-13.edf` (práctica de cinemática, un canal):

| Anotación | Formato | Definida en | Ejemplo real |
|---|---|---|---|
| Calentamiento | `WARMUP start` | `src/emgteach/phases.py:132` | `0,10 s → WARMUP start` |
| Inicio de repetición | `CAL start ch={canal} rep={n}` | `src/emgteach/phases.py:116` | `14,50 s → CAL start ch=1 rep=1` |
| Fin de repetición | `CAL end ch={canal} rep={n}` | `src/emgteach/phases.py:121` | `16,10 s → CAL end ch=1 rep=1` |
| Referencia en caché | `MVC ref ch={canal} value={valor:.6g} mV` | `src/emgteach/mvc.py:264` | `30,40 s → MVC ref ch=1 value=0.270517 mV` |
| Pausa de preparación | `PREP start` | `src/emgteach/phases.py:137` | `30,40 s → PREP start` |
| Inicio del registro | `REC start` | `src/emgteach/phases.py:142` | `36,00 s → REC start` |
| Carga de fuerza-velocidad | `FV load={kg:g} kg` | `src/emgteach/force_velocity.py:54` | `48,20 s → FV load=2 kg` |
| Inicio automático | `{Inicio (auto)} — {músculo}` | `acquisition.py` | `1,62 s → Inicio (auto) — Músculo` |

El canal va **en base 1** en la anotación aunque el código lo maneje en base 0.
Los nombres de los fragmentos con nombre se escriben como anotación propia en
el inicio de su fragmento dentro del EDF afinado.

**Precedencia**, que es la regla del §3.3 de la especificación y se respeta en
todo el código: los tramos `CAL` son la fuente y `MVC ref` es un resultado en
caché. Con tramos presentes la referencia se recalcula siempre; la anotación
solo se usa cuando no hay tramos, que es el caso de los archivos anteriores.

---

## 3. Flujo del alumno, pantalla a pantalla

Las tres pestañas se llaman, literalmente:

| EN | ES |
|---|---|
| Acquisition | Adquisición |
| Analysis | Análisis |
| MVC normalisation | Normalización CVM |

La práctica se elige en el desplegable de la esquina superior derecha,
«Practical the app is set up for» / «Práctica para la que la aplicación está
configurada», con estos valores: `Single-muscle contraction` / «Contracción de
un músculo», `Agonist / antagonist contraction` / «Contracción agonista /
antagonista» y `Muscle kinematics` / «Cinemática muscular».

### 3.1 Contracción de un músculo

1. **Pestaña Adquisición.** Caja `Device configuration` / «Configuración del
   dispositivo»: la dirección del BITalino o el puerto del Arduino, `Output
   path and file:` / «Ruta y archivo de salida:» con su `Browse…` /
   «Explorar…», `Labels:` / «Etiquetas:» para el nombre del músculo y
   `Test identifier:` / «Identificador de prueba:», que da nombre al
   registro.
2. Caja `Acquisition control` / «Control de adquisición»: `Connect` /
   «Conectar». El estado pasa de `Status: disconnected` / «Estado:
   desconectado» a `Status: connected (ready to record)` / «Estado: conectado
   (listo para grabar)».
3. `Start recording` / «Iniciar grabación» pide el nombre del archivo, que
   propone a partir del identificador de prueba y de la fecha
   (`P01_2026-09-06_09-15.edf`), en Documentos mientras no se elija otra
   carpeta, y empieza. El botón pasa a `Stop recording` / «Detener grabación» y el estado
   a `Status: recording…` / «Estado: grabando…».
4. `Calibrate MVC` / «Calibrar CVM», en la caja `Muscle load (live MVC)` /
   «Carga muscular (CVM en vivo)», lanza el asistente. Es un cuadro oscuro
   flotante sobre las gráficas, con esta secuencia por músculo: calentamiento
   de 10 s, y luego tres veces la pareja cuenta atrás (3 s) y esfuerzo (1,5 s),
   con 2 s de descanso. Los textos son `Warm up first` / «Caliente primero»,
   `Get ready — {label}{rep}` / «Prepárese — {label}{rep}» y `Maximum, short
   and hard — {label}{rep}` / «¡Máximo, breve y fuerte! — {label}{rep}», y al
   acabar `MVC ready` / «CVM listo». Mientras corre aparece `Cancel guide
   (Esc)` / «Cancelar guía (Esc)».
5. Terminada la calibración, las barras de `Muscle load (live MVC)` muestran el
   % CVM en vivo con sus zonas de color y los niveles P10/P50/P90.
6. Al detener, el registro completo se dibuja en la propia pestaña con sus
   fases sombreadas y sus nombres, y pasa solo a la pestaña de Análisis.
7. **Pestaña Análisis.** El registro se analiza al recibirlo, sin pulsar nada.
   Un cartel flotante nombra el paso siguiente. Primero
   `Calibration repetitions…` / «Repeticiones de la calibración…»: una lista
   con una casilla por repetición, su valor en mV, su porcentaje respecto de la
   mejor y su diafonía cuando hay dos canales; debajo, la referencia resultante
   y la anterior. Debe quedar al menos una conservada. Después
   `Select fragments…` / «Seleccionar fragmentos…»: una fila por contracción
   encontrada, con su casilla `Keep` / «Conservar» y un campo de nombre. Una
   línea amarilla sobre el gráfico dice en qué paso se está,
   `<b>Step {k} of 3</b> · {text}` / «`<b>Paso {k} de 3</b> · {text}`»:
   1. `Sensitivity` / «Sensibilidad», con `Marked / expected` /
      «Marcadas / esperadas» al lado: se mueve hasta que el recuento coincida
      con lo que se hizo. Los tramos que quedan bajo el umbral salen punteados,
      `below the threshold: click to add` / «bajo el umbral: pulse para
      añadir».
   2. Cada contracción, con ◀ ▶ o pulsando en el gráfico: `Keep it` /
      «Mantener», `Drop it` / «Eliminar» o `Split it` / «Dividir» (solo donde
      la fila guarda dos picos), y un botón por músculo para `Led by:` /
      «Quién la lleva:». Una marca se puede arrastrar sobre otra actividad; si
      debajo no hay ninguna, vuelve a su sitio.
   3. `Use these fragments` / «Usar estos fragmentos», que se aplica aunque no
      se cambie nada.
8. Los resultados: los paneles arriba, y abajo la tabla de contracciones y el
   resumen en fichas. `Save figure (PNG)` / «Guardar figura (PNG)`,
   `Generate PDF report` / «Generar informe PDF» y `Export CSV` /
   «Exportar CSV».
9. `Save tuned EDF…` / «Guardar EDF afinado…» escribe un archivo nuevo con las
   decisiones tomadas. El nombre propuesto es el del original con el sufijo
   `_tuned`; si existe, se añade un contador (`_tuned_2`). **El original no se
   toca nunca.** El derivado lleva en su cabecera y en tres anotaciones de qué
   archivo procede, qué se conservó de cada fase y cuándo se generó, y en
   `patientname` va el **código de la prueba**, no el nombre del alumno.
10. **Pestaña Normalización CVM.** La primera vez muestra un panel de entrada
    que explica qué es una CVM, con `I understand, continue` / «Entendido,
    continuar». Se abre el archivo con `Browse…` y se pulsa `Compute MVC` /
    «Calcular CVM». Un aviso bajo la casilla del archivo recuerda que el
    archivo `_tuned` es el que lleva las decisiones tomadas en Análisis.

### 3.2 Contracción agonista / antagonista

Igual que la anterior salvo en cinco puntos:

- Hay **dos campos de etiqueta**, uno por músculo, y dos carriles de señal,
  azul el canal 1 y rojo el canal 2.
- **La calibración es obligatoria y la lanza el propio botón de grabar**: no
  hay que acordarse de pulsar «Calibrar CVM». El flujo es calibración →
  preparación (5 s) → registro, sin detener la adquisición.
- El asistente calibra **primero un músculo y después el otro**.
- El editor de fragmentos abre con **k = 4,4** en vez de 3,0, y espera
  **seis flexiones, seis extensiones y una presa**; lo esperado se puede
  cambiar si se repite una serie.
- En Análisis aparece la caja `Co-activation` / «Coactivación» con una fila por
  ventana marcada, y el panel 9 compara las dos envolventes en % CVM.

### 3.3 El recorrido guiado, literal

Se ofrece al arrancar, con una casilla para no volver a ofrecerlo, y se puede
reabrir con el botón `Guide` / «Guía». Son **cinco pasos** en las prácticas de
un músculo y del par, y **siete** en la de cinemática, tomados de los nueve que
define `build_tour()`.

En la práctica del par, el paso de conexión lleva una imagen con los dos pares
de electrodos y la referencia, y el de grabación otra con la calibración:
`src/emgteach/gui/assets/recorrido/`, en inglés y en español, con la clave de
colores de la aplicación (primer músculo azul, segundo rojo). Las genera
`tools/imagenes_recorrido.py`, que lee de las constantes del asistente los
números de la calibración.

<<<TOUR>>>

El recorrido tiene **9** pasos definidos en `src/emgteach/gui/tour.py`; cuáles se muestran depende de la práctica.

- **`src/emgteach/gui/tour.py:69`**
  - EN: Choose the practical first
  - ES: Elegir primero la práctica
  - EN: Everything else follows from this. Each mode records what that practical needs — one muscle, an agonist/antagonist pair, or a muscle plus the accelerometer — and the rest of the interface offers only the measurements that make sense for it. The coloured band beside it is the level: basic, intermediate or advanced.
  - ES: Todo lo demás sale de aquí. Cada modo registra lo que esa práctica necesita (un músculo, un par agonista/antagonista, o un músculo más el acelerómetro) y el resto de la interfaz ofrece solo las medidas que tienen sentido para ella. La banda de color de al lado es el nivel: básico, intermedio o avanzado.
- **`src/emgteach/gui/tour.py:113`**
  - EN: Connecting the sensor
  - ES: Conexión del sensor
- **`src/emgteach/gui/tour.py:126`**
  - EN: Recording
  - ES: Registro
  - EN: Press record. The session asks first for a maximal contraction — the reference every measurement is expressed against — and then for the task. Both go into one file, so nothing has to be matched up afterwards. Watch the live trace: at rest it should be a flat line with only baseline noise. A signal that never returns to baseline usually means a loose electrode, not a tonic muscle. Each contraction onset is marked on its own.
  - ES: Pulse grabar. La sesión pide primero una contracción máxima (la referencia respecto a la que se expresa cada medida) y después la tarea. Las dos van a un solo archivo, así que no hay que emparejar nada después. Observe el trazo en directo: en reposo debe ser una línea plana con solo el ruido basal. Una señal que nunca vuelve a la línea base suele ser un electrodo suelto, no un músculo tónico. El inicio de cada contracción se marca solo.
- **`src/emgteach/gui/tour.py:146`**
  - EN: How to place the accelerometer
  - ES: Cómo situar el acelerómetro
  - EN: There are two possibilities: on the muscle it allows the mechanomyogram (MMG) to be measured, which runs in parallel with the electrical signal; on the moving segment of the joint it allows the movement, and the parameters associated with it, to be measured — including the delay between the muscle firing and the limb moving.
  - ES: Hay dos posibilidades: sobre el músculo permite medir el mecanomiograma (MMG), que corre en paralelo con la señal eléctrica; sobre el segmento móvil de la articulación permite medir el movimiento y los parámetros asociados a él, incluido el retraso entre que el músculo se activa y la extremidad se mueve.
- **`src/emgteach/gui/tour.py:159`**
  - EN: The force-velocity experiment, and its rehearsal
  - ES: El experimento fuerza-velocidad, y su ensayo
  - EN: The step-by-step wizard guides you through the contractions with different loads: with a greater load the velocity is lower, and that inverse relation is the force-velocity curve. As it is the longest procedure in the application, a simulation is provided as a rehearsal, so that what is going to be done live is understood first.
  - ES: El asistente paso a paso guía las contracciones con distintas cargas: con más carga la velocidad es menor, y esa relación inversa es la curva fuerza-velocidad. Como es el procedimiento más largo de la aplicación, se ofrece una simulación como ensayo, para entender primero lo que se va a hacer en vivo.
- **`src/emgteach/gui/tour.py:175`**
  - EN: Agonist and antagonist
  - ES: Agonista y antagonista
  - EN: The recording is analysed as soon as it is opened. Both muscles were calibrated while recording, so the two envelopes are overlaid in % MVC — the only form in which two different muscles compare at all, since each one's millivolts depend on its own electrodes and skin. In a clean movement the agonist activates while the antagonist stays nearly silent; simultaneous activation is co-activation, which holds the joint rigid and is typical of an unpractised or uncertain movement. The table below the panels gives one row per contraction, and which muscle led it.
  - ES: El registro se analiza en cuanto se abre. Los dos músculos se calibraron al grabar, así que las dos envolventes se superponen en % CVM, la única forma en que dos músculos distintos se pueden comparar, porque los milivoltios de cada uno dependen de sus electrodos y de su piel. En un movimiento limpio el agonista se activa mientras el antagonista queda casi en silencio; la activación simultánea es coactivación, que deja rígida la articulación y es típica de un movimiento poco practicado o inseguro. La tabla bajo los paneles da una fila por contracción, y qué músculo la lideró.
- **`src/emgteach/gui/tour.py:193`**
  - EN: Force-velocity study
  - ES: Estudio fuerza-velocidad
  - EN: The recording is analysed as soon as it is opened. The study builds the load-velocity, force-velocity and power curves from a recording where several known loads were lifted, and relates them to the EMG amplitude — that is, to how many motor units had to be recruited for each load. The panels also show the movement against the EMG and the delay between the two.
  - ES: El registro se analiza en cuanto se abre. El estudio construye las curvas carga-velocidad, fuerza-velocidad y potencia a partir de un registro en el que se levantaron varias cargas conocidas, y las relaciona con la amplitud del EMG, es decir, con cuántas unidades motoras hubo que reclutar para cada carga. Los paneles muestran también el movimiento frente al EMG y el retraso entre ambos.
- **`src/emgteach/gui/tour.py:208`**
  - EN: What the analysis shows
  - ES: Qué muestra el análisis
  - EN: The recording is analysed as soon as it is opened. Raw signal: what the contracting fibres produce. Normalised envelope: how activation changes over time, which is what is compared between efforts. Spectrum: how the activity is distributed across frequencies — as a sustained contraction fatigues the muscle, the median frequency (MDF) falls. The cards under the panels carry the numbers with their usual ranges, and the table beside them gives one row per contraction.
  - ES: El registro se analiza en cuanto se abre. Señal en bruto: lo que producen las fibras que se contraen. Envolvente normalizada: cómo cambia la activación con el tiempo, que es lo que se compara entre esfuerzos. Espectro: cómo se reparte la actividad entre frecuencias; a medida que una contracción sostenida fatiga el músculo, la frecuencia mediana (MDF) baja. Las fichas bajo los paneles llevan los números con sus rangos habituales, y la tabla de al lado da una fila por contracción.
- **`src/emgteach/gui/tour.py:228`**
  - EN: Why normalise at all
  - ES: Por qué normalizar
  - EN: A raw amplitude cannot be compared between two people, or between two sessions of the same person: it depends on the electrodes, the skin and the fat beneath it. Expressing every value as a percentage of the maximal contraction cancels all of that out, because the two amplitudes share the same electrodes and the same skin: what is left is how hard the muscle is working. The maximum is inside the recording: the session calibrates without stopping, so nothing else has to be chosen here.
  - ES: Una amplitud bruta no se puede comparar entre dos personas, ni entre dos sesiones de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. Expresar cada valor como porcentaje de la contracción máxima cancela todo eso, porque las dos amplitudes comparten los mismos electrodos y la misma piel: lo que queda es cuánto está trabajando el músculo. El máximo está dentro del registro: la sesión calibra sin parar, así que aquí no hay nada más que elegir.

<<<TOUR>>>

---

## 4. Parámetros por defecto

Todos los que afectan a los resultados. «No editable» significa que no hay
control en la interfaz: se cambia en el perfil de señal
(`src/emgteach/profiles.py`), que es un objeto de configuración, no una
constante repartida.

<<<PARAMETROS>>>

| Parámetro (EN) | Rótulo en pantalla (ES) | Valor | Unidad | Dónde se cambia | archivo:línea |
|---|---|---|---|---|---|
| Sampling rate | Frecuencia de muestreo | 1000 | Hz | no editable | `src/emgteach/profiles.py:98` |
| Band-pass, low cut | — | 20,0 | Hz | no editable | `src/emgteach/profiles.py:101` |
| Band-pass, high cut | — | 450,0 | Hz | no editable | `src/emgteach/profiles.py:102` |
| Notch | — | 50,0 | Hz | no editable | `src/emgteach/profiles.py:103` |
| Envelope cutoff frequency (Hz): | Frec. corte envolvente (Hz): | 5,0 | Hz | Análisis y Normalización CVM · casilla numérica (solo en cinemática) | `src/emgteach/profiles.py:104` |
| RMS window | Ventana RMS | 50,0 | ms | no editable | `src/emgteach/profiles.py:107` |
| Spectral segment length | — | 1,0 | s | no editable | `src/emgteach/profiles.py:108` |
| Spectral overlap | — | 0,5 | fracción | no editable | `src/emgteach/profiles.py:109` |
| MVC percentile | — | 95,0 | % | no editable | `src/emgteach/profiles.py:110` |
| MVC peak window | — | 0,2 | s | no editable | `src/emgteach/profiles.py:135` |
| Calibration efforts | — | 3 | repeticiones | no editable | `src/emgteach/profiles.py:143` |
| Duration of one effort | — | 1,5 | s | no editable | `src/emgteach/profiles.py:144` |
| Warm-up | — | 10,0 | s | no editable | `src/emgteach/profiles.py:202` |
| Preparation countdown | — | 5,0 | s | no editable | `src/emgteach/profiles.py:195` |
| Ready countdown | — | 3,0 | s | no editable (MVC_READY_S = 3,0) | `src/emgteach/gui/tabs/acquisition.py:128` |
| Rest between repetitions | — | 2,0 | s | no editable (MVC_REST_S = 2,0) | `src/emgteach/gui/tabs/acquisition.py:129` |
| Auto-onset k | — | 3,0 | desv. típicas | Adquisición · «Marcadores de eventos» · k | `src/emgteach/profiles.py:217` |
| Onset baseline | — | 1,0 | s | no editable | `src/emgteach/profiles.py:218` |
| Onset refractory | — | 0,5 | s | no editable | `src/emgteach/profiles.py:219` |
| Sensitivity | Sensibilidad | 3,0 · 4,4 · 3,0 | desv. típicas (un músculo · par · cinemática) | Análisis · «Seleccionar fragmentos…» · Sensibilidad («Restablecer» vuelve aquí) | `src/emgteach/modes.py:84` |
| Marked / expected | Marcadas / esperadas | 6 · 6 · 1 | contracciones (flexión · extensión · presa; solo en el par) | Análisis · «Seleccionar fragmentos…» · esperadas | `src/emgteach/modes.py:90` |
| Jonsson static limit (P10) | — | 5,0 | % CVM | no editable | `src/emgteach/profiles.py:113` |
| Jonsson median limit (P50) | — | 14,0 | % CVM | no editable | `src/emgteach/profiles.py:114` |
| Jonsson peak limit (P90) | — | 70,0 | % CVM | no editable | `src/emgteach/profiles.py:115` |
| Mean-activation limit | — | 10,0 | % CVM | no editable | `src/emgteach/profiles.py:118` |
| Live warning zone | — | 40,0 | % CVM | Adquisición · «Carga muscular» · Aviso | `src/emgteach/profiles.py:68` |
| Live danger zone | — | 70,0 | % CVM | Adquisición · «Carga muscular» · Peligro | `src/emgteach/profiles.py:68` |
| Co-activation floor | — | 5,0 | % CVM | no editable | `src/emgteach/profiles.py:187` |
| Implausible MVC | — | 150,0 | % CVM | no editable | `src/emgteach/profiles.py:154` |
| Minimum rest ratio | — | 5,0 | veces el reposo | no editable | `src/emgteach/profiles.py:124` |
| Cross-talk limit | — | 50,0 | % de su referencia | no editable | `src/emgteach/profiles.py:169` |
| Fatigue R² threshold | — | 0,3 | — | no editable (`fatigue_verdict(min_r2=)`) | `src/emgteach/fatigue.py:87` |
| Fatigue minimum segments | — | 4 | ventanas | no editable | `src/emgteach/profiles.py:214` |
| Fatigue active ratio | — | 0,3 | fracción | no editable | `src/emgteach/profiles.py:209` |
| BITalino ADC | — | 1023 | cuentas (10 bits) | no editable | `src/emgteach/devices/bitalino.py:141` |
| BITalino V_ref | — | 3,3 | V | no editable | `src/emgteach/devices/bitalino.py:142` |
| BITalino EMG gain | — | 1009,0 | — | no editable | `src/emgteach/devices/bitalino.py:145` |
| Arduino ADC | — | 1023,0 | cuentas (10 bits) | no editable | `src/emgteach/devices/arduino.py:80` |
| Arduino V_ref | — | 5,0 | V | no editable | `src/emgteach/devices/arduino.py:81` |
| MyoWare gain | — | 200,0 | — | no editable | `src/emgteach/devices/arduino.py:82` |
| F-V lifts per load | — | 3 | levantamientos | Adquisición · «Parámetros de la F-V…» | `src/emgteach/gui/tabs/acquisition.py:154` |
| F-V preparation | — | 6,0 | s | Adquisición · «Parámetros de la F-V…» | `src/emgteach/gui/tabs/acquisition.py:155` |
| F-V lift time | — | 1,0 | s | Adquisición · «Parámetros de la F-V…» | `src/emgteach/gui/tabs/acquisition.py:156` |

<<<PARAMETROS>>>

La conversión a milivoltios del BITalino es
`EMG(mV) = (ADC / 2^10 − 0,5) · VCC · 1000 / G`, con `G = 1009`
(`src/emgteach/devices/bitalino.py:657`). La del Arduino es
`(ADC · V_ref / 1023 − V_ref/2) · 1000 / 200`
(`src/emgteach/devices/arduino.py:192`).

---

## 5. Qué calcula y qué muestra

### 5.1 Paneles del análisis

<<<PANELES>>>

| Nº | Nombre largo (EN) | Nombre largo (ES) | Etiqueta corta (ES) |
|---|---|---|---|
| 1 | 1A. Raw signal | 1A. Señal en bruto | 1A. En bruto |
| 2 | 1B. Raw signal — 2nd muscle | 1B. Señal en bruto — 2º músculo | 1B. Bruto (2º) |
| 3 | 2. Normalised envelope | 2. Envolvente normalizada | 2. Env. norm. |
| 4 | 3. PSD with MNF/MDF | 3. PSD con MNF/MDF | 3. PSD |
| 5 | 4. Filtered + rectified | 4. Filtrada + rectificada | 4. Filtr.+rect. |
| 6 | 5. Envelope vs RMS | 5. Envolvente vs RMS | 5. Env. vs RMS |
| 7 | 6. RMS per window | 6. RMS por ventana | 6. RMS/ventana |
| 8 | 7. MDF vs time (fatigue) | 7. MDF vs tiempo (fatiga) | 7. MDF/tiempo |
| 9 | 8. RMS vs MDF | 8. RMS vs MDF | 8. RMS vs MDF |
| 10 | 9. Overlaid envelopes (agonist/antagonist) | 9. Envolventes superpuestas (agonista/antagonista) | 9. Env. superp. |
| 11 | 10. EMG vs MMG (electrical vs mechanical) | 10. EMG vs MMG (eléctrico vs mecánico) | 10. EMG vs MMG |
| 12 | 11. Tremor (accelerometer FFT) | 11. Temblor (FFT del acelerómetro) | 11. Temblor |
| 13 | 12. Movement vs EMG (limb kinematics) | 12. Movimiento vs EMG (cinemática del segmento) | (sin entrada en el catálogo) |

<<<PANELES>>>

Cuáles se abren depende de la práctica. Siempre disponibles: 1A y 3. La de un
músculo abre además el 2; la del par, el 1B, el 7 y el 9; la de cinemática, el
2 y los tres del acelerómetro (10, 11 y 12). Los paneles 4 a 8 están en
`More panels…` / «Más paneles…» en cualquier práctica.

### 5.2 Tabla de contracciones

Columnas, literales: `#`, `Start (s)` / «Inicio (s)», `Duration (s)` /
«Duración (s)», `Muscle` / «Músculo», `RMS (mV)`, `Peak (% MVC)` /
«Pico (% CVM)», `MDF (Hz)` y, solo en cinemática, `EMD (ms)`. Definidas en
`src/emgteach/gui/tabs/analysis.py:1882`.

### 5.3 Tabla de coactivación

Cuatro columnas: `Window` / «Ventana», el nombre del primer músculo sobre
`mean % MVC` / «media % CVM», lo mismo para el segundo, y
`Co-activation index` / «Índice de coactivación». En
`src/emgteach/gui/tabs/analysis.py:1797`.

### 5.4 Fichas del resumen

Nueve, con su rango orientativo debajo: `Mean frequency (MNF)`,
`Median frequency (MDF)`, `MDF slope`, `Fatigue`, `Task maximum`,
`Global RMS`, `iEMG`, `Duration` y `MVC`. En
`src/emgteach/gui/tabs/analysis.py:905-949`.

### 5.5 Informe PDF y CSV

El **PDF** (`src/emgteach/reports.py:584`, `build_session_report`) lleva
cabecera con identificador y archivo, una sección de calibración con las
repeticiones y la separación entre canales, los paneles elegidos, la tabla de
contracciones, la de coactivación, la tabla `Configuration used` /
«Configuración utilizada» —que desde la 3.1.0 incluye `Detection sensitivity
(k)` / «Sensibilidad de detección (k)»— y un pie reproducible con versión y
commit.

El **CSV** (`src/emgteach/exports.py:44`, `write_analysis_csv`) empieza por
quince líneas de cabecera comentadas con `#`: archivo, canal, frecuencia de
muestreo, ventana analizada, sensibilidad de detección (k), duración, RMS
global, MNF, MDF, iEMG, pendiente de la MDF en Hz/s y en Hz/min, R², caída
porcentual y veredicto de fatiga. La línea de la k es de la 3.1.0, y solo
falta cuando el resultado no la trae. Después
va la tabla por segmento con tres columnas: `t_s`, `rms_mv`, `mdf_hz`.

### 5.6 Índice de coactivación

Implementado en `coactivation_index()`,
`src/emgteach/coactivation.py:237`. Sobre las **dos envolventes expresadas en
% CVM de la referencia de su propio músculo**, con el **nivel de reposo de cada
músculo ya restado** (`resting_level`: el percentil 10 de la envolvente sobre
todo el tramo analizado, pasado como argumento y no medido sobre la ventana).
Con fragmentos elegidos, desde la 3.1.1 el tramo es la fase de registro sin
recortar y cada fragmento con nombre es una máscara sobre ella
(`coactivation_by_fragments`): la misma definición del reposo en las dos
vías.

```
índice = 100 · 2 · ∫ mín(a₁, a₂) dt / ∫ (a₁ + a₂) dt
```

donde `a₁` y `a₂` son las envolventes por encima del reposo. Es la formulación
de Falconer y Winter. El resultado se acota a [0, 100].

**No se informa** en tres casos, y en cada uno aparece su motivo en lugar del
número:

| Condición | EN | ES |
|---|---|---|
| Menos de dos muestras | `not reported — window too short` | `no se informa — ventana demasiado corta` |
| Un músculo por debajo del suelo | `not reported — {name} below {floor:.0f} % MVC` | `no se informa — {name} por debajo del {floor:.0f} % CVM` |
| Sin activación sobre el reposo | `not reported — no activation above rest` | `no se informa — no hay activación sobre el reposo` |

El suelo es `coact_floor_pct = 5,0 % CVM`.

### 5.7 Veredicto de fatiga

`fatigue_verdict()`, `src/emgteach/fatigue.py:82`. Tres salidas y un criterio
sin ambigüedad:

- menos de `fatigue_min_segments` (4) ventanas, o pendiente nula → **no
  concluyente**;
- R² por debajo de `min_r2` (0,30) → **no concluyente**;
- pendiente negativa → **fatiga**; pendiente positiva → **sin fatiga**.

Los tres textos son `Fatigue` / «Fatiga», `No fatigue` / «Sin fatiga» y
`Inconclusive` / «No concluyente», este último acompañado de la razón: la
tendencia no ajusta, con su R².

---

## 6. Avisos, advertencias y errores

<<<AVISOS>>>

Son **88** mensajes distintos. Se listan tal como están en el código, sin reordenar ni resumir.

- **`src/emgteach/charts.py:587`**
  - EN: not reported
  - ES: no se informa
- **`src/emgteach/coactivation.py:265`**
  - EN: not reported — window too short
  - ES: no se informa — ventana demasiado corta
- **`src/emgteach/coactivation.py:280`**
  - EN: not reported — {name} below {floor:.0f} % MVC
  - ES: no se informa — {name} por debajo del {floor:.0f} % de CVM
- **`src/emgteach/coactivation.py:292`**
  - EN: not reported — no activation above rest
  - ES: no se informa — sin activación por encima del reposo
- **`src/emgteach/crash.py:120`**
  - EN: The application hit an error it did not expect. What you were doing may not have been saved.

The details have been written to:
{path}

Send that file on, with a note of what you were doing at the time.
  - ES: La aplicación ha encontrado un error que no esperaba. Puede que lo que estaba haciendo no se haya guardado.

Los detalles se han escrito en:
{path}

Envíe ese fichero, indicando qué estaba haciendo en ese momento.
- **`src/emgteach/crash.py:125`**
  - EN: The application hit an error it did not expect, and could not write the details to a file.
  - ES: La aplicación ha encontrado un error que no esperaba, y no ha podido escribir los detalles en un fichero.
- **`src/emgteach/crash.py:131`**
  - EN: Unexpected error
  - ES: Error inesperado
- **`src/emgteach/dsp.py:523`**
  - EN: Suspiciously flat baseline at the start of the recording. May indicate a disconnected electrode or misconfigured gain.
  - ES: Línea base sospechosamente plana al inicio del registro. Puede indicar un electrodo desconectado o una ganancia mal configurada.
- **`src/emgteach/exports.py:41`**
  - EN: not conclusive (the MDF trend does not fit)
  - ES: no concluyente (la tendencia de MDF no ajusta)
- **`src/emgteach/gui/app.py:256`**
  - EN: Take a picture by itself every {s:.0f} s, but only while a recording is running. It needs no switching off: outside a recording it does nothing.
  - ES: Hace una captura sola cada {s:.0f} s, pero solo mientras se graba. No hay que desactivarlo: fuera de una grabación no hace nada.
- **`src/emgteach/gui/app.py:656`**
  - EN: The screenshot could not be saved: {error}
  - ES: No se pudo guardar la captura: {error}
- **`src/emgteach/gui/app.py:661`**
  - EN: The screenshot could not be saved to: {path}
  - ES: No se pudo guardar la captura en: {path}
- **`src/emgteach/gui/help_texts.py:44`**
  - EN: After {warm} s of warm-up, {n} brief maximal efforts of {dur} s are recorded for each muscle, each announced {cue} s ahead and followed by {rest} s of rest. The reference is the strongest {win} s across the repetitions kept, so it is a maximum the task cannot exceed; a repetition that came out weak can be discarded afterwards in the analysis.
  - ES: Tras {warm} s de calentamiento se graban {n} esfuerzos máximos breves de {dur} s por músculo, cada uno anunciado con {cue} s de antelación y seguido de {rest} s de descanso. La referencia es el tramo de {win} s más fuerte de las repeticiones que se conservan, de modo que es un máximo que la tarea no puede superar; una repetición que salió floja puede descartarse después en el análisis.
- **`src/emgteach/gui/help_texts.py:64`**
  - EN: The application supports two devices: the BITalino over Bluetooth and the Arduino + MyoWare 2.0 over USB. Only the single-muscle practical can use the Arduino; the other two need the BITalino's second channel or its accelerometer, so they fix it and the selector does not appear.
  - ES: La aplicación admite dos dispositivos: el BITalino por Bluetooth y el Arduino + MyoWare 2.0 por USB. Solo la práctica de un músculo puede usar el Arduino; las otras dos necesitan el segundo canal del BITalino o su acelerómetro, así que lo fijan y el selector no aparece.
- **`src/emgteach/gui/help_texts.py:78`**
  - EN: Start recording and ask for the contraction. Watch the live trace: at rest it should be a flat line with only baseline noise. A signal that never returns to baseline usually means a loose electrode or a poor contact, not a tonic muscle.
  - ES: Se inicia el registro y se pide la contracción. Conviene vigilar el trazado en vivo: en reposo debe ser una línea plana con solo ruido de base. Una señal que nunca vuelve a la línea de base suele indicar un electrodo suelto o mal contacto, no un músculo tónico.
- **`src/emgteach/gui/help_texts.py:91`**
  - EN: With this ticked the application timestamps each contraction onset as it finds it — the threshold is the resting level plus k standard deviations, and k is the knob beside it. The marks travel inside the EDF, so each effort can be found again during the analysis. Unticked, nothing is written: marking by hand during a recording asks the operator to keep up with a signal that does not wait.
  - ES: Con esto marcado, la aplicación anota el instante de cada inicio de contracción según lo encuentra: el umbral es el nivel de reposo más k desviaciones típicas, y k es el mando de al lado. Las marcas viajan dentro del EDF, así que cada esfuerzo se vuelve a encontrar en el análisis. Sin marcar, no se escribe ninguna: marcar a mano durante un registro es pedirle al operador que siga el ritmo de una señal que no espera.
- **`src/emgteach/gui/help_texts.py:121`**
  - EN: A muscle shortens more slowly the heavier the load it moves, and the power it delivers is greatest at intermediate loads. This box is the sequence that measures it. Three steps, and only the first two are here.

First, «Rehearse…», which is optional and needs no hardware: it plays the whole procedure over a synthetic recording, with the same prompts in the same order, and ends in the force-velocity study itself. It is worth one run before anyone holds a weight; skip it once you know the procedure.

Second, «F-V parameters…»: the loads in order, the lifts per load, the seconds to prepare each one and the seconds of the lift. Nothing starts there — the plan is kept for the recording.

Third, «Start recording», in the box to the left. It runs the whole session on its own: it asks for the file name, calibrates the maximum first (a warm-up and three brief maximal efforts against something that cannot move), announces the study, and then cues one quick lift for each repetition of each load, marking every one in the file with its load. There is no isometric maximum without load in between: the calibration was that. «Cancel guide (Esc)» stops the guidance at any moment and the recording goes on.

In the Analysis tab the contraction table then holds one row per lift, and the force-velocity study reads those rows to draw the load-velocity, force-velocity, power and recruitment curves.
  - ES: Un músculo se acorta más despacio cuanto mayor es la carga que mueve, y la potencia que entrega es máxima con cargas intermedias. Esta caja es la secuencia que lo mide. Son tres pasos, y aquí solo están los dos primeros.

Primero, «Ensayar…», que es opcional y no necesita hardware: recorre el procedimiento entero sobre un registro sintético, con los mismos avisos y en el mismo orden, y termina en el propio estudio fuerza-velocidad. Merece una pasada antes de que nadie sostenga un peso; sáltelo cuando ya conozca el procedimiento.

Segundo, «Parámetros de la F-V…»: las cargas en orden, los levantamientos por carga, los segundos para preparar cada una y los segundos de levantamiento. Ahí no empieza nada: el plan se guarda para la grabación.

Tercero, «Iniciar grabación», en la caja de la izquierda. Lleva la sesión entera sola: pide el nombre del archivo, calibra primero el máximo (un calentamiento y tres esfuerzos máximos breves contra algo que no se pueda mover), anuncia el estudio y después va pidiendo un levantamiento rápido por cada repetición de cada carga, marcando cada uno en el archivo con su carga. No hay máximo isométrico en vacío entre medias: la calibración ya lo fue. «Cancelar guía (Esc)» detiene la guía en cualquier momento y la grabación sigue.

En la pestaña de Análisis la tabla de contracciones trae entonces una fila por levantamiento, y el estudio fuerza-velocidad lee esas filas para dibujar las curvas carga-velocidad, fuerza-velocidad, potencia y reclutamiento.
- **`src/emgteach/gui/help_texts.py:241`**
  - EN: <b>Not detected</b>: the MDF stays flat or rises.
  - ES: <b>No detectada</b>: la MDF se mantiene o sube.
- **`src/emgteach/gui/help_texts.py:243`**
  - EN: <b>Not conclusive</b>: the line does not fit (low R²). This is usual with short or intermittent contractions; the recording does not answer the question, which is not the same as answering “no”.
  - ES: <b>No concluyente</b>: la recta no ajusta (R² bajo). Es lo habitual con contracciones cortas o intermitentes; el registro no responde a la pregunta, que no es lo mismo que responder «no».
- **`src/emgteach/gui/help_texts.py:280`**
  - EN: One line per window, its seconds on the right. A purple bar is the index, with the number in it. A gold block means the index is not reported, and the small square beside it is the colour of the muscle that worked alone — in a clean flexion or extension that is the correct answer, not a fault. No square at all is a rest. The two mean activations are in the table.
  - ES: Una línea por ventana, con sus segundos a la derecha. Una barra morada es el índice, con el número dentro. Un bloque dorado quiere decir que el índice no se informa, y el cuadradito de al lado lleva el color del músculo que trabajó solo: en una flexión o una extensión limpias esa es la respuesta correcta, no un fallo. Sin cuadradito, es un reposo. Las dos activaciones medias están en la tabla.
- **`src/emgteach/gui/help_texts.py:306`**
  - EN: median frequency of the spectrum. Typically 60–150 Hz for surface EMG of limb muscles; it falls along a sustained effort as the muscle fatigues. Not shown for contractions shorter than a quarter of a second.
  - ES: frecuencia mediana del espectro. Típicamente 60–150 Hz en EMG de superficie de músculos de las extremidades; baja a lo largo de un esfuerzo sostenido a medida que el músculo se fatiga. No se muestra en contracciones de menos de un cuarto de segundo.
- **`src/emgteach/gui/help_texts.py:335`**
  - EN: A raw amplitude cannot be compared between two people, or between two sessions of the same person: it depends on the electrodes, the skin and the fat beneath it. Expressing every value as a percentage of the maximal contraction cancels all of that out, because the two amplitudes share the same electrodes and the same skin: what is left is how hard the muscle is working. The maximum is inside the recording: the session calibrates without stopping, so nothing else has to be chosen here.
  - ES: Una amplitud bruta no se puede comparar entre dos personas, ni entre dos sesiones de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. Expresar cada valor como porcentaje de la contracción máxima cancela todo eso, porque las dos amplitudes comparten los mismos electrodos y la misma piel: lo que queda es cuánto está trabajando el músculo. El máximo está dentro del registro: la sesión calibra sin parar, así que aquí no hay nada más que elegir.
- **`src/emgteach/gui/tabs/acquisition.py:286`**
  - EN: This computer is not connected to any network, so the phones cannot reach it. Connect it to the network the phones use, or share this computer's own connection (Windows: Settings › Network & internet › Mobile hotspot) and connect the phones to that.
  - ES: Este equipo no está conectado a ninguna red, así que los móviles no pueden llegar a él. Conéctelo a la red que usan los móviles, o comparta la conexión del propio equipo (Windows: Configuración › Red e Internet › Zona con cobertura inalámbrica móvil) y conecte los móviles a ella.
- **`src/emgteach/gui/tabs/acquisition.py:981`**
  - EN: Live signal quality: saturation or a flat (disconnected) signal.
  - ES: Calidad de señal en vivo: saturación o señal plana (desconectada).
- **`src/emgteach/gui/tabs/acquisition.py:1843`**
  - EN: The recording cannot be saved
  - ES: No se puede guardar el registro
- **`src/emgteach/gui/tabs/acquisition.py:2068`**
  - EN: The session could not start the calibration on its own. Press «Calibrate MVC» when you are ready — the phases will be written just the same.
  - ES: La sesión no ha podido arrancar la calibración por su cuenta. Pulse «Calibrar CVM» cuando esté listo: las fases se escriben igual.
- **`src/emgteach/gui/tabs/acquisition.py:2247`**
  - EN: The recording could not be shown for review: {err}
  - ES: No se pudo mostrar el registro para revisarlo: {err}
- **`src/emgteach/gui/tabs/acquisition.py:2473`**
  - EN: No network: the phones cannot reach this computer.
  - ES: Sin red: los móviles no pueden llegar a este equipo.
- **`src/emgteach/gui/tabs/acquisition.py:3012`**
  - EN: One short, maximal effort when the count reaches 0 — against something that cannot move, such as the underside of the table, not against a hand.
  - ES: Un solo esfuerzo máximo y breve cuando la cuenta llegue a 0, contra algo que no se pueda mover —el canto inferior de la mesa, por ejemplo—, no contra una mano.
- **`src/emgteach/gui/tabs/acquisition.py:3105`**
  - EN: ⚠ «{muscle}»: the calibration reached {ref:.3f} mV, only {ratio:.1f}× its resting level. That is not a maximal contraction — every % MVC from now on will be too high by that factor. Calibrate again.
  - ES: ⚠ «{muscle}»: la calibración llegó a {ref:.3f} mV, solo {ratio:.1f}× su nivel de reposo. Eso no es una contracción máxima: a partir de ahora todos los % de CVM saldrán altos por ese mismo factor. Calibre de nuevo.
- **`src/emgteach/gui/tabs/acquisition.py:3343`**
  - EN: {muscles}: this is not a maximum. Calibrate again against a resistance the joint cannot move.
  - ES: {muscles}: esto no es un máximo. Calibre de nuevo contra una resistencia que la articulación no pueda mover.
- **`src/emgteach/gui/tabs/acquisition.py:3362`**
  - EN: Channels not separated
  - ES: Canales sin separar
- **`src/emgteach/gui/tabs/acquisition.py:3374`**
  - EN: Calibration failed (no signal).
  - ES: Calibración fallida (sin señal).
- **`src/emgteach/gui/tabs/acquisition.py:3376`**
  - EN: Calibration failed
  - ES: Calibración fallida
- **`src/emgteach/gui/tabs/analysis.py:521`**
  - EN: Restrict every metric (spectrum, RMS, fatigue) to the time window below instead of the whole recording.
  - ES: Restringe todas las métricas (espectro, RMS, fatiga) a la ventana temporal de abajo en lugar del registro completo.
- **`src/emgteach/gui/tabs/analysis.py:913`**
  - EN: usual 60–150 Hz
  - ES: habitual 60–150 Hz
- **`src/emgteach/gui/tabs/analysis.py:1380`**
  - EN: Could not open the fragment editor: {error}
  - ES: No se pudo abrir el editor de fragmentos: {error}
- **`src/emgteach/gui/tabs/analysis.py:1451`**
  - EN: Next: «{button}». It decides which maximal efforts set the reference, and every % MVC below is measured against it — so it goes before choosing the fragments.
  - ES: Siguiente: «{button}». Decide qué esfuerzos máximos fijan la referencia, y todos los % CVM de abajo se miden contra ella, así que va antes de elegir los fragmentos.
- **`src/emgteach/gui/tabs/analysis.py:1572`**
  - EN: This recording carries no calibration. Only sessions recorded with the guided flow mark their maximal efforts.
  - ES: Este registro no trae calibración. Solo las sesiones grabadas con el flujo guiado marcan sus esfuerzos máximos.
- **`src/emgteach/gui/tabs/analysis.py:1590`**
  - EN: This recording carries no calibration spans, so the repetition list stays off. Only sessions recorded with the guided flow have them.
  - ES: Este registro no trae tramos de calibración, así que la lista de repeticiones queda apagada. Solo las sesiones grabadas con el flujo guiado los llevan.
- **`src/emgteach/gui/tabs/analysis.py:1858`**
  - EN: Whole recording: with no named windows this number does not measure anything. Open «{button}» and accept what it proposes.
  - ES: Registro completo: sin ventanas con nombre este número no mide nada. Abra «{button}» y acepte lo que propone.
- **`src/emgteach/gui/tabs/analysis.py:2156`**
  - EN: The report for the phones could not be made: {error}
  - ES: No se ha podido preparar el informe para los móviles: {error}
- **`src/emgteach/gui/tabs/analysis.py:2201`**
  - EN: Not conclusive (trend does not fit, R²={r2:.2f})
  - ES: No concluyente (la tendencia no ajusta, R²={r2:.2f})
- **`src/emgteach/gui/tabs/analysis.py:2234`**
  - EN: The task went well past the reference: the calibration did not capture a maximum, so every % MVC here is too high in the same proportion. Calibrate again, against something that cannot move.
  - ES: La tarea superó con mucho la referencia: la calibración no recogió un máximo, así que todos los % CVM de aquí están inflados en la misma proporción. Vuelva a calibrar contra algo que no pueda moverse.
- **`src/emgteach/gui/tabs/analysis.py:2301`**
  - EN: Could not open the force-velocity study: {error}
  - ES: No se pudo abrir el estudio fuerza-velocidad: {error}
- **`src/emgteach/gui/tabs/analysis.py:2338`**
  - EN: Channel «{ch}»: flat — no signal (electrode not connected?).
  - ES: Canal «{ch}»: plano — sin señal (¿electrodo sin conectar?).
- **`src/emgteach/gui/tabs/analysis.py:2343`**
  - EN: Channel «{ch}»: saturated — the trace is pinned at the rails (check the electrode contact or the gain).
  - ES: Canal «{ch}»: saturado — la traza está pegada al tope (conviene revisar el contacto del electrodo o la ganancia).
- **`src/emgteach/gui/tabs/analysis.py:2350`**
  - EN: Channel «{ch}»: weak signal (low amplitude).
  - ES: Canal «{ch}»: señal débil (amplitud baja).
- **`src/emgteach/gui/tabs/analysis.py:2489`**
  - EN: Filtered EMG (20-450 Hz)
  - ES: EMG filtrado (20-450 Hz)
- **`src/emgteach/gui/tabs/analysis.py:2830`**
  - EN: The tuned recording cannot replace the one it comes from: tuning discards signal, so its source has to stay.
  - ES: El registro afinado no puede sustituir a aquel del que sale: afinar descarta señal, así que su origen tiene que quedarse.
- **`src/emgteach/gui/tabs/analysis.py:2882`**
  - EN: CSV export error: {error}
  - ES: Error al exportar CSV: {error}
- **`src/emgteach/gui/tabs/analysis.py:3035`**
  - EN: Error generating the PDF report: {error}
  - ES: Error al generar el informe PDF: {error}
- **`src/emgteach/gui/tabs/analysis.py:3378`**
  - EN: The recording does not match the mode
  - ES: El registro no concuerda con el modo
- **`src/emgteach/gui/tabs/mvc.py:417`**
  - EN: <p>Amplitude Probability Distribution Function (Jonsson): the % of time the muscle stays below each load level (% MVC). The static (P10), median (P50) and peak (P90) levels gauge overload risk.</p>
  - ES: <p>Función de distribución de probabilidad de amplitud (Jonsson): el % del tiempo que el músculo permanece por debajo de cada nivel de carga (% CVM). Los niveles estático (P10), mediano (P50) y pico (P90) valoran el riesgo de sobrecarga.</p>
- **`src/emgteach/gui/tabs/mvc.py:635`**
  - EN: A raw EMG amplitude cannot be compared between two people, or between two sessions of the same person: it depends on the electrodes, the skin and the fat layer beneath it. Normalisation solves this by expressing every value as a percentage of the amplitude that muscle reaches during a maximal effort.
  - ES: La amplitud bruta de una señal EMG no se puede comparar entre dos personas, ni entre dos sesiones de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. La normalización resuelve esto expresando cada valor como porcentaje de la amplitud que ese músculo alcanza en un esfuerzo máximo.
- **`src/emgteach/gui/tabs/mvc.py:649`**
  - EN: The reference has to be made against something that cannot move — the underside of a table, a fixed bar — with the joint held still. Not a hand, and least of all the subject's own other hand: a hand yields, and holding oneself splits the effort between two limbs, which produces less force than either would alone. This is the force-velocity relationship at work: whatever the muscle is allowed to shorten against, it shortens faster and therefore develops less force, so it recruits fewer motor units. A maximum performed in mid-air is submaximal by construction, and every percentage that follows comes out too high in the same proportion.
  - ES: La referencia hay que hacerla contra algo que no se pueda mover —el canto inferior de una mesa, una barra fija— y con la articulación quieta. No contra una mano, y menos aún contra la otra mano del propio sujeto: una mano cede, y sujetarse uno mismo reparte el esfuerzo entre dos miembros, que juntos dan menos fuerza que cualquiera de los dos por separado. Es la relación fuerza-velocidad en acción: contra lo que el músculo pueda acortarse, se acorta más deprisa y por tanto desarrolla menos fuerza, así que recluta menos unidades motoras. Una máxima hecha en el aire es submáxima por construcción, y todos los porcentajes posteriores salen altos en la misma proporción.
- **`src/emgteach/gui/tabs/mvc.py:662`**
  - EN: A recording with no calibration inside it cannot be normalised: without a maximum there is no percentage, and this tab says so rather than dividing the signal by itself.
  - ES: Un registro sin calibración dentro no se puede normalizar: sin un máximo no hay porcentaje, y esta pestaña lo dice en vez de dividir la señal por sí misma.
- **`src/emgteach/gui/tabs/mvc.py:1214`**
  - EN: 2. Envelope (no calibration in this recording)
  - ES: 2. Envolvente (este registro no trae calibración)
- **`src/emgteach/gui/tour.py:128`**
  - EN: Press record. The session asks first for a maximal contraction — the reference every measurement is expressed against — and then for the task. Both go into one file, so nothing has to be matched up afterwards. Watch the live trace: at rest it should be a flat line with only baseline noise. A signal that never returns to baseline usually means a loose electrode, not a tonic muscle. Each contraction onset is marked on its own.
  - ES: Pulse grabar. La sesión pide primero una contracción máxima (la referencia respecto a la que se expresa cada medida) y después la tarea. Las dos van a un solo archivo, así que no hay que emparejar nada después. Observe el trazo en directo: en reposo debe ser una línea plana con solo el ruido basal. Una señal que nunca vuelve a la línea base suele ser un electrodo suelto, no un músculo tónico. El inicio de cada contracción se marca solo.
- **`src/emgteach/gui/tour.py:177`**
  - EN: The recording is analysed as soon as it is opened. Both muscles were calibrated while recording, so the two envelopes are overlaid in % MVC — the only form in which two different muscles compare at all, since each one's millivolts depend on its own electrodes and skin. In a clean movement the agonist activates while the antagonist stays nearly silent; simultaneous activation is co-activation, which holds the joint rigid and is typical of an unpractised or uncertain movement. The table below the panels gives one row per contraction, and which muscle led it.
  - ES: El registro se analiza en cuanto se abre. Los dos músculos se calibraron al grabar, así que las dos envolventes se superponen en % CVM, la única forma en que dos músculos distintos se pueden comparar, porque los milivoltios de cada uno dependen de sus electrodos y de su piel. En un movimiento limpio el agonista se activa mientras el antagonista queda casi en silencio; la activación simultánea es coactivación, que deja rígida la articulación y es típica de un movimiento poco practicado o inseguro. La tabla bajo los paneles da una fila por contracción, y qué músculo la lideró.
- **`src/emgteach/gui/widgets/calibration_reps.py:187`**
  - EN: Keep at least one repetition: a channel with none is not a calibration with a smaller reference, it is no calibration.
  - ES: Conserve al menos una repetición: un canal sin ninguna no es una calibración con una referencia menor, es no haber calibrado.
- **`src/emgteach/gui/widgets/force_velocity_dialog.py:181`**
  - EN: ⚠ The accelerometer barely moved (flat / pinned at a rail), so the velocities are ~0. Put it on the moving segment, oriented so its resting value sits mid-range (not at ±1 g), and lift quickly.
  - ES: ⚠ El acelerómetro apenas se movió (plano / pegado a un extremo), así que las velocidades son ~0. Colocarlo en el segmento móvil, orientado para que en reposo quede a media escala (no en ±1 g), y levantar rápido.
- **`src/emgteach/gui/widgets/force_velocity_dialog.py:338`**
  - EN: No velocity — accelerometer flat
(see the warning)
  - ES: Sin velocidad — acelerómetro plano
(ver el aviso)
- **`src/emgteach/gui/widgets/force_velocity_plan_dialog.py:85`**
  - EN: ⚠ The accelerometer is set to the muscle. For force-velocity put it on the moving segment (set the placement to "on the moving segment"), or the velocity will be near zero.
  - ES: ⚠ El acelerómetro está en el músculo. Para fuerza-velocidad ponerlo en el segmento móvil (poner la colocación en «en el segmento móvil»), o la velocidad será casi cero.
- **`src/emgteach/gui/widgets/force_velocity_plan_dialog.py:108`**
  - EN: Contractions to perform at each load. The wizard prompts one at a time; keep it low (1-3) so fatigue does not bias the heavier loads.
  - ES: Contracciones a realizar en cada carga. El asistente las pide de una en una; mantenlo bajo (1-3) para que la fatiga no sesgue las cargas más pesadas.
- **`src/emgteach/gui/widgets/fragment_selection.py:1418`**
  - EN: The count does not match ({detail}). Move the sensitivity until it does, or as close as it gets; what is left is put right in step 2. Then press ▶.
  - ES: El recuento no coincide ({detail}). Mueva la sensibilidad hasta que coincida, o hasta lo más cerca posible; lo que quede se corrige en el paso 2. Después pulse ▶.
- **`src/emgteach/gui/widgets/fragment_selection.py:1444`**
  - EN: The count does not match yet ({detail}): look for what is missing among the dotted stretches, or drop what is left over.
  - ES: El recuento aún no coincide ({detail}): busque lo que falta entre los tramos punteados, o elimine lo que sobra.
- **`src/emgteach/gui/widgets/fragment_selection.py:1531`**
  - EN: below the threshold: click to add
  - ES: bajo el umbral: pulse para añadir
- **`src/emgteach/gui/widgets/fv_rehearsal_dialog.py:88`**
  - EN: Held, because a true maximum takes about a second to reach. It is isometric — nothing moves, so the accelerometer stays flat here. This contraction sets the amplitude reference, not a velocity.
  - ES: Se mantiene porque alcanzar un máximo de verdad lleva alrededor de un segundo. Es isométrica: no se mueve nada, así que aquí el acelerómetro permanece plano. Esta contracción fija la referencia de amplitud, no una velocidad.
- **`src/emgteach/gui/widgets/logger.py:46`**
  - EN: Error:
  - ES: Error:
- **`src/emgteach/phases.py:481`**
  - EN: no calibration
  - ES: sin calibración
- **`src/emgteach/reports.py:126`**
  - EN: Not conclusive — the trend does not fit ({slope:+.2f} Hz/s, R²={r2:.2f}). Fatigue needs a contraction held long enough for the trend to show.
  - ES: No concluyente: la tendencia no ajusta ({slope:+.2f} Hz/s, R²={r2:.2f}). La fatiga necesita una contracción mantenida el tiempo suficiente para que la tendencia se vea.
- **`src/emgteach/reports.py:227`**
  - EN: Filtered (20-450 Hz)
  - ES: Filtrado (20-450 Hz)
- **`src/emgteach/reports.py:557`**
  - EN: The task exceeds the reference by a wide margin: the calibration did not capture a maximum, so every percentage in this report is too high in the same proportion. Calibrate again with a genuinely maximal contraction, against something that cannot move.
  - ES: La tarea supera la referencia con mucho margen: la calibración no recogió un máximo, así que todos los porcentajes de este informe están inflados en la misma proporción. Vuelva a calibrar con una contracción realmente máxima, contra algo que no pueda moverse.
- **`src/emgteach/reports.py:792`**
  - EN: Notch (mains)
  - ES: Notch (red)
- **`src/emgteach/workers/acquisition.py:51`**
  - EN: The recording «{name}» could not be saved in the folder {folder} ({reason}). Choose another folder — Documents, for example — or another name, and press record again.
  - ES: El registro «{name}» no se ha podido guardar en la carpeta {folder} ({reason}). Elija otra carpeta —Documentos, por ejemplo— u otro nombre, y vuelva a pulsar grabar.
- **`src/emgteach/workers/acquisition.py:384`**
  - EN: Connection to {name} lost: {error}
  - ES: Conexión con {name} perdida: {error}
- **`src/emgteach/workers/acquisition.py:431`**
  - EN: Warning — EDF write error: {error}
  - ES: Aviso — error de escritura EDF: {error}
- **`src/emgteach/workers/acquisition.py:467`**
  - EN: Warning — annotation error: {error}
  - ES: Aviso — error de anotación: {error}
- **`src/emgteach/workers/acquisition.py:473`**
  - EN: Warning — EDF close error: {error}
  - ES: Aviso — error al cerrar el EDF: {error}
- **`src/emgteach/workers/analysis.py:407`**
  - EN: The selected fragments total {t:.2f} s, below the 1 s minimum required for analysis.
  - ES: Los fragmentos seleccionados suman {t:.2f} s, por debajo del mínimo de 1 s requerido para el análisis.
- **`src/emgteach/workers/analysis.py:657`**
  - EN: MDF trend fitted over {n} of {total} segments (the rest were below the contraction threshold).
  - ES: Tendencia de MDF ajustada sobre {n} de {total} segmentos (el resto quedaba por debajo del umbral de contracción).
- **`src/emgteach/workers/analysis.py:1006`**
  - EN: not reported — no MVC reference for one of the channels
  - ES: no se informa — falta la referencia de CVM en uno de los canales
- **`src/emgteach/workers/analysis.py:1020`**
  - EN: ⚠ «{name}»: the recording starts with the muscle already active, so no resting baseline could be measured and contraction onsets were not detected. Record a couple of quiet seconds before the first contraction.
  - ES: ⚠ «{name}»: el registro empieza con el músculo ya activo, así que no se pudo medir una línea base de reposo y no se han detectado inicios de contracción. Grabe un par de segundos en reposo antes de la primera contracción.
- **`src/emgteach/workers/analysis.py:1028`**
  - EN: No contraction detected in «{name}»: it never left its baseline.
  - ES: No se detecta contracción en «{name}»: no sale de su línea base.
- **`src/emgteach/workers/analysis.py:1079`**
  - EN: ⚠ «{name}» reaches {peak:.0f} % MVC, and spends {share:.0f} % of the recording above {limit:.0f} %. The calibration did not capture a maximum — the task beat it — so every percentage here is too high.
  - ES: ⚠ «{name}» llega al {peak:.0f} % de la CVM, y pasa el {share:.0f} % del registro por encima del {limit:.0f} %. La calibración no capturó un máximo —la tarea lo superó—, así que todos los porcentajes de aquí salen inflados.
- **`src/emgteach/workers/analysis.py:1195`**
  - EN: The contraction table could not be built: {err}
  - ES: No se pudo construir la tabla de contracciones: {err}
- **`src/emgteach/workers/mvc.py:282`**
  - EN: This recording carries no calibration, so there is no maximum to express it as a percentage of: no % MVC and no muscle-load analysis. The signal and its envelope do not depend on a reference and are drawn as usual.
  - ES: Este registro no trae calibración, así que no hay un máximo del que expresar porcentajes: ni % CVM ni análisis de carga muscular. La señal y su envolvente no dependen de una referencia y se dibujan como siempre.

<<<AVISOS>>>

---

## 7. Compatibilidad

Las tres clases de archivo del §7 de la especificación, y qué hace cada
pestaña con ellas. La procedencia se muestra siempre, en la ficha «CVM» del
resumen y en el panel de datos de la pestaña de normalización
(`reference_source_text`, `src/emgteach/phases.py:455`).

| Archivo | Qué tiene | Procedencia que muestra | Qué se ofrece |
|---|---|---|---|
| Grabado con 3.0.0 o 3.1.0 | tramos `CAL`, `PREP`, `REC` y `MVC ref` | `calibration in this recording ({n} repetitions)` / «calibración de este registro ({n} repeticiones)» | todo, y las repeticiones son editables |
| Con `MVC ref` pero sin fases | solo la anotación en caché | `calibration as recorded (repetitions not stored)` / «calibración tal como se grabó (no se guardaron las repeticiones)» | todo menos editar la calibración |
| Sin anotaciones | nada | `no calibration` / «sin calibración» | solo lo que no depende de referencia |

En el tercer caso, lo que se ofrece es la señal en bruto, la envolvente
normalizada a su propio máximo, el espectro, MNF/MDF y la fatiga. Lo que
depende de la referencia (% CVM, panel 9 en porcentaje, índice de coactivación
y análisis de Jonsson) queda **deshabilitado con su motivo a la vista**, no
oculto.

Al abrir un registro, la pestaña de análisis comprueba además la calidad de
cada canal y avisa de canal plano, saturado o débil (apartado 6).

---

## 8. Datos de banco

Medidos con la aplicación sobre registros reales, no estimados. El material
adjunto está en `docs/informe-sourcebook/` y lo produce
`tools/informe_material.py`.

Las del apartado 8.1 se volvieron a obtener con la 3.1.0 al rehacer el
material adjunto, y salen iguales; la 3.1.1 no las toca, porque se calculan
sin fragmentos. **Las del 8.2 se han vuelto a medir con la 3.1.1** (apartado
1.1). Las del 8.3 no pasan por la coactivación.

### 8.1 Registro de ejemplo: el par flexor / extensor

`ejemplo_par_FCR_ECR.edf`, dos canales, 140,0 s, del 3 de septiembre de 2026,
con el protocolo ya validado (máximo contra el canto de la mesa, flexor con el
puño cerrado). El tramo analizado son los 23,3 s de la fase de registro.

**Aviso sobre este archivo:** se grabó con el protocolo de calibración de
entonces, **seis repeticiones por músculo** (tres mantenidas y tres breves).
Desde la 3.0.0 la calibración son tres esfuerzos breves. La
referencia se calcula igual —el mejor 0,2 s de las repeticiones conservadas—,
así que las cifras de abajo son comparables, pero el archivo dice «6
repeticiones» donde uno nuevo diría «3». Se conserva como ejemplo porque es el
único registro de dos canales con las dos calibraciones completas y el
protocolo de maniobra ya corregido.

| Medida | Canal 1 (FCR) | Canal 2 (ECR) |
|---|---|---|
| Referencia de CVM | 0,2175 mV | 0,1734 mV |
| Procedencia | recalculada de los tramos `CAL` | recalculada de los tramos `CAL` |
| Nivel de reposo | 3,5 µV (1,62 % CVM) | 7,6 µV (4,39 % CVM) |
| Máximo de la tarea | 125 % CVM | 93 % CVM |

Índice de coactivación sobre el tramo de registro completo: **30 %**, con
medias de 14,4 % y 11,1 % CVM. Correlación de las dos envolventes:
**r = 0,126**.

### 8.2 Las tres maniobras: coactivación por maniobra

`ejemplo_tres_maniobras.edf`, dos canales, 100,0 s, del **6 de septiembre de
2026**, con el protocolo y la calibración actuales: tres esfuerzos breves por
músculo, `REC start` en el segundo 57,3 y 42,7 s de tarea. El protocolo fue
**seis flexiones de muñeca contra resistencia, dos segundos de
quietud, seis extensiones contra resistencia, dos segundos de quietud y una
presa sostenida de unos ocho segundos con la muñeca neutra**.

| Medida | Canal 1 (FCR) | Canal 2 (ECR) |
|---|---|---|
| Referencia de CVM | 0,1468 mV | 0,3558 mV |
| Procedencia | recalculada de los tramos `CAL` | recalculada de los tramos `CAL` |
| Nivel de reposo (el que resta el índice) | 1,75 % CVM | 2,19 % CVM |
| Máximo de la tarea (sostenido 0,2 s) | 73 % CVM | 41 % CVM |

Los dos máximos de tarea quedan **por debajo del 100 %**, que es la
comprobación de que la calibración capturó de verdad un máximo y de que los
porcentajes de abajo significan lo que dicen.

| Maniobra | Tramo | Índice de coactivación | Medias (FCR / ECR) |
|---|---|---|---|
| Flexión | 57,5–70,0 s | **28 %** (28,3) | 14,1 / 5,8 % CVM |
| Extensión | 72,0–85,0 s | **no reportada** | 4,2 / 6,2 % CVM |
| Presa | 88,0–97,0 s | **76 %** (75,7) | 14,5 / 9,1 % CVM |

Medido con la 3.1.1: cada maniobra es una máscara sobre la fase de registro sin
recortar, y el reposo que se resta es el de la fase entera (apartados 1.1 y
5.6). Hasta la 3.1.0 la herramienta que las calculaba tomaba el reposo de cada
ventana de la propia ventana, y las medias salían 14,2 / 5,5 · 3,9 / 5,9 ·
14,3 / 9,1, con índices de 27,6 y 76,0 %.

**Durante la presa el extensor llega al 29 % CVM** y el flexor al 64 %: son
máximos sostenidos de 0,2 s, los que enseña la tabla de contracciones, igual
que los máximos de tarea de arriba, que son los de la ficha «Task maximum».
Los 32 y 69 % de la presa y los 81 y 47 % de la tarea que figuraban aquí no
se reproducen con ningún cálculo del programa, y se sustituyen por los que
enseña la pantalla.

Los dos números que el §8.4 declaraba imposibles son ese 28 % frente a 76 % y
el extensor trabajando en la presa. La figura que los dibuja está en
`docs/articulo-advances/figura6.png`, y se rehace con

```
python tools/figura6.py --edf docs/informe-sourcebook/ejemplo_tres_maniobras.edf --ventana Flexion=57.5:70 --ventana Extension=72:85 --ventana Grip=88:97 --salida docs/articulo-advances
```

Y lo mismo, al decimal, sale en la pestaña de Análisis eligiendo cada
maniobra entera como un fragmento con nombre.

El registro va adjunto —`ejemplo_tres_maniobras.edf`— junto con su versión
afinada, `ejemplo_tres_maniobras_tuned.edf`, que es donde están los trece
fragmentos con nombre: seis `FCR`, seis `ECR` y un `Grip`.

**La extensión no da número, y el motivo importa.** El programa dice «FCR
below 5 % MVC»: el flexor se quedó en 4,2 % de media sobre su reposo, por
debajo del suelo de `coact_floor_pct`. No es una maniobra fallida sino la salvaguarda funcionando
— con el antagonista prácticamente en reposo el índice sería ruido dividido
por ruido. Dicho de otro modo, la extensión fue el más limpiamente recíproco
de los tres movimientos, y el precio de serlo es no tener índice.

**Maniobra entera frente a contracciones.** Elegir en el editor las trece filas
que propone, bien nombradas (seis de flexión, seis de extensión y la presa), mide
otra cosa: la actividad durante las contracciones, sin los reposos entre ellas.

| Selección | Flexión | Extensión | Presa |
|---|---|---|---|
| La maniobra entera, una fila cada una | 28,3 % · 14,1 / 5,8 | — · 4,2 / 6,2 | 75,7 % · 14,5 / 9,1 |
| Las trece filas del editor | 29,0 % · 26,9 / 8,0 | 69,4 % · 8,5 / 14,9 | 75,3 % · 17,0 / 10,9 |

Índice y medias FCR / ECR en % CVM, con la 3.1.1. Sin los reposos las medias
suben, y la extensión gana un índice: el flexor pasa de 4,2 a 8,5 % CVM y supera
el suelo del 5 %. Ese 69 % es la relación entre dos señales débiles —el extensor
en 14,9 y el flexor en 8,5 % de su máximo—, que es el caso que el suelo existe
para no medir. Para esta práctica, la ventana es la maniobra entera.

**Tres avisos sobre estas cifras**, los tres descubiertos al calcularlas:

1. **El EDF afinado y el original no dan el mismo número.** Sobre el afinado
   de este mismo registro salen «sin número» para la flexión, 63 % para la
   extensión y 67 % para la presa (vuelto a medir con la 3.1.1: 63,3 y
   67,3 %, igual que con la 3.0.0, porque el afinado es una concatenación en
   disco y se lee como tal). El afinado concatena los fragmentos y tira
   lo que hay entre ellos, así que la media del músculo activo sube y la del
   otro baja. El índice de Falconer-Winter se lee sobre la fase de movimiento
   con su curso temporal, reposos incluidos; concatenar las contracciones mide
   otra cosa. **Las cifras publicables son las del registro sin recortar.**
   Desde la 3.1.1, elegir los fragmentos en la pestaña sobre el original ya
   no concatena para la coactivación (apartado 1.1); el aviso vale para el
   archivo afinado.
2. **El borde de la ventana: el reposo que entra ya no mueve el índice.** Con
   la 3.0.0, estrechar la presa 0,8 s por delante la llevaba de 76 % a 70 %,
   porque el reposo se medía dentro de la ventana y quitarle segundos de
   reposo lo subía. Con la 3.1.1, restando el reposo de la fase entera, el
   mismo recorte deja el índice en 75,7 %: los segundos de reposo aportan
   cero a los dos lados del cociente. Lo que sí lo mueve es la actividad que
   queda fuera: el extensor sigue activo hasta los 97,95 s, y alargar la presa
   hasta ahí la baja a 74,4 %. Las medias sí dependen del borde, porque son
   medias sobre la duración de la ventana (el flexor pasa de 14,5 a 15,9 % CVM
   con el recorte). Las ventanas de la tabla son las de la maniobra completa,
   de la primera activación a la última relajación.
3. **Un segundo registro del mismo protocolo se descartó**: sus extensiones
   salieron mejor —índice de 43 %— pero la calibración del flexor no capturó
   un máximo (referencia 0,089 mV y máximo de tarea 185 % CVM), y con el
   denominador mal ningún porcentaje de él es publicable. El programa lo avisó
   en pantalla al analizarlo. Queda anotado porque explica por qué la tabla
   sale del registro adjunto y no del más reciente.

### 8.3 Registro de ejemplo: la cinemática

`C:\Records\emg_2026-09-05_18-13.edf`, un canal más acelerómetro, 178,0 s, del
5 de septiembre. Calibración de tres repeticiones, referencia 0,2705 mV,
inicio del registro en el segundo 36,0. Doce levantamientos, tres por cada una
de las cargas de 2, 3,4, 5 y 7 kg, cada uno marcado en el archivo con su carga.

| Carga | Velocidad media (u. a.) |
|---|---|
| 2 kg | 0,0267 |
| 3,4 kg | 0,0305 |
| 5 kg | 0,0200 |
| 7 kg | 0,0140 |

La velocidad cae al aumentar la carga a partir de 3,4 kg y la potencia hace su
máximo en cargas intermedias, que es la forma de Hill. Retraso electromecánico
mediano de 42 ms, dentro del rango de 30 a 100 ms de la literatura. Máximo de
la tarea, 117 % CVM.

### 8.4 Lo que no está medido

- **El tiempo de montaje no se da, y no es un hueco pendiente: se mide con los
  alumnos.** Cronometrar a quien escribió el programa no responde la pregunta
  que un departamento se hace, que es cuánto tarda alguien que llega nuevo.
  Una cifra con n = 1 y operador experto sería un límite inferior sin
  comparación posible, y presentarla invitaría a leerla como lo que no es. Va
  al estudio de pilotaje del curso 2026/27, con la cohorte, junto al resto de
  los datos de uso (§9.8).

  Queda dicho, para cuando se mida, **qué cuenta como montaje**: del sujeto sin
  nada encima a dos canales dando señal limpia — preparación de la piel, los
  dos pares de electrodos y la referencia, encender la placa, conectar y la
  comprobación de calidad. **Fuera el emparejamiento Bluetooth**, que es de una
  vez por ordenador y no de cada sesión. Y **fuera lo que dura el registro**,
  que no se cronometra porque ya se sabe: 10 s de calentamiento, 17,5 del
  primer músculo, 19,5 del segundo y 5 de preparación, unos 52 s hasta
  `REC start` más la tarea. Eso es una constante del programa —la secuencia la
  lleva él y no la persona—, sale del código y está en el §4, y sale idéntica
  para un docente y para un alumno.

> El índice de coactivación por maniobra y el porcentaje del extensor en la
> presa estaban aquí hasta que se midieron. Los da el §8.2.

---

## 9. Limitaciones conocidas y asuntos abiertos

1. **La amplitud del EMG baja al subir la carga** en los dos registros de
   cinemática disponibles (§8.3), que es lo contrario de lo esperable por
   reclutamiento. La velocidad y la potencia sí salen como deben. Es cuestión
   de la maniobra o del montaje, no del cálculo, y está sin resolver.
2. **`coact_floor_pct = 5 % CVM` está medido sobre un solo registro**:
   ventana quieta con medias de 0,2 % y 0,8 % sobre reposo frente a 19–30 %
   en ventana activa. El umbral cae en un hueco de un factor treinta, pero con
   un solo registro detrás. **Y el registro de las tres maniobras enseña su
   otra cara**: en un movimiento recíproco limpio el antagonista queda por
   debajo del suelo y la ventana se queda sin índice (§8.2). Es coherente
   —sin antagonista no hay coactivación que medir— pero significa que el caso
   más favorable del punto de vista fisiológico es el que no da número.
3. **El índice se mide sobre el registro sin recortar, no sobre el afinado.**
   Concatenar los fragmentos cambia las medias y con ellas el índice, hasta el
   punto de invertir qué ventana tiene número (§8.2, aviso 1). Desde la 3.1.1
   la pestaña lee así los fragmentos con nombre; el EDF afinado sigue siendo
   una concatenación y da otras cifras. Queda una elección que la interfaz no
   guía: una fila por contracción no es una fila por maniobra (§8.2).
   **Y el índice depende de cómo se defina el reposo.** La aplicación usa una
   sola definición, el percentil 10 de la fase de registro (apartado 5.6);
   con otras razonables —el archivo entero, el percentil 10 de la pausa de
   preparación, la media de su último segundo— la flexión va de 27,3 a 29,4 %
   y la presa de 74,6 a 76,7 %.
4. **El índice depende del borde solo por la actividad que deja fuera.** Desde
   la 3.1.1 el reposo que entra en la ventana no lo mueve (§8.2, aviso 2); la
   actividad que se queda fuera sí, y las medias dependen de la duración de la
   ventana. No hay una regla escrita de dónde empieza y acaba una maniobra más
   allá de «de la primera activación a la última relajación».
5. **La discrepancia entre la referencia anotada y la recalculada** es
   esperada y está documentada, pero no está cuantificada sobre una serie de
   registros: se sabe que es de unidades de por ciento.
6. **macOS no se prueba de forma automática** y no se ha usado con hardware.
7. **La práctica de cinemática se ha validado con un solo sujeto** y en cuatro
   registros.
8. **Este informe no contiene datos de alumnos.** Todo lo que da sale de
   registros de banco de un solo sujeto.
9. Del §13 de la especificación sigue vigente el aviso de que **este era el
   último cambio de arquitectura antes de la publicación**. La 3.1.0 lo
   respeta: cambia el manejo en el puesto y no el formato del archivo ni los
   cálculos (apartado 1.2). La 3.1.1 cambia una sola medida, la coactivación
   con fragmentos elegidos (apartado 1.1). El artículo describe la 3.1.1, y lo
   que venga después irá a versiones posteriores sin cambiar lo que describe.
10. **La k = 4,4 del par es empírica**: es el valor que dio una fila por
    maniobra en los registros en que se probó. Con otra piel, otro montaje u
    otra forma de hacer las maniobras puede proponer de más o de menos; por
    eso el editor cuenta las marcadas frente a las esperadas y deja mover la
    sensibilidad, y por eso la k usada va al informe y al CSV.
11. **La fatiga sigue calculándose sobre los fragmentos concatenados**, y el
    filtrado corre después de concatenar: en los segmentos de 1 s que cruzan
    una unión la MDF sale unos 1,4 Hz más alta que en sus vecinos (143,3 frente
    a 141,9 Hz en el registro de las tres maniobras, con las filas del editor).
    Ningún veredicto de los registros de ejemplo cambia por ello, y la práctica
    de fatiga es una contracción mantenida, sin uniones. El arreglo —filtrar el
    registro entero y concatenar después la señal ya filtrada— queda para una
    versión posterior.

---

## 10. Documentación

- **`docs/guion_practicas_es.md` y `docs/manual_emgteach_es.md` describen la
  versión actual.** Al preparar este informe quedaban cinco frases que aún
  contaban seis esfuerzos de calibración, en esos dos archivos y en sus
  equivalentes en inglés (`docs/lab_practicals.md`, `docs/manual_emgteach.md`);
  están corregidas. No queda ninguna otra discrepancia detectada. Para la
  3.1.0, los manuales, los guiones y las chuletas describen el editor de
  fragmentos en sus tres pasos, y ninguna guía habla ya de esfuerzos de
  calibración mantenidos de cuatro segundos.
- **Las especificaciones están ahora en `docs/`**: `ESPEC-sesion-en-dos-fases.md`,
  `ENMIENDAS-ESPEC-sesion-en-dos-fases.md`, `ESPEC-indice-coactivacion.md`,
  `ESPEC-niveles-y-avisos-emgteach.md` y `ESPEC-panel9-en-CVM.md`. Antes vivían
  solo en la carpeta del artículo.
- **El README no menciona ninguna ruta sintética.** Dice la versión correcta
  (3.1.1) y el número correcto de pruebas (1074, las mismas que en la
  etiqueta). No es
  cuestión de disciplina: `tests/test_readme.py::test_the_test_count_is_current`
  cuenta las pruebas recogidas y falla si el README dice otra cosa.
- **El material del artículo se genera aparte del del informe**, en
  `docs/articulo-advances/`, con `tools/informe_material.py --articulo` y
  `tools/figura6.py`. Va en inglés, con la ventana a 1150 px —a 1920 el texto
  de la interfaz cae por debajo de 3 puntos al ancho de página de la revista— y
  conducido desde una ruta neutra, de modo que ninguna captura ni la cabecera
  del CSV enseñan una ruta de usuario. El detalle, en el README de esa carpeta.
  **Ese material se generó con la 3.0.0.** Regenerado con la 3.1.0 y comparado
  píxel a píxel, los recortes que usa el artículo y la figura 6 salen
  idénticos; la 3.1.1 no toca la interfaz, y la figura 6 rehecha con ella
  también sale idéntica. Solo difieren las capturas de ventana entera (el
  botón de captura, el tamaño de «Calibrar CVM», el editor de fragmentos),
  que el artículo no usa.
- Los dos documentos docentes en Word (Guía del docente v2.3 y Cuaderno de
  prácticas v2.3) están al día con sus PDF, con las capturas rehechas contra
  la 3.0.0. No están en el repositorio; las capturas que enseñen el editor
  de fragmentos habrá que rehacerlas para la 3.1.0.

---

## Material adjunto

En `docs/informe-sourcebook/`:

| Archivo | Qué es |
|---|---|
| `ejemplo_par_FCR_ECR.edf` | el registro del apartado 8.1 |
| `ejemplo_informe.pdf` | el informe que genera la aplicación con ese registro |
| `ejemplo_analisis.csv` | la exportación CSV del mismo análisis |
| `captura_adquisicion.png` | pestaña de Adquisición con ese registro en revisión |
| `captura_analisis.png` | pestaña de Análisis con ese registro analizado |
| `captura_normalizacion.png` | pestaña de Normalización CVM con ese registro |
| `ejemplo_tres_maniobras.edf` | el registro del apartado 8.2 |
| `ejemplo_tres_maniobras_tuned.edf` | su versión afinada, con los trece fragmentos con nombre |

Los seis primeros se regeneran con `python tools/informe_material.py`, que en
esta actualización se ha ejecutado con la 3.1.0; los dos últimos son los
registros del apartado 8.2 tal como se grabaron y se afinaron.
