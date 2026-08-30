# Guion de prácticas de Electromiografía de superficie con emgteach

> **Asignatura:** Fisiología (laboratorio de prácticas).
> **Software:** emgteach. **Equipo:** BITalino o Arduino + MyoWare 2.0 con
> electrodos de superficie.
>
> Este guion propone **cinco prácticas** progresivas. Cada una es autocontenida:
> objetivos, fundamento breve, material, procedimiento paso a paso en la
> aplicación, datos a recoger y cuestiones para el alumnado. El/la docente puede
> seleccionar las que correspondan al tiempo disponible.

---

## Objetivos generales

Al terminar las prácticas, el alumnado debe ser capaz de:

1. Registrar correctamente una señal EMG de superficie (colocación de electrodos,
   conexión, grabación).
2. Distinguir señal **en bruto**, **filtrada** y **envolvente**, y explicar el
   sentido de cada paso de procesado.
3. Relacionar la **amplitud** del EMG con el **nivel de activación** muscular.
4. Observar la **coactivación** agonista/antagonista.
5. Identificar la **fatiga muscular** por el desplazamiento espectral
   (descenso de MNF/MDF).
6. **Normalizar** a % CVM y evaluar la **carga muscular** (método de Jonsson),
   incluida la monitorización en tiempo real.

---

## Seguridad e higiene

- Equipo de **muy baja tensión**, alimentado por batería/USB; no presenta riesgo
  eléctrico para el sujeto.
- Usar electrodos **desechables** individuales; limpiar la piel con una toallita.
  No reutilizar electrodos entre sujetos.
- Personas con lesiones cutáneas en la zona deben abstenerse.

---

## Preparación común (antes de cada práctica)

0. **Elegir la práctica.** En el desplegable de la esquina superior derecha, antes
   que nada. Fija el número de canales y el uso del acelerómetro, y las tres
   pestañas se configuran a partir de esa elección.

   | Práctica del guion | Modo |
   |---|---|
   | 1, 2, 4 y 5 | Contracción de un músculo |
   | 3 | Contracción agonista / antagonista |

   La casilla contigua, **«Opciones avanzadas»**, muestra los controles finos
   comunes a los tres modos: cortes de filtro, umbrales de aviso, región de interés
   y detección automática de inicio. Sin ella, la caja de conexión del dispositivo
   solo aparece mientras no haya ninguno guardado.

1. **Colocación de electrodos.** Limpiar la piel sobre el vientre del músculo;
   colocar dos electrodos activos alineados con las fibras y uno de **referencia**
   en una zona neutra (prominencia ósea cercana).
