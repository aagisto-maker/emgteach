# Guion de prácticas de electromiografía de superficie con emgteach

> **Asignatura:** Fisiología (laboratorio de prácticas).
> **Software:** emgteach (rama `feat/ui-levels`, septiembre de 2026).
> **Equipo:** BITalino con electrodos de superficie; en la práctica de un músculo
> sirve también un Arduino con sensor MyoWare 2.0.
>
> Este guion tiene **tres prácticas**, una por cada práctica que ofrece la
> aplicación en su selector. Dentro de cada una hay varios **ejercicios**, cada uno
> con lo que se hace, lo que la aplicación calcula sola, lo que hay que anotar y
> lo que hay que razonar. El profesorado elige los ejercicios que caben en el
> tiempo disponible; cada uno se entiende sin los demás.

---

## Cómo está organizado esto, y por qué

La aplicación se configura **eligiendo la práctica**, no ajustando controles. El
desplegable de la esquina superior derecha tiene tres opciones, y de esa elección
salen el número de canales, el uso del acelerómetro, qué pide la grabación y qué
paneles ofrece el análisis. La banda de color al lado dice el nivel.

| Práctica de este guion | Opción del selector | Nivel | Canales | Lo que se aprende |
|---|---|---|---|---|
| 1 | **Contracción de un músculo** | básico (verde) | 1 | de la señal al número: amplitud, espectro, fatiga, carga |
| 2 | **Contracción agonista / antagonista** | intermedio (naranja) | 2 | comparar dos músculos en % CVM; coactivación |
| 3 | **Cinemática muscular** | avanzado (violeta) | 1 + acelerómetro | fuerza-velocidad, retraso electromecánico, temblor |

Las tres pestañas de la ventana son siempre las mismas: **Adquisición** (grabar),
**Análisis** (leer un registro) y **Normalización CVM** (expresar la tarea en
porcentaje del máximo y medir la carga). Lo que cambia con la práctica es lo que
cada pestaña enseña.

---

## Objetivos generales

Al terminar las prácticas, el alumnado debe ser capaz de:

1. Colocar los electrodos y obtener una señal de EMG de superficie limpia, y
   reconocer en la pantalla una señal buena y una estropeada.
2. Explicar la cadena de procesado (filtrado, rectificación, envolvente) y qué
   pregunta responde cada medida: RMS e iEMG (cuánto se activa), MNF y MDF (a qué
   frecuencias), % CVM (cuánto respecto al propio máximo).
3. Calibrar una **contracción voluntaria máxima** que sea de verdad máxima, y
   reconocer en el análisis cuándo no lo fue.
4. Leer la **tabla por contracción** y las **fichas del resumen** contra los
   rangos orientativos, y decir qué es normal y qué es una pregunta.
5. Detectar la **fatiga** por el desplazamiento del espectro, y distinguir «no
   detectada» de «no concluyente».
6. Comparar un **agonista y su antagonista** en % CVM y medir su **coactivación**.
7. Evaluar la **carga muscular** de una tarea con el método de Jonsson.
8. En la práctica avanzada, obtener la **relación fuerza-velocidad** de un
   músculo, medir su **retraso electromecánico** y ver el **temblor fisiológico**.

---

## Seguridad e higiene

- Equipo de **muy baja tensión**, alimentado por batería o USB; no presenta riesgo
  eléctrico para el sujeto.
- Electrodos **desechables**, uno por persona; limpiar la piel con alcohol y dejar
  secar. No reutilizar electrodos entre sujetos.
- Personas con lesiones cutáneas en la zona deben abstenerse.
- Los esfuerzos máximos son breves (cuatro segundos) y se hacen contra la mesa,
  no contra otra persona. Quien note dolor articular, para.

---

## Antes de empezar (común a las tres prácticas)

### 0 · Elegir la práctica

En el desplegable de la esquina superior derecha, antes que nada. La aplicación
recuerda la última elección; conviene comprobarla cada sesión. La guía rápida
(botón **«Guía»**) recorre en cinco pasos lo que sigue, y cada caja de la
aplicación tiene un **«?»** en su esquina con la explicación de lo que hace.

### 1 · Colocar los electrodos

Regla general: dos electrodos activos sobre el **vientre del músculo**, alineados
con las fibras y separados **2 cm entre centros**; el de referencia sobre **hueso**
(olécranon o estiloides cubital). Piel limpia y seca, sin crema. Si la señal sale
pequeña, desplazar el par uno o dos centímetros hacia el tendón.

El par que usa este guion en las prácticas 1 y 2 es el del antebrazo: **flexor
radial del carpo** (FCR, cara anterior) y **extensores radiales del carpo** (ECR,
cara posterior). Dónde exactamente, con qué comprobación palpatoria y qué error
es fácil cometer, está en
[`colocacion_electrodos_antebrazo_es.md`](colocacion_electrodos_antebrazo_es.md).
La práctica 3 usa el bíceps braquial, con el acelerómetro en la muñeca.

