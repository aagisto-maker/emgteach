# emgteach — informe de estado para el artículo del Sourcebook

Escrito el 5 de septiembre de 2026 sobre `main`, después de publicar la versión
3.0.0, y actualizado a la **3.1.0**, a la **3.1.1** y a la **3.1.2** tras publicarlas, el 13 de
septiembre, y a la **3.2.0**, a la **3.3.0** y a la **3.4.0** el 14 de septiembre, y a la
**3.5.0** el 18 de septiembre, a la **3.6.0** el 19 y a la **3.7.0** el 26.
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
| **Versión que describe el artículo** | `v3.7.0`, publicada el 26 de septiembre de 2026 |
| DOI de esa versión | 10.5281/zenodo.22976106 |
| DOI de concepto | 10.5281/zenodo.21002297 |
| Commit de la etiqueta | `34294b4` |
| Pruebas en la etiqueta | **1376 recogidas, 1375 pasan y 1 se salta** |
| Versiones anteriores | `v3.6.0` (10.5281/zenodo.22842108, etiqueta en `6ab25d8`, 1217 pruebas) · `v3.5.0` (10.5281/zenodo.22832544, etiqueta en `826c920`, 1205 pruebas) · `v3.4.0` (10.5281/zenodo.22756263, `b7a9183`, 1121 pruebas) · `v3.3.0` (10.5281/zenodo.22750425, `85d6875`, 1093 pruebas) · `v3.2.0` (10.5281/zenodo.22744748, `b5ad8b7`, 1081 pruebas) · `v3.1.2` (10.5281/zenodo.22736393, `8367f1f`, 1078 pruebas) · `v3.1.1` (10.5281/zenodo.22734612, `aeb580d`, 1074 pruebas) · `v3.1.0` (10.5281/zenodo.22733151, `927eeff`, 1064 pruebas) · `v3.0.0` (10.5281/zenodo.22365602, `155fb07`, 940 pruebas) |
| Análisis estático | `ruff check .` limpio |

Los bloques generados de este informe (apartados 4, 6 y 5.1, y el recorrido
guiado) se leen del **código de `main` en el momento de generarlos**. En esta
actualización `main` coincide con la etiqueta `v3.7.0` en todo `src/`: lo único
que va detrás de la etiqueta es el DOI de versión de `CITATION.cff`, este
informe y el material regenerado. Así que lo que dicen los bloques es lo que
hace la versión publicada. Lo que cambió de la 3.6.0 a la 3.7.0 está en el
apartado 1.0, de la 3.5.0 a la 3.6.0 en el 1.1, de la 3.4.0 a la 3.5.0 en el
1.2, de la 3.3.0 a la 3.4.0 en el 1.3, de la 3.2.0 a la 3.3.0 en el 1.4, de la
3.1.2 a la 3.2.0 en el 1.5, de la 3.1.1 a la 3.1.2 en el 1.6, de la 3.1.0 a la
3.1.1 en el 1.7, y de la 3.0.0 a la 3.1.0 en el 1.8.

La prueba que se salta es `tests/test_gui_mvc_overlay.py:163`: con la
tipografía de la plataforma de prueba el mensaje mide menos que el suelo del
propio panel, así que no puede provocar el crecimiento que esa prueba vigila.

La versión etiquetada para el depósito es **3.7.0**, y es la que describe el
artículo. **Su publicación de GitHub lleva el ejecutable de Windows**,
`emgteach-v3.7.0-windows-x64.exe`, compilado por GitHub Actions desde la
etiqueta, con atestación de procedencia y su SHA-256 en las notas (apartado
1.12). No está firmado. Hasta la 3.6.0 las publicaciones llevaban solo el
código fuente; la regla se mantenía hasta tener una versión estable, y esa es la
3.7.0. El registro de Zenodo archiva el código fuente de la etiqueta, no el
ejecutable.

### 1.0 De la 3.6.0 a la 3.7.0

