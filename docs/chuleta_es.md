# emgteach — Chuleta de laboratorio (1 página)

**Paso 0: elegir la práctica.** Desplegable de la esquina superior derecha. Fija
los canales y el acelerómetro, y de ahí se deriva todo lo demás.

| Modo | Canales | Acelerómetro |
|---|---|---|
| **Contracción de un músculo** | 1 | no |
| **Contracción agonista / antagonista** | 2 | no |
| **Cinemática muscular** | 1 | sí |

Al lado, la casilla **«Opciones avanzadas»** (cortes de filtro, umbrales, región de
interés, auto‑inicio) y el botón **«Guía»**, que relanza el recorrido guiado.

**Las 3 pestañas** · **Adquisición**: registrar en vivo · **Análisis**: estudiar un
EDF ya grabado · **CVM**: normalizar a % CVM y evaluar la carga muscular.

**Cadena de señal:** En bruto → *notch 50 Hz + paso‑banda 20–450 Hz* → **Filtrada** →
rectificada → **Envolvente** (paso‑bajo 5 Hz). *En el EDF solo se guarda la señal en
bruto; lo demás se recalcula.* **Fondo de escala:** BITalino ±1,635 mV · Arduino +
MyoWare ±12,5 mV.

---

### Registrar (Adquisición)
1. **Conectar** (dispositivo + MAC/puerto + carpeta de destino).
2. **Iniciar grabación**. Los eventos se marcan con la tecla **M** (o el botón).
3. **Detener** (se guarda el EDF).
- **LED:** rojo = desconectado · amarillo = sin datos · verde = recibiendo.
- **Escalas:** ▲▼ por gráfica; zoom temporal con desplegable / ◀▶ / rueda.
- **2 canales:** en bruto **apilada**; envolvente **superpuesta** (azul = canal 1,
  rojo = canal 2).
- **Carga en vivo:** **Calibrar CVM** grabando (contracción máxima unos segundos) →
  barras 🟢 Normal · 🟠 cansancio · 🔴 fatiga.

### Seguimiento en móviles (a la vista en los tres modos)
Casilla **«Difundir a móviles (en laboratorio)»** → **Copiar enlace** o **QR**. Todos
en la misma Wi‑Fi, dirección con `http://`. Cada activación genera un **código de
sesión** nuevo: los enlaces de la práctica anterior caducan.

### Analizar (Análisis)
Abrir EDF → elegir **canal** → paneles + resumen → **Generar informe PDF** (selección
de gráficos y de rango temporal).

**Para la tabla de coactivación hay que nombrar las maniobras.** «Seleccionar
fragmentos…» → columna **«Qué es»**: «Flexión», «Extensión», «Presa». Un
fragmento con nombre es una ventana de la tabla; sin nombre es solo señal que se
conserva. Nadie puede nombrarlo por usted —el detector sabe dónde empezó una
contracción, no cuál era—, y por eso la tabla dice «registro completo» mientras
no se haga. Siempre **1A. En bruto**, **2. Env. norm.** y
**3. PSD**; con opciones avanzadas los paneles **4 a 8** (la fatiga está en el
**7. MDF/tiempo**); según el modo, el **9** (envolventes superpuestas) o los
**10 · 11 · 12** (acelerómetro).

### Normalizar y carga (CVM)
**El EDF de la sesión** → paneles + **gráfico APDF** + panel de datos → **informe
PDF**. No se pide ningún segundo archivo: la referencia sale de la calibración
que el propio registro lleva marcada, y la carga se mide sobre la **fase de
registro**, no sobre el fichero entero.

---

### Métricas clave — qué significan
| Métrica | Significado |
|---|---|
| **RMS / envolvente** | Amplitud → **nivel de activación** (≈ fuerza, no lineal) |
| **iEMG** | Actividad total acumulada (área bajo la envolvente) |
| **MNF / MDF** | Frecuencia media / mediana del espectro (PSD) |
| **MDF ↓ con el tiempo** | **FATIGA** (el espectro se desplaza a frecuencias bajas) |
| **% CVM** | Activación respecto al máximo (permite comparar) |

### Carga muscular (método de Jonsson, en % CVM)
| Nivel | = | Significado | Límite orientativo |
|---|---|---|---|
| **Estático** | P10 | Carga casi continua "de fondo" | ≤ ~5 % |
| **Mediano** | P50 | Carga de trabajo típica | ≤ ~14 % |
| **Pico** | P90 | Esfuerzos altos recurrentes | ≤ ~70 % |

🔴 **En rojo** = supera su límite. ⚠️ Sin calibración en el registro no hay
máximo del que ser porcentaje: no se calculan ni el % CVM ni estos tres
niveles, y el gráfico APDF no se dibuja. La señal y su envolvente sí.

### Problemas rápidos
- **Sin señal / línea plana** → contacto de electrodos, referencia, canal correcto.
- **Ruido 50 Hz** → mejorar contacto; alejar cargadores/cables.
- **"Sin calibrar"** → **Calibrar CVM** *mientras se graba*.
- **No aparece la caja de la MAC / el puerto** → está tras **Opciones avanzadas**.
- **Falta el selector de canales o del acelerómetro** → los fija el **modo**.
- **El registro no coincide con el modo** → el EDF tiene un canal y agonista /
  antagonista necesita dos.
- **Informe ilegible (registro largo)** → acortar el **rango temporal** en el diálogo.
- **BITalino no conecta** → emparejar antes en Bluetooth del sistema y dar su
  **dirección MAC** (o dejar el campo vacío para autodetectar).

> **Idea clave:** *amplitud = cuánto se activa el músculo; frecuencia = fatiga.*
