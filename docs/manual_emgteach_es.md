# emgteach — Documento fuente para el manual de usuario (ilustrado)

> **Para quien elabora el manual.** Este documento reúne, con detalle, *todo lo
> que hace el programa, su significado fisiológico y lo relevante para
> interpretarlo*. Está pensado como **material de partida**: a partir de él se
> redactará y maquetará el **manual de usuario ilustrado** (con capturas de
> pantalla y figuras). A lo largo del texto hay marcas **[Figura sugerida: …]**
> que indican dónde conviene una captura o ilustración. El programa y su interfaz
> están en castellano (también disponible en inglés); este documento usa la
> terminología tal y como aparece en pantalla en castellano.
>
> Autor del software: Dr. Ángel Agis‑Torres — Sección Departamental de
> Fisiología, Facultad de Farmacia, Universidad Complutense de Madrid.

---

## 0. Resumen ejecutivo (una página)

**emgteach** es una aplicación de escritorio para la **adquisición, análisis y
normalización de señales de electromiografía de superficie (EMG)** en el
laboratorio docente de fisiología. Permite:

- **Registrar** la actividad eléctrica muscular en tiempo real con un BITalino
  (o, en la práctica de un músculo, con un Arduino + MyoWare), en **uno o dos
  canales** y, si la práctica lo pide, con el **acelerómetro**.
- **Calibrar la contracción voluntaria máxima dentro de la propia sesión**, con
  un asistente que la escribe en el mismo fichero, y **monitorizar la carga
  muscular en tiempo real** con avisos de cansancio y fatiga.
- **Analizar** un registro en cuanto se abre, sin pulsar nada: una **tabla por
  contracción** (RMS, pico en % CVM, frecuencia mediana, retraso electromecánico),
  las **fichas del resumen** con sus rangos orientativos, el espectro antes y
  después del filtro, y el **veredicto de fatiga** con las condiciones que exige.
- **Comparar dos músculos** en % CVM y medir su **coactivación** (índice de
  Falconer-Winter) por maniobra.
- **Normalizar** la tarea respecto a la **CVM** y evaluar la **carga muscular**
  según el método de Jonsson (ergonomía).
- **Exportar informes PDF** reproducibles, que llevan la calibración, las tablas y
  las fichas: el entregable de la práctica.

Los archivos se guardan en formato estándar **EDF+** (compatible con otras
herramientas como MNE‑Python o EDFbrowser).

La aplicación se organiza en **tres pestañas**: **Adquisición**, **Análisis** y
**Normalización CVM**. Antes que ellas está el **selector de práctica**, con tres
opciones y una banda de color que dice el nivel (básico, intermedio, avanzado),
del que se derivan el número de canales, el uso del acelerómetro, qué pide la
grabación y qué medidas ofrece cada pestaña (§4.1). Una **guía de cinco pasos** y
un **«?»** en la esquina de cada caja llevan la explicación al sitio donde surge la
pregunta (§4.2).

[Figura sugerida: captura de la ventana principal mostrando las tres pestañas y el
selector de práctica en la esquina superior derecha.]

---

## 1. Fundamento fisiológico de la electromiografía de superficie (sEMG)

### 1.1 Qué se mide

La **electromiografía de superficie** registra, mediante electrodos colocados
sobre la piel, la **actividad eléctrica generada por las fibras musculares**
cuando se contraen. No mide directamente la fuerza ni el movimiento, sino el
**comando eléctrico** que el sistema nervioso envía al músculo.

### 1.2 Origen de la señal

- La unidad funcional es la **unidad motora**: una motoneurona y todas las
  fibras musculares que inerva.
- Cuando la motoneurona se activa, sus fibras se despolarizan y generan un
  **potencial de acción de unidad motora (PAUM)**.
- El electrodo de superficie capta la **suma** de los PAUM de las unidades
  motoras cercanas. La señal resultante es de aspecto **estocástico** (parece
  ruido aleatorio), con amplitudes típicas de **decenas de µV a unos pocos mV**.

### 1.3 Qué información lleva la señal (amplitud y frecuencia)

La señal EMG transmite dos tipos de información complementaria:

- **Amplitud** (cuán "grande" es la señal): refleja el **nivel de activación
  muscular** — cuántas unidades motoras están reclutadas y a qué frecuencia
  disparan. Se relaciona (de forma no lineal) con la **fuerza** ejercida. Se
  cuantifica con la **envolvente** o el valor **RMS**.
- **Frecuencia** (cómo se reparte la energía en el espectro): refleja, entre
  otras cosas, la **velocidad de conducción** de las fibras y el patrón de
  reclutamiento. Es la base de la **detección de fatiga** (ver §6.4). Se estudia
  con la **densidad espectral de potencia (PSD)** y las **frecuencias media
  (MNF) y mediana (MDF)**.

### 1.4 Artefactos y ruido (por qué se filtra)

La señal en bruto contiene componentes que no son actividad muscular útil:

- **Interferencia de red eléctrica** a 50 Hz (en Europa) y armónicos.
- **Movimiento de electrodos** y deriva de la línea base (baja frecuencia).
- **Ruido** de alta frecuencia.

Por eso la señal se **filtra** antes de interpretarla (ver §4).