### 2 · Conectar

Pestaña **Adquisición**, caja **Configuración del dispositivo**:

- En la práctica de un músculo se elige el dispositivo (BITalino por Bluetooth o
  Arduino + MyoWare por USB). En las otras dos la caja dice **«Dispositivo:
  BITalino»** sin desplegable, porque necesitan dos canales o el acelerómetro,
  que solo tiene el BITalino. En todos los casos la dirección (MAC o puerto) se
  puede cambiar; el BITalino se identifica mejor por su **MAC**, que es la misma
  en cualquier ordenador.
- **Ruta y archivo de salida**: carpeta donde se guardará el EDF.
- **Etiquetas**: el nombre de cada músculo, en el orden de los canales de la
  placa (**Músculo 1 es el que se registra por A1**). En el par, las casillas
  empiezan vacías con una pista («Agonista, p. ej. FCR»). Lo que se escriba aquí
  es lo que aparecerá en los carriles, las tablas y el informe.
- **Identificador de prueba**: un alumno, una pareja, una mesa o un intento;
  va a la cabecera del EDF y al informe.
- Pulsar **Conectar**. El indicador pasa a amarillo (conectado) y a verde cuando
  llegan datos.

### 3 · Probar la señal antes de grabar

Con la conexión hecha, pedir una contracción breve y mirar las dos gráficas: la
señal en bruto debe estallar en picos simétricos y la envolvente subir y volver a
la línea base. En reposo, la línea base es casi plana. La aplicación avisa en el
registro de eventos de dos fallos frecuentes: **canal plano** (electrodo suelto o
no conectado) y **saturación** (mal contacto o electrodo sobre el tendón).

### 4 · Cómo transcurre una grabación con calibración

Las medidas en **% CVM** necesitan saber cuál es el máximo de ese músculo en esa
sesión. La aplicación lo pide con un asistente que va escribiendo todo en el mismo
fichero, sin parar la grabación:

1. **Calentamiento (10 s).** Dos o tres contracciones suaves de cada músculo. La
   primera contracción máxima de una sesión nunca es la más fuerte, y esto lo
   corrige en parte.
2. **Tres contracciones máximas mantenidas**, de 4 s cada una, con cuenta atrás de
   3 s y 2 s de descanso entre ellas. La pantalla dice «¡Contraiga FCR al máximo!».
3. **Tres sacudidas máximas breves**, de 1,5 s. La pantalla dice «Haga una
   contracción o sacudida muscular simple (breve) con la máxima fuerza posible».
4. Con dos músculos, lo mismo para el segundo.
5. En la práctica del par, después viene una **preparación** de 5 s y empieza el
   **registro** de la tarea. En las otras dos prácticas la calibración se lanza
   con el botón **«Calibrar CVM»** mientras se graba, y el registro sigue.

La referencia es **el mejor 0,2 s de las seis repeticiones**. ¿Por qué seis y por
qué sacudidas? Porque una contracción mantenida muestra un pico al empezar y luego
una meseta, y los esfuerzos breves de una tarea alcanzan ese pico. Si la
referencia se midiera sobre la meseta, la tarea la superaría, y eso es lo que
pasaba: 135 % de «máximo» en el banco del 1 de septiembre.

> **La maniobra del máximo es lo que decide la práctica.** Comprobado en el banco
> el 3 de septiembre con cuatro registros seguidos:
>
> - **Contra algo que no ceda.** El canto inferior de la mesa, no una mano.
>   Antebrazo apoyado del todo. Sin resistencia el músculo se acorta a su
>   velocidad máxima y, por la relación fuerza-velocidad, da su fuerza mínima:
>   una «máxima» en el aire es submáxima por construcción.
> - **Flexor (FCR): puño cerrado**, palma hacia arriba bajo el borde de la mesa,
>   muñeca unos 20° en extensión, y empujar hacia arriba. Con la mano abierta la
>   referencia salió a la mitad de lo que la tarea produjo después (178 %); con
>   el puño cerrado, la tarea quedó al 109 %.
> - **Extensor (ECR): dorso de la mano** contra el tablero, antebrazo pronado,
>   muñeca unos 20° en flexión, dedos relajados.
> - **Mantener los cuatro segundos.** Si la envolvente hace una púa y cae, la
>   repetición no vale; la aplicación permite descartarla después.
> - **Comprobación inmediata:** al terminar la tarea, el resumen del análisis dice
>   el **máximo de la tarea** en % CVM. Si pasa del 150 % lo marca en rojo, «no fue
>   un máximo», y hay que repetir la calibración. Entre el 90 y el 125 % es lo que
>   dan las sesiones bien calibradas.

### 5 · Qué pasa al parar

