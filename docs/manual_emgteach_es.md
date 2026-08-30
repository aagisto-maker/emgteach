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

- **Registrar** la actividad eléctrica muscular en tiempo real, con las
  plataformas BITalino o Arduino + MyoWare, en **uno o dos canales**
  (p. ej. músculo agonista y antagonista) y, si la práctica lo pide, con el
  **acelerómetro**.
- **Visualizar** en vivo la señal en bruto, filtrada y su envolvente, marcar
  eventos (manual o automáticamente) y **monitorizar la carga muscular en
  tiempo real** con avisos de cansancio/fatiga.
- **Analizar** un registro a posteriori: amplitud (RMS), contenido espectral
  (PSD, frecuencia media y mediana) e **indicadores de fatiga muscular**.
- **Normalizar** la señal respecto a la **Contracción Voluntaria Máxima (CVM)**
  y evaluar la **carga muscular** según el método de Jonsson (ergonomía).
- **Exportar informes PDF** reproducibles de la sesión.

Los archivos se guardan en formato estándar **EDF+** (compatible con otras
herramientas como MNE‑Python o EDFbrowser).

La aplicación se organiza en **tres pestañas**: **Adquisición**, **Análisis** y
**CVM** (normalización a la contracción máxima). Antes que ellas está el
**selector de práctica**, con tres modos, del que se derivan el número de canales,
el uso del acelerómetro y las medidas que cada pestaña ofrece (§4.1).

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
| Percentil para la referencia CVM | 95 | Referencia robusta de máximo (ver §6.1) |

[Figura sugerida: cuatro trazados apilados del mismo tramo —en bruto, filtrado,
rectificado y envolvente— para ilustrar la cadena de procesado.]

---

## 4. La interfaz: primero la práctica, después las tres pestañas

### 4.1 Elegir la práctica

En la esquina superior derecha de la ventana, en la misma fila que el selector de
idioma, hay un desplegable con tres opciones. Es el primer control que se toca en
cada sesión: fija qué se registra, y las tres pestañas se configuran a partir de
ahí.

| Modo | Canales EMG | Acelerómetro | Prácticas del cuaderno |
|---|---|---|---|
| **Contracción de un músculo** | 1 | no | 1, 2, 4 y 5 |
| **Contracción agonista / antagonista** | 2 | no | 3 |
| **Cinemática muscular** | 1 | sí | 6 |

El modo **decide lo que se registra**, y no se limita a filtrar lo que se ve. Fija el
número de canales y el uso del acelerómetro, y cada pestaña ofrece solo las
medidas que tienen sentido para esa práctica. Por eso han desaparecido de la
pantalla el selector de número de canales y la casilla del acelerómetro: eran
controles que solo podían contradecir al modo elegido, y un montaje de dos
músculos elegido en un modo podía sobrevivir a un cambio de modo que ya no tenía
forma de mostrarlo ni de cambiarlo.

Conviene conocer de antemano dos comportamientos que, sin explicación, parecen
caprichosos:

1. **Lo que un modo oculta, además lo desmarca**, y al volver a ese modo se
   restaura la selección anterior. Un panel que quedara marcado se seguiría
   dibujando sin forma visible de quitarlo.
2. **Una función que está funcionando no se oculta**, aunque se apaguen las
   opciones avanzadas. La detección automática de inicio, si está activa,
   permanece a la vista: una marca automática que nadie pueda parar es peor que
   un control de más.

**Opciones avanzadas.** Casilla contigua al selector, e independiente de él.
Muestra los controles finos comunes a las tres prácticas: frecuencias de corte de
los filtros, umbrales de aviso de carga, región de interés y detección automática
de inicio. Sin marcarla, la pestaña de adquisición se queda en lo imprescindible y
la de análisis ofrece tres paneles.