[Figura sugerida: esquema "motoneurona → fibras → electrodo de superficie →
señal sEMG", con ejemplo de trazado en bruto.]

---

## 2. Equipo y montaje

### 2.1 Dispositivos soportados

| Dispositivo | Conexión | Notas |
|---|---|---|
| **BITalino (revolution)** | Bluetooth (Classic/SPP, como puerto COM virtual) | Plataforma de biopotenciales. Hay que emparejarlo antes en el sistema operativo. |
| **Arduino RedBoard Plus + MyoWare 2.0** | USB serie | Sensor EMG de hardware abierto; el firmware se incluye en el repositorio. |

Ninguno necesita un extra opcional ni un compilador: ambos hablan con su
dispositivo mediante `pyserial`, y ambos funcionan en todas las versiones de
Python soportadas (3.10–3.12).

Ambos se manejan de forma intercambiable desde la aplicación (se elige el tipo
de dispositivo en la pestaña de Adquisición).

### 2.2 Colocación de electrodos

- Electrodos sobre el **vientre muscular**, alineados con la dirección de las
  fibras, con un electrodo de **referencia** en una zona eléctricamente neutra
  (p. ej. una prominencia ósea).
- Piel limpia para reducir la impedancia y los artefactos.

[Figura sugerida: foto/ilustración de la colocación de electrodos en un músculo
(p. ej. bíceps braquial) con etiquetas de electrodo activo / referencia.]

### 2.3 Uno o dos canales (agonista / antagonista)

La aplicación admite **1 o 2 canales simultáneos**. El caso de dos canales es
útil para estudiar **pares agonista/antagonista** (p. ej. bíceps y tríceps):
permite observar la **coactivación** y la coordinación entre músculos. Cada
canal tiene una **etiqueta editable** (nombre del músculo) y un **color** fijo
(canal 1 = azul, canal 2 = rojo) consistente en todas las gráficas.

El número de canales **no se elige ya como un ajuste aparte**: lo fija el modo de
práctica seleccionado (§4.1). Dos canales corresponden al modo agonista /
antagonista; los otros dos modos registran uno.

### 2.4 Unidades y muestreo

- La señal se expresa en **milivoltios (mV)**.
- La **frecuencia de muestreo** nominal es de **1000 Hz** (1000 muestras por
  segundo y canal), suficiente para cubrir la banda informativa del EMG.

**Del valor del conversor a milivoltios.** El conversor analógico-digital no lee
el biopotencial: lee la salida de un amplificador, de modo que la función de
transferencia tiene que dividir por su ganancia.

| Plataforma | Conversión | Fondo de escala |
|---|---|---|
| BITalino | `EMG(mV) = (ADC / 2¹⁰ − 0,5) · VCC · 1000 / G`, con VCC = 3,3 V y G = 1009 | **±1,635 mV** |
| Arduino + MyoWare 2.0 (modo RAW) | la misma expresión, con V_ref = 5 V y G = 200 | ±12,5 mV |

> **Nota para quien compare registros de distintos cursos.** Hasta la versión
> anterior, la conversión del BITalino trataba el canal como si el conversor
> leyera el biopotencial directamente, y el fondo de escala resultante era
> ±1,65 mV. El error pasó desapercibido porque la ganancia es casi 1000 y un
> voltio son 1000 mV: los dos errores se cancelaban casi por completo. Las
> amplitudes absolutas en milivoltios bajan un **0,90 %** respecto a las de antes.
> **No cambia nada que sea un cociente**: el % CVM, los niveles APDF de Jonsson y
> las pendientes de fatiga son idénticos. Sobre cómo distinguir unos registros de
> otros, ver §6.1.

---

## 3. Cadena de procesado de señal (DSP) y su significado

A partir de la señal **en bruto**, el programa calcula en tiempo real (y vuelve
a calcular en el análisis) una cadena de procesado. Cada paso tiene un sentido
fisiológico:

1. **Filtro notch a 50 Hz** — elimina la **interferencia de la red eléctrica**
   (y deja "limpia" la actividad muscular real).
2. **Filtro paso‑banda 20–450 Hz** — conserva la **banda informativa del EMG**
   y descarta la deriva de línea base (< 20 Hz, movimiento de electrodos) y el
   ruido de alta frecuencia (> 450 Hz).
3. **Rectificación** — toma el **valor absoluto** de la señal filtrada; como la
   actividad es positiva y negativa de forma simétrica, rectificar permite medir
   su "magnitud".
4. **Envolvente (filtro paso‑bajo a 5 Hz)** — suaviza la señal rectificada para
   obtener una curva que sigue el **nivel de activación** a lo largo del tiempo
   (la "intensidad" del esfuerzo).
5. **RMS (Root Mean Square)** — otra medida de amplitud, calculada en ventanas;
   es el indicador clásico de **amplitud de la señal EMG** y se relaciona con la
   activación/fuerza.

**Importante (diseño del archivo):** en el EDF solo se guarda la **señal en bruto**
(una por sensor). La señal filtrada y la envolvente son **funciones
deterministas** de la señal en bruto y se **recalculan** al analizar; así el archivo
es más pequeño y siempre reproducible.

### Parámetros de procesado por defecto

| Parámetro | Valor por defecto | Significado |
|---|---|---|
| Frecuencia de muestreo | 1000 Hz | Muestras por segundo |
| Paso‑banda | 20–450 Hz | Banda informativa del EMG |
| Notch | 50 Hz | Interferencia de red (Europa) |
| Corte de envolvente | 5 Hz | Suavizado del nivel de activación |
| Ventana RMS | 50 ms | Cálculo de amplitud RMS |
| Segmento de análisis de fatiga | 1 s (solape 50 %) | Ventanas para RMS/MDF en el tiempo |
| Ventana de la referencia CVM | 0,2 s | El mejor 0,2 s de las seis repeticiones de calibración (ver §5.1) |
| Calibración | 3 × 4 s mantenidas + 3 × 1,5 s breves, tras 10 s de calentamiento | Lo que pide el asistente por músculo |

[Figura sugerida: cuatro trazados apilados del mismo tramo —en bruto, filtrado,
rectificado y envolvente— para ilustrar la cadena de procesado.]

---

## 4. La interfaz: primero la práctica, después las tres pestañas

### 4.1 Elegir la práctica

En la esquina superior derecha de la ventana, en la misma fila que el selector de
idioma, hay un desplegable con tres opciones. Es el primer control que se toca en
cada sesión: fija qué se registra, y las tres pestañas se configuran a partir de
ahí.

| Práctica | Nivel (banda) | Canales EMG | Acelerómetro | Dispositivo | Calibración |
|---|---|---|---|---|---|
| **Contracción de un músculo** | básico (verde) | 1 | no | BITalino o Arduino + MyoWare | con el botón «Calibrar CVM» |
| **Contracción agonista / antagonista** | intermedio (naranja) | 2 | no | BITalino | automática al iniciar la grabación |
| **Cinemática muscular** | avanzado (violeta) | 1 | sí | BITalino | con el botón «Calibrar CVM» |

La práctica **decide lo que se registra**, y no se limita a filtrar lo que se ve.
Fija el número de canales y el uso del acelerómetro, y cada pestaña ofrece solo
las medidas que tienen sentido para ella. Por eso no hay en pantalla un selector
de número de canales ni una casilla del acelerómetro, y el selector de
dispositivo aparece solo en la práctica de un músculo: las otras dos necesitan un
segundo canal o el acelerómetro, que solo tiene el BITalino, así que la caja dice
«Dispositivo: BITalino» y deja editable la dirección.

**El nivel es la práctica.** No hay una casilla de «opciones avanzadas»: los
controles finos (frecuencia de corte de la envolvente, región de interés, guardar
el registro afinado, estudio de fuerza-velocidad) pertenecen a la práctica de
cinemática, que es avanzada por su propia naturaleza, y allí ocupan una fila
propia. Las otras dos prácticas no los muestran.

Dos comportamientos que conviene conocer de antemano:

1. **Lo que una práctica no ofrece, además lo desmarca**, y al volver a esa
   práctica se restaura la selección anterior. Un panel que quedara marcado se
   seguiría dibujando sin forma visible de quitarlo.
2. **Cada práctica abre con sus paneles y el botón «Más paneles…» revela el
   resto**, salvo los que el registro no puede alimentar (un segundo músculo, el
   acelerómetro). Un alumno curioso no está confinado a la práctica avanzada.

**El registro manda sobre la práctica.** Al abrir en agonista / antagonista un
EDF que solo tiene un canal, se avisa de cuántos canales tiene el archivo y se
propone la práctica que le corresponde, en lugar de comportarse en silencio como
un análisis de un canal mientras el selector sigue afirmando que hay dos músculos.
Con un archivo de dos canales, la comparación de envolventes se activa sola.

[Figura sugerida: detalle de la esquina superior derecha con el selector de
práctica desplegado, la banda de nivel, el selector de idioma y los botones
«Guía» y «?».]

### 4.2 La guía interactiva

Recorrido que señala cada control **sobre la propia pantalla**: oscurece el resto,
rodea el control del que habla y muestra al lado qué es y qué significa
fisiológicamente. Cambia de pestaña por su cuenta cuando el recorrido lo pide.

**Cinco pasos** (siete en cinemática): elegir la práctica; conectar, con el
dispositivo que esa práctica admite y el orden de los canales (Músculo 1 es el
registrado por A1); grabar, con el máximo dentro del registro; leer el análisis;
y por qué todo está en % CVM. En cinemática se añaden la colocación del
acelerómetro y el estudio de fuerza-velocidad. Lo que antes eran catorce a
diecisiete pasos se repartió entre estos cinco y los **«?»** de cada caja: la
explicación de un control aparece donde surge la pregunta, sobre la propia caja,
con el mismo panel que usa la guía.

Se ofrece al arrancar, mediante un diálogo con una casilla **«Mostrar esta guía la
próxima vez»** marcada por defecto. Un ordenador de laboratorio ve un alumno
distinto cada sesión, así que la decisión de apagarla corresponde a quien tiene el
equipo a su cargo y no a quien lo abrió primero. Ese diálogo nombra el sensor de
la práctica elegida: los dos en la de un músculo, solo el BITalino en las otras.
El botón **«Guía»**, junto al **«?»**, la relanza en cualquier momento. Se niega a
arrancar si hay un registro en marcha.

**Los pasos guiados del análisis.** Al abrir un registro, la pestaña de Análisis
señala con el mismo panel flotante el siguiente paso: primero «Repeticiones de la
calibración…», después «Seleccionar fragmentos…». El cuadro espera a que la
pestaña esté en pantalla y desaparece al cambiar de pestaña.

[Figura sugerida: un paso de la guía en funcionamiento, con la pantalla oscurecida
y el control resaltado.]

### 4.3 Pestaña **Adquisición** (tiempo real)

Permite **registrar** una sesión y observarla en vivo.

**Configuración del dispositivo**
- Tipo de dispositivo (BITalino o Arduino + MyoWare), solo en la práctica de un
  músculo; en las otras dos la fila dice «Dispositivo: BITalino».
- Dirección **MAC** (BITalino) o **puerto COM** (Arduino), siempre editable. El
  botón «Por defecto» restaura la guardada.
- **Ruta y archivo de salida**: la carpeta donde se escribirá el EDF.
- **Etiquetas**: el nombre de cada músculo, en el orden de los canales de la
  placa (Músculo 1 es el registrado por A1). En el par, las casillas empiezan
  vacías con una pista («Agonista, p. ej. FCR»); vacías, el registro dice
  «Agonista» y «Antagonista». En las otras dos prácticas el canal se llama
  «Músculo» y no hay casilla.
- **Identificador de prueba**: un alumno, una pareja, una mesa o un intento; va a
  la cabecera del EDF y al informe. Comparte línea con la difusión a móviles.

**Control de adquisición**
- Botones **Conectar/Desconectar** e **Iniciar/Detener grabación**.
- Un **LED** de estado de comunicación: rojo (desconectado), amarillo (conectado,
  sin tráfico), verde (recibiendo datos). Un *watchdog* fuerza la desconexión si
  el dispositivo deja de enviar datos (p. ej. pérdida de Bluetooth).

**Gráficas en tiempo real** (dos):
- **Señal EMG en bruto** (mV).
- **Envolvente**.

En cinemática muscular se añade una tercera gráfica con la traza del
**acelerómetro**, con sus propios botones de escala.

> El filtrado (notch de 50 Hz + paso‑banda 20–450 Hz) se sigue aplicando para
> calcular la envolvente, pero la señal filtrada intermedia **ya no se dibuja**:
> para docencia de Fisiología basta con la señal en bruto y su envolvente.

Con **dos canales**, la gráfica de la señal en bruto se muestra **apilada**
(un "carril" por canal, con su color), mientras que la envolvente, al ser no
negativa, se **superpone** para comparar directamente ambos músculos. La escala
vertical de cada gráfica se ajusta con botones **▲▼**, y la **ventana temporal**
con un desplegable de zoom y botones ◀▶ (también con la rueda del ratón).

**Marcadores de eventos**
- **Detección automática de inicio de contracción** (*Auto-inicio*), a la vista en
  las tres prácticas: se marca el comienzo de una contracción cuando la envolvente
  supera un **umbral** igual al reposo más *k* veces su ruido; *k* está al lado
  con su explicación («umbral = reposo + k × ruido; lo habitual es 3»). Una *k*
  menor detecta esfuerzos más suaves y admite más falsas alarmas. (Significado en
  §5.6.)
- No hay marcado manual: pedir al operador que teclee mientras vigila al sujeto y
  la señal era una fuente de errores. Las maniobras se reconocen después, en el
  editor de fragmentos, y la aplicación rellena sola qué músculo llevó cada una.
- Las marcas se dibujan en vivo sobre las gráficas y quedan registradas como
  **anotaciones** en el EDF, igual que las fases de la sesión (calentamiento,
  cada repetición de calibración, preparación, registro).

**Carga muscular (CVM en vivo)**
- **La calibración es un asistente**, y siempre el mismo: 10 s de calentamiento
  con dos o tres contracciones suaves; por músculo, **tres contracciones máximas
  mantenidas** de 4 s («¡Contraiga FCR al máximo!») y **tres sacudidas máximas
  breves** de 1,5 s («Haga una contracción o sacudida muscular simple (breve) con
  la máxima fuerza posible»), cada una con su cuenta atrás y sus 2 s de descanso.
  En la práctica del par lo lanza el propio botón de grabar, antes de la tarea,
  y después escribe 5 s de preparación y el inicio del registro; en las otras dos
  se lanza con **«Calibrar CVM»** con la grabación en marcha. Todo queda dentro del
  mismo fichero, cada repetición con su tramo marcado (§5.1).
- **Cancelar una guía.** Mientras corre la calibración o el plan de
  fuerza-velocidad aparece **«Cancelar guía (Esc)»** junto al botón de grabar, y
  Esc hace lo mismo desde cualquier punto de la pestaña. La grabación sigue; una
  calibración cortada no deja referencia, y sus repeticiones cerradas quedan en
  el fichero.
- Al terminar cada músculo, el asistente comprueba que la referencia supere al
  menos cinco veces su nivel de reposo (si no, avisa: no fue una contracción
  máxima) y, con dos músculos, mide **cuánto leyó el otro canal** durante el
  máximo. Por encima del 50 % de su propia referencia el panel termina en
  «Canales sin separar».
- Tras calibrar, por cada canal se muestra una **barra de carga** con el **% de
  CVM actual** y sus **zonas de color**: verde hasta el 40 %, naranja (cansancio)
  hasta el 70 %, roja (fatiga) por encima; y los niveles **P10/P50/P90** en vivo.
  (Significado en §5.5.)

**El acelerómetro** (solo en cinemática muscular). Se registra como un canal más,
en unidades `g` y sin calibrar. La caja de acelerómetro dice el cableado, **el
músculo en A1 y el acelerómetro en A2**, que es una convención y no un ajuste: el
selector de entrada y el diagnóstico «buscar canal del ACC» que había aquí no
encontraron nada en el banco mientras la convención acertaba. Y reúne el selector
de colocación: sobre el músculo (MMG) o sobre el segmento que se mueve (temblor,
fuerza-velocidad y retraso electromecánico). En esta caja están también **«F-V
guiada…»**, que dirige la adquisición de una serie de cargas conocidas, y
**«Ensayar…»**, que corre ese procedimiento sin
hardware sobre una señal simulada.

[Figura sugerida: captura completa de la pestaña de Adquisición durante una
grabación de 2 canales, señalando: gráficas apiladas, controles de escala,
caja de marcadores y caja del monitor de carga con las barras de colores.]

[Figura sugerida: detalle de la caja "Carga muscular (CVM en vivo)" con una barra
en zona verde, otra en naranja/roja.]

### 4.4 Pestaña **Análisis** (desconectado)

Analiza en profundidad un registro EDF ya guardado.

**Parámetros de análisis** (una caja, dos o tres filas)
- Primera fila: el **archivo EDF** y los botones Explorar, Analizar, Guardar figura,
  Generar informe PDF y Exportar CSV. El registro **se analiza solo al abrirlo**
  (o al terminar una grabación); «Analizar» solo se enciende cuando ha cambiado
  algún ajuste desde el último análisis.
- Segunda fila, **en el orden en que se hacen las cosas**: «Repeticiones de la
  calibración…», «Seleccionar fragmentos…» con el recuento de fragmentos elegidos,
  el **canal** (y, en el par, el compañero, que se fija solo), y las **casillas de
  paneles** de la práctica con «Más paneles…» al final.
- Solo en cinemática, una fila de controles finos: **analizar solo una región**
  (de… a…), **frecuencia de corte de la envolvente**, **Guardar EDF afinado…** y
  **Estudio fuerza-velocidad…**.
- El **identificador de prueba** no se pide aquí: se lee de la cabecera del EDF,
  donde lo escribió la pestaña de Adquisición, y va al informe. Debajo de la
  caja, una línea dice cuál es el siguiente paso.

**Los trece paneles de análisis** y su significado. Cada práctica abre con los
suyos y **«Más paneles…»** revela el resto, salvo los que el registro no puede
alimentar. Los paneles se apilan en una página que se desplaza con la rueda del
ratón; a la izquierda de cada uno, ▲▼ cambian la escala de amplitud y ▶◀ la de
tiempo.

| Panel | Qué muestra | Significado | Abre con |
|---|---|---|---|
| **1A. Señal en bruto** | EMG sin procesar, con los inicios marcados por líneas finas | Punto de partida; permite ver artefactos | las tres prácticas |
| **1B. Señal en bruto (2.º)** | El segundo músculo | Cada músculo en su carril | agonista / antagonista |
| **2. Envolvente normalizada** | Envolvente escalada a su máximo (0–1) | Forma de la activación, comparable | un músculo, cinemática |
| **3. PSD con MNF/MDF** | Densidad espectral; en gris, el espectro **antes** del filtro; en el par, los dos músculos con su MDF | Qué quitó el filtro; reparto de energía; base de la fatiga | las tres prácticas |
| **4. Filtrada + rectificada** | Señal limpia y su valor absoluto | Aísla la actividad muscular real | «Más paneles…» |
| **5. Envolvente frente a RMS** | Dos medidas de amplitud superpuestas | Nivel de activación en el tiempo | «Más paneles…» |
| **6. RMS por ventana** | Amplitud RMS a lo largo del tiempo | Evolución del esfuerzo | «Más paneles…» |
| **7. MDF frente al tiempo** | MDF por ventana y su recta; en el par, los dos músculos | **Indicador de fatiga** (§5.4) | agonista / antagonista |
| **8. RMS frente a MDF** | Relación amplitud–frecuencia | Relación fuerza/fatiga durante la tarea | «Más paneles…» |
| **9. Envolventes superpuestas** | Las dos envolventes en % CVM sobre el mismo eje, con la banda del 100 % | Coactivación y coordinación | agonista / antagonista |
| **10. EMG frente a MMG** | Envolvente eléctrica y mecánica | Acoplamiento electromecánico | cinemática muscular |
| **11. Temblor** | Espectro del acelerómetro | Pico del temblor fisiológico (8–12 Hz) | cinemática muscular |
| **12. Movimiento frente a EMG** | Trazado cinemático y envolvente EMG, con el retraso electromecánico medio anotado | El movimiento sigue a la contracción | cinemática muscular |

En la fila de casillas los nombres aparecen abreviados (*1A. En bruto*, *2. Env.
norm.*, *3. PSD*…); los de la tabla son los de los títulos de los paneles y del
informe. Sobre cualquier panel en % CVM, una banda rosa marca lo que pasa del
100 %, y si el registro pasa mucho tiempo ahí el panel lo dice en rojo.

**La banda inferior**, en tres cuadros que comparten el ancho:

- **Coactivación** (solo en el par): una fila por ventana con la activación media
  de cada músculo en % CVM y el índice de Falconer-Winter, o «no se informa» y su
  razón (§5.7).
- **Contracciones**: una fila por contracción encontrada, con inicio, duración,
  músculo que la llevó (o «Coactivación»), RMS, pico en % CVM (en rojo si pasa
  del 100 %), MDF y, en cinemática, el retraso electromecánico. Son las mismas
  contracciones que propone el editor de fragmentos.
- **Resumen del análisis**, en fichas: frecuencia media, frecuencia mediana,
  pendiente de la MDF con su R², fatiga (el veredicto), **máximo de la tarea**
  (por músculo, en rojo con «no fue un máximo» si la calibración no lo fue), RMS
  global, iEMG, duración y CVM con su origen. Bajo cada ficha, en gris, el rango
  orientativo (§5.7). El «?» de cada cuadro explica cómo leerlo.

**Estudio de fuerza-velocidad** (solo en cinemática muscular). Un botón toma las
repeticiones de un mismo registro, con su carga anotada en cada una, y devuelve
cuatro curvas: carga frente a velocidad, la fuerza-velocidad normalizada de forma
hiperbólica, la potencia como producto de ambas, y el reclutamiento, que es la
amplitud EMG frente a la carga.

**Navegación**: la **ventana de visualización** (minimapa, abajo) permite acotar el
tramo dibujado arrastrando con el ratón. La rueda del ratón sobre los paneles los
desplaza verticalmente; las escalas se cambian con los botones de la izquierda.

**Informe PDF**: el botón *Generar informe PDF* abre un diálogo para **elegir qué
gráficos** incluir y el **rango temporal** a representar (por defecto, la ventana
visible). El PDF incluye cabecera (con alumno/a y archivo), los gráficos elegidos,
una **tabla de métricas** y un pie reproducible (versión y fecha).

[Figura sugerida: captura de la pestaña de Análisis con los tres paneles del
núcleo docente, señalando el resumen numérico y el navegador temporal.]

[Figura sugerida: ejemplo de informe PDF de Análisis (1ª página con gráficos y
2ª con la tabla de métricas).]

### 4.5 Pestaña **CVM** (normalización a la Contracción Voluntaria Máxima)

Expresa la señal como **porcentaje de la CVM** y evalúa la **carga muscular**.

**Panel de entrada.** La primera vez que se abre la pestaña en cada ejecución de la
aplicación, recibe con una explicación de qué es una contracción voluntaria
máxima, por qué se hace contra algo que no cede y por qué la referencia está
dentro del propio registro. Se cierra con **«Entendido, continuar»** y no vuelve
hasta que se reinicie la aplicación: «Nueva sesión» no lo resucita.

**Calcula sola.** Al terminar una grabación, o al abrir un registro, la pestaña
recibe el fichero y calcula sin pulsar nada; **«Calcular CVM»** queda para volver
a hacerlo tras cambiar algo. La fila de controles va en el orden de uso:
«Seleccionar fragmentos…», el canal, y las casillas de los tres paneles.

**Entradas**
- **El EDF de la sesión**, y nada más. La sesión marca su propia calibración,
  así que el máximo está dentro del archivo que se abre: preguntar por un
  segundo archivo era pedir al operador que respondiera algo que el fichero ya
  responde, y dejaba que las dos pestañas discreparan.
- El tramo analizado es, por defecto, la **fase de registro**: la calibración y
  la pausa quedan fuera sin que nadie los recorte a ojo. El editor de fragmentos
  sigue estando para mirar un esfuerzo concreto dentro de esa fase.
- **Sin calibración no hay % CVM ni carga muscular.** La antigua
  auto‑normalización —dividir la señal por su propio percentil 95— se ha
  retirado: una tarea llega siempre a ~100 % de sí misma, así que los límites de
  Jonsson declaraban sobrecarga hiciera lo que hiciera el sujeto. Lo que no
  depende de una referencia —la señal y su envolvente— se sigue dibujando.

**Los 3 paneles temporales**
1. Señal **filtrada y rectificada**.
2. **Envolvente** con la **línea de amplitud de referencia CVM**.
3. Señal **normalizada (% CVM)**, con la línea del 100 %.

**Análisis de carga muscular (APDF de Jonsson)**
- Un **gráfico de distribución de carga (APDF)**: la **distribución acumulada de
  amplitud** de la envolvente en % CVM, con los tres niveles marcados (cada uno
  con su color; **anillo rojo** si supera su límite recomendado). (Ver §5.5.)
- Un **panel de datos** estructurado: referencia CVM, fuente, **activación media**
  y los niveles **estático (P10) / mediano (P50) / pico (P90)**, cada uno con su
  **valor** (en **rojo** si se sale de lo normal), su **rango normal** y una
  **explicación breve** de su significado.

**Qué ocurre con un resultado auto‑normalizado.** Dividir una señal por un
percentil de sí misma deja sin sentido los límites de Jonsson, porque una
contracción sostenida los supera por construcción. Cuando la referencia es
automática, el gráfico APDF **no se dibuja**: en su lugar se explica que el
análisis de carga necesita un registro de referencia. Los títulos de los paneles,
en pantalla y en el PDF, llevan el sufijo **«(auto-normalizada, no es %CVM)»**,
porque el informe es lo que entrega el alumno y viaja solo.

**Registro de eventos propio.** La pestaña tiene su propio registro. El registro
compartido solo puede estar en un sitio, que era la pestaña de análisis, de modo
que todo lo que esta escribía se escribía donde no se veía, incluidos los avisos
de canal plano (electrodo desconectado) y canal saturado (mal contacto), que son
el error más común de un alumno.

**Informe PDF de normalización**: igual que en Análisis, con selección de rango
temporal; incluye los paneles, el gráfico APDF y la tabla de métricas de carga.

[Figura sugerida: el panel de entrada de la pestaña CVM tal y como aparece al
abrirla.]

[Figura sugerida: captura de la pestaña CVM señalando los 3 paneles, el gráfico
APDF (con los puntos de colores y anillos) y el panel de datos.]

[Figura sugerida: detalle del panel de datos con un valor en rojo (fuera de
rango) y su explicación.]

### 4.6 Seguimiento en móviles

Permite que **un solo equipo** (el ordenador que maneja el BITalino) **retransmita
la sesión en vivo** a los móviles o tabletas del resto del grupo, que solo la
**siguen** desde el navegador, sin instalar nada. Pensado para prácticas en grupo:
una persona opera y varias siguen.

La casilla está **a la vista en los tres modos**, y no entre las opciones
avanzadas. Un laboratorio docente suele tener un único sensor, y esto es lo que
convierte un solo registro en algo que lee toda la clase a la vez: es para lo que
sirve la práctica, no un ajuste fino.

**Activación (pestaña Adquisición).**
- Casilla **«Difundir a móviles (en laboratorio)»**. Al activarla se levanta un
  servidor en la **red local** y se muestra la dirección **«Los alumnos abren:
  `http://<IP‑del‑PC>:8070/?k=<código>`»** y el número de seguidores conectados. Los mensajes
  del registro de eventos hablan de **«modo seguimiento en móviles»**.
- Junto a ella, **«Copiar enlace»** y un botón **QR** que muestra un código para
  abrir la página con la cámara del móvil.
- Cada vez que se activa la difusión se genera un **código de sesión** nuevo, que
  viaja en el enlace. Los enlaces de una práctica anterior dejan de valer en
  cuanto esa difusión se detiene.
- El PC y los móviles deben estar en la **misma red Wi‑Fi o LAN**.

**Qué ven los seguidores** (página de solo lectura):
- La **envolvente** de cada canal en tiempo real y la **barra de % CVM** con sus
  zonas de color; el estado de **grabación** y el guiado de **calibración CVM**
  (preparar/mantener/relajar) reflejado en su móvil.
- Botón **⬇️ Descargar sesión (CSV)** para guardar en su teléfono lo mostrado en
  vivo (tiempo, envolvente, % CVM y marcadores).
- Bloque **📊 Resultados del análisis**: cuando el operador/a ejecuta el análisis
  desconectado, sus **métricas** (MNF, MDF, pendiente, RMS, iEMG, fatiga) se envían
  a los móviles, junto con **⬇️ Descargar informe (PDF)** y **⬇️ Descargar
  resultados (CSV)** en cuanto el operador/a los genera o exporta.

> **Arquitectura.** El BITalino usa Bluetooth *punto a punto* (un dispositivo por
> tarjeta): por eso **un** PC posee el enlace Bluetooth y **re‑difunde** por la red a
> los seguidores. En los móviles no se instala nada y estos no pueden controlar el
> equipo ni alterar la grabación (vista de solo lectura).

[Figura sugerida: móvil de un alumno mostrando la página de seguimiento con la
envolvente, la barra de % CVM y el botón de descarga de sesión.]

---

## 5. Conceptos fisiológicos y métricas (guía de interpretación)

### 5.1 Contracción Voluntaria Máxima (CVM) y normalización

La **CVM** es la máxima activación que un sujeto puede generar voluntariamente en
un músculo. Sirve de **referencia** para expresar cualquier otra activación como
**% de CVM**. Normalizar es importante porque la amplitud absoluta del EMG (en mV)
depende de factores no fisiológicos (impedancia de la piel, posición exacta de los
electrodos, anatomía); el **% CVM** permite **comparar** entre músculos, sujetos y
sesiones.

> **Cómo se mide la referencia.** Es el **mejor 0,2 s sostenido** de las seis
> repeticiones de calibración (tres máximas mantenidas y tres sacudidas breves),
> con el reposo de la ventana ya descontado. No es el máximo instantáneo, que una
> sola muestra de ruido podría fijar, ni el medio segundo mantenido, que se
> quedaba en la meseta: una contracción mantenida muestra un pico al empezar y
> luego una meseta, y los esfuerzos breves de la tarea alcanzan ese pico. Medida
> sobre la meseta, la tarea superaba el 100 % con la calibración bien hecha (135 %
> en el banco). El máximo de la tarea y el pico de cada contracción se miden con
> la misma ventana de 0,2 s, así que la comparación es con una sola vara.
>
> **Cómo se hace un máximo que lo sea.** Contra algo que no ceda (el canto inferior
> de la mesa), con el antebrazo apoyado y la muñeca unos 20° hacia el lado
> contrario a la acción del músculo; para el flexor, **con el puño cerrado**. Sin
> resistencia el músculo se acorta a su velocidad máxima y, por la relación
> fuerza-velocidad, desarrolla su fuerza mínima: una máxima en el aire es
> submáxima por construcción. Con la mano abierta contra la mesa la tarea llegó al
> 178 % de la referencia del flexor; con el puño cerrado, al 109 %.
>
> **Cómo se comprueba.** La ficha «Máximo de la tarea» del análisis. Entre el 90 y
> el 125 % es lo que dan las calibraciones correctas; a partir del 150 % la
> aplicación lo escribe en rojo, «no fue un máximo», en la ficha, sobre el panel
> 9 y en el informe, porque todos los porcentajes posteriores están mal en la
> misma proporción. Las repeticiones que salieron flojas se descartan en
> «Repeticiones de la calibración…» y la referencia se recalcula.

### 5.2 Medidas de amplitud: RMS, iEMG, envolvente

- **Envolvente**: curva suavizada que sigue la **intensidad** de la activación
  instantánea.
- **RMS (valor cuadrático medio)**: medida estándar de amplitud en una ventana;
  se relaciona con el **nivel de reclutamiento** y, de forma no lineal, con la
  **fuerza**.
- **iEMG (EMG integrado)**: el **área** bajo la envolvente; cuantifica la
  **actividad total** acumulada durante un periodo (esfuerzo total).

### 5.3 Contenido espectral: PSD, MNF y MDF

- **PSD (densidad espectral de potencia)**: muestra **cómo se reparte la energía
  de la señal entre las distintas frecuencias**.
- **MNF (frecuencia media)** y **MDF (frecuencia mediana)**: dos resúmenes del
  espectro. La MDF es la frecuencia que **divide el espectro en dos mitades de
  igual potencia**; la MNF es el "centro de gravedad" del espectro. Ambas
  **descienden con la fatiga**.

### 5.4 Fatiga muscular y su detección

Durante una contracción sostenida, el músculo se **fatiga**: disminuye la
**velocidad de conducción** de las fibras y cambia el patrón de reclutamiento.
Eléctricamente, esto se traduce en un **desplazamiento del espectro hacia
frecuencias más bajas** (*compresión espectral*) — es decir, **MNF y MDF
disminuyen con el tiempo**.

- El programa calcula la MDF en ventanas de un segundo (solape del 50 %), **solo
  en las ventanas en que el músculo trabajaba**, y ajusta una recta a la MDF
  frente al tiempo (panel 7 del Análisis). El veredicto sigue a esa recta:
  - **Fatiga detectada**: pendiente negativa y una recta que explica algo
    (R² ≥ 0,30) sobre al menos cuatro ventanas.
  - **No detectada**: la MDF se mantiene o sube, con una recta que ajusta.
  - **No concluyente**: la recta no ajusta (R² < 0,30), o hay menos de cuatro
    ventanas. Es lo normal en una serie de contracciones breves: el registro no
    responde a la pregunta, lo cual no es lo mismo que responder «no».
- La fatiga solo tiene sentido sobre una contracción **mantenida** de algunas
  decenas de segundos. Mezclar reposo y esfuerzo fabrica una pendiente de la nada
  (la MDF del reposo es la del amplificador, muy alta): por eso el ajuste excluye
  las ventanas quietas, y por eso en el ejercicio de fatiga conviene seleccionar
  solo el tramo mantenido.
- A menudo, la fatiga se acompaña de un **aumento de la amplitud (RMS)** para
  mantener la fuerza, de ahí el interés del panel 8 (RMS frente a MDF). Pero parte
  de esa subida procede de que cambia la cancelación de amplitud entre
  potenciales, no del reclutamiento; la prueba específica es la MDF.

[Figura sugerida: ilustración del desplazamiento del espectro a la izquierda con
la fatiga (dos PSD: inicio vs final) y un trazado de MDF descendente en el tiempo.]

### 5.5 Carga muscular ergonómica: método de Jonsson (APDF)

Para evaluar la **carga muscular sostenida** durante una tarea (ergonomía,
biomecánica, deporte) se usa el **método de Jonsson** — el análisis de la
**Función de Distribución de Probabilidad de Amplitud (APDF)** de la envolvente
normalizada a % CVM. Es un método **publicado y de dominio público** (Jonsson,
1978/1982). De la distribución acumulada se leen **tres niveles de carga**:

| Nivel | Percentil | Definición | Significado | Límite de Jonsson | La aplicación usa |
|---|---|---|---|---|---|
| **Estático** | P10 | Carga superada el **90 %** del tiempo | Carga casi continua «de fondo» | 2–5 % CVM | 5 % |
| **Mediano** | P50 | Carga superada el **50 %** del tiempo | Carga de trabajo típica | 10–14 % CVM | 14 % |
| **Pico** | P90 | Carga superada el **10 %** del tiempo | Esfuerzos altos recurrentes | 50–70 % CVM | 70 % |

- Jonsson dio los límites como un intervalo: el valor bajo para trabajo de larga
  duración (jornada entera) y el alto para tareas más cortas. La aplicación usa el
  **extremo alto** de cada intervalo, que es el adecuado para una tarea de
  laboratorio de un minuto; si el ejercicio simula una jornada, conviene leer los
  números contra el extremo bajo. La activación media se compara con el 10 %.
- Superar estos límites de forma sostenida se asocia a **fatiga** y a mayor riesgo
  de **trastornos musculoesqueléticos**. El riesgo no suele venir de los picos
  sino de un estático alto y mantenido: un músculo que nunca descansa acaba
  resintiéndose aunque trabaje a un nivel bajo.
- En el **monitor en vivo**, la carga instantánea se clasifica en **zonas**: verde
  hasta el 40 % CVM, naranja (cansancio) hasta el 70 % y roja (fatiga) por encima.
  Mide otra cosa que el APDF: el instante, no la distribución. Una tarea puede no
  pasar nunca del 40 % y tener un estático del 8 %, el doble del límite; las dos
  lecturas se complementan y conviene explicar la diferencia en la práctica.

> **Nota.** Los límites son **valores orientativos** derivados de la literatura,
> **no umbrales clínicos**; pueden ajustarse en el perfil.

[Figura sugerida: gráfico APDF anotado, con la curva acumulada y los puntos
estático/mediano/pico; al lado, la barra del monitor en vivo con las zonas
verde/naranja/roja.]

> **Una condición previa que anula la lectura.** Estos tres límites solo
> significan algo si la referencia es una contracción máxima registrada aparte.
> Con auto‑normalización la señal se divide por un percentil de sí misma, el P90
> queda cerca del 100 % por construcción y una contracción sostenida sale entera
> en rojo, lo que parece un hallazgo y no lo es. Por eso la aplicación no dibuja
> el gráfico APDF cuando la referencia es automática (§4.5).

### 5.6 Detección de inicio de contracción (onset)

El **inicio de una contracción** se detecta automáticamente cuando la envolvente
supera un **umbral** definido como la **media del reposo más k desviaciones
típicas** del propio reposo (tomado del primer segundo del registro), con un
tiempo mínimo de permanencia de 50 ms para no marcar una oscilación del ruido y
un periodo refractario de medio segundo para no marcar el mismo evento dos veces.
El parámetro **k** controla la **sensibilidad**: una k menor detecta esfuerzos más
suaves y admite más falsos positivos; una k mayor descarta el ruido y puede pasar
por alto activaciones débiles. El valor por defecto, **k = 3**, es el que
recomendaron Hodges y Bui (1996) tras comparar veintisiete variantes del método.
Por eso el registro debe empezar con **unos segundos de reposo**: sin línea base
no hay umbral que calcular.

### 5.7 Coactivación, separación entre canales y retraso electromecánico

**Índice de coactivación (Falconer y Winter, 1985).** De toda la actividad
registrada en los dos músculos, qué fracción es actividad **compartida**, es decir,
ejercida por ambos a la vez: 0 % si trabajó uno y el otro no, 100 % si los dos
hicieron lo mismo todo el tiempo. Se calcula sobre las envolventes en % CVM de
cada músculo, con su reposo descontado, **por ventana**: una ventana es un grupo
de contracciones seguidas que la aplicación atribuyó al mismo músculo (o a los
dos) en el editor de fragmentos. Sobre un registro entero que mezcla reposo,
flexión y presa el índice produce un número que no mide nada; por eso se calcula
por maniobra. Cuando uno de los dos músculos no llega al 5 % CVM de media en la
ventana, la fila dice **«no se informa»** con su razón: en una flexión limpia el
extensor calla, y decir «coactivación baja» sería inventar una medida. Con una
presa firme, en cambio, los dos trabajan y el índice sale alto.

**Por qué el protocolo incluye una presa.** Con solo flexiones y extensiones el
índice diría «no se informa» en todas las filas: es la respuesta correcta, pero es
un resultado nulo, y el alumnado no llegaría a ver funcionar lo que la práctica
mide. La presa es la única maniobra de este montaje en la que los dos músculos
trabajan a la vez. Se prefirió a las dos alternativas evidentes. La cocontracción
voluntaria («rigidice la muñeca sin moverla») también da número, pero es una
instrucción artificial, sin función, que cada sujeto interpreta a su manera;
sostener un peso con la muñeca neutra activa los dos músculos demasiado poco, con
medias que rozan el suelo del 5 %. La presa es una tarea real que nadie tiene que
aprender, activa mucho los dos músculos y tiene lectura clínica inmediata.

| Maniobra | Qué hacen los dos músculos | Qué da el índice |
|---|---|---|
| Flexiones | trabaja el flexor; el extensor no llega al suelo del 5 % | no se informa |
| Extensiones | los papeles se intercambian | no se informa |
| Presa | los dos trabajan a la vez | número alto, del orden del 60–95 % |
| Alternancia rápida | los dos trabajan, pero por turnos | número bajo |

La lección de fondo es que la coactivación es una propiedad de la **tarea** y no
del músculo. El contraste entre la presa y la alternancia rápida es el más útil de
los cuatro: en las dos trabajan los dos músculos, pero solo en la presa trabajan a
la vez, que es exactamente lo que el índice mide y no la cantidad de actividad.

**La fisiología de la presa.** Los flexores de los dedos son extrínsecos y sus
tendones cruzan la muñeca, de modo que al cerrar el puño generan un momento flexor
que la doblaría; los extensores radiales del carpo lo contrarrestan y la mantienen
en ligera extensión, que es la longitud a la que esos flexores dan más fuerza, y
por eso la fuerza de presa cae con la muñeca flexionada (Beringer y cols., 2020).
Medidos con sEMG durante combinaciones de presa y fuerza de muñeca, los extensores
se mantienen activos de forma continua, sin periodos de actividad baja, mientras
que los flexores sí dependen de la tarea; los autores señalan ese trabajo
sostenido como el mecanismo probable de que los extensores desarrollen lesiones
crónicas por sobreuso con más frecuencia (Forman y cols., 2021). De ahí el gancho
clínico de la práctica: la epicondilitis lateral es una lesión por presa repetida y
no por extender la muñeca. En el laboratorio hay un detalle de postura del que
depende todo: **la muñeca tiene que quedar en el aire, fuera del borde de la mesa**.
Apoyada, el tablero hace de estabilizador, el extensor afloja y la maniobra deja de
medir lo que se pretende.

**Separación entre canales.** Durante el máximo de un músculo, el otro canal nunca
está en silencio: parte es coactivación real (el antagonista sujeta la
articulación) y parte es la señal del primero conducida por el tejido hasta el
segundo par. El asistente lo mide al calibrar y lo escribe en el registro de
eventos y en el informe. Con los electrodos bien situados en el antebrazo sale
entre el 10 y el 25 % de la propia referencia; por encima del 50 % el panel termina
en **«Canales sin separar»**, porque entonces los dos pares están leyendo el mismo
músculo y todo lo que se compare después está midiendo lo mismo dos veces.

**Retraso electromecánico (EMD).** En la práctica de cinemática, con el
acelerómetro sobre el segmento que se mueve, la tabla de contracciones da para
cada esfuerzo el tiempo entre el inicio de la señal eléctrica y el inicio del
movimiento, ambos medidos donde cada señal alcanza la quinta parte de su propio
pico. Es el tiempo que tarda el músculo en liberar el calcio, formar puentes y
tensar sus elementos elásticos: 30–100 ms en adultos sanos, 35–80 ms en
contracciones voluntarias (Cavanagh y Komi, 1979).

### 5.8 Valores orientativos

Los rangos que la aplicación muestra en gris bajo las fichas y en los «?» de las
tablas. Son **orientativos**, para EMG de superficie en adultos sanos: dependen del
músculo, de los electrodos y del sujeto, y un valor fuera de rango es una pregunta,
no un fallo.

| Medida | Rango orientativo | Fuente |
|---|---|---|
| Frecuencia media (MNF) | 80–170 Hz | el grueso de la energía del EMG de superficie está entre 50 y 150 Hz; la MNF queda algo por encima de la MDF por la cola del espectro (Phinyomark, 2012) |
| Frecuencia mediana (MDF) | 60–150 Hz; en el antebrazo, 90–150 | la misma banda; banco de emgteach: FCR y ECR entre 86 y 127 Hz con buen montaje, 176 Hz con el electrodo mal situado |
| RMS en reposo | ≈ 0,005–0,02 mV | ruido de fondo del amplificador y la piel, ≥ 8 µV pico a pico en el mejor caso (McManus, 2020) |
| RMS en esfuerzo | 0,1–1 mV; máximos hasta ~1,5 mV | electrodos de superficie sobre músculos de extremidad |
| Esfuerzo de tarea | 20–80 % CVM | esfuerzos submáximos típicos |
| Máximo de la tarea con buena calibración | 90–125 % CVM | sesiones de banco de emgteach; aviso en rojo a partir del 150 % |
| Coactivación del antagonista | 5–10 % CVM en esfuerzos suaves; 25–35 % en máximos | tríceps durante la flexión máxima del codo ≈ 26 % CVM; extensor de los dedos durante la flexión de muñeca al 75 % ≈ 15 % |
| Índice de coactivación | recíproco: «no se informa»; presa firme: 60–95 % | Falconer y Winter (1985); Ervilha (2012) sobre coactivación voluntaria |
| Separación entre canales | ≤ 20–25 % de la propia referencia | banco de emgteach con electrodos bien situados |
| Carga estática, mediana, pico | ≤ 2–5, 10–14, 50–70 % CVM (la aplicación: 5, 14, 70) | Jonsson (1978, 1982) |
| Retraso electromecánico | 30–100 ms; voluntario 35–80 | Cavanagh y Komi (1979): bíceps 41 ± 13 ms, tríceps 26 ± 11 ms |
| Temblor fisiológico | pico a 8–12 Hz | acelerometría de la postura mantenida |
| Umbral de inicio | reposo + 3 desviaciones típicas | Hodges y Bui (1996) |

---

## 6. Formatos de archivo y reproducibilidad

### 6.1 EDF+ y la escritura fiable

Los registros se guardan en **EDF+** (*European Data Format*), un estándar
ampliamente usado en electrofisiología, legible por herramientas como
**MNE‑Python** o **EDFbrowser**. emgteach usa un **patrón de escritura con búfer**
(*buffered‑write*) que evita un fallo de corrupción silenciosa que puede producirse
al escribir EDF durante la transmisión en tiempo real (descrito en una publicación
metodológica del autor).

**El rango físico viaja en la cabecera.** Cada registro guarda su propio rango
físico dentro del archivo EDF, y se relee con él. Ese valor es lo que distingue un
registro de BITalino anterior a la corrección de ganancia de uno posterior:
**1,65 mV** en los anteriores, **1,635 mV** en los corregidos (§2.4). Para llevar
una amplitud antigua a la escala nueva, el factor es 1000/1009 = 0,99108.

### 6.2 Anotaciones (marcadores)

Los inicios automáticos de contracción y las **fases de la sesión** (calentamiento,
cada repetición de calibración con su músculo y su número, preparación, inicio del
registro) se guardan como **anotaciones EDF+**, junto con la referencia de CVM de
cada canal. Así el contexto del registro viaja **dentro del propio archivo**: el
análisis recalcula la referencia desde los tramos marcados, sabe qué parte del
fichero es la tarea y puede descartar una repetición sin tocar la señal. Se
reservan cuatro señales de anotación, porque una sola admite unas cinco por
segundo y una sesión guiada escribe ráfagas de ellas.

### 6.3 Informes PDF

Los informes son **autocontenidos y reproducibles**: incluyen los gráficos
elegidos, una tabla de métricas y un **pie con la versión del programa y la fecha**
de generación, y se guardan automáticamente junto al EDF de origen.

---

## 7. Flujos de trabajo típicos (paso a paso)

Cada flujo empieza por el mismo gesto: **elegir la práctica** en el selector de la
esquina superior derecha (§4.1). De esa elección se derivan el número de canales,
el acelerómetro y las medidas que se ofrecen después.

### 7.1 Contracción de un músculo

1. **Práctica**: *Contracción de un músculo* (nivel básico).
2. **Adquisición.** Conectar, escribir el identificador de prueba, *Iniciar
   grabación*. Si el ejercicio necesita % CVM (escalones de esfuerzo, fatiga,
   carga), pulsar **«Calibrar CVM»** de inmediato: el asistente pide el
   calentamiento y los seis esfuerzos máximos contra la mesa, con el puño cerrado.
   Después, la tarea; los inicios se marcan solos. *Detener grabación*.
3. **Análisis.** Se analiza solo. Seguir los dos cuadros guiados: revisar las
   **repeticiones de la calibración** y, en los **fragmentos**, dejar solo la tarea
   (desmarcando los seis esfuerzos de calibración si los hubo). Leer la tabla de
   contracciones (una fila por esfuerzo, con RMS, pico en % CVM y MDF), las fichas
   del resumen contra sus rangos, y los paneles 1A, 2 y 3; para la fatiga, el
   panel 7 desde «Más paneles…». Comprobar la ficha «Máximo de la tarea». Generar
   el **informe PDF**.
4. **Normalización CVM.** Recibe el registro y calcula sola. Con «Seleccionar
   fragmentos…» dejar solo la tarea, y leer los niveles P10, P50 y P90 contra sus
   límites. Generar su informe.

Los ejercicios 1a a 1d del guion de prácticas siguen este flujo.

### 7.2 Contracción agonista / antagonista

1. **Práctica**: *Contracción agonista / antagonista* (nivel intermedio). El
   registro pasa a dos canales y la caja del dispositivo dice «BITalino».
2. **Adquisición.** Se etiquetan los dos músculos en el orden de los canales (FCR
   en A1, ECR en A2). Al pulsar *Iniciar grabación*, el asistente calibra los dos
   músculos (puño cerrado contra la mesa para el flexor, dorso de la mano para el
   extensor), mide la separación entre canales, y tras 5 s de preparación abre el
   registro. La señal en bruto se dibuja apilada, un carril por músculo, y las
   envolventes superpuestas. Maniobras: flexiones, extensiones y una presa.
3. **Análisis.** Se analiza solo. Revisar las repeticiones de los dos músculos y
   aceptar los fragmentos: la columna «Músculo» ya dice quién llevó cada
   contracción, medido en % CVM de cada uno. Leer el panel **9. Envolventes
   superpuestas** (en % CVM, con la banda del 100 %), el **3. PSD** y el **7.
   MDF frente al tiempo** con los dos músculos, la tabla de contracciones y la
   **tabla de coactivación**, una fila por maniobra. Si el archivo tuviera un solo
   canal, se avisa y se propone la práctica que le corresponde.
4. **Normalización CVM.** Se normaliza un canal cada vez, con la referencia que el
   propio fichero lleva para ese músculo.

### 7.3 Cinemática muscular

1. **Práctica**: *Cinemática muscular* (nivel avanzado). Aparecen la gráfica del
   acelerómetro, su caja de ajustes y los controles finos.
2. **Cableado y colocación del sensor.** El músculo en A1 y el acelerómetro en A2,
   como dice la caja. Se elige entre sobre el músculo (MMG) o sobre el segmento
   que se mueve (temblor, fuerza-velocidad, retraso electromecánico).
   **«Ensayar…»** corre el procedimiento de fuerza-velocidad sin hardware, con una
   señal simulada.
3. **Adquisición.** Para la curva de fuerza-velocidad, **«F-V guiada…»** pide el
   plan (cargas, repeticiones por carga, preparación), inicia la grabación si hace
   falta y dirige la serie: un máximo isométrico sin carga de 3 s y después cada
   repetición de cada carga, marcadas en el EDF con su carga. Para el retraso
   electromecánico bastan flexiones rápidas sueltas; para el temblor, una postura
   mantenida.
4. **Análisis.** Paneles **10. EMG frente a MMG**, **11. Temblor** y **12.
   Movimiento frente a EMG**; la tabla de contracciones con la columna **EMD**; y
   **«Estudio fuerza-velocidad…»**, que devuelve las curvas carga-velocidad,
   fuerza-velocidad, potencia y reclutamiento.

### 7.4 Monitorización de carga en vivo (ergonomía)

1. Conectar e **Iniciar grabación**.
2. Pulsar **Calibrar CVM** y seguir al asistente: calentamiento, tres máximas
   mantenidas y tres sacudidas, contra la mesa.
3. Realizar la tarea observando las **barras de carga**: si entran en naranja
   (cansancio, más del 40 %) o rojo (fatiga, más del 70 %), conviene intervenir
   (pausa, cambio de postura). Si una contracción cualquiera pasa del 100 %, la
   calibración no fue máxima: repetirla.

Los umbrales de esos avisos están en el perfil de señal, no en la interfaz.

### 7.5 Sesión de laboratorio con seguimiento en móviles

1. En cada puesto, **una persona** conecta el BITalino e **Inicia grabación** en su
   PC.
2. Activa **«Difundir a móviles (en laboratorio)»** y comparte la dirección con su
   grupo, con el botón de copiar el enlace o mostrando el **QR** (todos en la misma
   Wi‑Fi).
3. El resto del grupo abre esa dirección en el móvil y **sigue** la señal, la
   calibración y las marcas. Al terminar, cada alumno/a puede **descargar la sesión
   (CSV)** y, tras el análisis del operador/a, el **informe y los resultados** en su
   teléfono.

La casilla está a la vista en los tres modos, así que este flujo se superpone a
cualquiera de los tres anteriores.

[Figura sugerida: diagrama de flujo de los tres modos, con el seguimiento en
móviles como capa común (1 operador → N seguidores).]

---

## 8. Idioma y configuración

- La interfaz es **bilingüe (español/inglés)**; el idioma se detecta del sistema
  al arrancar y se puede cambiar desde el selector de la esquina superior derecha
  (el cambio se aplica al reiniciar). Los botones de los diálogos del sistema
  (*Sí*, *No*, *Aceptar*, *Cancelar*, *Guardar*) los dibuja Qt y salen también en
  español.
- El **español de la aplicación trata siempre de usted, o habla en impersonal**.
  El criterio es infinitivo o «hay que» para las instrucciones, «conviene» para
  las recomendaciones, y tercera persona simple en los textos de ayuda que
  describen lo que hace un control.
- **Ajustes que persisten entre sesiones**: la práctica elegida, el idioma, el
  dispositivo y su dirección, la ruta de salida, las etiquetas de los músculos, el
  identificador de prueba, el plan de fuerza-velocidad y la casilla «Mostrar esta
  guía la próxima vez» (§4.2). La práctica se aplica en caliente, sin reiniciar.
- Los **parámetros por defecto** (filtros, percentil CVM, límites de carga,
  duración de calibración, etc.) están centralizados y son ajustables.

---

## 9. Resolución de problemas (FAQ)

### La interfaz no ofrece lo que se busca

**Falta el selector de dispositivo.** Solo aparece en la práctica de un músculo;
las otras dos necesitan el BITalino y la caja lo dice. La dirección sigue siendo
editable.

**Falta el selector de número de canales, o la casilla del acelerómetro.** No
existen como controles: los fija la **práctica** (§4.1). Para registrar dos
canales, *Contracción agonista / antagonista*; para el acelerómetro, *Cinemática
muscular*.

**Faltan los controles finos (región, corte de la envolvente, EDF afinado).**
Pertenecen a la práctica de cinemática. No hay casilla de «opciones avanzadas».

**Un panel de análisis ha desaparecido y estaba marcado.** La práctica activa no
lo abre por defecto. **«Más paneles…»** lo revela; al volver a la práctica que lo
ofrece se restaura marcado como estaba.

**No aparece el cuadro guía del análisis.** Espera a que la pestaña de Análisis
esté en pantalla; si se cerró, la línea «Siguiente: …» bajo la caja de parámetros
dice lo mismo.

**La guía interactiva no arranca.** No se inicia con un registro en marcha. Hay
que detener la grabación y pulsar de nuevo **«Guía»**.

### Lo que dicen los resultados

**«Máximo de la tarea: … no fue un máximo», en rojo.** El registro pasa del 150 %
de la referencia: la calibración no fue una contracción máxima y todos los
porcentajes están altos en la misma proporción. Repetirla contra la mesa, con el
puño cerrado, manteniendo los cuatro segundos; y revisar en «Repeticiones de la
calibración…» si alguna repetición floja está bajando la referencia (§5.1).

**La tabla de coactivación dice «no se informa».** Uno de los dos músculos no
llegó al 5 % CVM de media en esa ventana: en una flexión o una extensión limpias
es la respuesta correcta. Para que el índice dé número hace falta una maniobra
en que los dos trabajen, como una presa firme (§5.7).

**La tabla de coactivación dice «registro completo».** Ninguna contracción tiene
nombre: abrir «Seleccionar fragmentos…» y aceptar lo que propone. La aplicación
rellena sola qué músculo llevó cada una.

**«Canales sin separar» al terminar de calibrar.** Durante el máximo de un
músculo el otro canal leyó más del 50 % de su propia referencia: los dos pares
están viendo el mismo músculo. Separar los pares hacia el borde cubital y el
dorsal, comprobar que cada uno está sobre su vientre y apoyar el antebrazo
(§5.7).

**«Fatiga: no concluyente».** La recta de la MDF no ajusta, o hay menos de cuatro
ventanas de trabajo: el registro no responde a la pregunta. Es lo esperable en una
serie de contracciones breves. Para medir fatiga hace falta una contracción
mantenida de decenas de segundos, y seleccionar solo ese tramo (§5.4).

**Una MDF muy alta (más de 150 Hz) en un solo músculo.** Suele ser el electrodo:
demasiado cerca del tendón o sobre otro músculo. Comparar con la del otro canal y
mover el par uno o dos centímetros hacia el vientre.

### Conexión y dispositivo

**El dispositivo no conecta, o el LED se queda en amarillo.**
- *BITalino*: conviene comprobar la dirección MAC y que el dispositivo esté
  emparejado por Bluetooth. Es preferible la **dirección MAC** al número de COM:
  la MAC es la misma en cualquier ordenador, el número de COM no.
- *Arduino + MyoWare*: hay que comprobar el **puerto COM** (el botón *Refrescar*
  lista los puertos disponibles) y el cable USB.
- El **watchdog** fuerza la desconexión si no llegan datos en unos 3 s. Después
  hay que reconectar e intentarlo de nuevo.

### Calidad de la señal

**Línea plana o sin señal.** Hay que comprobar el contacto de los electrodos y el
de referencia, la ganancia, y que el canal mostrado sea el correcto.

**Interferencia de red a 50 Hz, o señal muy ruidosa.** Conviene asegurar un buen
contacto de los electrodos, ya que el filtro notch elimina los 50 Hz pero el mal
contacto amplifica el ruido, y alejar cargadores y cables de red.

**Deriva de la línea base, o picos.** Suele deberse al movimiento de electrodos o
cables: hay que fijar los cables y volver a limpiar la piel.

**Aviso de «posible saturación».** La señal llega a los límites del conversor. Hay
que bajar la ganancia o revisar los electrodos.

**Aviso de «línea base plana».** Poca o ninguna señal: conviene revisar el
contacto.

**Estos dos avisos aparecen también al abrir un archivo**, en la pestaña de
análisis y en la de CVM, cada una en su propio registro de eventos. Son el error
más común en una práctica: un canal declarado y nunca conectado.

### Monitor de carga en vivo y calibración

**«Calibración fallida (sin señal)».** Hay que estar **grabando** y contraer **al
máximo** durante la ventana de calibración.

**Las barras dicen «sin calibrar».** Hay que pulsar **Calibrar CVM** mientras se
graba.

**La carga en vivo parece incorrecta.** Conviene recalibrar: la referencia CVM es
por sesión de grabación y se reinicia al empezar una grabación nueva.

### Análisis e informes

**El EDF no abre, o se analiza el canal equivocado.** Hay que comprobar el archivo
y el **nombre del canal** (la lista se rellena desde la cabecera del EDF).

**Aviso de que el registro no coincide con el modo.** El archivo tiene un solo
canal EMG y el modo agonista / antagonista necesita dos. El propio aviso propone
el modo que le corresponde.

**«Generar informe PDF» no hace nada.** Hay que realizar primero un análisis: el
botón se activa tras un análisis correcto.

**El informe es ilegible con un registro largo.** Conviene elegir un **rango
temporal más corto** en el diálogo del informe (por defecto, la ventana visible).

**El gráfico APDF sale vacío, con un texto en su lugar.** El resultado está
auto‑normalizado y el análisis de carga necesita un registro de referencia CVM
(§4.5).

### Seguimiento en móviles

**El móvil no abre la página.** Hay que comprobar que está en la **misma red
Wi‑Fi** que el PC y que la dirección se escribe **tal cual**, empezando por
**`http://`** y no `https://`. Algunos navegadores fuerzan HTTPS, de modo que
conviene escribir el `http://` de forma explícita.

**La dirección no carga en ningún móvil.** El *firewall* de Windows puede bloquear
el puerto la primera vez: hay que permitir el acceso de **emgteach** en «redes
privadas». Conviene comprobar también que la IP mostrada es la de la red del
laboratorio y no la de una VPN.

**El enlace de la práctica anterior ya no vale.** Es el comportamiento previsto.
Cada activación de la difusión genera un código de sesión nuevo, y los enlaces
antiguos caducan en cuanto esa difusión se detiene.

**Los seguidores no ven la señal.** Deben conectarse **después** de activar la
difusión y con una **grabación en curso**: la vista se actualiza al llegar datos.

**No aparecen los resultados ni las descargas en el móvil.** Los resultados se
envían cuando el operador/a **ejecuta el análisis**, y el PDF o el CSV cuando los
genera o exporta en la pestaña Análisis, con la difusión activa.

### Software e instalación

**La aplicación no arranca.** Hay que usar **Python 3.10–3.12** en el entorno
virtual del proyecto. Python 3.13 y posteriores no están soportados todavía,
porque la pila científica no tiene *wheels*.

---

## 10. Glosario

- **sEMG**: electromiografía de superficie.
- **PAUM**: potencial de acción de unidad motora.
- **Envolvente**: curva suavizada de la amplitud de activación.
- **RMS**: valor cuadrático medio (amplitud).
- **iEMG**: EMG integrado (área bajo la envolvente).
- **PSD**: densidad espectral de potencia.
- **MNF / MDF**: frecuencia media / mediana del espectro.
- **CVM**: contracción voluntaria máxima.
- **% CVM**: amplitud expresada como porcentaje de la CVM.
- **APDF**: función de distribución de probabilidad de amplitud (método de Jonsson).
- **Estático / Mediano / Pico (P10/P50/P90)**: niveles de carga muscular.
- **Onset**: inicio de contracción.
- **EDF+**: formato de archivo estándar para biopotenciales.
- **Seguimiento en móviles**: retransmisión de la sesión en vivo por la red local
  para que los alumnos la sigan (solo lectura) desde el navegador del móvil.
- **Práctica**: la elección que configura la aplicación (un músculo, agonista /
  antagonista o cinemática muscular), con su nivel (básico, intermedio, avanzado).
- **Máximo de la tarea**: el 0,2 s más fuerte de la tarea como porcentaje de la
  referencia; por encima del 150 %, la calibración no fue máxima.
- **Índice de coactivación (Falconer-Winter)**: fracción de la actividad de los dos
  músculos que fue compartida, por ventana; «no se informa» cuando uno no trabajó.
- **Separación entre canales**: lo que un canal lee del otro músculo durante su
  máximo, en % de su propia referencia.
- **Retraso electromecánico (EMD)**: tiempo entre el inicio de la señal eléctrica y
  el inicio del movimiento.
- **Repetición de calibración**: cada uno de los seis esfuerzos máximos por músculo
  (tres mantenidos, tres breves) marcados en el fichero.

---

## 11. Referencias

- Jonsson, B. (1978). *Kinesiology: with special reference to electromyographic
  kinesiology.* Electroencephalography and Clinical Neurophysiology, Suppl. 34,
  417–428. (Y Jonsson, B. (1982), *Journal of Human Ergology*, 11, 73–88.)
- Agis‑Torres, Á. (2026). *emgteach: an open‑source teaching platform for surface
  electromyography* (software). Zenodo.
- Agis‑Torres, Á. (2026). *Silent corruption of EDF recordings during real‑time
  biopotential streaming: a buffered‑write solution* (paquete de reproducibilidad).
- Cavanagh, P. R., y Komi, P. V. (1979). Electromechanical delay in human skeletal
  muscle under concentric and eccentric contractions. *European Journal of Applied
  Physiology*, 42, 159–163.
- Falconer, K., y Winter, D. A. (1985). Quantitative assessment of co‑contraction
  at the ankle joint in walking. *Electromyography and Clinical Neurophysiology*,
  25, 135–149.
- Hodges, P. W., y Bui, B. H. (1996). A comparison of computer‑based methods for the
  determination of onset of muscle contraction using electromyography.
  *Electroencephalography and Clinical Neurophysiology*, 101, 511–519.
- McManus, L., De Vito, G., y Lowery, M. M. (2020). Analysis and biophysics of
  surface EMG for physiotherapists and kinesiologists. *Frontiers in Neurology*,
  11, 576729.
- Phinyomark, A., Thongpanja, S., Hu, H., Phukpattaranont, P., y Limsakul, C.
  (2012). The usefulness of mean and median frequencies in electromyography
  analysis. En *Computational Intelligence in Electromyography Analysis* (pp.
  195–220). InTech.
- Ervilha, U. F., Graven‑Nielsen, T., y Duarte, M. (2012). A simple test of muscle
  coactivation estimation using electromyography. *Brazilian Journal of Medical and
  Biological Research*, 45, 977–981.
- Beringer, C. R., Mansouri, M., Fisher, L. E., Collinger, J. L., Munin, M. C.,
  Boninger, M. L., y Gaunt, R. A. (2020). The effect of wrist posture on extrinsic
  finger muscle activity during single joint movements. *Scientific Reports*, 10,
  8377.
- Forman, D. A., Forman, G. N., y Holmes, M. W. R. (2021). Wrist extensor muscle
  activity is less task‑dependent than wrist flexor muscle activity while
  simultaneously performing moderate‑to‑high handgrip and wrist forces.
  *Ergonomics*, 64(12). doi:10.1080/00140139.2021.1934564

---

## 12. Anexo — Lista de figuras/capturas sugeridas (checklist para el manual)

1. Ventana principal con las tres pestañas y el selector de práctica.
2. Esquema fisiológico: motoneurona → fibras → electrodo → señal sEMG.
3. Colocación de electrodos en un músculo (activo / referencia).
4. Cadena de procesado: en bruto → filtrada → rectificada → envolvente.
5. Pestaña Adquisición (2 canales) anotada.
6. Detalle del monitor de carga en vivo (barras con zonas de color).
7. Pestaña Análisis con los paneles del núcleo docente + resumen + navegador.
8. Ejemplo de informe PDF de Análisis (2 páginas).
9. Pestaña CVM con los 3 paneles, el gráfico APDF y el panel de datos.
10. Detalle del panel de datos con un valor fuera de rango (rojo) + explicación.
11. Ilustración de la fatiga: desplazamiento espectral + MDF descendente.
12. Gráfico APDF anotado con los niveles estático/mediano/pico y las zonas.
13. Diagrama de flujo de los flujos de trabajo típicos.
14. Seguimiento en móviles: móvil del alumnado con la envolvente, la barra de
    % CVM y el botón de descarga de sesión.
15. Selector de práctica desplegado, con la banda de nivel al lado.
16. Un paso de la guía interactiva, con la pantalla oscurecida y el control
    resaltado.
17. La banda inferior de Análisis con sus tres cuadros: coactivación,
    contracciones y resumen en fichas, con un «Máximo de la tarea» en rojo.
18. El asistente de calibración en una sacudida breve, con la barra de esfuerzo.
19. La tabla de contracciones de un registro del par, con la columna «Músculo».

> **Sugerencia de tono para el manual:** combinar instrucciones prácticas ("cómo
> se hace") con recuadros de "¿qué significa fisiológicamente?" junto a cada
> métrica, de forma que sirva tanto de guía de uso como de material docente.