Al pulsar **Detener grabación**, la pestaña de Adquisición muestra la **sesión
entera** con sus tramos sombreados (calentamiento, cada repetición de calibración,
preparación, registro) y la pestaña de **Análisis** analiza el registro **sola**,
sin pulsar nada. Al pasar a Análisis aparece un cuadro que señala el paso
siguiente:

1. **«Repeticiones de la calibración…»**: la lista de las seis repeticiones de
   cada músculo con su valor. Se desmarcan las que salieron flojas y se acepta;
   la referencia se recalcula. Esto va primero porque **todos los porcentajes se
   miden contra esa referencia**.
2. **«Seleccionar fragmentos…»**: una fila por contracción encontrada, con su
   inicio, fin, duración y, con dos músculos, cuál llevó cada una. Se desmarcan
   las que no merezca la pena analizar (un movimiento mal hecho, un tirón del
   cable) y se pulsa **«Usar estos fragmentos»** aunque no se cambie nada. En la
   práctica de un músculo, si la calibración se hizo con el botón, aquí se
   desmarcan también los seis esfuerzos de calibración para quedarse con la tarea.
   El cuadro se ajusta mirando: dos deslizadores, la **sensibilidad** (cuántas
   contracciones encuentra; la línea discontinua sobre la envolvente es el umbral
   que fija) y, en el par, el **umbral de coactivación** (a partir de qué fracción
   del músculo mayor el menor cuenta como coactivación). Cada movimiento redibuja
   el sombreado y las filas al momento, y pulsar sobre un tramo sombreado lo
   descarta o lo repone. El **ajuste fino** (duración mínima, unión de huecos,
   separación entre contracciones) está plegado y rara vez hace falta.

Después se lee. La pestaña tiene tres zonas: los **paneles** (arriba, con la rueda
del ratón se desplazan; los botones ▲▼ y ▶◀ de la izquierda cambian las escalas),
el **gráfico de contracciones** y el **resumen** (abajo) y, en el par, el
**gráfico de coactivación**. El de contracciones enseña una vista cada vez,
elegida en su línea de título, y abre en la **relación**, que es de la que se
saca la conclusión. Con un músculo es la **amplitud frente a la MDF**,
contracción a contracción y unidas en orden: una deriva hacia más amplitud y
menos frecuencia es fatiga, hacia más de las dos es más fuerza, y los otros dos
cuadrantes son sus contrarios. Con dos músculos es **un músculo frente al otro**,
con la cuña en la que la aplicación llama coactivación a una contracción: una
flexión cae sobre un eje, una extensión sobre el otro y una presa dentro de la
cuña. Con dos músculos hay además **«Categoría»**, la media de cada músculo por
maniobra con cada contracción como punto, y **«Quién lidera»**, una barra por
contracción hacia la derecha si llevó el primer músculo y hacia la izquierda si
llevó el segundo, con la banda de coactivación en medio. **«Serie»** sigue las
contracciones en orden, con su recta de tendencia y la MDF en el eje derecho, y
en cinemática **«Por carga»** agrupa amplitud, velocidad y retraso electromecánico por
la carga que dejó marcada el asistente. **«Tabla»** son los números, que son los
que se copian en las tablas de este guion. El de coactivación es una línea por
ventana: el nombre a la izquierda, los segundos a la derecha y, en medio, el
índice como barra morada o, cuando no se informa, un bloque dorado y un
cuadradito del color del músculo que trabajó solo; la leyenda de arriba dice
qué es cada color, y las medias en % CVM están en su «Tabla». El botón **«Generar informe
PDF»** produce el entregable con las figuras, la calibración, los gráficos, las
tablas y las fichas.

### 6 · Seguir la sesión desde el móvil

En una práctica en grupo, **una persona maneja el equipo** y el resto sigue la
señal en el navegador del móvil. En Adquisición, casilla **«Difundir a móviles (en
laboratorio)»**; aparece una dirección `http://…:8070/?k=…` y un botón **QR**.
Todos en la misma Wi-Fi, y la dirección escrita con `http://`. El móvil solo mira
y descarga: la sesión en CSV mientras se graba y, cuando el operador analiza, el
informe PDF y los resultados. Cada activación genera un código nuevo; los enlaces
de una práctica anterior caducan.

---

## Práctica 1 — Contracción de un músculo (nivel básico)

**Montaje.** Un canal sobre el FCR (o sobre el bíceps si se prefiere un músculo
grande), referencia en el olécranon. Selector en **Contracción de un músculo**.

**Lo que enseña la aplicación en esta práctica.** Tres paneles por defecto: **1A.
En bruto**, **2. Env. norm.** (la envolvente escalada a su máximo) y **3. PSD** (el
espectro, con el espectro *antes* del filtro en gris detrás). Abajo, la **tabla de
contracciones** con una fila por esfuerzo (inicio, duración, RMS, pico en % CVM,
MDF) y las **fichas del resumen** (MNF, MDF, pendiente de la MDF, fatiga, máximo de
la tarea, RMS global, iEMG, duración, CVM). El botón **«Más paneles…»** revela el
resto para quien quiera mirar más.