Hay una excepción deliberada. Si no hay ningún puerto ni dirección guardados, la
caja de conexión del dispositivo se muestra igualmente, con un aviso de primera
configuración. Sin ella, una instalación recién hecha no tendría manera de
conectar nada y la aplicación parecería rota. Una vez guardado el dispositivo, esa
caja pasa a depender de las opciones avanzadas.

**El registro manda sobre el modo.** Al abrir en modo agonista / antagonista un
EDF que solo tiene un canal, se avisa de cuántos canales tiene el archivo y se
propone el modo que le corresponde, en lugar de comportarse en silencio como un
análisis de un canal mientras el modo sigue afirmando que hay dos músculos. Con
un archivo de dos canales, en cambio, la comparación de envolventes se activa
sola.

[Figura sugerida: detalle de la esquina superior derecha con el selector de
práctica desplegado, la casilla «Opciones avanzadas», el selector de idioma y los
botones «Guía» y «?».]

[Figura sugerida: la pestaña de Adquisición en el mismo modo, con y sin opciones
avanzadas, una al lado de la otra.]

### 4.2 La guía interactiva

Recorrido que señala cada control **sobre la propia pantalla**: oscurece el resto,
rodea el control del que habla y muestra al lado qué es y qué significa
fisiológicamente. Cambia de pestaña por su cuenta cuando el recorrido lo pide.

**Sigue al modo:** 14 pasos en la contracción de un músculo, 15 en agonista /
antagonista y 17 en cinemática muscular. El acelerómetro se explica solo en la
práctica que lo usa, y la coordinación agonista / antagonista solo en la suya.

Se ofrece al arrancar, mediante un diálogo con una casilla **«Ofrecer esta guía la
próxima vez»** marcada por defecto. Un ordenador de laboratorio ve un alumno
distinto cada sesión, así que la decisión de apagarla corresponde a quien tiene el
equipo a su cargo y no a quien lo abrió primero. El botón **«Guía»**, junto al
**«?»**, la relanza en cualquier momento. Se niega a arrancar si hay un registro
en marcha.

El recorrido cubre, por este orden: la elección de la práctica y las opciones
avanzadas, los dispositivos admitidos y la conexión, las etiquetas de canal, la
colocación del acelerómetro (solo en cinemática), la grabación, el seguimiento en
móviles, los marcadores, la adquisición guiada de fuerza-velocidad (solo en
cinemática), la calibración del máximo, la fatiga en el espectro, la coordinación
agonista / antagonista (solo en su modo), el estudio de fuerza-velocidad (solo en
cinemática), la descarga de informe y datos, el sentido de normalizar y la carga
muscular.

[Figura sugerida: un paso de la guía en funcionamiento, con la pantalla oscurecida
y el control resaltado.]

### 4.3 Pestaña **Adquisición** (tiempo real)

Permite **registrar** una sesión y observarla en vivo.

**Configuración del dispositivo** (visible con las opciones avanzadas, o en una
instalación sin dispositivo guardado)
- Selección del tipo de dispositivo (BITalino o Arduino + MyoWare).
- Dirección **MAC** (BITalino) o **puerto COM** (Arduino).
- **Carpeta de destino** del archivo EDF.
- **Etiqueta** de cada canal (nombre del músculo). El número de canales ya no se
  elige aquí: lo fija el modo.

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
- Marcadores **manuales** con etiquetas predefinidas (*Inicio contracción*, *Fin
  contracción*, *Fatiga*, *Reposo*, *Otro…*) o personalizadas; se pueden insertar
  con un botón o con la tecla **M**.
- **Detección automática de inicio de contracción** (*Auto‑inicio*), entre las
  opciones avanzadas: se marca el comienzo de una contracción cuando la envolvente
  supera un **umbral** (línea base + *k*·desviación típica del reposo); la
  sensibilidad se ajusta con el parámetro **k**. (Significado en §5.6.) Si queda
  activa, sigue a la vista aunque se apaguen las opciones avanzadas.
