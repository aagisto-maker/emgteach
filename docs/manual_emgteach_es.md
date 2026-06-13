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

- **Registrar** la actividad eléctrica muscular en tiempo real con hardware de
  bajo coste (BITalino o Arduino + MyoWare), en **uno o dos canales**
  (p. ej. músculo agonista y antagonista).
- **Visualizar** en vivo la señal cruda, filtrada y su envolvente, marcar
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
**CVM** (normalización a la contracción máxima).

[Figura sugerida: captura de la ventana principal mostrando las tres pestañas.]

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

La señal cruda contiene componentes que no son actividad muscular útil:

- **Interferencia de red eléctrica** a 50 Hz (en Europa) y armónicos.
- **Movimiento de electrodos** y deriva de la línea base (baja frecuencia).
- **Ruido** de alta frecuencia.

Por eso la señal se **filtra** antes de interpretarla (ver §4).

[Figura sugerida: esquema "motoneurona → fibras → electrodo de superficie →
señal sEMG", con ejemplo de trazado crudo.]

---

## 2. Equipo y montaje

### 2.1 Dispositivos soportados

| Dispositivo | Conexión | Notas |
|---|---|---|
| **BITalino (revolution)** | Bluetooth | Plataforma de biopotenciales. Requiere Python ≤ 3.11. |
| **Arduino RedBoard Plus + MyoWare 2.0** | USB serie | Sensor EMG de hardware abierto; funciona en todas las versiones soportadas. |

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

### 2.4 Unidades y muestreo

- La señal se expresa en **milivoltios (mV)**.
- La **frecuencia de muestreo** nominal es de **1000 Hz** (1000 muestras por
  segundo y canal), suficiente para cubrir la banda informativa del EMG.

---

## 3. Cadena de procesado de señal (DSP) y su significado

A partir de la señal **cruda**, el programa calcula en tiempo real (y vuelve
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

**Importante (diseño del archivo):** en el EDF solo se guarda la **señal cruda**
(una por sensor). La señal filtrada y la envolvente son **funciones
deterministas** de la señal cruda y se **recalculan** al analizar; así el archivo
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

[Figura sugerida: cuatro trazados apilados del mismo tramo —crudo, filtrado,
rectificado y envolvente— para ilustrar la cadena de procesado.]

---

## 4. La interfaz: las tres pestañas

### 4.1 Pestaña **Adquisición** (tiempo real)

Permite **registrar** una sesión y observarla en vivo.

**Configuración del dispositivo**
- Selección del tipo de dispositivo (BITalino o Arduino + MyoWare).
- Dirección **MAC** (BITalino) o **puerto COM** (Arduino).
- **Carpeta de destino** del archivo EDF.
- **Número de canales** (1 o 2) y **etiqueta** de cada canal (nombre del músculo).

**Control de adquisición**
- Botones **Conectar/Desconectar** e **Iniciar/Detener grabación**.
- Un **LED** de estado de comunicación: rojo (desconectado), amarillo (conectado,
  sin tráfico), verde (recibiendo datos). Un *watchdog* fuerza la desconexión si
  el dispositivo deja de enviar datos (p. ej. pérdida de Bluetooth).

**Gráficas en tiempo real** (tres):
- **Señal EMG cruda** (mV).
- **Señal filtrada** (notch + paso‑banda).
- **Envolvente**.

Con **dos canales**, las gráficas de la señal cruda y la filtrada se muestran **apiladas**
(un "carril" por canal, con su color), mientras que la envolvente, al ser no
negativa, se **superpone** para comparar directamente ambos músculos. La escala
vertical de cada gráfica se ajusta con botones **▲▼**, y la **ventana temporal**
con un desplegable de zoom y botones ◀▶ (también con la rueda del ratón).

**Marcadores de eventos**
- Marcadores **manuales** con etiquetas predefinidas (*Inicio contracción*, *Fin
  contracción*, *Fatiga*, *Reposo*, *Otro…*) o personalizadas; se pueden insertar
  con un botón o con la tecla **M**.
- **Detección automática de inicio de contracción** (*Auto‑inicio*): el programa
  marca el comienzo de una contracción cuando la envolvente supera un **umbral**
  (línea base + *k*·desviación típica del reposo); la sensibilidad se ajusta con
  el parámetro **k**. (Significado en §6.6.)
- Las marcas se dibujan en vivo sobre las gráficas y quedan registradas como
  **anotaciones** en el EDF.

**Monitor de carga muscular en vivo (CVM en tiempo real)** *(novedad)*
- Botón **Calibrar CVM**: durante la grabación, el usuario realiza unos segundos
  de **contracción máxima**; el programa calcula la **referencia CVM** por canal.
- Tras calibrar, por cada canal se muestra una **barra de carga** que indica el
  **% de CVM actual**, con **zonas de color**: verde (normal), naranja
  (*Warning* — cansancio) y roja (*Danger* — fatiga), y los niveles **P10/P50/P90**
  (estático/mediano/pico) en tiempo real. (Significado en §6.5.)

[Figura sugerida: captura completa de la pestaña de Adquisición durante una
grabación de 2 canales, señalando: gráficas apiladas, controles de escala,
caja de marcadores y caja del monitor de carga con las barras de colores.]

[Figura sugerida: detalle de la caja "Carga muscular (CVM en vivo)" con una barra
en zona verde, otra en naranja/roja.]

### 4.2 Pestaña **Análisis** (offline)

Analiza en profundidad un registro EDF ya guardado.

**Parámetros**
- Selección del **archivo EDF** y del **canal** a analizar.
- **Frecuencia de corte de la envolvente** (editable).
- Datos opcionales de **alumno/a** y **código** (para el informe).

**Los 8 paneles de análisis** (seleccionables) y su significado:

| Panel | Qué muestra | Significado |
|---|---|---|
| **1A. Señal cruda** | EMG sin procesar | Punto de partida; permite ver artefactos |
| **1B. Filtrada + rectificada** | Señal limpia y su valor absoluto | Aísla la actividad muscular real |
| **2. Envolvente vs RMS** | Dos medidas de amplitud superpuestas | Nivel de activación en el tiempo |
| **3. Envolvente normalizada** | Envolvente escalada a su máximo (0–1) | Forma de la activación, comparable |
| **4. PSD con MNF/MDF** | Densidad espectral de potencia | Reparto de energía por frecuencia; base de la fatiga |
| **5. RMS por ventana** | Amplitud RMS a lo largo del tiempo | Evolución del esfuerzo |
| **6. MDF vs tiempo (fatiga)** | Frecuencia mediana por segmento + tendencia | **Indicador de fatiga**: si desciende, hay fatiga |
| **7. RMS vs MDF** | Relación amplitud–frecuencia | Relación fuerza/fatiga durante la tarea |

**Resumen de métricas** (panel numérico): RMS global, frecuencia media (MNF),
frecuencia mediana (MDF), pendiente de la MDF, indicador de **fatiga**, iEMG y
duración. (Definiciones e interpretación en §6.)

**Navegación**: la **ventana de visualización** (minimapa) permite acotar el
tramo dibujado arrastrando con el ratón; también con la rueda del ratón sobre los
paneles.

**Informe PDF**: el botón *Generar informe PDF* abre un diálogo para **elegir qué
gráficos** incluir y el **rango temporal** a representar (por defecto, la ventana
visible). El PDF incluye cabecera (con alumno/a y archivo), los gráficos elegidos,
una **tabla de métricas** y un pie reproducible (versión y fecha).

[Figura sugerida: captura de la pestaña de Análisis con los 8 paneles, señalando
el resumen numérico y el navegador temporal.]

[Figura sugerida: ejemplo de informe PDF de Análisis (1ª página con gráficos y
2ª con la tabla de métricas).]

### 4.3 Pestaña **CVM** (normalización a la Contracción Voluntaria Máxima)

Expresa la señal como **porcentaje de la CVM** y evalúa la **carga muscular**.

**Entradas**
- **EDF de prueba** (la tarea a normalizar) y, opcionalmente, **EDF de referencia
  CVM** (una contracción máxima registrada aparte). Si no se proporciona, se usa
  **auto‑normalización** (la propia señal de prueba como referencia).

**Los 3 paneles temporales**
1. Señal **filtrada y rectificada**.
2. **Envolvente** con la **línea de amplitud de referencia CVM**.
3. Señal **normalizada (% CVM)**, con la línea del 100 %.

**Análisis de carga muscular (APDF de Jonsson)** *(novedad)*
- Un **gráfico de distribución de carga (APDF)**: la **distribución acumulada de
  amplitud** de la envolvente en % CVM, con los tres niveles marcados (cada uno
  con su color; **anillo rojo** si supera su límite recomendado). (Ver §6.5.)
- Un **panel de datos** estructurado: referencia CVM, fuente, **activación media**
  y los niveles **estático (P10) / mediano (P50) / pico (P90)**, cada uno con su
  **valor** (en **rojo** si se sale de lo normal), su **rango normal** y una
  **explicación breve** de su significado.

**Informe PDF de normalización**: igual que en Análisis, con selección de rango
temporal; incluye los paneles, el gráfico APDF y la tabla de métricas de carga.

[Figura sugerida: captura de la pestaña CVM señalando los 3 paneles, el gráfico
APDF (con los puntos de colores y anillos) y el panel de datos.]

[Figura sugerida: detalle del panel de datos con un valor en rojo (fuera de
rango) y su explicación.]

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

- El programa estima la fatiga ajustando la **MDF frente al tiempo** (panel 6 del
  Análisis) y observando su **pendiente**:
  - Pendiente **negativa** (la MDF baja) → **fatiga detectada**.
  - Pendiente plana o positiva → **sin fatiga**.
- A menudo, la fatiga se acompaña de un **aumento de la amplitud (RMS)** para
  mantener la fuerza, de ahí el interés del panel 7 (RMS vs MDF).

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

### 7.1 Sesión completa: adquirir → analizar → normalizar → informe

1. **Adquisición.** Conectar el dispositivo, elegir 1–2 canales y etiquetas,
   *Iniciar grabación*. Pedir al sujeto la tarea; marcar eventos relevantes
   (manual o automático). *Detener grabación* (se guarda el EDF).
2. **Análisis.** Abrir el EDF en la pestaña Análisis, elegir el canal, revisar los
   8 paneles y el resumen (RMS, MNF/MDF, fatiga). Acotar el tramo de interés.
   Generar el **informe PDF**.
3. **Normalización CVM.** (Opcional) Registrar una contracción máxima como
   referencia, o usar auto‑normalización. En la pestaña CVM, normalizar la tarea a
   % CVM y revisar la **carga muscular (APDF)**. Generar su informe.

### 7.2 Monitorización de carga en vivo (ergonomía)

1. Conectar e **Iniciar grabación**.
2. Pulsar **Calibrar CVM** y realizar unos segundos de contracción máxima.
3. Realizar la tarea observando las **barras de carga**: si entran en naranja
   (cansancio) o rojo (fatiga), intervenir (pausa, cambio de postura).

[Figura sugerida: diagrama de flujo de los dos flujos de trabajo.]

---

## 8. Idioma y configuración

- La interfaz es **bilingüe (español/inglés)**; el idioma se detecta del sistema
  al arrancar y se puede cambiar desde el selector de la esquina superior derecha
  (el cambio se aplica al reiniciar).
- Los **parámetros por defecto** (filtros, percentil CVM, límites de carga,
  duración de calibración, etc.) están centralizados y son ajustables.

---

## 9. Resolución de problemas (FAQ)

### Conexión y dispositivo

**El dispositivo no conecta o el LED se queda en amarillo.**
- *BITalino*: comprueba la dirección MAC y que el dispositivo esté emparejado por
  Bluetooth. BITalino necesita **Python ≤ 3.11** (no funciona en 3.12).
- *Arduino + MyoWare*: comprueba el **puerto COM** (usa *Refrescar* para listar los
  puertos) y el cable USB.
- El **watchdog** fuerza la desconexión si no llegan datos en ~3 s; reconecta e
  inténtalo de nuevo.

### Calidad de la señal

**Línea plana / sin señal.** Comprueba el contacto de los electrodos y el de
referencia, la ganancia, y que el canal mostrado sea el correcto.

**Interferencia de red a 50 Hz / señal muy ruidosa.** Asegura un buen contacto de
los electrodos (el filtro notch elimina 50 Hz, pero el mal contacto amplifica el
ruido); aléjate de cargadores y cables de red.

**Deriva de la línea base o picos.** Suele ser movimiento de electrodos/cable —
fija los cables y vuelve a limpiar la piel.

**Aviso de "posible saturación".** La señal llega a los límites del ADC; baja la
ganancia o revisa los electrodos.

**Aviso de "línea base plana".** Poca o ninguna señal — revisa el contacto.

### Monitor de carga en vivo y calibración

**"Calibración fallida (sin señal)".** Debes estar **grabando** y contraer **al
máximo** durante la ventana de calibración.

**Las barras dicen "sin calibrar".** Pulsa **Calibrar CVM** mientras grabas.

**La carga en vivo parece incorrecta.** Recalibra — la referencia CVM es por sesión
de grabación y se reinicia al empezar una grabación nueva.

### Análisis e informes

**El EDF no abre o se analiza el canal equivocado.** Comprueba el archivo y el
**nombre del canal** (la lista se rellena desde la cabecera del EDF).

**"Generar informe PDF" no hace nada.** Realiza primero un análisis (el botón se
activa tras un análisis correcto).

**El informe es ilegible con un registro largo.** Elige un **rango temporal más
corto** en el diálogo del informe (por defecto, la ventana visible).

### Software e instalación

**La app no arranca.** Usa **Python 3.10–3.12** en el entorno virtual del proyecto.
Python 3.13+ aún no está soportado (la pila científica no tiene *wheels*).

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

1. Ventana principal con las tres pestañas.
2. Esquema fisiológico: motoneurona → fibras → electrodo → señal sEMG.
3. Colocación de electrodos en un músculo (activo / referencia).
4. Cadena de procesado: cruda → filtrada → rectificada → envolvente.
5. Pestaña Adquisición (2 canales) anotada.
6. Detalle del monitor de carga en vivo (barras con zonas de color).
7. Pestaña Análisis con los 8 paneles + resumen + navegador.
8. Ejemplo de informe PDF de Análisis (2 páginas).
9. Pestaña CVM con los 3 paneles, el gráfico APDF y el panel de datos.
10. Detalle del panel de datos con un valor fuera de rango (rojo) + explicación.
11. Ilustración de la fatiga: desplazamiento espectral + MDF descendente.
12. Gráfico APDF anotado con los niveles estático/mediano/pico y las zonas.
13. Diagrama de flujo de los flujos de trabajo típicos.

> **Sugerencia de tono para el manual:** combinar instrucciones prácticas ("cómo
> se hace") con recuadros de "¿qué significa fisiológicamente?" junto a cada
> métrica, de forma que sirva tanto de guía de uso como de material docente.