### Ejercicio 1a · Primer registro: de la señal al número

**Objetivo.** Obtener un registro limpio y reconocer las representaciones de la
señal.

**Procedimiento.**
1. **Iniciar grabación**. Secuencia: 5 s de reposo, contracción suave 4 s, reposo
   5 s, contracción fuerte 4 s, reposo 5 s. La aplicación marca sola el inicio de
   cada contracción (**Auto-inicio**, umbral = reposo + k × ruido, con k = 3).
2. **Detener**. Pasar a **Análisis** y aceptar los fragmentos que propone.

**Datos a recoger.** De la tabla de contracciones:

| Contracción | Duración (s) | RMS (mV) | MDF (Hz) |
|---|---|---|---|
| suave | | | |
| fuerte | | | |

**Cuestiones.**
- ¿Por qué la señal en bruto es positiva y negativa y la envolvente solo
  positiva? ¿Qué hace la rectificación?
- En el panel 3, el espectro gris es la señal antes del filtro y el azul después.
  ¿Qué ha desaparecido? ¿A qué frecuencia estaba? ¿Y por debajo de 20 Hz?
- El RMS de la contracción fuerte, ¿es mayor que el de la suave? ¿Cuántas veces?
  ¿Qué dos mecanismos nerviosos explican que crezca la amplitud?
- ¿Coinciden los inicios automáticos con lo que se ve en la envolvente?

### Ejercicio 1b · Escalones de esfuerzo: más fuerza, más señal, pero no el doble

**Objetivo.** Comprobar que la amplitud crece con la activación de forma monótona
pero **no lineal**, y ver para qué sirve normalizar.

**Procedimiento.**
1. **Iniciar grabación** y pulsar **«Calibrar CVM»** de inmediato: el asistente
   pide el calentamiento y los seis esfuerzos máximos (apartado 4). Después, las
   **barras de carga** de la caja «Carga muscular» muestran el % CVM en vivo.
2. Guiándose por la barra, hacer cuatro contracciones isométricas de 4 s contra la
   mesa a **25, 50, 75 y 100 %** de la barra, con 5 s de reposo entre ellas.
3. **Detener**. En Análisis, revisar las repeticiones de la calibración y, en los
   fragmentos, dejar solo los cuatro escalones.

**Datos a recoger.** De la tabla de contracciones:

| Escalón pedido | RMS (mV) | Pico (% CVM) |
|---|---|---|
| 25 % | | |
| 50 % | | |
| 75 % | | |
| 100 % | | |

**Cuestiones.**
- ¿Sube el RMS en cada escalón? ¿Se duplica del 25 al 50 %? ¿Y del 50 al 100 %?
  Comente la forma de la relación y por qué la sEMG es un buen indicador de
  activación y un mal dinamómetro.
- Compare su RMS al 100 % con el de un compañero. ¿Quién «hace más fuerza»? ¿Por
  qué esa comparación no vale, y sí vale la columna de % CVM?
- ¿Qué dice la ficha **«Máximo de la tarea»**? Si pasa del 100 %, ¿qué ocurrió en
  la calibración?

### Ejercicio 1c · Contracción mantenida: la firma de la fatiga

**Objetivo.** Detectar la fatiga por el desplazamiento del espectro hacia
frecuencias bajas, y entender qué hace falta para poder afirmarla.

**Fundamento.** Al sostener una contracción bajan el pH y la velocidad de
conducción de las fibras; el espectro se comprime hacia abajo y **la MDF cae**. A
la vez el RMS suele **subir**, porque se reclutan más unidades para mantener la
fuerza. La prueba específica es la caída de la MDF, no la subida del RMS.

**Procedimiento.**
1. **Iniciar grabación**, **Calibrar CVM**, y después mantener una contracción
   isométrica contra la mesa a un **50 %** de la barra **durante 30 a 60 s**, o
   hasta no poder sostenerla. Reposo 5 s antes y después.
2. **Detener**. En Análisis, revisar las repeticiones y, en los fragmentos,
   dejar **solo la contracción mantenida**. Marcar el panel **7. MDF/tiempo**
   (está en «Más paneles…»).

**Cómo decide la aplicación.** Ajusta una recta a la MDF de las ventanas de un
segundo en que el músculo trabajaba. Dice **«Fatiga detectada»** si la pendiente
es negativa y la recta explica algo (R² ≥ 0,30, al menos cuatro ventanas);
**«No detectada»** si la MDF se mantiene o sube con una recta que ajusta; y **«No
concluyente»** si la recta no ajusta, que es lo normal en una serie de
contracciones breves. No concluyente no es «no»: es que el registro no responde a
la pregunta.

**Datos a recoger.**

| Magnitud | Primeros 5 s | Últimos 5 s |
|---|---|---|
| MDF (Hz) (panel 7) | | |
| RMS (mV) (panel 6, en «Más paneles…») | | |