- Las marcas se dibujan en vivo sobre las gráficas y quedan registradas como
  **anotaciones** en el EDF.

**Monitor de carga muscular en vivo (CVM en tiempo real)**
- Botón **Calibrar CVM**: durante la grabación se realizan unos segundos de
  **contracción máxima** y se calcula la **referencia CVM** por canal. La variante
  **«Mejor de 3»** está entre las opciones avanzadas.
- Tras calibrar, por cada canal se muestra una **barra de carga** que indica el
  **% de CVM actual**, con **zonas de color**: verde (normal), naranja
  (*Warning*, cansancio) y roja (*Danger*, fatiga), y los niveles **P10/P50/P90**
  (estático/mediano/pico) en tiempo real. (Significado en §5.5.) Los umbrales de
  esos avisos se editan con las opciones avanzadas.

**El acelerómetro** (solo en cinemática muscular). Se registra como un canal más,
en unidades `g` y sin calibrar. La caja de acelerómetro reúne el selector de
entrada analógica (A1–A6, por defecto A4), el botón **«Buscar canal del ACC…»** que lo
localiza leyendo las seis entradas en vivo, y el selector de colocación: sobre el
músculo (MMG) o sobre el segmento que se mueve (temblor y fuerza-velocidad). El
selector de entrada no depende de las opciones avanzadas: el valor por defecto no
acierta en todas las placas, y esconderlo dejaría un primer registro de cinemática
sin leer nada. En esta caja está también el botón **«F-V guiada…»**, que dirige la
adquisición de una serie de cargas conocidas.

[Figura sugerida: captura completa de la pestaña de Adquisición durante una
grabación de 2 canales, señalando: gráficas apiladas, controles de escala,
caja de marcadores y caja del monitor de carga con las barras de colores.]

[Figura sugerida: detalle de la caja "Carga muscular (CVM en vivo)" con una barra
en zona verde, otra en naranja/roja.]

### 4.4 Pestaña **Análisis** (desconectado)

Analiza en profundidad un registro EDF ya guardado.

**Parámetros**
- Selección del **archivo EDF** y del **canal** a analizar.
- **Frecuencia de corte de la envolvente** y **región de interés**, entre las
  opciones avanzadas.
- Datos opcionales de **alumno/a** y **código** (para el informe).

**Los doce paneles de análisis** y su significado. Los tres primeros son el núcleo
docente y se ofrecen siempre; los cinco siguientes valen para cualquier práctica y
dependen de las opciones avanzadas; los cuatro últimos pertenecen cada uno a una
práctica.

| Panel | Qué muestra | Significado | Se ofrece |
|---|---|---|---|
| **1A. Señal en bruto** | EMG sin procesar | Punto de partida; permite ver artefactos | siempre |
| **2. Envolvente normalizada** | Envolvente escalada a su máximo (0–1) | Forma de la activación, comparable | siempre |
| **3. PSD con MNF/MDF** | Densidad espectral de potencia | Reparto de energía por frecuencia; base de la fatiga | siempre |
| **4. Filtrada + rectificada** | Señal limpia y su valor absoluto | Aísla la actividad muscular real | opciones avanzadas |
| **5. Envolvente vs RMS** | Dos medidas de amplitud superpuestas | Nivel de activación en el tiempo | opciones avanzadas |
| **6. RMS por ventana** | Amplitud RMS a lo largo del tiempo | Evolución del esfuerzo | opciones avanzadas |
| **7. MDF vs tiempo (fatiga)** | Frecuencia mediana por segmento + tendencia | **Indicador de fatiga**: si desciende, hay fatiga | opciones avanzadas |
| **8. RMS vs MDF** | Relación amplitud–frecuencia | Relación fuerza/fatiga durante la tarea | opciones avanzadas |
| **9. Envolventes superpuestas** | Las dos envolventes en el mismo eje | Coactivación y coordinación | agonista / antagonista |
| **10. EMG vs MMG** | Envolvente eléctrica y mecánica | Acoplamiento electromecánico | cinemática muscular |
| **11. Temblor** | Espectro del acelerómetro | Pico de temblor fisiológico (~8–12 Hz) | cinemática muscular |
| **12. Movimiento vs EMG** | Trazado cinemático y envolvente EMG | El movimiento sigue a la contracción | cinemática muscular |