2. **Conexión.** Abrir emgteach → pestaña **Adquisición**. Elegir el dispositivo
   (BITalino/Arduino), introducir la **MAC**/**puerto** y la **carpeta de destino**.
   Pulsar **Conectar** (el **LED** debe pasar a amarillo). El número de canales ya
   no se elige aquí: lo fija el modo.
3. **Prueba.** Pulsar **Iniciar grabación**; pedir una contracción breve y
   comprobar que las dos gráficas (en bruto y envolvente) responden. **Detener** y
   descartar si hay mucho artefacto (recolocar electrodos).

[Figura sugerida: foto de la colocación de electrodos y captura de la pestaña de
Adquisición con el LED en verde durante una contracción.]

---

## Seguir la sesión desde el móvil (seguimiento en móviles)

En una práctica en grupo, **una sola persona maneja el equipo** (el ordenador con el
BITalino) y **el resto sigue la sesión en el navegador del móvil**, sin instalar
nada. Así todo el grupo ve la misma señal en tiempo real y cada uno puede guardar los
datos en su propio teléfono.

**Para quien maneja el equipo (operador/a):**
1. En la pestaña **Adquisición**, marcar la casilla **«Difundir a móviles (en
   laboratorio)»**. Está a la vista en los tres modos, sin necesidad de opciones
   avanzadas.
2. Aparece una dirección del tipo **`http://192.168.x.x:8070`**. Se comparte con el
   botón **«Copiar enlace»** o mostrando el **QR**. El ordenador y los móviles deben
   estar en **la misma red Wi‑Fi**.
3. Grabar con normalidad: la señal, la calibración de CVM y las marcas se envían
   solas a los móviles conectados. Cada activación genera un **código de sesión**
   nuevo, de modo que los enlaces de una práctica anterior dejan de valer.

**Para quien sigue desde el móvil (seguidores):**
1. Conecta el móvil a **la misma red Wi‑Fi** que el ordenador.
2. Abre el navegador (Chrome, Safari…) y escribe la **dirección** que ha dado el
   operador/a. Verás la pantalla **«emgteach · Aula»**.
3. Sigue en vivo la **envolvente** de cada canal y el **% de CVM** con sus colores,
   igual que en el ordenador. Durante la calibración verás el mismo cuadro de
   *preparar / mantener / relajar*.

**Guardar en tu móvil.**
- **⬇️ Descargar sesión (CSV):** guarda en el teléfono lo que has visto en vivo
  (tiempo, envolvente por canal, % CVM y las marcas) para incluirlo en el informe.
- Cuando el operador/a **analice** el registro, aparecerá el bloque **«📊 Resultados
  del análisis»** con las métricas (MNF, MDF, RMS, iEMG, fatiga…) y los botones
  **⬇️ Descargar informe (PDF)** y **⬇️ Descargar resultados (CSV)**.

> **Nota.** El móvil solo **mira y descarga**: no maneja el equipo ni modifica la
> grabación. Si no carga, revisa que estás en la **misma Wi‑Fi** y que has escrito la
> dirección **tal cual**, empezando por **`http://`** (no `https://`).

---

## Práctica 1 — Familiarización y primer registro

**Objetivo.** Obtener un registro limpio y reconocer las tres representaciones de
la señal.

**Fundamento.** El EMG de superficie capta la suma de los potenciales de las
unidades motoras activas. La señal en bruto se **filtra** (notch 50 Hz + paso‑banda
20–450 Hz), se **rectifica** y se calcula su **envolvente**, que sigue el nivel de
activación.

**Procedimiento.**
1. Con un canal sobre, p. ej., el **bíceps braquial**, iniciar grabación.
2. Realizar la secuencia: **5 s reposo → contracción suave 5 s → reposo 5 s →
   contracción fuerte 5 s → reposo 5 s**. Marcar cada inicio con la tecla **M**
   (etiqueta *Inicio contracción*).
3. Detener y abrir el archivo en la pestaña **Análisis**.

**Datos a recoger.** Observar en el panel **2 (Envolvente vs RMS)** la diferencia
de amplitud entre contracción suave y fuerte.

**Cuestiones.**
- ¿Por qué la señal en bruto es positiva y negativa, y la envolvente solo positiva?
- ¿Qué efecto tiene el filtro de 50 Hz? ¿Y el paso‑banda?
- ¿Coincide el inicio de la envolvente con tus marcas manuales?

---

## Práctica 2 — Relación EMG–activación (graduación del esfuerzo)

**Objetivo.** Comprobar que la **amplitud** del EMG aumenta con el **nivel de
activación** muscular.

**Fundamento.** A mayor activación, más unidades motoras reclutadas y a mayor
frecuencia de disparo → **mayor amplitud** (envolvente / RMS). La relación con la
fuerza es **monótona pero no lineal**.

**Procedimiento.**
1. Un canal sobre el músculo de estudio. Iniciar grabación.
2. Realizar **contracciones isométricas escalonadas** de ~5 s cada una a niveles
   subjetivos crecientes (p. ej. 25 %, 50 %, 75 %, 100 % del esfuerzo máximo
   percibido), separadas por reposo. Marcar cada escalón.
3. En **Análisis**, usar el panel **5 (RMS por ventana)** y el resumen (**RMS
   global**).

**Datos a recoger.** Rellenar la tabla:

| Nivel de esfuerzo (subjetivo) | RMS aproximado |
|---|---|
| 25 % | |
| 50 % | |
| 75 % | |
| 100 % (CVM) | |

**Cuestiones.**
- ¿Es lineal el aumento de RMS con el nivel de esfuerzo? Comentar.
- ¿Qué fuentes de variabilidad pueden afectar a la amplitud absoluta (mV)?
- ¿Por qué conviene **normalizar** a % CVM para comparar entre sujetos?

[Figura sugerida: gráfica del panel RMS por ventana con los escalones, y tabla de
datos.]

---

## Práctica 3 — Coactivación agonista/antagonista (dos canales)

**Objetivo.** Observar la activación coordinada de un par agonista/antagonista.

**Fundamento.** En muchos movimientos, el músculo **antagonista** se coactiva para
estabilizar la articulación. Con dos canales se visualiza esta coordinación.

**Procedimiento.**
1. Elegir el modo **Contracción agonista / antagonista**, que pone el registro en
   dos canales. Etiquetarlos (p. ej. **bíceps** = canal 1, **tríceps** = canal 2) e
   iniciar grabación.
2. Realizar **flexiones y extensiones** del codo de forma controlada (isométricas
   alternas o movimientos lentos). Marcar las fases.
3. Observar en vivo la gráfica de señal en bruto **apilada**, un carril por canal, y
   la **envolvente superpuesta** (azul/rojo). Detener y revisar en **Análisis** cada
   canal: con un archivo de dos canales, el panel **9. Envolventes superpuestas** se
   activa solo.

**Datos a recoger.** Para una flexión y una extensión, anotar qué canal domina y
si hay coactivación del otro.

> **Calibre la CVM de los dos músculos mientras graba.** El panel 9 los dibuja
> entonces en **% CVM**, que es la única forma en que dos músculos distintos se
> comparan: sus milivoltios dependen de dónde quedaron los electrodos y de cuánta
> piel y grasa hay debajo, así que un bíceps más grueso parecería coactivación.
> Sin las dos referencias el panel se queda en milivoltios y lo advierte sobre la
> propia figura. Aquí «dominar» significa, por tanto, *un porcentaje mayor de su
> propio máximo*, no más amplitud.

**Cuestiones.**
- ¿En la flexión, se activa algo el tríceps? ¿Qué función tendría esa coactivación?
- ¿Cómo ayuda la **vista apilada** frente a la superpuesta para comparar?

[Figura sugerida: captura en vivo de 2 canales con envolvente superpuesta durante
flexión y extensión.]

---

## Práctica 4 — Fatiga muscular (contracción sostenida)

**Objetivo.** Detectar la **fatiga muscular** por el desplazamiento del espectro a
frecuencias más bajas.

**Fundamento.** En una contracción sostenida, la **velocidad de conducción** de las
fibras disminuye y el espectro se **desplaza a la izquierda**: **MNF y MDF bajan**
con el tiempo. A menudo, la **amplitud (RMS) sube** para mantener la fuerza.

**Procedimiento.**
1. Un canal sobre el músculo. Iniciar grabación.
2. Mantener una **contracción isométrica submáxima sostenida** (p. ej. ~50 % del
   máximo) **el mayor tiempo posible** (30–60 s o hasta no poder mantenerla).
   Marcar inicio y fin.
3. En **Análisis**, revisar el panel **6 (MDF vs tiempo)** y el panel **4 (PSD)**;
   leer en el resumen la **pendiente de la MDF** y el indicador de **fatiga**.

**Datos a recoger.**

| Magnitud | Inicio | Final |
|---|---|---|
| MDF (Hz) | | |
| RMS | | |

Pendiente de la MDF: ____ Hz/s. ¿Fatiga detectada? Sí / No.

**Cuestiones.**
- ¿Disminuyó la MDF a lo largo de la contracción? ¿Qué lo explica fisiológicamente?
- ¿Aumentó la RMS al final? ¿Por qué el sistema nervioso lo haría?
- ¿Cómo se vería el desplazamiento en el panel de la PSD (inicio vs final)?

[Figura sugerida: panel MDF vs tiempo con tendencia descendente y dos PSD
(inicio/final) mostrando el desplazamiento espectral.]

---

## Práctica 5 — Normalización CVM y carga muscular (método de Jonsson)

**Objetivo.** Expresar la activación como **% CVM** y evaluar la **carga muscular**
de una tarea, tanto **a posteriori** como **en tiempo real**.

**Fundamento.** La **CVM** es la referencia de máximo esfuerzo. Normalizar a % CVM
permite comparar. El **método de Jonsson (APDF)** resume la carga en tres niveles:
**estático (P10)**, **mediano (P50)** y **pico (P90)**, con límites recomendados;
superarlos de forma sostenida se asocia a fatiga y riesgo musculoesquelético.

**Parte A — Desconectado (pestaña CVM).**
1. Registrar una **CVM de referencia**: contracción máxima de ~3–5 s (guardar EDF).
   Es obligatoria: sin ella la pestaña no calcula, salvo con las opciones avanzadas
   marcadas, y un resultado auto‑normalizado no se puede leer frente a los límites de
   Jonsson.
2. Registrar una **tarea** representativa (p. ej. sostener un peso, una postura de
   trabajo) durante un tiempo (guardar EDF).
3. En la pestaña **CVM**, cargar el **EDF de la tarea** y el **EDF de CVM** de
   referencia. Revisar los **3 paneles** y el **gráfico APDF** + **panel de datos**.

**Parte B — En vivo (pestaña Adquisición).**
1. Iniciar grabación. Pulsar **Calibrar CVM** y contraer al máximo unos segundos.
2. Realizar la tarea observando las **barras de carga**: anotar cuándo entran en
   **naranja** (cansancio) o **rojo** (fatiga).

**Datos a recoger.**

| Nivel | Valor (% CVM) | ¿Dentro del rango normal? |
|---|---|---|
| Estático (P10) | | |
| Mediano (P50) | | |
| Pico (P90) | | |
| Activación media | | |

**Cuestiones.**
- ¿Qué nivel(es) superan su límite recomendado? ¿Qué implicación ergonómica tiene?
- ¿Coincide la impresión del **monitor en vivo** (zonas de color) con el análisis
  APDF desconectado?
- ¿Qué intervención propondrías si la carga estática es alta de forma sostenida?

[Figura sugerida: gráfico APDF con los tres niveles y el panel de datos; captura del
monitor en vivo con una barra en zona naranja/roja.]

---

## Anexo — Plantilla de informe del alumnado

Para cada práctica, entregar:

1. **Identificación**: nombre/grupo, músculo(s) estudiado(s), dispositivo.
2. **Capturas/figuras** de los paneles relevantes (o el **informe PDF** generado
   por la app; con la difusión activa puede descargarse en el propio móvil).
3. **Tablas de datos** cumplimentadas.
4. **Respuestas razonadas** a las cuestiones.
5. **Conclusión** breve relacionando lo observado con el fundamento fisiológico.

> **Nota para el profesorado.** La app genera **informes PDF** reproducibles
> (con nombre y código del alumnado) desde las pestañas de Análisis y CVM; pueden
> usarse como entregable o anexo del informe de prácticas. Los **parámetros**
> (filtros, límites de carga, sensibilidad de detección de inicio, etc.) son
> ajustables si se desea adaptar la dificultad.