Pendiente de la MDF: ____ Hz/s (R² = ____). Veredicto: ______________.

**Cuestiones.**
- ¿Bajó la MDF? ¿Cuánto en porcentaje? ¿Qué lo explica en las fibras?
- ¿Subió el RMS al final? ¿Por qué lo haría el sistema nervioso? ¿Qué parte de
  esa subida puede no ser reclutamiento?
- Un compañero sostuvo 15 s y su veredicto es «no concluyente». ¿Está fatigado o
  no? ¿Qué le falta al registro?

### Ejercicio 1d · La carga de una tarea (método de Jonsson)

**Objetivo.** Expresar una tarea en % CVM y describir su carga con tres niveles.

**Fundamento.** El **APDF** ordena todos los instantes de la tarea de menor a
mayor esfuerzo y lee tres puntos: **P10 (estático)**, la carga que el músculo no
suelta en ningún momento; **P50 (mediano)**, el esfuerzo típico; **P90 (pico)**,
los momentos de máxima exigencia. Jonsson recomendó no pasar del 2–5 % en el
estático, 10–14 % en el mediano y 50–70 % en el pico; la aplicación usa el
extremo alto de cada rango (5, 14 y 70 %). El riesgo no suele venir de los picos
sino de un estático alto y mantenido.

**Procedimiento.**
1. **Iniciar grabación**, **Calibrar CVM**, y hacer durante **60 s** una tarea:
   sostener una botella de agua con la muñeca en neutro, o teclear con la mano en
   alto, o cargar y descargar un peso cada 10 s. Cada grupo una distinta.
2. **Detener**. En **Normalización CVM** el resultado aparece solo. Con
   **«Seleccionar fragmentos…»** dejar solo la tarea (sin la calibración), o el
   pico será el propio máximo.

**Datos a recoger.** Del panel de datos:

| Nivel | Valor (% CVM) | Límite | ¿Dentro? |
|---|---|---|---|
| Estático (P10) | | 5 % | |
| Mediano (P50) | | 14 % | |
| Pico (P90) | | 70 % | |
| Activación media | | 10 % | |

**Cuestiones.**
- ¿Qué nivel supera su límite? Compare con la tarea de otro grupo: ¿cuál tiene el
  pico más alto y cuál el estático más alto? ¿Cuál es peor para el músculo, y por
  qué?
- Las barras en vivo avisaban en naranja al pasar del 40 % y en rojo del 70 %.
  ¿Coincide esa impresión con el APDF? Explique por qué miden cosas distintas.
- Proponga un cambio de la tarea que baje el estático sin bajar el pico.

---

## Práctica 2 — Contracción agonista / antagonista (nivel intermedio)

**Montaje.** Dos canales: **FCR** en el canal 1 (A1) y **ECR** en el canal 2 (A2),
referencia común en el olécranon o una en cada estiloides. Selector en
**Contracción agonista / antagonista**. Etiquetas: FCR y ECR.

**Lo que enseña la aplicación en esta práctica.** Al pulsar **Iniciar grabación**
el asistente calibra **los dos músculos** (apartado 4) y después abre el registro.
El análisis ofrece **1A. En bruto**, **1B. Bruto (2º)**, **3. PSD** con las dos
curvas, **7. MDF/tiempo** de los dos y **9. Env. superp.**, las dos envolventes en
% CVM sobre el mismo eje. La tabla de contracciones dice **qué músculo llevó cada
una** (FCR, ECR o «Coactivación», cuando el menor supera la mitad del mayor,
medidos cada uno contra su propio máximo) y la **tabla de coactivación** da, por
ventana, la activación media de cada músculo y el **índice de Falconer-Winter**.

**Por qué en % CVM y no en milivoltios.** Los milivoltios de dos músculos distintos
no se comparan: dependen de dónde quedaron los electrodos y de cuánta piel y grasa
hay debajo. En el banco del 3 de septiembre la referencia del flexor era un tercio
de la del extensor; una flexión al 100 % del flexor leía *menos milivoltios* que el
extensor al 42 %. Todo lo que compara dos músculos en esta práctica lo hace en
porcentaje del máximo de cada uno.

### Ejercicio 2a · Flexión, extensión y presa

**Objetivo.** Ver el patrón recíproco de un par antagonista y medir su
coactivación.

**Fundamento de la presa.** Los flexores de los dedos son extrínsecos: sus
vientres están en el antebrazo y sus tendones cruzan la muñeca. Al cerrar el puño
producen, además del cierre de los dedos, un momento flexor sobre la muñeca que la
doblaría; los extensores radiales del carpo lo contrarrestan y la sostienen en
ligera extensión, que es la longitud a la que esos flexores dan más fuerza. Por eso
la fuerza de presa cae cuando la muñeca se flexiona, y por eso los extensores están
activos de forma continua durante toda la presa, sin los silencios que muestran en
un movimiento recíproco. Aquí no son antagonistas, son estabilizadores. Es también
el mecanismo de la epicondilitis lateral, que es una lesión por presa repetida y no
por extender la muñeca.