Los tres primeros vienen **marcados por defecto**. Los nombres de la tabla son los
del diálogo de informe; en la fila de casillas de la pantalla aparecen abreviados
(*1A. En bruto*, *2. Env. norm.*, *3. PSD*…).

**Resumen de métricas** (panel numérico): RMS global, frecuencia media (MNF),
frecuencia mediana (MDF), pendiente de la MDF, indicador de **fatiga**, iEMG y
duración. (Definiciones e interpretación en §5.)

**Estudio de fuerza-velocidad** (solo en cinemática muscular). Un botón toma las
repeticiones de un mismo registro, con su carga anotada en cada una, y devuelve
cuatro curvas: carga frente a velocidad, la fuerza-velocidad normalizada de forma
hiperbólica, la potencia como producto de ambas, y el reclutamiento, que es la
amplitud EMG frente a la carga.

**Navegación**: la **ventana de visualización** (minimapa) permite acotar el
tramo dibujado arrastrando con el ratón; también con la rueda del ratón sobre los
paneles.

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

**Panel de entrada.** La primera vez que se abre la pestaña en cada sesión, y de
nuevo después de *Nueva sesión*, la pestaña recibe con una explicación de qué es
una contracción voluntaria máxima y por qué hace falta un registro de referencia.
Se cierra con **«Entendido, continuar»**. La abreviatura CVM aparecía en el título
de la pestaña, en dos selectores de archivo, en el botón de calcular y en los ejes
de las gráficas, y no se expandía en ninguno.

**Entradas**
- **EDF de prueba** (la tarea a normalizar) y **EDF de referencia CVM** (una
  contracción máxima registrada aparte, con los mismos electrodos y sin
  despegarlos entre uno y otro).
- La referencia es **obligatoria** salvo que estén marcadas las opciones
  avanzadas. Solo entonces se ofrece la **auto‑normalización**, y con una
  confirmación antes de calcular cuya opción por defecto es elegir un archivo de
  referencia.

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

> La referencia CVM se calcula como el **percentil 95** de la envolvente (no el
> máximo absoluto), para que sea **robusta** frente a artefactos o picos
> espurios.

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

- El programa estima la fatiga ajustando la **MDF frente al tiempo** (panel 7 del
  Análisis) y observando su **pendiente**:
  - Pendiente **negativa** (la MDF baja) → **fatiga detectada**.
  - Pendiente plana o positiva → **sin fatiga**.
- A menudo, la fatiga se acompaña de un **aumento de la amplitud (RMS)** para
  mantener la fuerza, de ahí el interés del panel 8 (RMS vs MDF).

[Figura sugerida: ilustración del desplazamiento del espectro a la izquierda con
la fatiga (dos PSD: inicio vs final) y un trazado de MDF descendente en el tiempo.]

### 5.5 Carga muscular ergonómica: método de Jonsson (APDF)

Para evaluar la **carga muscular sostenida** durante una tarea (ergonomía,
biomecánica, deporte) se usa el **método de Jonsson** — el análisis de la
**Función de Distribución de Probabilidad de Amplitud (APDF)** de la envolvente
normalizada a % CVM. Es un método **publicado y de dominio público** (Jonsson,
1978/1982). De la distribución acumulada se leen **tres niveles de carga**:

| Nivel | Percentil | Definición | Significado | Límite orientativo |
|---|---|---|---|---|
| **Estático** | P10 | Carga superada el **90 %** del tiempo | Carga casi continua "de fondo" | ≤ ~5 % CVM |
| **Mediano** | P50 | Carga superada el **50 %** del tiempo | Carga de trabajo típica | ≤ ~14 % CVM |
| **Pico** | P90 | Carga superada el **10 %** del tiempo | Esfuerzos altos recurrentes | ≤ ~70 % CVM |

- Superar estos límites de forma sostenida se asocia a **fatiga** y a mayor riesgo
  de **trastornos musculoesqueléticos**.
- En el **monitor en vivo**, la carga actual se clasifica en **zonas**: *Normal*
  (verde), *Warning* / cansancio (naranja, por defecto a partir de ~40 % CVM) y
  *Danger* / fatiga (roja, por defecto a partir de ~70 % CVM). Esto permite
  **intervenir** (pausa, cambio de postura) antes de llegar a la fatiga.

> **Nota.** Los límites por defecto (estático 5 %, mediano 14 %, pico 70 %;
> *warning* 40 %, *danger* 70 %) son **valores orientativos** derivados de la
> literatura, **no umbrales clínicos**; pueden ajustarse.

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
supera un **umbral** definido como la **media de la línea base (reposo) más
k·desviaciones típicas**, con un tiempo mínimo de permanencia (anti‑rebote) y un
periodo refractario para no marcar el mismo evento dos veces. El parámetro **k**
controla la **sensibilidad** (menor k = más sensible).

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

Los marcadores (manuales y automáticos) se guardan como **anotaciones EDF+**, de
modo que el contexto del registro (inicios de contracción, fatiga, reposo…) viaja
**dentro del propio archivo** y se recupera al analizarlo.

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

1. **Modo**: *Contracción de un músculo*.
2. **Adquisición.** Conectar el dispositivo, etiquetar el canal con el nombre del
   músculo, *Iniciar grabación*. Se pide al sujeto la tarea y se marcan los eventos
   relevantes con la tecla **M**. *Detener grabación* (se guarda el EDF).
3. **Análisis.** Se abre el EDF, se revisan los tres paneles del núcleo docente
   (señal en bruto, envolvente normalizada y PSD) y el resumen numérico (RMS,
   MNF/MDF, fatiga). Con las opciones avanzadas se acota el tramo de interés y se
   añaden los paneles 4 a 8. Se genera el **informe PDF**.
4. **Normalización CVM.** Se registra aparte una contracción máxima como
   referencia, se normaliza la tarea a % CVM y se revisa la **carga muscular
   (APDF)**. Se genera su informe.

Las prácticas 1, 2, 4 y 5 del cuaderno siguen este flujo. La de fatiga se apoya
sobre todo en el panel 7 (MDF frente al tiempo), que requiere las opciones
avanzadas.

### 7.2 Contracción agonista / antagonista

1. **Modo**: *Contracción agonista / antagonista*. El registro pasa a dos canales
   sin tocar nada más.
2. **Adquisición.** Se etiquetan los dos canales (p. ej. bíceps y tríceps). La
   señal en bruto se dibuja apilada, un carril por músculo, y las envolventes
   superpuestas.
3. **Análisis.** Al abrir un EDF de dos canales, la comparación de envolventes se
   activa sola y aparece el panel **9. Envolventes superpuestas**. Se elige cuál de
   los dos canales lleva el resto del análisis. Si el archivo tuviera un solo
   canal, se avisa y se propone el modo que le corresponde.
4. **Normalización CVM.** Se normaliza un canal cada vez.

### 7.3 Cinemática muscular

1. **Modo**: *Cinemática muscular*. Aparecen la gráfica del acelerómetro y su caja
   de ajustes.
2. **Colocación del sensor.** Se elige entre sobre el músculo (MMG) o sobre el
   segmento que se mueve (temblor y fuerza-velocidad). Si la traza no responde al
   inclinar el sensor, se usa **«Buscar canal del ACC…»** para localizar la entrada
   analógica correcta.