La versión del artículo y la de las prácticas de noviembre (PR #70 a #101). Se ensayó de punta a
punta con la placa simulada y se comprobó en el banco con el BITalino antes de etiquetarla
(registros COMPROB05b y COMPROB06b, 26 de septiembre). **Para un conjunto dado de fragmentos el
análisis calcula lo mismo que la 3.6.0.** Cambia el conjunto que propone el editor, y una
contracción que ninguna marca de carga anunció ya no toma prestada una.

**La sesión guiada sigue hasta la tarea.** Terminaba al medir la referencia. Ahora la guían cuatro
cuadros —calentamiento, calibración, maniobras libres y presa—, y cada uno lleva una fila de
casillas que es el mapa de su fase, en el color del músculo en las trazas.

- La primera cuenta atrás de cada músculo dura 7 s (`MVC_READY_PRIMERA_S`) y enseña el pictograma
  del gesto; las demás, 3 s.
- Una maniobra libre cuenta cuando el músculo pasa del 10 % de su propia CVM durante 0.30 s
  (`MANIOBRA_MINIMO_PCT`, `MANIOBRA_MINIMA_S`). La fase pasa sola cuando se han contado seis y el
  músculo lleva un segundo en reposo, o tras 12 s sin contar nada nuevo
  (`MANIOBRA_SIN_NOVEDAD_S`). «Hecho — siguiente» queda como salida, no como obligación.
- La presa es **una** de 8 s (`COACT_HOLD_S`), **apretando una pelota**, con las dos barras de carga
  dentro de su propio cuadro. Con el puño cerrado en vacío, el extensor se quedó en el 4 % de su
  referencia en el banco y la presa no dio índice.
- En cinemática, el estudio fuerza-velocidad lleva el mismo mapa en dos filas: la carga en curso y
  el experimento entero.
- El cuadro es opaco y se redimensiona al recibir su mapa.

**El editor de fragmentos.**

- Cada fila propuesta va desde que la envolvente deja el reposo hasta que vuelve a él, con 0.05 s de
  margen y sin pisar la vecina. El reposo es la línea que pondría la mitad de la sensibilidad, y se
  dibuja de puntos. En el banco, las filas del par empiezan 0.06–0.17 s antes y acaban hasta 0.36 s
  después que las del detector, y la coactivación de las tres ventanas sale como salía
  ampliándolas a mano.
- En cinemática propone **una fila por levantamiento marcado**. Cada marca de carga da su carga a
  la contracción que anunció (`force_velocity.marker_owners`), en el editor, en el análisis y en el
  registro afinado. Lo que el asistente no pidió queda como candidato punteado, y el estudio lo
  empieza desmarcado.

**La práctica.**

- El par se elige (antebrazo, brazo u otro par) y va a la cabecera EDF.
- Una sola referencia, en el olécranon, y los dos pares a 5 cm del epicóndilo de su lado.
- La figura de colocación es la del artículo.

**La conexión.**

- El estado dice «conectando con la placa…» hasta el primer bloque.
- A los 20 s sin datos (`CONEXION_MAX_S`) la grabación se detiene y un aviso ofrece reintentar, sin
  congelar la ventana mientras Windows suelta el puerto Bluetooth.
- Un «Detener» pulsado durante la apertura ya no se pierde.

**El material adjunto** se regeneró en la etiqueta y **no cambia ninguna cifra**. Cambian las
capturas enteras de las figuras 3a y 3b y la de adquisición: el selector del par, los ejes en
segundos y «Screenshot ▾» donde antes estaban «Screenshot» y «Auto». En las demás capturas
completas solo cambia esa franja de la barra, y los recortes de las figuras 4 y 7 salen idénticos.
En el ejemplo de CSV y de PDF solo cambian la versión, el pie y la línea «Protocol», que ahora se
lee en el idioma del lector.

### 1.1 De la 3.5.0 a la 3.6.0

Una versión menor con una sola cosa dentro (PR #67): **la placa simulada obedece a la
calibración**. Ningún cálculo cambia y ningún registro hecho con la placa se lee distinto; lo
que cambia es lo que enseña un ensayo sin hardware.

**Qué pasaba.** El sujeto sintético repite un ciclo fijo de 12 s que arranca al conectar
—flexión del primer músculo, extensión del segundo, presa con los dos— y **nunca llega a la
activación plena**: 0.50, 0.50 y 0.40 del máximo de cada músculo. No leía nada de la
aplicación, así que la ventana de calibración caía donde estuviera el ciclo: en reposo la
mitad del tiempo, o en un flanco, que pasa sin el aviso de «calibración débil» y deja una
referencia a medio camino. La tarea leía entonces **por encima del 100 % de la CVM**, y una
práctica ensayada sin placa enseñaba lo contrario de lo que la práctica quiere enseñar.

**Qué se hizo.** El asistente ya sabe cuándo pide un máximo, porque abre un tramo `CAL` y lo
cierra; ahora se lo dice también al dispositivo. `AcquisitionDevice.instruct(channel_index,
level)` no hace nada por omisión —una placa no manda sobre lo que hace la persona conectada a
ella— y no es abstracto, para que ningún otro backend tenga que escribir un método vacío.
`BitalinoDevice` lo reenvía al puerto solo cuando la dirección es la simulada. Mientras se
pide un esfuerzo a un músculo, el sujeto lo da entero y el otro descansa —que es el gesto que
pide la instrucción—, y nada toca el reloj, de modo que el ciclo sigue donde iba cuando se
deja de pedir.

**Qué da ahora un ensayo**, medido sobre la envolvente de la propia aplicación:

| | primer músculo | segundo músculo |
|---|---|---|
| referencia, como fracción del máximo de ese músculo | 0.67 | 0.69 |
| máximo de la tarea, en % CVM | 53 % | 54 % |

La referencia no es la desviación típica del músculo porque la envolvente de una señal
gaussiana vale menos que ella (rectificada da σ·√(2/π), y el paso-bajo la suaviza más). Lo que
importa es que la tarea lee alrededor de la mitad que pide el ciclo, con holgura, en lugar de
más que el máximo. Y el **índice de coactivación de la presa simulada sale 81 %**, frente al
20 % de la flexión y el 33 % de la extensión: la forma de las cifras de banco de esta práctica
(apartado 8.2), que es lo que un ensayo debería enseñar.

**Lo demás de la versión** no toca la aplicación: dos pruebas que esperaban por reloj a que
otro hilo hiciera algo —y fallaban en los runners cargados con un índice fuera de rango que
parecía un worker roto— esperan ahora al suceso, y la descripción del depósito en Zenodo deja
de ofrecer un perfil de ECG entre las características, que no es seleccionable en ninguna
versión publicada.

**El material adjunto** se regeneró con la 3.6.0 y **no cambia ninguna cifra ni ninguna
captura**: esta versión no toca ni un texto de pantalla. Solo se mueven el pie del PDF de
ejemplo y la línea de versión del CSV.

### 1.2 De la 3.4.0 a la 3.5.0

Una versión menor (PR #45 a #62). Añade lo que una práctica necesita alrededor
de la medida y repara los dos documentos que se lleva el alumnado. **Las
definiciones no cambian**: la referencia de CVM, el % CVM, el índice de
coactivación y su suelo, la tabla de contracciones, el máximo de la tarea y el
análisis de fatiga son los de la 3.4.0. Cambian tres cosas que mueven números,
y las tres son faltas que se reparan; van al final del apartado.

- **Una placa BITalino simulada por la propia aplicación.** Escribir `simulada`
  (o `simulated`) como dirección conecta una placa que simula la aplicación,
  sin Bluetooth: habla su protocolo byte a byte —la respuesta de versión, los
  comandos de frecuencia y de arranque, las tramas con su número de secuencia y
  su CRC—, de modo que el decodificador, la adquisición, la calibración, el
  registro y la difusión al aula funcionan igual que con la placa. La señal es
  sintética (un ciclo de 12 s de reposo, flexión, extensión y presa, con un
  acelerómetro que sigue al primer músculo) y el aparato se llama «BITalino
  (simulated)». Una práctica se puede preparar, ensayar y dar donde no hay
  placa.
- **La dirección del puesto, en un archivo de texto.** Un `bitalino.txt` junto a
  la aplicación fija la dirección de ese ordenador: la pestaña de adquisición
  arranca con ella, lo dice en el registro y «Por omisión» vuelve a ella.
  Escrita en el campo, había que volver a escribirla dondequiera que los ajustes
  no sobrevivieran —otra cuenta, un PC reinstalado, la aplicación copiada en un
  lápiz—; el archivo viaja con la aplicación.
- **Un diagnóstico de conexión**, `diagnostico_bitalino.exe`, que contesta por
  orden: qué dirección prueba y de dónde sale; si Windows ve un adaptador
  Bluetooth que funcione; si hay una placa emparejada y en qué puerto COM; si
  contesta al saludo y en cuánto; y diez segundos de adquisición —tramas,
  frecuencia, fallos de CRC y si cada canal trae señal—. Se conecta como la
  pestaña de adquisición, así que un puesto que pasa aquí conecta en la
  aplicación; con `simulada` se comprueba a sí mismo, sin placa.
- **El registro de eventos de cada grabación se guarda a su lado**, en
  `<nombre>.eventos.txt`, también cuando la grabación acaba mal, que es cuando
  hace falta. Y **una grabación que no se cerró se puede recuperar**: cada marca
  se refleja, según se hace, en `<nombre>.marcas.txt`, y
  `python -m emgteach.recovery <archivo>.edf` escribe `<archivo>_recuperado.edf`
  con la señal que hay en disco y las marcas de ese archivo de al lado. El
  original no se toca.
- **El informe y el CSV, reparados.** La tabla de contracciones —siete columnas,
  55 cm sobre un marco de 17— perdía Músculo, RMS, Pico y MDF por el borde
  derecho del papel: todas las tablas se construían con dos anchos de columna y
  reportlab repite el último para las que no tienen. Una tabla partida entre
  páginas repite ahora su cabecera. El informe imprime las medidas de los **dos**
  músculos y nombra los dos canales; el dispositivo, el protocolo y la
  procedencia del archivo llegan a los dos informes, y el identificador que
  imprime es el del archivo, o ninguno. El CSV lleva el nombre del archivo —no la
  ruta completa, que traía el nombre de usuario de Windows—, la versión, la
  referencia con su procedencia, los dos músculos, y las contracciones y las
  ventanas de coactivación detrás de la tabla por segmento (apartado 5.5).
- **Una sola marca decimal, el punto, en los dos idiomas.** Había tres a la vez:
  los números formateados a mano escribían 1.5; el puñado que pasaba por el
  ayudante de la interfaz escribía 1.5 en español; y los campos numéricos seguían
  al sistema operativo, de modo que en un Windows español escribían 1.5 y
  **rechazaban** el 1.5 que imprimía el rótulo de al lado. Los campos escriben
  ahora el punto y aceptan la coma tecleada, que es la que envía el teclado
  numérico español. La excepción, a propósito, es la exportación CSV, cuyo
  dialecto es el de la hoja de cálculo (apartado 5.5).
- **La sesión guiada dice la regla antes que el ejemplo.** Las instrucciones de
  calibración empiezan por «una sacudida breve y explosiva, a la máxima potencia,
  del movimiento que hace este músculo» y nombran el antebrazo detrás, como
  ejemplo del guion; el aviso de electrodos pide apoyar «el miembro». Y **los
  límites por defecto declaran dónde se midieron** —el par del antebrazo, FCR y
  ECR— en `profiles.py`, en la ayuda del índice de coactivación y en los dos
  manuales. El guion documenta un **segundo par**, bíceps y tríceps, con su
  gesto de referencia, una cocontracción en lugar de la presa y los tres avisos
  que conviene comprobar con un registro de prueba.
- **En español el aparato es «la placa BITalino»** —es una tarjeta— y la
  interfaz trata de usted de principio a fin.
- **El móvil solo se descarga el informe.** La página de seguimiento ofrecía
  además un CSV de la sesión que escribía el propio navegador y el CSV de
  resultados: un CSV en un teléfono es un archivo que el alumnado no abre, y si
  lo abre no sabe qué mirar.
- **Las capturas automáticas paran a las 60 por grabación** (tres minutos a una
  cada 3 s), y los niveles de Jonsson en vivo se leen de un histograma, de modo
  que cuestan lo mismo con cualquier duración de registro.
- **`import emgteach` no carga nada hasta que se le pide**, que es lo que
  permite construir el diagnóstico sin scipy: 23 MB en lugar de 61. Los dos
  ejecutables se construyen con las versiones fijadas en
  `packaging/requirements-exe.txt` y se autoprueban en el flujo de trabajo.

**Lo único que mueve números**, y los tres son arreglos:

1. **El detector de inicios toma su reposo al principio de la fase de
   registro**, no del primer segundo del flujo. En una sesión guiada ese segundo
   es el principio del calentamiento —contracciones, no reposo—, así que el
   umbral salía inflado y se perdían contracciones débiles. Una sesión guiada
   reanalizada con la 3.5.0 puede marcar contracciones que la anterior no
   marcaba.
2. **Los P10/P50/P90 en vivo cuentan desde la fase de registro**, no desde el
   final de la calibración: los segundos de reposo de la cuenta atrás entraban en
   la distribución de la tarea y bajaban los tres niveles. El análisis de Jonsson
   desconectado no cambia.
3. **Una referencia de CVM por debajo de 1e-4 mV se leía mal** (`5e-05` se leía
   como `5`), así que un archivo escrito con una se normaliza ahora contra la
   referencia que llevaba.

**Ninguna de las tres toca las cifras del apartado 8**, y se ha comprobado con
la 3.5.0, no supuesto: el CSV y el informe de ejemplo regenerados traen
exactamente los mismos números que con la 3.4.0 —solo cambian el pie y la línea
de versión—; la prueba que fija los índices de las tres maniobras sobre el
registro sin recortar sigue pasando; y el registro de cinemática vuelve a dar
178.0 s, referencia 0.2923 mV recalculada de los tramos `CAL`, doce
contracciones, retraso electromecánico mediano de 42 ms y máximo de la tarea del
123 % CVM.

### 1.3 De la 3.3.0 a la 3.4.0

Una versión menor (PR #39 a #43): cambia lo que enseña la pestaña de análisis
y cómo numera sus paneles. Ningún cálculo cambia.

- **Los dos trazos en bruto del par van en un solo panel, el 1**, cada músculo
  contra su propio eje vertical, pintado del color de su traza y con su nombre,
  como la EMG y el acelerómetro en los paneles 10 y 12. Dos músculos en
  milivoltios sobre un mismo eje invitan a comparar alturas que la EMG de
  superficie no permite comparar; con un eje cada uno, el panel enseña cuándo
  dispara cada músculo. Los dos ejes son simétricos respecto al cero, así que
  los dos ceros quedan a la misma altura, y ▲▼ escala los dos. Desaparece el
  1B. Con un solo músculo, el panel es el de antes.
- **El panel 2 no se ofrece en la práctica del par**, ni bajo «Más paneles…» ni
  en el cuadro de gráficas del informe: normaliza cada envolvente por su máximo
  dentro de la ventana, y el 9 enseña el mismo curso temporal en % CVM, que es
  la vara de la práctica. En las demás prácticas sigue igual.
- **El panel 6 dibuja los dos músculos en el par**, cada uno contra su eje,
  como el 1: el RMS va en milivoltios.
- **El panel 8 es un recorrido en el tiempo**: une en orden temporal, con una
  punta de flecha al final, las ventanas en que el músculo elegido se
  contraía —las mismas sobre las que se ajusta la tendencia de fatiga, porque
  la frecuencia mediana de una ventana en reposo es la del amplificador—, con
  los puntos oscureciéndose según avanza el tiempo. La fatiga mueve el
  recorrido arriba y a la izquierda: más amplitud, menos frecuencia. Ya no se
  dibuja el ajuste de grado 2, que se leía como la tendencia temporal del 7 y
  no lo es; se sigue calculando. Enseña solo el músculo elegido: dos
  recorridos sobre un mismo eje en milivoltios serían una maraña. En una tarea
  de contracciones breves y separadas el recorrido zigzaguea, porque las
  ventanas alternan entre esfuerzos; en una contracción sostenida se lee
  limpio. Sigue fuera del conjunto propio de todas las prácticas.
- **Cada título dice su lectura**, en una segunda línea —el del 7, «un
  descenso indica fatiga muscular», era el modelo—, y el de un panel de un
  solo músculo lo nombra. Las lecturas, literales, están en la tabla del
  apartado 5.1.
- **Cambiar de músculo en «Canal EMG» vuelve a analizar al momento.** Antes el
  análisis quedaba pendiente y los paneles seguían enseñando el músculo
  anterior hasta pulsar Analizar, sin que ninguno dijera de quién era.
- **«Más paneles…» tiene el estilo de los botones de modo** (texto y borde
  azules sobre blanco, blanco sobre azul al marcarse), en vez del texto pálido
  de un botón sin color propio; abierto, dice «Menos paneles».
- **Una sola tabla, `emgteach.panels`,** da el número, los nombres, las
  lecturas y el tooltip de cada panel, y de ella salen los títulos (en
  pantalla y en el informe PDF), las casillas, el cuadro de gráficas del
  informe y el «P#» de la barra derecha. Ningún número va escrito a mano en
  otro sitio. La etiqueta y el tooltip del panel 12 no tenían entrada en el
  catálogo y salían en inglés en la interfaz en español; ya la tienen, y una
  prueba vigila que la tenga todo lo de la tabla.
- Los colores de los dos músculos se importan de `charts.py` en todo lo que
  dibuja, de modo que un eje y su traza no pueden discrepar.

La numeración final, la misma en todas las prácticas; la que no ofrece un
panel deja su número sin usar en vez de renumerar el resto. **Los paneles 5 y
9 conservan su número.**

| Nº | Panel | Abre con |
|---|---|---|
| 1 | Señal en bruto (en el par, los dos músculos, un eje cada uno) | las tres prácticas |
| 2 | Envolvente normalizada | un músculo y cinemática; nunca en el par |
| 3 | PSD con MNF/MDF | las tres prácticas |
| 4 | Filtrada + rectificada | «Más paneles…» |
| 5 | Envolvente vs RMS (la curva «RMS envelope») | «Más paneles…» |
| 6 | RMS por ventana | «Más paneles…» |
| 7 | MDF vs tiempo (fatiga) | par; en las demás, «Más paneles…» |
| 8 | RMS vs MDF (recorrido en el tiempo) | «Más paneles…» |
| 9 | Envolventes superpuestas (agonista/antagonista) | par |
| 10 | EMG vs MMG | cinemática |
| 11 | Temblor | cinemática |
| 12 | Movimiento vs EMG | cinemática |

**Lo que el §5 del artículo cita no cambia con la 3.4.0, y está medido, no
deducido**: las referencias y los máximos de tarea de las tres maniobras y del
par, la tabla A, las trece filas, el registro afinado y el de cinemática se han
vuelto a calcular sobre la etiqueta `v3.4.0` con el mismo script que sobre la
`v3.2.0` y la `v3.3.0`, y la salida es idéntica línea a línea a la de la 3.3.0.
Los paneles dibujan lo que calcula el análisis; ninguno calcula nada. Donde sí
cambian las figuras del artículo es en las capturas de la pestaña de análisis
(apartado 10).

### 1.4 De la 3.2.0 a la 3.3.0

Una versión menor (PR #35 a #37): una cifra que enseña el programa puede
cambiar, y un panel se dibuja de otra manera. Ningún otro cálculo cambia.

- **El máximo de la tarea se lee sobre la fase de registro entera**: del
  `REC start` al final del archivo —el archivo entero si el registro no tiene
  fases—, se elijan los fragmentos o la ventana que se elijan. Es un máximo de
  la fase, no de la selección. Hasta la 3.2.0 se leía sobre el tramo
  analizado, que con fragmentos elegidos es su concatenación: ahí, dos
  fragmentos cortados dentro de la contracción y pegados uno a otro subían la
  envolvente por encima del pico real (5.3 puntos en el registro de ejemplo),
  y una activación fuera de los fragmentos no se veía. Comprobado sobre el
  banco con la 3.2.0, aceptando en el editor lo que propone: en 28 registros
  de dos fases, la ficha coincide por las dos vías a menos de 0.05 puntos en
  18; difiere hasta 0.35 puntos en 7, que es lo que cuesta filtrar la
  concatenación en vez de la fase; y en 3 el máximo de la fase cae en una
  activación que la propuesta del editor dejó fuera, y sube entre 2 y 11
  puntos. En el registro de ejemplo, 68.4 y 41.2 % por las dos vías. El «?» de
  la ficha y el del resumen dicen dónde se lee; `task_peak_span_s`, en el
  resultado, da los segundos del archivo.
- **El panel 3 (PSD) dibuja cada espectro escalado a área 1.** La PSD va con
  el cuadrado de la amplitud, así que en mV²/Hz la altura de un músculo frente
  al otro comparaba la piel y la colocación de los electrodos —lo que los
  paneles en % CVM existen para no comparar— y el músculo que menos se
  contrae quedaba pegado al eje. Cada curva es ahora una densidad, con su
  área sombreada y la línea de la MDF partiéndola en dos mitades iguales, en
  los dos músculos por igual; el eje dice «densidad espectral relativa (área
  1)»; la leyenda lleva la MDF de cada músculo y su potencia total en mV²; y
  un músculo cuya potencia quede por debajo del 2 % de la del otro se dibuja
  atenuado y su leyenda pregunta si es ruido. MDF y MNF son invariantes al
  escalado: no cambia ningún número. Pantalla e informe PDF dibujan el panel
  desde una sola función (`emgteach.figures.draw_psd_panel`).

**Lo que el §5 del artículo cita no cambia con la 3.3.0**: las referencias,
los máximos de tarea, la tabla A, la figura 6, «lo que no hay que hacer», la
sensibilidad y el borde son los de la tabla del apartado 1.4, medidos sobre la
etiqueta `v3.2.0` y comprobados sobre la `v3.3.0`. Ninguna figura del artículo
enseña el panel 3.

### 1.5 De la 3.1.2 a la 3.2.0

Una versión menor, no un parche, porque cambia los números que el programa
produce para la misma señal (PR #29 a #32). **Un registro reanalizado con la
3.2.0 da porcentajes de CVM distintos de los de la 3.1.2.**

- **La referencia de CVM es el pico de la envolvente.** Cada repetición de
  calibración vale el punto más alto que alcanza su envolvente, no el máximo
  de su media móvil de 0.2 s; la referencia sigue siendo la mejor de las
  repeticiones conservadas. La CVM es el extremo de la escala, la mayor
  contracción que cabe esperar del músculo, así que lo que la representa es
  un máximo y no la media de un tramo que incluye la subida y la bajada del
  pico. Lo que impide que una muestra de ruido la fije es el propio paso bajo
  de 5 Hz de la envolvente, que deja una espiga de una muestra, a 1000 Hz, en
  1/90 de su altura. Todo lo que se juzga contra la referencia se mide igual:
  el máximo de la tarea, el pico de cada contracción, los valores por
  repetición y el cruce entre canales, y la referencia de las barras en vivo.
  En el banco —80 canales de 46 registros con la sesión en dos fases— el pico
  es 1.16 veces la media móvil (mediana 1.14; de 1.02 a 1.50), y el máximo de
  tarea se mueve +3 puntos de media (mediana +1.5; de −37 a +78), porque el
  mismo estadístico se aplica a los dos lados del cociente. Los 19 canales
  que con la media móvil tenían un máximo de tarea entre el 90 y el 125 % lo
  tienen entre el 91 y el 125 % con el pico; los 12 que pasaban del 150 % van
  del 141 al 537 %; cuatro canales cruzan la línea del 150 %, tres hacia
  arriba (139 → 158, 142 → 164 y 135 → 159) y uno hacia abajo (178 → 141).
  El umbral del 150 % no se toca.
- **El suelo del índice de coactivación es el 4.5 % CVM** (apartados 5.6 y
  9, punto 2): el mismo nivel de activación sobre el reposo que el 5 % de la
  referencia de 0.2 s, expresado sobre la referencia de pico.
- **La MDF de cada segmento del análisis de fatiga se calcula en la banda de
  análisis** (20–450 Hz), como la del resumen y la de cada contracción;
  tomaba la mediana de todo el espectro. En los registros de ejemplo la MDF
  de un segmento activo se mueve 0.4 Hz de media, sin dirección fija; de 52
  tramos, un veredicto cambia, de «no concluyente» a «sin fatiga», por un R²
  que pasa de 0.295 a 0.301 con el umbral en 0.30. Un veredicto que se decide
  en el tercer decimal no es un veredicto: ese caso no se cita como ejemplo
  de nada.
- **Las flexiones y las extensiones de la tarea del par son libres, sin
  resistencia** (documentación): si la muñeca empuja contra algo, el
  antagonista entra a estabilizarla y el patrón recíproco se emborrona.

**Qué cambia en las cifras del apartado 8**, medido con la 3.2.0 sobre la
etiqueta, antes → después:

| Cifra | 3.1.2 | 3.2.0 |
|---|---|---|
| Referencias de las tres maniobras (FCR / ECR) | 0.1468 / 0.3558 mV | 0.1870 / 0.4226 mV |
| Máximos de la tarea, tres maniobras | 73 / 41 % | 68 / 41 % |
| Máximos durante la presa (fila de la tabla de contracciones) | flexor 64, extensor 29 % | flexor 58, extensor 28 % |
| Tabla A: flexión | 28.3 %; 14.1 / 5.8 | 29.4 %; 11.1 / 4.9 |
| Tabla A: extensión | no se informa; 4.2 / 6.2 | no se informa; 3.3 / 5.2 |
| Tabla A: presa | 75.7 %; 14.5 / 9.1 | 78.6 %; 11.4 / 7.7 |
| Las trece filas del editor (flexión · extensión · presa) | 29.0 · 69.4 · 75.3 % | 30.4 · 66.8 · 78.1 % |
| El archivo afinado, abierto tal cual | — · 63.3 · 67.3 % | — · 60.6 · 70.2 % |
| Sensibilidad a la definición del reposo (apartado 9, punto 3) | flexión 27.3–29.4; presa 74.6–76.7 % | flexión 28.4–30.5; presa 77.6–79.5 % |
| Borde de la presa: 88.8–97.0 s / 88.0–98.0 s | 75.7 / 74.4 % | 78.6 / 77.2 % |
| Referencias del par (FCR / ECR) | 0.2175 / 0.1734 mV | 0.2705 / 0.1967 mV |
| Máximos de la tarea, el par | 125 / 93 % | 101 / 82 % |
| Coactivación del par, tramo entero | 30 %; 14.4 / 11.1 | 31 %; 11.5 / 9.8 |
| Cinemática: referencia y máximo de la tarea | 0.2544 mV recalculada (0.2705 en la anotación del archivo); 117 % | 0.2923 mV; 123 % |

Los máximos de tarea del par de la 3.1.2 eran el pico instantáneo de la
envolvente sobre una referencia de media móvil, los dos estadísticos
mezclados que la 3.2.0 deja de mezclar; los de las tres maniobras eran la
media móvil sobre la media móvil. Los umbrales (150 %, 5×) no cambian.

Comprobado sobre la etiqueta: la prueba de aceptación que fija las cifras del
registro de las tres maniobras (`tests/test_coactivation_sin_recortar.py`)
pasa con los valores nuevos, y el comando de la figura 6 da la figura
regenerada que hay en `docs/articulo-advances/` (apartado 10).

### 1.6 De la 3.1.1 a la 3.1.2

Un parche de lo que la calibración pide y de cómo se describe (PR #24 a #26).
No cambia ningún cálculo, umbral ni valor por defecto.

- **La calibración pide una sacudida breve y explosiva a la máxima potencia**,
  no un empuje sostenido contra algo fijo. En la práctica del par, el asistente
  dice el gesto de cada canal durante la cuenta atrás: flexión de muñeca
  cerrando el puño con toda la fuerza para el flexor, extensión de muñeca con
  la mano abierta y los dedos extendidos a tope para el extensor. Las otras dos
  prácticas, cuyo músculo puede ser el bíceps, dan la regla general. Lo mismo
  dicen los avisos de «no es un máximo», el panel de entrada de la pestaña
  CVM, las ayudas, la imagen del recorrido, la hoja de puesto y la
  documentación; los textos literales de los apartados 3 y 6 están regenerados.
- **La documentación describe la referencia como la calcula el código**: el
  máximo de la media móvil de 0.2 s de la envolvente, tal cual, sin restar
  reposo, y la mejor de las repeticiones. El manual decía que se restaba el
  reposo de la ventana.
- **Las publicaciones llevan solo el código fuente** (apartado 1.12).

Ninguna figura del artículo enseña los textos de la calibración, y las cifras
del apartado 8 no dependen de estos cambios. Comprobado sobre la etiqueta: la
prueba de aceptación que fija las cifras del registro de las tres maniobras
(`tests/test_coactivation_sin_recortar.py`) pasa, y el comando de la figura 6
da la misma figura, píxel a píxel.

### 1.7 De la 3.1.0 a la 3.1.1

Un parche de una sola medida (PR #21). **La coactivación de una ventana con
nombre se lee sobre la fase de registro sin recortar.** Hasta la 3.1.0, elegir
fragmentos en la pestaña de Análisis los concatenaba, y la tabla de
coactivación se leía sobre esa señal concatenada. El índice resta a cada
músculo su nivel de reposo, el percentil 10 de la señal analizada, y una señal
hecha solo de contracciones no tiene reposo: su percentil 10 era lo más callado
que estuvo cada músculo *mientras trabajaba*. Para el antagonista, su propia
parte en la maniobra del otro; restarla castigaba a la señal pequeña, que es la
que la práctica enseña. En el registro de ejemplo, la fila que el editor
propone para la presa daba 58 % con el extensor en 6.3 % CVM; ahora da 75 % y
10.9 %.

Ahora las envolventes de los dos músculos se calculan una vez sobre la fase de
registro sin recortar, cada fragmento con nombre es una máscara sobre ellas, y
el reposo es el percentil 10 de la fase entera (`coactivation_by_fragments`,
`src/emgteach/coactivation.py`). **Es la definición que la tabla ya usaba sin
fragmentos** (apartado 5.6): con ella, las dos vías restan el mismo cero.
`tools/figura6.py` lee sus `--ventana` con la misma función, así que la figura
y la pestaña no pueden discrepar.

**Qué cambia en las cifras.** La herramienta tomaba antes el reposo de cada
ventana de la propia ventana; con la definición común sus medias se mueven hasta
0.3 % CVM y sus índices hasta 0.7 puntos (apartado 8.2). Con otras definiciones
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

### 1.8 De la 3.0.0 a la 3.1.0

Son **39 commits** (29 sin contar las fusiones). La 3.1.0 no cambia el formato
del archivo ni los cálculos: los módulos que calculan (`coactivation.py`,
`phases.py`, `mvc.py`, `dsp.py`, `fatigue.py`, `contractions.py`,
`force_velocity.py`) son los de la 3.0.0 salvo en comentarios. Lo que cambia
es el manejo de la aplicación en el puesto de laboratorio, y **lo único que
puede mover resultados es la propuesta de filas del editor de fragmentos**:

- **La sensibilidad de detección se fija por práctica y forma parte del
  resultado.** En el par agonista/antagonista el editor de fragmentos abre en
  **k = 4.4**, el valor que da una fila por maniobra de la serie en los
  registros en que se probó; las otras dos prácticas siguen en 3.0. El
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
- **Capturas de pantalla** con F12 desde cualquier pestaña y, en la flechita
  del propio botón «Captura», una entrada que las hace solas, cada tres
  segundos y únicamente mientras se graba, con el nombre del registro al que
  pertenecen; el registro **se nombra con el
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

### 1.9 Lo que trajo la 3.0.0 (desde el commit `7234b02`)

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
- **La referencia se mide sobre el mejor 0.2 s** y la calibración pide **tres
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
  la excursión completa es ±1.635 mV, no ±1.65 mV. Nada expresado como
  cociente cambia.

### 1.10 Dependencias

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

### 1.11 Plataformas probadas

La integración continua ejecuta la suite en **Ubuntu y Windows**, con
**Python 3.10, 3.11 y 3.12**: seis combinaciones, todas en verde para
`v3.1.2`. macOS no se prueba de forma automática. El hardware se ha probado
solo en Windows 11.

### 1.12 Instalación y arranque

Desde el código fuente:

```
git clone https://github.com/aagisto-maker/emgteach.git
cd emgteach
pip install -e ".[dev]"
emgteach
```

Desde la 3.7.0, la publicación lleva el ejecutable de Windows,
`emgteach-v3.7.0-windows-x64.exe`:

- **De dónde sale.** Lo compila GitHub Actions desde la etiqueta
  (`.github/workflows/build-windows-exe.yml`), comprobando que dice la versión
  de la etiqueta.
- **Cómo se comprueba.** Lleva atestación de procedencia, que se verifica con
  `gh attestation verify emgteach-v3.7.0-windows-x64.exe --repo aagisto-maker/emgteach`.
  Su SHA-256 está en las notas de la publicación:
  `db49fac56028699c111285e175dde7094c70e6368cad27390652328e474f6975`.
- **Antivirus.** No está firmado. En VirusTotal, antes de publicar, lo
  marcaron 3 de 67 motores y Microsoft Defender no.

Quien prefiera compilarlo lo hace desde la etiqueta con
`packaging/emgteach.spec` (instrucciones en `packaging/README.md`). El ejecutable acepta `--selftest`,
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
| Calentamiento | `WARMUP start` | `src/emgteach/phases.py:132` | `0.10 s → WARMUP start` |
| Inicio de repetición | `CAL start ch={canal} rep={n}` | `src/emgteach/phases.py:116` | `14.50 s → CAL start ch=1 rep=1` |
| Fin de repetición | `CAL end ch={canal} rep={n}` | `src/emgteach/phases.py:121` | `16.10 s → CAL end ch=1 rep=1` |
| Referencia en caché | `MVC ref ch={canal} value={valor:.6g} mV` | `src/emgteach/mvc.py:264` | `30.40 s → MVC ref ch=1 value=0.270517 mV` |
| Pausa de preparación | `PREP start` | `src/emgteach/phases.py:137` | `30.40 s → PREP start` |
| Inicio del registro | `REC start` | `src/emgteach/phases.py:142` | `36.00 s → REC start` |
| Carga de fuerza-velocidad | `FV load={kg:g} kg` | `src/emgteach/force_velocity.py:54` | `48.20 s → FV load=2 kg` |
| Inicio automático | `{Inicio (auto)} — {músculo}` | `acquisition.py` | `1.62 s → Inicio (auto) — Músculo` |

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
   a `Status: connecting to the board…` / «Estado: conectando con la placa…»,
   y con el primer bloque de datos a `Status: recording…` / «Estado:
   grabando…». Si en 20 s no llega ninguno, la grabación se detiene, el estado
   dice `Status: the board did not answer` / «Estado: la placa no respondió» y
   un aviso ofrece volver a intentarlo.
4. `Calibrate MVC` / «Calibrar CVM», en la caja `Muscle load (live MVC)` /
   «Carga muscular (CVM en vivo)», lanza el asistente. Es un cuadro oscuro
   flotante sobre las gráficas, con esta secuencia por músculo: calentamiento
   de 10 s, y luego tres veces la pareja cuenta atrás (3 s; la primera de cada
   músculo, 7 s, con el pictograma del gesto) y esfuerzo (1.5 s), con 2 s de
   descanso. Los textos son `Warm up first` / «Caliente primero»,
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

Igual que la anterior salvo en estos puntos:

- Hay **dos campos de etiqueta**, uno por músculo, y dos carriles de señal,
  azul el canal 1 y rojo el canal 2, y un desplegable `Pair:` / «Par:» para el
  par de músculos.
- **La calibración es obligatoria y la lanza el propio botón de grabar**: no
  hay que acordarse de pulsar «Calibrar CVM». El flujo es calibración →
  preparación (5 s) → registro, sin detener la adquisición.
- El asistente calibra **primero un músculo y después el otro**.
- **La sesión guiada sigue hasta la tarea** (apartado 1.0): seis maniobras
  libres de cada músculo con su fila de casillas, que pasan solas, y una presa
  de 8 s apretando una pelota, con las barras de carga dentro del cuadro.
- El editor de fragmentos abre con **k = 4.4** en vez de 3.0, y espera
  **seis flexiones, seis extensiones y una presa**; lo esperado se puede
  cambiar si se repite una serie. Cada fila propuesta abarca la contracción
  entera, hasta la línea de puntos «reposo».
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

- **`src/emgteach/gui/tour.py:71`**
  - EN: Choose the practical first
  - ES: Elegir primero la práctica
  - EN: Everything else follows from this. Each mode records what that practical needs — one muscle, an agonist/antagonist pair, or a muscle plus the accelerometer — and the rest of the interface offers only the measurements that make sense for it. The coloured band beside it is the level: basic, intermediate or advanced.
  - ES: Todo lo demás sale de aquí. Cada modo registra lo que esa práctica necesita (un músculo, un par agonista/antagonista, o un músculo más el acelerómetro) y el resto de la interfaz ofrece solo las medidas que tienen sentido para ella. La banda de color de al lado es el nivel: básico, intermedio o avanzado.
- **`src/emgteach/gui/tour.py:115`**
  - EN: Connecting the sensor
  - ES: Conexión del sensor
- **`src/emgteach/gui/tour.py:128`**
  - EN: Recording
  - ES: Registro
  - EN: Press record. The session asks first for a maximal contraction — the reference every measurement is expressed against — and then for the task. Both go into one file, so nothing has to be matched up afterwards. Watch the live trace: at rest it should be a flat line with only baseline noise. A signal that never returns to baseline usually means a loose electrode, not a tonic muscle. Each contraction onset is marked on its own.
  - ES: Pulse grabar. La sesión pide primero una contracción máxima (la referencia respecto a la que se expresa cada medida) y después la tarea. Las dos van a un solo archivo, así que no hay que emparejar nada después. Observe el trazo en directo: en reposo debe ser una línea plana con solo el ruido basal. Una señal que nunca vuelve a la línea base suele ser un electrodo suelto, no un músculo tónico. El inicio de cada contracción se marca solo.
- **`src/emgteach/gui/tour.py:148`**
  - EN: How to place the accelerometer
  - ES: Cómo situar el acelerómetro
  - EN: There are two possibilities: on the muscle it allows the mechanomyogram (MMG) to be measured, which runs in parallel with the electrical signal; on the moving segment of the joint it allows the movement, and the parameters associated with it, to be measured — including the delay between the muscle firing and the limb moving.
  - ES: Hay dos posibilidades: sobre el músculo permite medir el mecanomiograma (MMG), que corre en paralelo con la señal eléctrica; sobre el segmento móvil de la articulación permite medir el movimiento y los parámetros asociados a él, incluido el retraso entre que el músculo se activa y la extremidad se mueve.
- **`src/emgteach/gui/tour.py:161`**
  - EN: The force-velocity experiment, and its rehearsal
  - ES: El experimento fuerza-velocidad, y su ensayo
  - EN: The step-by-step wizard guides you through the contractions with different loads: with a greater load the velocity is lower, and that inverse relation is the force-velocity curve. As it is the longest procedure in the application, a simulation is provided as a rehearsal, so that what is going to be done live is understood first.
  - ES: El asistente paso a paso guía las contracciones con distintas cargas: con más carga la velocidad es menor, y esa relación inversa es la curva fuerza-velocidad. Como es el procedimiento más largo de la aplicación, se ofrece una simulación como ensayo, para entender primero lo que se va a hacer en vivo.
- **`src/emgteach/gui/tour.py:177`**
  - EN: Agonist and antagonist
  - ES: Agonista y antagonista
  - EN: The recording is analysed as soon as it is opened. Both muscles were calibrated while recording, so the two envelopes are overlaid in % MVC — the only form in which two different muscles compare at all, since each one's millivolts depend on its own electrodes and skin. In a clean movement the agonist activates while the antagonist stays nearly silent; simultaneous activation is co-activation, which holds the joint rigid and is typical of an unpractised or uncertain movement. The table below the panels gives one row per contraction, and which muscle led it.
  - ES: El registro se analiza en cuanto se abre. Los dos músculos se calibraron al grabar, así que las dos envolventes se superponen en % CVM, la única forma en que dos músculos distintos se pueden comparar, porque los milivoltios de cada uno dependen de sus electrodos y de su piel. En un movimiento limpio el agonista se activa mientras el antagonista queda casi en silencio; la activación simultánea es coactivación, que deja rígida la articulación y es típica de un movimiento poco practicado o inseguro. La tabla bajo los paneles da una fila por contracción, y qué músculo la lideró.
- **`src/emgteach/gui/tour.py:195`**
  - EN: Force-velocity study
  - ES: Estudio fuerza-velocidad
  - EN: The recording is analysed as soon as it is opened. The study builds the load-velocity, force-velocity and power curves from a recording where several known loads were lifted, and relates them to the EMG amplitude — that is, to how many motor units had to be recruited for each load. The panels also show the movement against the EMG and the delay between the two.
  - ES: El registro se analiza en cuanto se abre. El estudio construye las curvas carga-velocidad, fuerza-velocidad y potencia a partir de un registro en el que se levantaron varias cargas conocidas, y las relaciona con la amplitud del EMG, es decir, con cuántas unidades motoras hubo que reclutar para cada carga. Los paneles muestran también el movimiento frente al EMG y el retraso entre ambos.
- **`src/emgteach/gui/tour.py:210`**
  - EN: What the analysis shows
  - ES: Qué muestra el análisis
  - EN: The recording is analysed as soon as it is opened. Raw signal: what the contracting fibres produce. Normalised envelope: how activation changes over time, which is what is compared between efforts. Spectrum: how the activity is distributed across frequencies — as a sustained contraction fatigues the muscle, the median frequency (MDF) falls. The cards under the panels carry the numbers with their usual ranges, and the table beside them gives one row per contraction.
  - ES: El registro se analiza en cuanto se abre. Señal en bruto: lo que producen las fibras que se contraen. Envolvente normalizada: cómo cambia la activación con el tiempo, que es lo que se compara entre esfuerzos. Espectro: cómo se reparte la actividad entre frecuencias; a medida que una contracción sostenida fatiga el músculo, la frecuencia mediana (MDF) baja. Las fichas bajo los paneles llevan los números con sus rangos habituales, y la tabla de al lado da una fila por contracción.
- **`src/emgteach/gui/tour.py:230`**
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
| Sampling rate | Frecuencia de muestreo | 1000 | Hz | no editable | `src/emgteach/profiles.py:112` |
| Band-pass, low cut | — | 20.0 | Hz | no editable | `src/emgteach/profiles.py:115` |
| Band-pass, high cut | — | 450.0 | Hz | no editable | `src/emgteach/profiles.py:116` |
| Notch | — | 50.0 | Hz | no editable | `src/emgteach/profiles.py:117` |
| Envelope cutoff frequency (Hz): | Frec. corte envolvente (Hz): | 5.0 | Hz | Análisis y Normalización CVM · casilla numérica (solo en cinemática) | `src/emgteach/profiles.py:118` |
| RMS window | Ventana RMS | 50.0 | ms | no editable | `src/emgteach/profiles.py:121` |
| Spectral segment length | — | 1.0 | s | no editable | `src/emgteach/profiles.py:122` |
| Spectral overlap | — | 0.5 | fracción | no editable | `src/emgteach/profiles.py:123` |
| MVC percentile | — | 95.0 | % | no editable | `src/emgteach/profiles.py:124` |
| MVC peak window | — | 0.0 | s | no editable | `src/emgteach/profiles.py:155` |
| Calibration efforts | — | 3 | repeticiones | no editable | `src/emgteach/profiles.py:163` |
| Duration of one effort | — | 1.5 | s | no editable | `src/emgteach/profiles.py:164` |
| Warm-up | — | 10.0 | s | no editable | `src/emgteach/profiles.py:233` |
| Preparation countdown | — | 5.0 | s | no editable | `src/emgteach/profiles.py:226` |
| Ready countdown | — | 3.0 | s | no editable (MVC_READY_S = 3.0) | `src/emgteach/gui/tabs/acquisition.py:158` |
| Rest between repetitions | — | 2.0 | s | no editable (MVC_REST_S = 2.0) | `src/emgteach/gui/tabs/acquisition.py:165` |
| Auto-onset k | — | 3.0 | desv. típicas | Adquisición · «Marcadores de eventos» · k | `src/emgteach/profiles.py:248` |
| Onset baseline | — | 1.0 | s | no editable | `src/emgteach/profiles.py:249` |
| Onset refractory | — | 0.5 | s | no editable | `src/emgteach/profiles.py:250` |
| Sensitivity | Sensibilidad | 3.0 · 4.4 · 3.0 | desv. típicas (un músculo · par · cinemática) | Análisis · «Seleccionar fragmentos…» · Sensibilidad («Restablecer» vuelve aquí) | `src/emgteach/modes.py:85` |
| Marked / expected | Marcadas / esperadas | 6 · 6 · 1 | contracciones (flexión · extensión · presa; solo en el par) | Análisis · «Seleccionar fragmentos…» · esperadas | `src/emgteach/modes.py:91` |
| Jonsson static limit (P10) | — | 5.0 | % CVM | no editable | `src/emgteach/profiles.py:127` |
| Jonsson median limit (P50) | — | 14.0 | % CVM | no editable | `src/emgteach/profiles.py:128` |
| Jonsson peak limit (P90) | — | 70.0 | % CVM | no editable | `src/emgteach/profiles.py:129` |
| Mean-activation limit | — | 10.0 | % CVM | no editable | `src/emgteach/profiles.py:132` |
| Live warning zone | — | 40.0 | % CVM | Adquisición · «Carga muscular» · Aviso | `src/emgteach/profiles.py:82` |
| Live danger zone | — | 70.0 | % CVM | Adquisición · «Carga muscular» · Peligro | `src/emgteach/profiles.py:82` |
| Co-activation floor | — | 4.5 | % CVM | no editable | `src/emgteach/profiles.py:218` |
| Implausible MVC | — | 150.0 | % CVM | no editable | `src/emgteach/profiles.py:174` |
| Minimum rest ratio | — | 5.0 | veces el reposo | no editable | `src/emgteach/profiles.py:138` |
| Cross-talk limit | — | 50.0 | % de su referencia | no editable | `src/emgteach/profiles.py:189` |
| Fatigue R² threshold | — | 0.3 | — | no editable (`fatigue_verdict(min_r2=)`) | `src/emgteach/fatigue.py:87` |
| Fatigue minimum segments | — | 4 | ventanas | no editable | `src/emgteach/profiles.py:245` |
| Fatigue active ratio | — | 0.3 | fracción | no editable | `src/emgteach/profiles.py:240` |
| BITalino ADC | — | 1023 | cuentas (10 bits) | no editable | `src/emgteach/devices/bitalino.py:149` |
| BITalino V_ref | — | 3.3 | V | no editable | `src/emgteach/devices/bitalino.py:150` |
| BITalino EMG gain | — | 1009.0 | — | no editable | `src/emgteach/devices/bitalino.py:153` |
| Arduino ADC | — | 1023.0 | cuentas (10 bits) | no editable | `src/emgteach/devices/arduino.py:80` |
| Arduino V_ref | — | 5.0 | V | no editable | `src/emgteach/devices/arduino.py:81` |
| MyoWare gain | — | 200.0 | — | no editable | `src/emgteach/devices/arduino.py:82` |
| F-V lifts per load | — | 3 | levantamientos | Adquisición · «Parámetros de la F-V…» | `src/emgteach/gui/tabs/acquisition.py:359` |
| F-V preparation | — | 6.0 | s | Adquisición · «Parámetros de la F-V…» | `src/emgteach/gui/tabs/acquisition.py:360` |
| F-V lift time | — | 1.0 | s | Adquisición · «Parámetros de la F-V…» | `src/emgteach/gui/tabs/acquisition.py:361` |

<<<PARAMETROS>>>

La conversión a milivoltios del BITalino es
`EMG(mV) = (ADC / 2^10 − 0.5) · VCC · 1000 / G`, con `G = 1009`
(`src/emgteach/devices/bitalino.py:657`). La del Arduino es
`(ADC · V_ref / 1023 − V_ref/2) · 1000 / 200`
(`src/emgteach/devices/arduino.py:192`).

---

## 5. Qué calcula y qué muestra

### 5.1 Paneles del análisis

<<<PANELES>>>

| Nº | Nombre largo (EN) | Nombre largo (ES) | Etiqueta corta (ES) | Lectura en el título (ES) |
|---|---|---|---|---|
| 1 | Raw signal | Señal en bruto | En bruto | la traza se ensancha mientras el músculo se contrae y se estrecha en reposo; con dos músculos: cada músculo contra su propio eje: se lee cuándo dispara cada uno, no cuál es más alto |
| 2 | Normalised envelope | Envolvente normalizada | Env. norm. | 1 es el punto más alto de esta ventana, no la CVM: se lee la forma, no la altura |
| 3 | PSD with MNF/MDF | PSD con MNF/MDF | PSD | dónde está la potencia de la señal; en gris, lo que quitó el filtro; con dos músculos: cada curva tiene área 1, así que se comparan las formas; la línea discontinua es la MDF de cada músculo |
| 4 | Filtered + rectified | Filtrada + rectificada | Filtr.+rect. | rectificada, cada oscilación cuenta hacia arriba: cuanto más alta la traza, más fuerte la activación |
| 5 | Envelope vs RMS | Envolvente vs RMS | Env. vs RMS | cuanto más alta la curva, más fuerte la activación; las dos líneas son dos formas de medirla |
| 6 | RMS per window | RMS por ventana | RMS/ventana | un punto por ventana: si sube con el mismo esfuerzo, entran más unidades motoras, a menudo por fatiga; con dos músculos: cada músculo contra su propio eje: se lee cómo evoluciona cada uno, no cuál está más alto |
| 7 | MDF vs time (fatigue) | MDF vs tiempo (fatiga) | MDF/tiempo | un descenso indica fatiga muscular |
| 8 | RMS vs MDF | RMS vs MDF | RMS vs MDF | los puntos avanzan en el tiempo siguiendo la flecha; la fatiga mueve el recorrido arriba y a la izquierda: más amplitud, menos frecuencia |
| 9 | Overlaid envelopes (agonist/antagonist) | Envolventes superpuestas (agonista/antagonista) | Env. superp. | cada músculo contra su propio máximo: si uno sube mientras el otro baja, se alternan; si suben a la vez, coactivación |
| 10 | EMG vs MMG (electrical vs mechanical) | EMG vs MMG (eléctrico vs mecánico) | EMG vs MMG | la vibración del músculo (MMG) sigue a su actividad eléctrica (EMG) |
| 11 | Tremor (accelerometer FFT) | Temblor (FFT del acelerómetro) | Temblor | el pico es la frecuencia del temblor; el fisiológico está entre 8 y 12 Hz |
| 12 | Movement vs EMG (limb kinematics) | Movimiento vs EMG (cinemática del segmento) | Mov. vs EMG | primero sube la EMG y después llega el movimiento: el desfase es el retraso electromecánico |

<<<PANELES>>>

Cuáles se abren depende de la práctica. Siempre disponibles: 1 y 3. La de un
músculo abre además el 2; la del par, el 7 y el 9, con los dos músculos en el
1 (un eje cada uno); la de cinemática, el 2 y los tres del acelerómetro (10, 11
y 12). Los paneles 4 a 8 están en `More panels…` / «Más paneles…» en
cualquier práctica, y el botón pasa a decir `Fewer panels` / «Menos paneles»
al abrirlo. El 2 no se ofrece nunca en el par, donde lo sustituye el 9. La
numeración es la misma en todas las prácticas: la que no ofrece un panel deja
su número sin usar. Cada título lleva en una segunda línea su lectura (la
columna de la derecha) y, si el panel enseña un solo músculo, su nombre.

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

El **PDF** (`src/emgteach/reports.py`, `build_session_report`) lleva cabecera con
identificador y archivo, una sección de calibración con las repeticiones y la
separación entre canales, los paneles elegidos, la tabla de contracciones, la de
coactivación, la tabla `Configuration used` / «Configuración utilizada» —que
desde la 3.1.0 incluye `Detection sensitivity (k)` / «Sensibilidad de detección
(k)»— y un pie reproducible con versión y commit. Desde la 3.5.0 cada tabla se
construye con un ancho por columna, así que la de contracciones cabe en el papel
—antes perdía cuatro de sus siete columnas por el borde derecho—, una tabla
partida entre páginas repite su cabecera, el informe imprime las medidas de los
**dos** músculos y nombra los dos canales, y el dispositivo, el protocolo y la
procedencia del archivo llegan también al informe.

El **CSV** (`src/emgteach/exports.py`, `write_analysis_csv`) empieza por una
cabecera comentada con `#`: el separador y la marca decimal que lleva el archivo,
el nombre del archivo —no la ruta completa, que traía el nombre de usuario de
Windows—, la versión de la aplicación, el canal y el segundo canal, la frecuencia
de muestreo, la sensibilidad de detección (k), la ventana analizada y la
duración; y después, **por músculo**, la referencia de CVM con su procedencia, el
máximo de la tarea, el RMS global, MNF, MDF, iEMG, la pendiente de la MDF en Hz/s
y en Hz/min, R², la caída porcentual y el veredicto de fatiga. Detrás va la tabla
por segmento (`t_s`, `rms_mv`, `mdf_hz`, y `rms_mv_2` y `mdf_hz_2` cuando hay dos
músculos) y, como bloques separados, las contracciones y las ventanas de
coactivación que imprime el informe.

**Su dialecto es el de la hoja de cálculo, no el del texto**: coma de separador y
punto decimal en inglés, punto y coma de separador y coma decimal en español, que
es lo que esperan Excel o LibreOffice configurados en español —con la otra
combinación abren el archivo entero en una sola columna y leen 0.05 como texto—.
Es la excepción declarada a la marca decimal única de la 3.5.0 (apartado 1.2), y
la primera línea del archivo dice cuál de las dos parejas lleva.

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
| Un músculo por debajo del suelo | `not reported — {name} below {floor} % MVC` | `no se informa — {name} por debajo del {floor} % de CVM` |
| Sin activación sobre el reposo | `not reported — no activation above rest` | `no se informa — no hay activación sobre el reposo` |

El suelo es `coact_floor_pct = 4.5 % CVM`; `{floor}` se escribe con su decimal
(«4.5» en inglés, «4.5» en español).

### 5.7 Veredicto de fatiga

`fatigue_verdict()`, `src/emgteach/fatigue.py:82`. Tres salidas y un criterio
sin ambigüedad:

- menos de `fatigue_min_segments` (4) ventanas, o pendiente nula → **no
  concluyente**;
- R² por debajo de `min_r2` (0.30) → **no concluyente**;
- pendiente negativa → **fatiga**; pendiente positiva → **sin fatiga**.

Los tres textos son `Fatigue` / «Fatiga», `No fatigue` / «Sin fatiga» y
`Inconclusive` / «No concluyente», este último acompañado de la razón: la
tendencia no ajusta, con su R².

---

## 6. Avisos, advertencias y errores

<<<AVISOS>>>

Son **101** mensajes distintos. Se listan tal como están en el código, sin reordenar ni resumir.

- **`src/emgteach/charts.py:590`**
  - EN: not reported
  - ES: no se informa
- **`src/emgteach/coactivation.py:265`**
  - EN: not reported — window too short
  - ES: no se informa — ventana demasiado corta
- **`src/emgteach/coactivation.py:280`**
  - EN: not reported — {name} below {floor} % MVC
  - ES: no se informa — {name} por debajo del {floor} % de CVM
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

Envíe ese archivo, indicando qué estaba haciendo en ese momento.
- **`src/emgteach/crash.py:125`**
  - EN: The application hit an error it did not expect, and could not write the details to a file.
  - ES: La aplicación ha encontrado un error que no esperaba, y no ha podido escribir los detalles en un archivo.
- **`src/emgteach/crash.py:131`**
  - EN: Unexpected error
  - ES: Error inesperado
- **`src/emgteach/diagnostics.py:152`**
  - EN: Windows could not be asked; the connection below says the rest.
  - ES: No se pudo consultar a Windows; la conexión, más abajo, dice el resto.
- **`src/emgteach/diagnostics.py:238`**
  - EN: It stopped: {error}
  - ES: Se detuvo: {error}
- **`src/emgteach/diagnostics.py:240`**
  - EN: No frame failed its CRC.
  - ES: Ninguna trama falló su CRC.
- **`src/emgteach/diagnostics.py:248`**
  - EN: flat: nothing reaches this input
  - ES: plana: a esta entrada no llega nada
- **`src/emgteach/diagnostics.py:250`**
  - EN: saturated in {pct:.0f} % of the samples
  - ES: saturada en el {pct:.0f} % de las muestras
- **`src/emgteach/diagnostics.py:299`**
  - EN: Result: not ready. The first check that failed says why.
  - ES: Resultado: no está listo. La primera comprobación que falla dice por qué.
- **`src/emgteach/diagnostics.py:309`**
  - EN: The report could not be saved: {error}
  - ES: No se pudo guardar el informe: {error}
- **`src/emgteach/dsp.py:527`**
  - EN: Suspiciously flat baseline at the start of the recording. May indicate a disconnected electrode or misconfigured gain.
  - ES: Línea base sospechosamente plana al inicio del registro. Puede indicar un electrodo desconectado o una ganancia mal configurada.
- **`src/emgteach/exports.py:66`**
  - EN: not conclusive (the MDF trend does not fit)
  - ES: no concluyente (la tendencia de MDF no ajusta)
- **`src/emgteach/gui/app.py:284`**
  - EN: Take a picture by itself every {s:.0f} s, but only while a recording is running, and at most {n} per recording. It needs no switching off: outside a recording it does nothing.
  - ES: Hace una captura sola cada {s:.0f} s, pero solo mientras se graba y como mucho {n} por registro. No hay que desactivarlo: fuera de una grabación no hace nada.
- **`src/emgteach/gui/app.py:714`**
  - EN: The screenshot could not be saved: {error}
  - ES: No se pudo guardar la captura: {error}
- **`src/emgteach/gui/app.py:719`**
  - EN: The screenshot could not be saved to: {path}
  - ES: No se pudo guardar la captura en: {path}
- **`src/emgteach/gui/help_texts.py:39`**
  - EN: After {warm} s of warm-up, {n} brief maximal efforts of {dur} s are recorded for each muscle, each announced {cue} s ahead and followed by {rest} s of rest. Each effort is one brief, explosive maximal jerk, not a sustained push against something fixed. The reference is the highest point the envelope reaches across the repetitions kept, so it is a maximum the task cannot exceed; a repetition that came out weak can be discarded afterwards in the analysis.
  - ES: Tras {warm} s de calentamiento se graban {n} esfuerzos máximos breves de {dur} s por músculo, cada uno anunciado con {cue} s de antelación y seguido de {rest} s de descanso. Cada esfuerzo es una sacudida breve y explosiva a la máxima potencia, no un empuje sostenido contra algo fijo. La referencia es el punto más alto que alcanza la envolvente en las repeticiones que se conservan, de modo que es un máximo que la tarea no puede superar; una repetición que salió floja puede descartarse después en el análisis.
- **`src/emgteach/gui/help_texts.py:59`**
  - EN: The application supports two devices: the BITalino over Bluetooth and the Arduino + MyoWare 2.0 over USB. Only the single-muscle practical can use the Arduino; the other two need the BITalino's second channel or its accelerometer, so they fix it and the selector does not appear.
  - ES: La aplicación admite dos dispositivos: la placa BITalino por Bluetooth y el Arduino + MyoWare 2.0 por USB. Solo la práctica de un músculo puede usar el Arduino; las otras dos necesitan el segundo canal de la placa o su acelerómetro, así que lo fijan y el selector no aparece.
- **`src/emgteach/gui/help_texts.py:74`**
  - EN: Start recording and ask for the contraction. Watch the live trace: at rest it should be a flat line with only baseline noise. A signal that never returns to baseline usually means a loose electrode or a poor contact, not a tonic muscle.
  - ES: Se inicia el registro y se pide la contracción. Conviene vigilar el trazado en vivo: en reposo debe ser una línea plana con solo ruido de base. Una señal que nunca vuelve a la línea de base suele indicar un electrodo suelto o mal contacto, no un músculo tónico.
- **`src/emgteach/gui/help_texts.py:87`**
  - EN: With this ticked the application timestamps each contraction onset as it finds it — the threshold is the resting level plus k standard deviations, and k is the knob beside it. The marks travel inside the EDF, so each effort can be found again during the analysis. Unticked, nothing is written: marking by hand during a recording asks the operator to keep up with a signal that does not wait.
  - ES: Con esto marcado, la aplicación anota el instante de cada inicio de contracción según lo encuentra: el umbral es el nivel de reposo más k desviaciones típicas, y k es el mando de al lado. Las marcas viajan dentro del EDF, así que cada esfuerzo se vuelve a encontrar en el análisis. Sin marcar, no se escribe ninguna: marcar a mano durante un registro es pedirle al operador que siga el ritmo de una señal que no espera.
- **`src/emgteach/gui/help_texts.py:251`**
  - EN: <b>Not detected</b>: the MDF stays flat or rises.
  - ES: <b>No detectada</b>: la MDF se mantiene o sube.
- **`src/emgteach/gui/help_texts.py:253`**
  - EN: <b>Not conclusive</b>: the line does not fit (low R²). This is usual with short or intermittent contractions; the recording does not answer the question, which is not the same as answering “no”.
  - ES: <b>No concluyente</b>: la recta no ajusta (R² bajo). Es lo habitual con contracciones cortas o intermitentes; el registro no responde a la pregunta, que no es lo mismo que responder «no».
- **`src/emgteach/gui/help_texts.py:271`**
  - EN: When it is not reported
  - ES: Cuándo no se informa
- **`src/emgteach/gui/help_texts.py:300`**
  - EN: One line per window, its seconds on the right. A purple bar is the index, with the number in it. A gold block means the index is not reported, and the small square beside it is the colour of the muscle that worked alone — in a clean flexion or extension that is the correct answer, not a fault. No square at all is a rest. The two mean activations are in the table.
  - ES: Una línea por ventana, con sus segundos a la derecha. Una barra morada es el índice, con el número dentro. Un bloque dorado quiere decir que el índice no se informa, y el cuadradito de al lado lleva el color del músculo que trabajó solo: en una flexión o una extensión limpias esa es la respuesta correcta, no un fallo. Sin cuadradito, es un reposo. Las dos activaciones medias están en la tabla.
- **`src/emgteach/gui/help_texts.py:322`**
  - EN: the highest point of the contraction's envelope, as a share of the maximum. A task effort is usually 20–80 %; above 100 % (in red) the calibration was not a maximum.
  - ES: el punto más alto de la envolvente de la contracción, como porcentaje del máximo. Un esfuerzo de tarea suele estar entre el 20 y el 80 %; por encima del 100 % (en rojo) la calibración no fue un máximo.
- **`src/emgteach/gui/help_texts.py:326`**
  - EN: median frequency of the spectrum. Typically 60–150 Hz for surface EMG of limb muscles; it falls along a sustained effort as the muscle fatigues. Not shown for contractions shorter than a quarter of a second.
  - ES: frecuencia mediana del espectro. Típicamente 60–150 Hz en EMG de superficie de músculos de las extremidades; baja a lo largo de un esfuerzo sostenido a medida que el músculo se fatiga. No se muestra en contracciones de menos de un cuarto de segundo.
- **`src/emgteach/gui/help_texts.py:355`**
  - EN: A raw amplitude cannot be compared between two people, or between two sessions of the same person: it depends on the electrodes, the skin and the fat beneath it. Expressing every value as a percentage of the maximal contraction cancels all of that out, because the two amplitudes share the same electrodes and the same skin: what is left is how hard the muscle is working. The maximum is inside the recording: the session calibrates without stopping, so nothing else has to be chosen here.
  - ES: Una amplitud bruta no se puede comparar entre dos personas, ni entre dos sesiones de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. Expresar cada valor como porcentaje de la contracción máxima cancela todo eso, porque las dos amplitudes comparten los mismos electrodos y la misma piel: lo que queda es cuánto está trabajando el músculo. El máximo está dentro del registro: la sesión calibra sin parar, así que aquí no hay nada más que elegir.
- **`src/emgteach/gui/tabs/acquisition.py:496`**
  - EN: This computer is not connected to any network, so the phones cannot reach it. Connect it to the network the phones use, or share this computer's own connection (Windows: Settings › Network & internet › Mobile hotspot) and connect the phones to that.
  - ES: Este equipo no está conectado a ninguna red, así que los móviles no pueden llegar a él. Conéctelo a la red que usan los móviles, o comparta la conexión del propio equipo (Windows: Configuración › Red e Internet › Zona con cobertura inalámbrica móvil) y conecte los móviles a ella.
- **`src/emgteach/gui/tabs/acquisition.py:840`**
  - EN: Error:
  - ES: Error:
- **`src/emgteach/gui/tabs/acquisition.py:865`**
  - EN: The event log could not be saved in {path}: {error}
  - ES: No se ha podido guardar el registro de eventos en {path}: {error}
- **`src/emgteach/gui/tabs/acquisition.py:1312`**
  - EN: Live signal quality: saturation or a flat (disconnected) signal.
  - ES: Calidad de señal en vivo: saturación o señal plana (desconectada).
- **`src/emgteach/gui/tabs/acquisition.py:2190`**
  - EN: The recording cannot be saved
  - ES: No se puede guardar el registro
- **`src/emgteach/gui/tabs/acquisition.py:2465`**
  - EN: The session could not start the calibration on its own. Press «Calibrate MVC» when you are ready — the phases will be written just the same.
  - ES: La sesión no ha podido arrancar la calibración por su cuenta. Pulse «Calibrar CVM» cuando esté listo: las fases se escriben igual.
- **`src/emgteach/gui/tabs/acquisition.py:2651`**
  - EN: The recording could not be shown for review: {err}
  - ES: No se pudo mostrar el registro para revisarlo: {err}
- **`src/emgteach/gui/tabs/acquisition.py:2875`**
  - EN: No network: the phones cannot reach this computer.
  - ES: Sin red: los móviles no pueden llegar a este equipo.
- **`src/emgteach/gui/tabs/acquisition.py:3567`**
  - EN: ⚠ «{muscle}»: the calibration reached {ref:.3f} mV, only {ratio:.1f}× its resting level. That is not a maximal contraction — every % MVC from now on will be too high by that factor. Calibrate again.
  - ES: ⚠ «{muscle}»: la calibración llegó a {ref:.3f} mV, solo {ratio:.1f}× su nivel de reposo. Eso no es una contracción máxima: a partir de ahora todos los % de CVM saldrán altos por ese mismo factor. Calibre de nuevo.
- **`src/emgteach/gui/tabs/acquisition.py:4174`**
  - EN: {muscles}: this is not a maximum. Calibrate again with a brief, explosive maximal jerk, not a sustained push against something fixed.
  - ES: {muscles}: esto no es un máximo. Calibre de nuevo con una sacudida breve y explosiva a la máxima potencia, no con un empuje sostenido contra algo fijo.
- **`src/emgteach/gui/tabs/acquisition.py:4195`**
  - EN: Channels not separated
  - ES: Canales sin separar
- **`src/emgteach/gui/tabs/acquisition.py:4207`**
  - EN: Calibration failed (no signal).
  - ES: Calibración fallida (sin señal).
- **`src/emgteach/gui/tabs/acquisition.py:4209`**
  - EN: Calibration failed
  - ES: Calibración fallida
- **`src/emgteach/gui/tabs/analysis.py:475`**
  - EN: Restrict every metric (spectrum, RMS, fatigue) to the time window below instead of the whole recording.
  - ES: Restringe todas las métricas (espectro, RMS, fatiga) a la ventana temporal de abajo en lugar del registro completo.
- **`src/emgteach/gui/tabs/analysis.py:869`**
  - EN: usual 60–150 Hz
  - ES: habitual 60–150 Hz
- **`src/emgteach/gui/tabs/analysis.py:885`**
  - EN: Highest point of the task's envelope, as % of the maximal contraction, read on the whole recording phase — from the start of the recording to the end of the file — whatever fragments are chosen: a maximum of the phase, not of the selection. Well above 100 % means the calibration was not a maximum.
  - ES: Punto más alto de la envolvente durante la tarea, en % de la contracción máxima, leído sobre la fase de registro entera —del inicio del registro al final del archivo—, se elijan los fragmentos que se elijan: es un máximo de la fase, no de la selección. Muy por encima del 100 % significa que la calibración no fue un máximo.
- **`src/emgteach/gui/tabs/analysis.py:1358`**
  - EN: Could not open the fragment editor: {error}
  - ES: No se pudo abrir el editor de fragmentos: {error}
- **`src/emgteach/gui/tabs/analysis.py:1429`**
  - EN: Next: «{button}». It decides which maximal efforts set the reference, and every % MVC below is measured against it — so it goes before choosing the fragments.
  - ES: Siguiente: «{button}». Decide qué esfuerzos máximos fijan la referencia, y todos los % CVM de abajo se miden contra ella, así que va antes de elegir los fragmentos.
- **`src/emgteach/gui/tabs/analysis.py:1568`**
  - EN: This recording carries no calibration. Only sessions recorded with the guided flow mark their maximal efforts.
  - ES: Este registro no trae calibración. Solo las sesiones grabadas con el flujo guiado marcan sus esfuerzos máximos.
- **`src/emgteach/gui/tabs/analysis.py:1586`**
  - EN: This recording carries no calibration spans, so the repetition list stays off. Only sessions recorded with the guided flow have them.
  - ES: Este registro no trae tramos de calibración, así que la lista de repeticiones queda apagada. Solo las sesiones grabadas con el flujo guiado los llevan.
- **`src/emgteach/gui/tabs/analysis.py:1854`**
  - EN: Whole recording: with no named windows this number does not measure anything. Open «{button}» and accept what it proposes.
  - ES: Registro completo: sin ventanas con nombre este número no mide nada. Abra «{button}» y acepte lo que propone.
- **`src/emgteach/gui/tabs/analysis.py:2150`**
  - EN: The report for the phones could not be made: {error}
  - ES: No se ha podido preparar el informe para los móviles: {error}
- **`src/emgteach/gui/tabs/analysis.py:2188`**
  - EN: Not conclusive (trend does not fit, R²={r2:.2f})
  - ES: No concluyente (la tendencia no ajusta, R²={r2:.2f})
- **`src/emgteach/gui/tabs/analysis.py:2217`**
  - EN: not a maximum
  - ES: no fue un máximo
- **`src/emgteach/gui/tabs/analysis.py:2221`**
  - EN: The task went well past the reference: the calibration did not capture a maximum, so every % MVC here is too high in the same proportion. Calibrate again with a brief, explosive maximal jerk, not a sustained push against something fixed.
  - ES: La tarea superó con mucho la referencia: la calibración no recogió un máximo, así que todos los % CVM de aquí están inflados en la misma proporción. Vuelva a calibrar con una sacudida breve y explosiva a la máxima potencia, no con un empuje sostenido contra algo fijo.
- **`src/emgteach/gui/tabs/analysis.py:2288`**
  - EN: Could not open the force-velocity study: {error}
  - ES: No se pudo abrir el estudio fuerza-velocidad: {error}
- **`src/emgteach/gui/tabs/analysis.py:2332`**
  - EN: Channel «{ch}»: flat — no signal (electrode not connected?).
  - ES: Canal «{ch}»: plano — sin señal (¿electrodo sin conectar?).
- **`src/emgteach/gui/tabs/analysis.py:2337`**
  - EN: Channel «{ch}»: saturated — the trace is pinned at the rails (check the electrode contact or the gain).
  - ES: Canal «{ch}»: saturado — la traza está pegada al tope (conviene revisar el contacto del electrodo o la ganancia).
- **`src/emgteach/gui/tabs/analysis.py:2344`**
  - EN: Channel «{ch}»: weak signal (low amplitude).
  - ES: Canal «{ch}»: señal débil (amplitud baja).
- **`src/emgteach/gui/tabs/analysis.py:2472`**
  - EN: Filtered EMG (20-450 Hz)
  - ES: EMG filtrado (20-450 Hz)
- **`src/emgteach/gui/tabs/analysis.py:2778`**
  - EN: The tuned recording cannot replace the one it comes from: tuning discards signal, so its source has to stay.
  - ES: El registro afinado no puede sustituir a aquel del que sale: afinar descarta señal, así que su origen tiene que quedarse.
- **`src/emgteach/gui/tabs/analysis.py:2830`**
  - EN: CSV export error: {error}
  - ES: Error al exportar CSV: {error}
- **`src/emgteach/gui/tabs/analysis.py:2980`**
  - EN: Error generating the PDF report: {error}
  - ES: Error al generar el informe PDF: {error}
- **`src/emgteach/gui/tabs/analysis.py:3327`**
  - EN: The recording does not match the mode
  - ES: El registro no concuerda con el modo
- **`src/emgteach/gui/tabs/mvc.py:420`**
  - EN: <p>Amplitude Probability Distribution Function (Jonsson): the % of time the muscle stays below each load level (% MVC). The static (P10), median (P50) and peak (P90) levels gauge overload risk.</p>
  - ES: <p>Función de distribución de probabilidad de amplitud (Jonsson): el % del tiempo que el músculo permanece por debajo de cada nivel de carga (% CVM). Los niveles estático (P10), mediano (P50) y pico (P90) valoran el riesgo de sobrecarga.</p>
- **`src/emgteach/gui/tabs/mvc.py:638`**
  - EN: A raw EMG amplitude cannot be compared between two people, or between two sessions of the same person: it depends on the electrodes, the skin and the fat layer beneath it. Normalisation solves this by expressing every value as a percentage of the amplitude that muscle reaches during a maximal effort.
  - ES: La amplitud bruta de una señal EMG no se puede comparar entre dos personas, ni entre dos sesiones de la misma persona: depende de los electrodos, de la piel y de la grasa que hay debajo. La normalización resuelve esto expresando cada valor como porcentaje de la amplitud que ese músculo alcanza en un esfuerzo máximo.
- **`src/emgteach/gui/tabs/mvc.py:652`**
  - EN: A reference is only a yardstick if it recruits the same muscle mass as the task, and a surface electrode does not see one muscle but the compartment beneath it. So the reference is a brief, explosive maximal jerk of the movement the muscle makes, not a sustained push against something fixed: a push has to be braced, which switches on the antagonist as well. On the forearm — the pair of the practical guide — the flexor's is a jerk of wrist flexion with the fist clenched with all one's strength, and the extensor's a jerk of wrist extension with the hand open and the fingers stretched out as far as they go: the task includes a grip, and clenching the fist brings in the finger flexors of the same compartment, which a push of the wrist leaves out. With another pair — biceps and triceps, say — the gesture is that pair's own, chosen by the same rule.
  - ES: Una referencia solo sirve de vara de medir si recluta la misma masa muscular que la tarea, y un electrodo de superficie no ve un músculo, sino el compartimento que tiene debajo. Por eso la referencia es una sacudida breve y explosiva, a la máxima potencia, del movimiento que hace el músculo, y no un empuje sostenido contra algo fijo: el empuje obliga a fijar el miembro, lo que enciende además al antagonista. En el antebrazo, que es el par del guion de prácticas, la del flexor es una sacudida de flexión de muñeca cerrando el puño con toda la fuerza, y la del extensor una sacudida de extensión de muñeca con la mano abierta y los dedos extendidos a tope: la tarea incluye una presa, y cerrar el puño enciende los flexores de los dedos del mismo compartimento, que el empuje de muñeca deja fuera. Con otro par —bíceps y tríceps, por ejemplo— el gesto es el propio de ese par, elegido con la misma regla.
- **`src/emgteach/gui/tabs/mvc.py:669`**
  - EN: A recording with no calibration inside it cannot be normalised: without a maximum there is no percentage, and this tab says so rather than dividing the signal by itself.
  - ES: Un registro sin calibración dentro no se puede normalizar: sin un máximo no hay porcentaje, y esta pestaña lo dice en vez de dividir la señal por sí misma.
- **`src/emgteach/gui/tabs/mvc.py:1233`**
  - EN: 2. Envelope (no calibration in this recording)
  - ES: 2. Envolvente (este registro no trae calibración)
- **`src/emgteach/gui/tour.py:130`**
  - EN: Press record. The session asks first for a maximal contraction — the reference every measurement is expressed against — and then for the task. Both go into one file, so nothing has to be matched up afterwards. Watch the live trace: at rest it should be a flat line with only baseline noise. A signal that never returns to baseline usually means a loose electrode, not a tonic muscle. Each contraction onset is marked on its own.
  - ES: Pulse grabar. La sesión pide primero una contracción máxima (la referencia respecto a la que se expresa cada medida) y después la tarea. Las dos van a un solo archivo, así que no hay que emparejar nada después. Observe el trazo en directo: en reposo debe ser una línea plana con solo el ruido basal. Una señal que nunca vuelve a la línea base suele ser un electrodo suelto, no un músculo tónico. El inicio de cada contracción se marca solo.
- **`src/emgteach/gui/tour.py:179`**
  - EN: The recording is analysed as soon as it is opened. Both muscles were calibrated while recording, so the two envelopes are overlaid in % MVC — the only form in which two different muscles compare at all, since each one's millivolts depend on its own electrodes and skin. In a clean movement the agonist activates while the antagonist stays nearly silent; simultaneous activation is co-activation, which holds the joint rigid and is typical of an unpractised or uncertain movement. The table below the panels gives one row per contraction, and which muscle led it.
  - ES: El registro se analiza en cuanto se abre. Los dos músculos se calibraron al grabar, así que las dos envolventes se superponen en % CVM, la única forma en que dos músculos distintos se pueden comparar, porque los milivoltios de cada uno dependen de sus electrodos y de su piel. En un movimiento limpio el agonista se activa mientras el antagonista queda casi en silencio; la activación simultánea es coactivación, que deja rígida la articulación y es típica de un movimiento poco practicado o inseguro. La tabla bajo los paneles da una fila por contracción, y qué músculo la lideró.
- **`src/emgteach/gui/widgets/calibration_reps.py:187`**
  - EN: Keep at least one repetition: a channel with none is not a calibration with a smaller reference, it is no calibration.
  - ES: Conserve al menos una repetición: un canal sin ninguna no es una calibración con una referencia menor, es no haber calibrado.
- **`src/emgteach/gui/widgets/force_velocity_dialog.py:188`**
  - EN: ⚠ The accelerometer barely moved (flat / pinned at a rail), so the velocities are ~0. Put it on the moving segment, oriented so its resting value sits mid-range (not at ±1 g), and lift quickly.
  - ES: ⚠ El acelerómetro apenas se movió (plano / pegado a un extremo), así que las velocidades son ~0. Colocarlo en el segmento móvil, orientado para que en reposo quede a media escala (no en ±1 g), y levantar rápido.
- **`src/emgteach/gui/widgets/force_velocity_dialog.py:367`**
  - EN: No velocity — accelerometer flat
(see the warning)
  - ES: Sin velocidad — acelerómetro plano
(ver el aviso)
- **`src/emgteach/gui/widgets/force_velocity_plan_dialog.py:85`**
  - EN: ⚠ The accelerometer is set to the muscle. For force-velocity put it on the moving segment (set the placement to "on the moving segment"), or the velocity will be near zero.
  - ES: ⚠ El acelerómetro está en el músculo. Para fuerza-velocidad ponerlo en el segmento móvil (poner la colocación en «en el segmento móvil»), o la velocidad será casi cero.
- **`src/emgteach/gui/widgets/force_velocity_plan_dialog.py:108`**
  - EN: Contractions to perform at each load. The wizard prompts one at a time; keep it low (1-3) so fatigue does not bias the heavier loads.
  - ES: Contracciones a realizar en cada carga. El asistente las pide de una en una; manténgalo bajo (1-3) para que la fatiga no sesgue las cargas más pesadas.
- **`src/emgteach/gui/widgets/fragment_selection.py:1600`**
  - EN: The count does not match ({detail}). Move the sensitivity until it does, or as close as it gets; what is left is put right in step 2. Then press ▶.
  - ES: El recuento no coincide ({detail}). Mueva la sensibilidad hasta que coincida, o hasta lo más cerca posible; lo que quede se corrige en el paso 2. Después pulse ▶.
- **`src/emgteach/gui/widgets/fragment_selection.py:1626`**
  - EN: The count does not match yet ({detail}): look for what is missing among the dotted stretches, or drop what is left over.
  - ES: El recuento aún no coincide ({detail}): busque lo que falta entre los tramos punteados, o elimine lo que sobra.
- **`src/emgteach/gui/widgets/fragment_selection.py:1719`**
  - EN: below the threshold: click to add
  - ES: bajo el umbral: pulse para añadir
- **`src/emgteach/gui/widgets/fv_rehearsal_dialog.py:88`**
  - EN: Held, because a true maximum takes about a second to reach. It is isometric — nothing moves, so the accelerometer stays flat here. This contraction sets the amplitude reference, not a velocity.
  - ES: Se mantiene porque alcanzar un máximo de verdad lleva alrededor de un segundo. Es isométrica: no se mueve nada, así que aquí el acelerómetro permanece plano. Esta contracción fija la referencia de amplitud, no una velocidad.
- **`src/emgteach/phases.py:482`**
  - EN: no calibration
  - ES: sin calibración
- **`src/emgteach/recovery.py:92`**
  - EN: {path} is too short to be an EDF file.
  - ES: {path} es demasiado corto para ser un archivo EDF.
- **`src/emgteach/recovery.py:101`**
  - EN: {path} does not have a readable EDF header.
  - ES: {path} no tiene una cabecera EDF legible.
- **`src/emgteach/reports.py:141`**
  - EN: Not conclusive — the trend does not fit ({slope:+.2f} Hz/s, R²={r2:.2f}). Fatigue needs a contraction held long enough for the trend to show.
  - ES: No concluyente: la tendencia no ajusta ({slope:+.2f} Hz/s, R²={r2:.2f}). La fatiga necesita una contracción mantenida el tiempo suficiente para que la tendencia se vea.
- **`src/emgteach/reports.py:222`**
  - EN: Filtered (20-450 Hz)
  - ES: Filtrado (20-450 Hz)
- **`src/emgteach/reports.py:577`**
  - EN: The task exceeds the reference by a wide margin: the calibration did not capture a maximum, so every percentage in this report is too high in the same proportion. Calibrate again with a brief, explosive maximal jerk, not a sustained push against something fixed.
  - ES: La tarea supera la referencia con mucho margen: la calibración no recogió un máximo, así que todos los porcentajes de este informe están inflados en la misma proporción. Vuelva a calibrar con una sacudida breve y explosiva a la máxima potencia, no con un empuje sostenido contra algo fijo.
- **`src/emgteach/reports.py:832`**
  - EN: Notch (mains)
  - ES: Notch (red eléctrica)
- **`src/emgteach/tuning.py:344`**
  - EN: the recording has no recording phase (no «REC start», no calibration and no load marks): there is nothing to tune
  - ES: el registro no tiene fase de registro (ni «REC start», ni calibración, ni marcas de carga): no hay nada que afinar
- **`src/emgteach/workers/acquisition.py:53`**
  - EN: The recording «{name}» could not be saved in the folder {folder} ({reason}). Choose another folder — Documents, for example — or another name, and press record again.
  - ES: El registro «{name}» no se ha podido guardar en la carpeta {folder} ({reason}). Elija otra carpeta —Documentos, por ejemplo— u otro nombre, y vuelva a pulsar grabar.
- **`src/emgteach/workers/acquisition.py:488`**
  - EN: Connection to {name} lost: {error}
  - ES: Conexión con {name} perdida: {error}
- **`src/emgteach/workers/acquisition.py:569`**
  - EN: The abandoned connection attempt ended: {error}
  - ES: Terminó el intento de conexión abandonado: {error}
- **`src/emgteach/workers/acquisition.py:598`**
  - EN: Warning — annotation error: {error}
  - ES: Aviso — error de anotación: {error}
- **`src/emgteach/workers/acquisition.py:603`**
  - EN: Warning — EDF close error: {error}
  - ES: Aviso — error al cerrar el EDF: {error}
- **`src/emgteach/workers/analysis.py:405`**
  - EN: The selected fragments total {t:.2f} s, below the 1 s minimum required for analysis.
  - ES: Los fragmentos seleccionados suman {t:.2f} s, por debajo del mínimo de 1 s requerido para el análisis.
- **`src/emgteach/workers/analysis.py:686`**
  - EN: MDF trend fitted over {n} of {total} segments (the rest were below the contraction threshold).
  - ES: Tendencia de MDF ajustada sobre {n} de {total} segmentos (el resto quedaba por debajo del umbral de contracción).
- **`src/emgteach/workers/analysis.py:1068`**
  - EN: not reported — no MVC reference for one of the channels
  - ES: no se informa — falta la referencia de CVM en uno de los canales
- **`src/emgteach/workers/analysis.py:1082`**
  - EN: ⚠ «{name}»: the recording starts with the muscle already active, so no resting baseline could be measured and contraction onsets were not detected. Record a couple of quiet seconds before the first contraction.
  - ES: ⚠ «{name}»: el registro empieza con el músculo ya activo, así que no se pudo medir una línea base de reposo y no se han detectado inicios de contracción. Grabe un par de segundos en reposo antes de la primera contracción.
- **`src/emgteach/workers/analysis.py:1090`**
  - EN: No contraction detected in «{name}»: it never left its baseline.
  - ES: No se detecta contracción en «{name}»: no sale de su línea base.
- **`src/emgteach/workers/analysis.py:1146`**
  - EN: ⚠ «{name}» reaches {peak:.0f} % MVC, and spends {share:.0f} % of the recording above {limit:.0f} %. The calibration did not capture a maximum — the task beat it — so every percentage here is too high.
  - ES: ⚠ «{name}» llega al {peak:.0f} % de la CVM, y pasa el {share:.0f} % del registro por encima del {limit:.0f} %. La calibración no capturó un máximo —la tarea lo superó—, así que todos los porcentajes de aquí salen inflados.
- **`src/emgteach/workers/analysis.py:1265`**
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

**Todas las cifras de este apartado están medidas con la 3.2.0** sobre su
etiqueta y **no cambian con la 3.3.0 ni con la 3.4.0** (apartados 1.4 y 1.3);
las que cambiaron respecto de la 3.1.2, y cuánto, están en la tabla del
apartado 1.5. Las del 8.3 no pasan por la coactivación.

### 8.1 Registro de ejemplo: el par flexor / extensor

`ejemplo_par_FCR_ECR.edf`, dos canales, 140.0 s, del 3 de septiembre de 2026.
El tramo analizado son los 23.3 s de la fase de registro.

**Aviso sobre este archivo:** se grabó con el protocolo de calibración de
entonces, **seis repeticiones por músculo** (tres mantenidas y tres breves).
Desde la 3.0.0 la calibración son tres esfuerzos breves. La
referencia se calcula igual —el pico de la envolvente, la mejor de las
repeticiones conservadas—,
así que las cifras de abajo son comparables, pero el archivo dice «6
repeticiones» donde uno nuevo diría «3». Se conserva como ejemplo porque es el
único registro de dos canales con las dos calibraciones completas y el
protocolo de maniobra ya corregido.

| Medida | Canal 1 (FCR) | Canal 2 (ECR) |
|---|---|---|
| Referencia de CVM | 0.2705 mV | 0.1967 mV |
| Procedencia | recalculada de los tramos `CAL` | recalculada de los tramos `CAL` |
| Nivel de reposo | 3.5 µV (1.30 % CVM) | 7.6 µV (3.87 % CVM) |
| Máximo de la tarea | 101 % CVM | 82 % CVM |

Índice de coactivación sobre el tramo de registro completo: **31 %** (30.7),
con medias de 11.5 % y 9.8 % CVM. Correlación de las dos envolventes:
**r = 0.126**.

### 8.2 Las tres maniobras: coactivación por maniobra

`ejemplo_tres_maniobras.edf`, dos canales, 100.0 s, del **6 de septiembre de
2026**, con la calibración de tres esfuerzos breves por músculo, hechos como
sacudidas —la maniobra que pide la 3.1.2—; `REC start` en el segundo 57.3 y
42.7 s de tarea. El protocolo fue
**seis flexiones de muñeca, dos segundos de quietud, seis extensiones, dos
segundos de quietud y una
presa sostenida de unos ocho segundos con la muñeca neutra**.

| Medida | Canal 1 (FCR) | Canal 2 (ECR) |
|---|---|---|
| Referencia de CVM | 0.1870 mV | 0.4226 mV |
| Procedencia | recalculada de los tramos `CAL` | recalculada de los tramos `CAL` |
| Nivel de reposo (el que resta el índice) | 1.37 % CVM | 1.84 % CVM |
| Máximo de la tarea (pico de la envolvente) | 68 % CVM | 41 % CVM |

Los dos máximos de tarea quedan **por debajo del 100 %**, que es la
comprobación de que la calibración capturó de verdad un máximo y de que los
porcentajes de abajo significan lo que dicen.

| Maniobra | Tramo | Índice de coactivación | Medias (FCR / ECR) |
|---|---|---|---|
| Flexión | 57.5–70.0 s | **29 %** (29.4) | 11.1 / 4.9 % CVM |
| Extensión | 72.0–85.0 s | **no reportada** | 3.3 / 5.2 % CVM |
| Presa | 88.0–97.0 s | **79 %** (78.6) | 11.4 / 7.7 % CVM |

Medido con la 3.2.0: cada maniobra es una máscara sobre la fase de registro sin
recortar, el reposo que se resta es el de la fase entera (apartados 1.7 y
5.6) y la referencia es el pico de la envolvente (apartado 1.5). Con la 3.1.2
—referencia de 0.2 s y suelo del 5 %— la tabla era 28.3 / no reportada / 75.7 %
con medias 14.1 / 5.8 · 4.2 / 6.2 · 14.5 / 9.1; con el pico y el suelo del 5 %
la flexión se quedaba sin número (el extensor, en 4.9 %), y es la razón del
suelo del 4.5 % (apartado 9, punto 2). Hasta la 3.1.0 la herramienta que las
calculaba tomaba el reposo de cada ventana de la propia ventana.

**Durante la presa el extensor llega al 28 % CVM** y el flexor al 58 %: son
los picos de la envolvente en la fila de la presa de la tabla de
contracciones, medidos igual que los máximos de tarea de arriba, que son los
de la ficha «Task maximum».

Los dos números que el §8.4 declaraba imposibles son ese 29 % frente a 79 % y
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
below 4.5 % MVC»: el flexor se quedó en 3.3 % de media sobre su reposo, por
debajo del suelo de `coact_floor_pct`. No es una maniobra fallida sino la salvaguarda funcionando
— con el antagonista prácticamente en reposo el índice sería ruido dividido
por ruido. Dicho de otro modo, la extensión fue el más limpiamente recíproco
de los tres movimientos, y el precio de serlo es no tener índice.

**Maniobra entera frente a contracciones.** Elegir en el editor las trece filas
que propone, bien nombradas (seis de flexión, seis de extensión y la presa), mide
otra cosa: la actividad durante las contracciones, sin los reposos entre ellas.

| Selección | Flexión | Extensión | Presa |
|---|---|---|---|
| La maniobra entera, una fila cada una | 29.4 % · 11.1 / 4.9 | — · 3.3 / 5.2 | 78.6 % · 11.4 / 7.7 |
| Las trece filas del editor | 30.4 % · 21.1 / 6.8 | 66.8 % · 6.7 / 12.5 | 78.1 % · 13.3 / 9.2 |

Índice y medias FCR / ECR en % CVM, con la 3.2.0. Sin los reposos las medias
suben, y la extensión gana un índice: el flexor pasa de 3.3 a 6.7 % CVM y supera
el suelo del 4.5 %. Ese 67 % es la relación entre dos señales débiles —el extensor
en 12.5 y el flexor en 6.7 % de su máximo—, que es el caso que el suelo existe
para no medir. Para esta práctica, la ventana es la maniobra entera.

**Tres avisos sobre estas cifras**, los tres descubiertos al calcularlas:

1. **El EDF afinado y el original no dan el mismo número.** Sobre el afinado
   de este mismo registro salen «sin número» para la flexión, 61 % para la
   extensión y 70 % para la presa (con la 3.2.0: 60.6 y 70.2 %; con la
   3.1.1 eran 63.3 y 67.3 %, porque el afinado es una concatenación en
   disco y se lee como tal). El afinado concatena los fragmentos y tira
   lo que hay entre ellos, así que la media del músculo activo sube y la del
   otro baja. El índice de Falconer-Winter se lee sobre la fase de movimiento
   con su curso temporal, reposos incluidos; concatenar las contracciones mide
   otra cosa. **Las cifras publicables son las del registro sin recortar.**
   Desde la 3.1.1, elegir los fragmentos en la pestaña sobre el original ya
   no concatena para la coactivación (apartado 1.7); el aviso vale para el
   archivo afinado.
2. **El borde de la ventana: el reposo que entra ya no mueve el índice.** Con
   la 3.0.0, estrechar la presa 0.8 s por delante la llevaba de 76 % a 70 %,
   porque el reposo se medía dentro de la ventana y quitarle segundos de
   reposo lo subía. Desde la 3.1.1, restando el reposo de la fase entera, el
   mismo recorte deja el índice donde estaba (78.6 % con la 3.2.0): los
   segundos de reposo aportan cero a los dos lados del cociente. Lo que sí lo
   mueve es la actividad que queda fuera: el extensor sigue activo hasta los
   97.95 s, y alargar la presa hasta ahí la baja a 77.2 %. Las medias sí
   dependen del borde, porque son medias sobre la duración de la ventana (el
   flexor pasa de 11.4 a 12.5 % CVM con el recorte). Las ventanas de la tabla
   son las de la maniobra completa,
   de la primera activación a la última relajación.
3. **Un segundo registro del mismo protocolo se descartó**: sus extensiones
   salieron mejor —índice de 43 %— pero la calibración del flexor no capturó
   un máximo (referencia 0.089 mV y máximo de tarea 185 % CVM, medidos con la
   3.1.1), y con el
   denominador mal ningún porcentaje de él es publicable. El programa lo avisó
   en pantalla al analizarlo. Queda anotado porque explica por qué la tabla
   sale del registro adjunto y no del más reciente.

### 8.3 Registro de ejemplo: la cinemática

`C:\Records\emg_2026-09-05_18-13.edf`, un canal más acelerómetro, 178.0 s, del
5 de septiembre. Calibración de tres repeticiones, referencia 0.2923 mV
(recalculada de los tramos `CAL`; la anotación que escribió el asistente al
grabar dice 0.2705 mV, y la aplicación prefiere la recalculada),
inicio del registro en el segundo 36.0. Doce levantamientos, tres por cada una
de las cargas de 2, 3.4, 5 y 7 kg, cada uno marcado en el archivo con su carga.

| Carga | Velocidad media (u. a.) |
|---|---|
| 2 kg | 0.0267 |
| 3.4 kg | 0.0305 |
| 5 kg | 0.0200 |
| 7 kg | 0.0140 |

La velocidad cae al aumentar la carga a partir de 3.4 kg y la potencia hace su
máximo en cargas intermedias, que es la forma de Hill. Retraso electromecánico
mediano de 42 ms, dentro del rango de 30 a 100 ms de la literatura. Máximo de
la tarea, 123 % CVM.

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
  que no se cronometra porque ya se sabe: con la 3.7.0, `REC start` llega a
  los 66.2 s en los registros del par (ENSAYO01b y COMPROB05b) —calentamiento,
  las dos calibraciones con la primera cuenta atrás de 7 s y la preparación—,
  más la tarea guiada. Eso es una constante del programa —la secuencia la
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
2. **`coact_floor_pct = 4.5 % CVM`.** El 5 % original se midió sobre un solo
   registro —ventana quieta con medias de 0.2 % y 0.8 % sobre reposo frente a
   19–30 % en ventana activa: un hueco de un factor treinta— y sobre la
   referencia de 0.2 s. El suelo es un nivel de activación sobre el reposo
   expresado como fracción de la referencia; con la referencia de pico, un
   16 % más alta de media en 80 canales del banco, el mismo nivel es el 4.3 %
   de la nueva, y el suelo pasa a 4.5 %. Comprobado sobre el banco: con ese
   valor, 33 de 34 ventanas de registro entero y las tres maniobras del
   registro de ejemplo conservan el estado (se informa / no se informa) que
   tenían con el 5 % de la referencia antigua; con el 5 % de la nueva lo
   conservan 31 de 34 y dos de las tres. Sigue habiendo un solo registro
   detrás del nivel en sí. **Y el registro de las tres maniobras enseña su
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
   preparación, la media de su último segundo— la flexión va de 28.4 a 30.5 %
   y la presa de 77.6 a 79.5 %.
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
   cálculos (apartado 1.7). La 3.1.1 cambia una sola medida, la coactivación
   con fragmentos elegidos (apartado 1.6), y la 3.1.2 solo lo que la
   calibración pide y cómo se describe (apartado 1.5). La 3.2.0 cambia el
   estadístico de la referencia, el suelo del índice y la MDF de los
   segmentos (apartado 1.4); la 3.3.0 lee el máximo de la tarea sobre la fase
   entera y dibuja el panel 3 en relativo (apartado 1.3); la 3.4.0 cambia lo
   que enseña la pestaña de análisis y cómo numera sus paneles, sin tocar
   ningún cálculo (apartado 1.3). La 3.5.0 añade lo que rodea a la medida —la
   placa simulada, el diagnóstico, el registro de eventos y la recuperación—,
   repara el informe y el CSV y deja una sola marca decimal, y las tres cosas
   que mueven números son faltas que se reparan, declaradas una por una
   (apartado 1.2). La 3.6.0 no cambia ningún cálculo: hace que la placa
   simulada obedezca a la calibración, de modo que un ensayo sin hardware
   enseñe lo que enseña la práctica (apartado 1.1). La 3.7.0 lleva la sesión
   guiada hasta la tarea y propone las filas del editor hasta el reposo, sin
   cambiar ningún cálculo para un conjunto dado de fragmentos (apartado 1.0);
   es la que describe el artículo, y lo que venga después irá a versiones
   posteriores sin cambiar lo que describe.
10. **La k = 4.4 del par es empírica**: es el valor que dio una fila por
    maniobra en los registros en que se probó. Con otra piel, otro montaje u
    otra forma de hacer las maniobras puede proponer de más o de menos; por
    eso el editor cuenta las marcadas frente a las esperadas y deja mover la
    sensibilidad, y por eso la k usada va al informe y al CSV.
11. **La fatiga sigue calculándose sobre los fragmentos concatenados**, y el
    filtrado corre después de concatenar: en los segmentos de 1 s que cruzan
    una unión la MDF sale unos 1.4 Hz más alta que en sus vecinos (143.3 frente
    a 141.9 Hz en el registro de las tres maniobras, con las filas del editor).
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
  (3.6.0) y el número correcto de pruebas (1217, las mismas que en la
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
  también sale idéntica. La 3.1.2 cambia textos de la calibración, que no
  aparecen en ninguna figura del artículo, y la figura 6 rehecha con ella sale
  idéntica. **Con la 3.2.0 el material se ha regenerado entero**
  (`informe_material.py --articulo` y `figura6.py`): la figura 6 cambia, porque
  las curvas van en % CVM de una referencia más alta y los índices son los
  nuevos (29 %, no se informa, 79 %); los recortes de la figura 7 cambian,
  porque enseñan cifras en % CVM (referencia 0.2705 mV, activación media
  13 %, P10 1 %, P50 4 %, P90 42 %, donde con la 3.1.2 decían 0.2175 mV,
  16 %, 2 %, 5 % y 52 %); los recortes de las figuras 3 y 4 salen idénticos
  píxel a píxel (los selectores de la figura 3 difieren en dos píxeles del
  borde inferior); las capturas de ventana entera difieren en lo que ya
  diferían y en las cifras en % CVM. El PDF y el CSV de ejemplo llevan las
  cifras nuevas. **Con la 3.3.0, regenerado otra vez**: cambian las capturas
  de la pestaña de análisis, porque el panel 3 va en relativo, y con ellas la
  captura entera de la figura 4a y su recorte, solo en lo que se ve del panel
  3 oscurecido detrás del cuadro de la guía (el texto del cuadro es el mismo);
  la figura 6 sale idéntica píxel a píxel (su PDF cambia en los metadatos), y
  los recortes de la figura 7, las capturas de adquisición y de normalización
  y los recortes de la figura 3 salen idénticos. El PDF de ejemplo no dibuja
  paneles de análisis —`informe_material.py` lo genera sin elegirlos, con la
  figura de señal de siempre—, así que no llevaba el panel 3, como se dijo aquí
  con la 3.3.0; el CSV solo cambia en los finales de línea. **Con la 3.4.0,
  regenerado otra vez**: cambian las capturas de la pestaña de análisis —la fila de
  casillas pasa a «1. Raw · 3. PSD · 7. MDF/time · 9. Env. overlay» (en
  español en el material del informe), el botón «More panels…» lleva el
  estilo de los de modo y el panel 1 enseña los dos músculos en dos ejes, con
  los títulos en dos líneas—, y con ellas la captura entera de la figura 4a y
  su recorte, en la fila de casillas y en lo que se ve de los paneles
  oscurecidos detrás del cuadro de la guía (el texto del cuadro es el mismo).
  **Con la 3.5.0, regenerado otra vez**, y lo que cambia se ha mirado píxel a
  píxel. En el material del artículo, que va en inglés: las tres capturas de
  ventana entera (adquisición y las dos de la figura 3) difieren en **cuatro
  píxeles**, los de la casilla de la k, que escribía `3.00` y ahora escribe
  `3.00`; la figura 7 y su recorte de datos cambian en la primera línea de la
  ficha, que ahora nombra el canal («…o.edf - **Channel**: FCR»), y no en
  ninguna cifra; el PDF de ejemplo cambia solo en su pie (versión, commit y
  fecha) y el CSV solo en su línea de versión. Salen **idénticas** las capturas
  de análisis y de normalización, los recortes de las figuras 3 y 4, el recorte
  de la curva APDF de la figura 7 y la figura 6. En el material de este informe,
  que va en español, cambian además los textos que la 3.5.0 corrigió:
  «Calibración en el fichero» pasa a «en el archivo», «Envolvente LP» a
  «Envolvente paso-bajo», «normalizada al CVM» a «normalizada a la CVM», la
  potencia del espectro y la leyenda de amplitud llevan punto decimal, y la ficha
  de datos nombra el canal; el PDF de ejemplo cambia en el pie y en la figura de
  señal, que lleva esas leyendas. **Ninguna cifra medida cambia**: la tabla por
  segmento del CSV es idéntica byte a byte una vez descontados los finales de
  línea, y la referencia de CVM, el máximo de la tarea y las métricas del informe
  son las mismas.
  **Con la 3.6.0, regenerado otra vez y sin una sola diferencia visible**: esta
  versión no toca ningún texto de pantalla ni ningún cálculo, así que las ocho
  capturas y los recortes salen idénticos byte a byte, y el PDF y el CSV de
  ejemplo solo cambian en el pie y en la línea de versión.
  La figura 6 sale idéntica píxel a píxel (su PDF cambia en los metadatos), y
  los recortes de las figuras 3 y 7, la figura 4b, las capturas de adquisición
  y de normalización y el CSV salen idénticos; los PDF de ejemplo, por lo
  dicho, solo cambian en el pie (versión, commit y fecha).
- Los dos documentos docentes en Word (Guía del docente v2.4 y Cuaderno de
  prácticas v2.4) describen la 3.1.2 —la maniobra de sacudida y las flexiones
  libres— con las capturas de la 3.0.0. No están en el repositorio. Para la
  3.2.0 hace falta una v2.5, con el pico y el suelo, y las capturas que
  enseñen cifras en % CVM o el editor de fragmentos rehechas.

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