**Procedimiento.**
1. **Iniciar grabación**. Calibrar los dos músculos como dice el apartado 4 (puño
   cerrado para el FCR, dorso de la mano para el ECR).
2. En el registro, y siempre en este orden, con 2 s de quietud entre maniobras:
   **seis flexiones** de muñeca (1 s cada una, contra la mesa), **seis
   extensiones**, y por último la **presa**.
3. **La presa, con detalle**, porque es la maniobra que da número y la que más
   fácil sale mal:
   - Antebrazo apoyado en la mesa hasta la muñeca, codo a 90°, pulgar hacia
     arriba, y **la muñeca fuera del borde, en el aire**. Si la muñeca descansa
     sobre la mesa, el tablero hace de estabilizador, el extensor afloja y la
     maniobra no mide nada.
   - Apretar algo que no se deforme y dé una postura repetible: un manguito de
     tensión enrollado, una pelota de tenis o una toalla apretada. Con
     dinamómetro de mano, mejor, porque además cuantifica el esfuerzo.
   - «Cierre el puño con fuerza y manténgalo» **5 s**, firme pero submáximo,
     guiándose por la barra de carga hacia el 50–60 %. **Nunca «extienda la
     muñeca»**: los extensores tienen que entrar solos.
   - Tres presas de 5 s separadas por 2 s dan más señal y siguen contando como una
     sola ventana, porque las filas seguidas con el mismo nombre se agrupan.
   - Va la última, para que su fatiga no contamine las flexiones ni las
     extensiones.
4. **Detener**. En Análisis, revisar las repeticiones y aceptar los fragmentos:
   la columna **Músculo** viene rellena con quién llevó cada contracción; corregir
   solo si la traza dice otra cosa. Las filas seguidas con el mismo nombre forman
   una sola ventana de la tabla de coactivación.

**Datos a recoger.**

| Ventana | FCR (% CVM medio) | ECR (% CVM medio) | Índice de coactivación |
|---|---|---|---|
| Flexiones | | | |
| Extensiones | | | |
| Presa | | | |

Del registro de eventos o del PDF, la **separación entre canales** durante la
calibración: ECR durante el máximo del FCR ____ %; FCR durante el máximo del ECR
____ %.

**Lo que enseña cada maniobra.** Las tres de este ejercicio, más la del 2b, forman
una progresión; conviene leerla entera antes de responder:

| Maniobra | Qué hacen los dos músculos | Qué da el índice |
|---|---|---|
| Flexiones | trabaja el FCR; el ECR no llega al suelo del 5 % | no se informa |
| Extensiones | los papeles se intercambian | no se informa |
| Presa | los dos trabajan a la vez | número alto, del orden del 60–95 % |
| Alternancia rápida (2b) | los dos trabajan, pero por turnos | número bajo |

La presa es la única maniobra de este montaje que produce un número, y la
comparación con la alternancia rápida del ejercicio 2b es la que cierra el
argumento: en las dos trabajan los dos músculos, pero solo en la presa trabajan **a
la vez**, que es lo que el índice mide. La coactivación es una propiedad de la
tarea, no del músculo.

**Cuestiones.**
- En las flexiones, ¿qué hace el ECR? Si su fila dice «no se informa», ¿por qué es
  eso la respuesta correcta y no un fallo?
- Durante la presa, ¿quién trabaja? Explique por qué los extensores de la muñeca
  se contraen con fuerza al cerrar la mano aunque nadie extienda nada, y qué tiene
  que ver con la epicondilitis lateral.
- La separación entre canales durante los máximos: ¿está por debajo del 25 %? Si
  pasa del 50 % la aplicación dice «canales sin separar». ¿Qué mide ese número y
  qué se puede hacer con los electrodos?
- Compare las MDF de los dos músculos en el panel 3. ¿Son distintas? ¿Qué puede
  significar una MDF muy por encima del rango habitual?

### Ejercicio 2b · Coactivación voluntaria y fatiga de un par

**Objetivo.** Ver que la coactivación depende de la tarea, no del músculo.

**Procedimiento.** Sin recalibrar, grabar de nuevo: 10 s de **flexiones y
extensiones alternas rápidas** (como agitar la mano), y luego una **presa
mantenida 30 s**.

**Datos a recoger.** Índice de coactivación de la ventana de alternancia y de la
presa; veredicto de fatiga de cada músculo en la presa (panel 7 dibuja los dos).

**Cuestiones.**
- ¿Sale más coactivación en la alternancia rápida o en la presa? ¿Por qué el
  índice compara la *forma* de las dos envolventes y no su tamaño?
- En la presa mantenida, ¿cuál de los dos músculos muestra antes la caída de la
  MDF? Proponga una explicación.

---