3. **Adquisición.** Para la curva de fuerza-velocidad, el botón **«F-V guiada…»**
   dirige la serie: primero un máximo sin carga, después cada carga y cada
   repetición, con las elevaciones marcadas automáticamente en el EDF.
4. **Análisis.** Paneles **10. EMG vs MMG**, **11. Temblor** y **12. Movimiento vs
   EMG**, y el botón de **estudio de fuerza-velocidad**, que devuelve las curvas
   carga-velocidad, fuerza-velocidad, potencia y reclutamiento.

### 7.4 Monitorización de carga en vivo (ergonomía)

1. Conectar e **Iniciar grabación**.
2. Pulsar **Calibrar CVM** y realizar unos segundos de contracción máxima.
3. Realizar la tarea observando las **barras de carga**: si entran en naranja
   (cansancio) o rojo (fatiga), conviene intervenir (pausa, cambio de postura).

Los umbrales de esos avisos se editan con las opciones avanzadas marcadas.

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
- **Ajustes que persisten entre sesiones**: el modo de práctica, la casilla de
  opciones avanzadas, el idioma, el dispositivo y su puerto, y la casilla
  «Ofrecer esta guía la próxima vez» del recorrido guiado (§4.2). El modo y las
  opciones avanzadas se aplican en caliente, sin reiniciar.
- Los **parámetros por defecto** (filtros, percentil CVM, límites de carga,
  duración de calibración, etc.) están centralizados y son ajustables.

---

## 9. Resolución de problemas (FAQ)

### La interfaz no ofrece lo que se busca

**No aparece la caja de conexión con la MAC o el puerto.** Una vez guardado el
dispositivo, esa caja depende de las **opciones avanzadas**: hay que marcar la
casilla de la esquina superior derecha. En una instalación sin dispositivo
guardado se muestra siempre.

**Falta el selector de número de canales, o la casilla del acelerómetro.** Ya no
existen como controles: los fija el **modo de práctica** (§4.1). Para registrar
dos canales, se elige *Contracción agonista / antagonista*; para el acelerómetro,
*Cinemática muscular*.

**Un panel de análisis ha desaparecido y estaba marcado.** El modo activo no lo
usa. Al volver al modo que lo ofrece se restaura marcado como estaba.

**No se ofrece la auto‑normalización en la pestaña CVM.** Es deliberado: sin
opciones avanzadas el registro de referencia es obligatorio, porque los límites de
carga de un resultado auto‑normalizado no significan nada (§5.5).

**La guía interactiva no arranca.** No se inicia con un registro en marcha. Hay
que detener la grabación y pulsar de nuevo **«Guía»**.

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
- **Modo de práctica**: la elección que configura la aplicación (un músculo,
  agonista / antagonista o cinemática muscular).

---

## 11. Referencias

- Jonsson, B. (1978). *Kinesiology: with special reference to electromyographic
  kinesiology.* Electroencephalography and Clinical Neurophysiology, Suppl. 34,
  417–428. (Y Jonsson, B. (1982), *Journal of Human Ergology*, 11, 73–88.)
- Agis‑Torres, Á. (2026). *emgteach: an open‑source teaching platform for surface
  electromyography* (software). Zenodo.
- Agis‑Torres, Á. (2026). *Silent corruption of EDF recordings during real‑time
  biopotential streaming: a buffered‑write solution* (paquete de reproducibilidad).

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
15. Selector de práctica desplegado, con la casilla de opciones avanzadas al lado.
16. Un paso de la guía interactiva, con la pantalla oscurecida y el control
    resaltado.
17. La misma pestaña con y sin opciones avanzadas, una al lado de la otra.

> **Sugerencia de tono para el manual:** combinar instrucciones prácticas ("cómo
> se hace") con recuadros de "¿qué significa fisiológicamente?" junto a cada
> métrica, de forma que sirva tanto de guía de uso como de material docente.
