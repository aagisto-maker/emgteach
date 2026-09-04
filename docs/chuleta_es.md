# emgteach — Chuleta de laboratorio (2 páginas)

**Paso 0: elegir la práctica.** Desplegable de la esquina superior derecha. La
banda de al lado dice el nivel. Todo lo demás se deriva de esa elección.

| Práctica | Nivel | Canales | Qué mide |
|---|---|---|---|
| **Contracción de un músculo** | básico | 1 | amplitud, espectro, fatiga, carga |
| **Contracción agonista / antagonista** | intermedio | 2 | dos músculos en % CVM, coactivación |
| **Cinemática muscular** | avanzado | 1 + acelerómetro | fuerza-velocidad, retraso electromecánico, temblor |

**«Guía»** relanza el recorrido de cinco pasos; cada caja tiene un **«?»** en su
esquina con lo que hace.

**Las 3 pestañas** · **Adquisición**: grabar · **Análisis**: leer un registro (se
analiza solo al abrirlo) · **Normalización CVM**: la tarea en % CVM y su carga.

**Cadena de señal:** en bruto → *notch 50 Hz + paso-banda 20–450 Hz* → rectificada
→ **envolvente** (paso-bajo 5 Hz). *En el EDF solo va la señal en bruto; lo demás
se recalcula.* Fondo de escala BITalino ±1,635 mV.

---

### Grabar (Adquisición)
1. **Conectar**. Solo la práctica de un músculo elige dispositivo; las otras dos
   son BITalino. Identificarlo por su **MAC**. Escribir las **etiquetas** de los
   músculos (Músculo 1 = A1) y el **identificador de prueba**.
2. **Iniciar grabación**. En el par, el asistente calibra los dos músculos antes
   de la tarea. En las otras dos, **«Calibrar CVM»** mientras se graba.
3. **Detener**: se guarda el EDF y aparece la sesión entera con sus tramos.
- **Calibración**: 10 s de calentamiento; por músculo, **3 máximas mantenidas**
  (4 s) y **3 sacudidas breves** (1,5 s). Referencia = el mejor 0,2 s de las seis.
- **El máximo se hace contra la mesa, nunca contra una mano.** FCR: **puño
  cerrado**, palma arriba bajo el canto de la mesa. ECR: dorso de la mano contra
  el tablero. Muñeca unos 20° hacia el lado contrario a la acción del músculo.
- **Auto-inicio** marca solo cada contracción (umbral = reposo + k × ruido, k = 3).
- **Barras de carga** tras calibrar: 🟢 hasta 40 % · 🟠 hasta 70 % · 🔴 más.

### Seguir la sesión desde el móvil
Casilla **«Difundir a móviles (en laboratorio)»** → **QR** o enlace
`http://…:8070/?k=…`. Misma Wi-Fi, con `http://`. Cada activación cambia el código.

### Analizar (Análisis)
Al abrir el registro se analiza solo. Seguir los cuadros que aparecen, en orden:
1. **«Repeticiones de la calibración…»**: quitar las flojas. Primero, porque fija
   la referencia de todos los porcentajes.
2. **«Seleccionar fragmentos…»**: una fila por contracción; desmarcar las malas
   (y, en la práctica de un músculo, los esfuerzos de calibración) y **«Usar estos
   fragmentos»**. Dos deslizadores en vivo: **sensibilidad** y, en el par, **umbral
   de coactivación**; pulsar sobre un tramo sombreado lo quita o lo repone; el
   ajuste fino, plegado.

Después leer: **paneles** (rueda del ratón para desplazar; ▲▼ amplitud, ▶◀ tiempo),
**gráfico de contracciones** (una vista cada vez, en su título: **Relación**,
amplitud frente a MDF con un músculo o un músculo frente al otro con la cuña de
coactivación en el par; en el par **Categoría** y **Quién lidera**; **Serie**; en
cinemática **Por carga**; y **Tabla** con los números), **resumen** en fichas, y
en el par el **gráfico de coactivación** (una barra por ventana con el índice, con
su «Gráfico · Tabla»). **«Generar informe PDF»** = entregable.

Paneles por práctica: un músculo **1A · 2 · 3**; par **1A · 1B · 3 · 7 · 9**;
cinemática **1A · 2 · 3 · 10 · 11 · 12**. **«Más paneles…»** revela el resto.

### Normalizar y carga (Normalización CVM)
Se calcula solo al recibir el registro. **«Seleccionar fragmentos…»** para dejar
solo la tarea (sin la calibración). Panel de datos: P10 / P50 / P90 y su límite.

---

### Qué significan los números
| Medida | Significado | Orientativo |
|---|---|---|
| **RMS** | cuánto se activa el músculo (no lineal con la fuerza) | reposo ≈ 0,01 mV · esfuerzo 0,1–1 mV |
| **Pico (% CVM)** | el esfuerzo respecto al propio máximo | tarea 20–80 % · > 150 % = la calibración no fue máxima |
| **MNF / MDF** | frecuencia media / mediana del espectro | 80–170 / 60–150 Hz |
| **MDF ↓ con el tiempo** | **fatiga** (pendiente negativa que ajuste, R² ≥ 0,30) | «no concluyente» = el registro no responde |
| **Índice de coactivación** | actividad compartida por los dos músculos | recíproco: «no se informa» · presa: alto |
| **Separación entre canales** | lo que un canal lee del otro músculo en su máximo | ≤ 25 % bien · > 50 % «sin separar» |
| **P10 · P50 · P90** | carga estática · mediana · pico (Jonsson) | ≤ 5 · 14 · 70 % CVM |
| **EMD** | de la señal eléctrica al movimiento | 30–100 ms |
| **Temblor** | pico del espectro del acelerómetro | 8–12 Hz |

### Problemas rápidos
- **Sin señal / línea plana** → contacto de electrodos, referencia, canal correcto.
- **Ruido a 50 Hz** → mejorar contacto; alejar cargadores y cables.
- **«no fue un máximo»** (en rojo, Máximo de la tarea) → recalibrar contra la
  mesa, puño cerrado, mantener los 4 s.
- **La tabla de coactivación dice «no se informa»** → en una flexión o extensión
  limpia es lo correcto; hace falta una **presa** para que dé número.
- **La presa no coactiva** → la muñeca está apoyada en la mesa. Tiene que quedar
  **en el aire, fuera del borde**: apoyada, el tablero estabiliza y el extensor
  afloja. Y nunca se pide «extienda la muñeca»: los extensores entran solos.
- **«Canales sin separar»** → separar los pares hacia el borde cubital y dorsal;
  cada par sobre su vientre; antebrazo apoyado.
- **«Fatiga: no concluyente»** → contracción demasiado corta o intermitente;
  seleccionar solo el tramo mantenido.
- **No aparece el cuadro guía** → pasar a la pestaña Análisis: espera allí.
- **BITalino no conecta** → emparejar antes en Bluetooth del sistema y dar su
  **MAC** (o dejar el campo vacío para autodetectar).

> **Idea clave:** *amplitud = cuánto se activa el músculo · frecuencia = si se
> fatiga · % CVM = con qué compararlo.*