## Práctica 3 — Cinemática muscular (nivel avanzado)

**Montaje.** Un canal sobre el **bíceps braquial**, referencia en el olécranon, y
el **acelerómetro** del BITalino sujeto con cinta sobre el **dorso de la muñeca**
(el segmento que se mueve). Selector en **Cinemática muscular**. El cableado es
una convención que la caja del acelerómetro dice: **el músculo en A1 y el
acelerómetro en A2**. En esa caja, colocación «sobre el segmento que se mueve», y
en «Etiquetas» el nombre del músculo (bíceps), que va a la cabecera del EDF.

**Lo que enseña la aplicación en esta práctica.** Los controles finos aparecen
(corte de la envolvente, región, EDF afinado, estudio fuerza-velocidad). El
análisis ofrece los tres paneles básicos más **10. EMG vs MMG**, **11. Temblor** y
**12. Movimiento vs EMG**. La tabla de contracciones añade el **retraso
electromecánico (EMD)** de cada esfuerzo: el tiempo entre el inicio de la señal
eléctrica y el inicio del movimiento en el acelerómetro. El botón **«Ensayar…»**
corre todo el procedimiento de fuerza-velocidad sin hardware, con una señal
simulada, para aprenderlo antes de atar a nadie a nada.

### Ejercicio 3a · La relación fuerza-velocidad

**Objetivo.** Obtener la curva fuerza-velocidad del bíceps con cargas conocidas.

**Fundamento.** Cuanta más carga, más despacio se acorta el músculo; contra una
carga igual a su máximo no se mueve (isométrica). La potencia (fuerza × velocidad)
es máxima con cargas intermedias. El acelerómetro da la velocidad de la elevación
y el EMG la activación.

**Procedimiento.**
1. Preparar cuatro cargas conocidas (por ejemplo 0, 1, 2 y 3 kg: una botella y
   mancuernas o botellas llenas).
2. Pulsar **«F-V guiada…»**. Primero pide el **plan**: las cargas en orden, cuántas
   repeticiones por carga (dos o tres) y los segundos de preparación; si la
   grabación no estaba en marcha, la inicia. Después dirige la serie: un **máximo
   isométrico sin carga** de 3 s (codo a 90°, contra la mesa) y, para cada carga,
   las repeticiones pedidas de **una elevación rápida**, cada una con su cuenta
   atrás y marcada en el fichero con su carga. Basta seguir la pantalla.
3. **Detener**. En Análisis, la tabla de contracciones trae una fila por
   levantamiento con su carga, y **«Estudio fuerza-velocidad…»** lee esas filas y
   devuelve cuatro curvas: carga-velocidad, fuerza-velocidad (hiperbólica
   normalizada), potencia y reclutamiento (amplitud EMG frente a carga).

**Datos a recoger.**

| Carga (kg) | Velocidad pico (u. rel.) | RMS del bíceps (% CVM) |
|---|---|---|
| 0 | | |
| 1 | | |
| 2 | | |
| 3 | | |

Carga de potencia máxima: ____ kg.

**Cuestiones.**
- ¿Baja la velocidad al subir la carga? ¿Con qué forma? ¿Dónde cae la potencia
  máxima?
- ¿Sube la amplitud EMG con la carga aunque la velocidad baje? ¿Qué mecanismo lo
  explica?
- ¿Por qué la calibración isométrica del máximo se hace con el codo bloqueado?

### Ejercicio 3b · El retraso electromecánico

**Objetivo.** Medir el tiempo entre la orden eléctrica y el movimiento.

**Fundamento.** Entre que la fibra se despolariza y el segmento empieza a moverse
pasan unas decenas de milisegundos: liberación de calcio, formación de puentes,
tensado de los elementos elásticos en serie. En adultos sanos el retraso está
entre **30 y 100 ms** en contracciones voluntarias.

**Procedimiento.** Con el mismo montaje, **Iniciar grabación** y hacer **ocho
flexiones rápidas** del codo sin carga, partiendo del brazo relajado y colgando, con
3 s de reposo entre ellas. **Detener**. En la tabla de contracciones, columna
**EMD (ms)**.

**Datos a recoger.** EMD de las ocho flexiones; media y desviación.

**Cuestiones.**
- ¿Están sus valores dentro del rango? ¿Qué pasos fisiológicos ocupan ese tiempo?
- Repita tres flexiones **con 2 kg en la mano**. ¿Cambia el retraso? ¿Por qué el
  segmento tarda más en empezar a moverse cuando hay que vencer una carga?

### Ejercicio 3c · El temblor fisiológico

**Objetivo.** Ver el temblor fisiológico en el acelerómetro y situar su frecuencia.

**Procedimiento.** **Iniciar grabación** y mantener el brazo **extendido al frente,
horizontal, 30 s**, sin apoyo; después, otros 30 s sosteniendo 2 kg. **Detener**.
Panel **11. Temblor**: el espectro del acelerómetro.

**Datos a recoger.** Frecuencia del pico del temblor sin carga ____ Hz; con carga
____ Hz.

**Cuestiones.**
- ¿Cae el pico entre 8 y 12 Hz? ¿Cambia con la carga?
- El temblor fisiológico se debe en parte a la descarga sincronizada de unidades
  motoras y en parte a la mecánica del segmento. ¿Qué parte cambiaría con la
  carga y cuál no?

---

## Rangos orientativos para interpretar

Los números de la tabla son **orientativos**, no límites: valen para EMG de
superficie en adultos sanos, y dependen del músculo, de los electrodos y del
sujeto. Un valor fuera de rango es una pregunta, no un error. Estos mismos rangos
aparecen en gris bajo las fichas del resumen y en los «?» de las tablas.

| Medida | Rango orientativo | De dónde sale |
|---|---|---|
| Frecuencia media (MNF) | 80–170 Hz | el grueso de la energía del EMG de superficie está entre 50 y 150 Hz; la MNF queda siempre algo por encima de la MDF por la cola del espectro |
| Frecuencia mediana (MDF) | 60–150 Hz; en el antebrazo, más bien 90–150 | la misma banda; en el banco (FCR y ECR) 86–127 Hz con buen montaje; 176 Hz con el electrodo mal situado |
| Caída de la MDF con la fatiga | pendiente negativa clara; sin umbral universal de magnitud | la aplicación no exige una cuantía sino una tendencia que ajuste (R² ≥ 0,30, ≥ 4 ventanas de 1 s) |
| RMS en reposo | ≈ 0,005–0,02 mV | ruido de fondo del amplificador y la piel (≥ 8 µV pico a pico en el mejor caso) |
| RMS en esfuerzo firme | 0,1–1 mV; máximos hasta ~1,5 mV | electrodos de superficie sobre músculos de extremidad |
| Esfuerzo de tarea | 20–80 % CVM | un esfuerzo submáximo típico; > 100 % sostenido dice que la calibración no fue máxima |
| Máximo de la tarea con buena calibración | 90–125 % CVM | sesiones de banco con calibración correcta; la aplicación avisa en rojo a partir del 150 % |
| Coactivación del antagonista | 5–10 % CVM en esfuerzos suaves; 25–35 % en máximos | tríceps durante la flexión máxima del codo ≈ 26 %; extensor de los dedos durante la flexión de muñeca al 75 % ≈ 15 % |
| Índice de coactivación (Falconer-Winter) | movimiento recíproco: «no se informa»; presa firme: 60–95 % | el índice mide actividad compartida; en una flexión limpia el antagonista no llega al suelo del 5 % |
| Separación entre canales (diafonía) | ≤ 20–25 % de la propia referencia | banco con electrodos bien situados; > 50 %, «canales sin separar» |
| Carga estática (P10) | ≤ 2–5 % CVM (la aplicación usa 5) | Jonsson 1978, 1982 |
| Carga mediana (P50) | ≤ 10–14 % CVM (la aplicación usa 14) | Jonsson 1978, 1982 |
| Carga pico (P90) | ≤ 50–70 % CVM (la aplicación usa 70) | Jonsson 1978, 1982 |
| Retraso electromecánico | 30–100 ms; voluntario, 35–80 ms | Cavanagh y Komi 1979: bíceps 41 ± 13 ms, tríceps 26 ± 11 ms |
| Temblor fisiológico | pico a 8–12 Hz | acelerometría de la postura mantenida en adultos sanos |
| Umbral de inicio de contracción | reposo + 3 desviaciones típicas | Hodges y Bui 1996 |

---

## Anexo — Plantilla de informe del alumnado

Para cada práctica, entregar:

1. **Identificación**: identificador de prueba, músculo(s), dispositivo, práctica
   y ejercicios realizados.
2. El **informe PDF** que genera la aplicación (tiene las figuras, la calibración
   con sus repeticiones, la tabla de contracciones y las fichas). Con la difusión
   activa se descarga en el propio móvil.
3. Las **tablas de datos** de los ejercicios, copiadas del informe.
4. Las **respuestas razonadas** a las cuestiones, citando los números.
5. Una **conclusión** breve que relacione lo observado con la fisiología: unidad
   motora, reclutamiento, velocidad de conducción, relación fuerza-velocidad,
   riesgo ergonómico.

> **Nota para el profesorado.** Lo que decide la calidad de una práctica es la
> calibración: una máxima que no lo fue vuelve falsos todos los porcentajes, y la
> aplicación lo dice en rojo en la ficha «Máximo de la tarea». Conviene
> comprobarla antes de dejar que el grupo siga. Las cuestiones marcadas con
> comparaciones entre grupos funcionan mejor si cada grupo hace una tarea
> distinta en 1d. Los rangos de la tabla anterior están también en la aplicación,
> de modo que el alumno tiene contra qué interpretar sin abrir el guion.
