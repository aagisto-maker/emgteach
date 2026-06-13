# emgteach — Chuleta de laboratorio (1 página)

**Las 3 pestañas** · **Adquisición**: registrar en vivo · **Análisis**: estudiar un
EDF ya grabado · **CVM**: normalizar a % CVM y evaluar la carga muscular.

**Cadena de señal:** En bruto → *notch 50 Hz + paso‑banda 20–450 Hz* → **Filtrada** →
rectificada → **Envolvente** (paso‑bajo 5 Hz). *En el EDF solo se guarda la señal en bruto;
lo demás se recalcula.*

---

### Registrar (Adquisición)
1. **Conectar** (elige dispositivo + MAC/puerto + carpeta + nº de canales).
2. **Iniciar grabación**. Marca eventos con la tecla **M** (o el botón).
3. **Detener** (se guarda el EDF). Puedes activar **Auto‑inicio** (marca inicios
   de contracción solo).
- **LED:** rojo = desconectado · amarillo = sin datos · verde = recibiendo.
- **Escalas:** ▲▼ por gráfica; zoom temporal con desplegable / ◀▶ / rueda.
- **2 canales:** en bruto y filtrada **apiladas**; envolvente **superpuesta** (azul =
  canal 1, rojo = canal 2).

### Carga muscular en vivo
1. **Iniciar grabación** → **Calibrar CVM** (contrae al **máximo** unos segundos).
2. Observa las **barras**: 🟢 Normal · 🟠 *Warning* (cansancio) · 🔴 *Danger* (fatiga).

### Analizar (Análisis)
Abrir EDF → elegir **canal** → revisar paneles + resumen → **Generar informe PDF**
(elige gráficos y rango temporal).

### Normalizar y carga (CVM)
Cargar **EDF de prueba** (+ opcional **EDF de CVM**) → ver paneles + **gráfico APDF**
+ panel de datos → **informe PDF**.

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

🔴 **En rojo** = supera su límite (revisar carga/ergonomía).

---

### Problemas rápidos
- **Sin señal / línea plana** → contacto de electrodos, referencia, canal correcto.
- **Ruido 50 Hz** → mejorar contacto; alejar cargadores/cables.
- **"Sin calibrar"** → pulsa **Calibrar CVM** *mientras grabas*.
- **Informe ilegible (registro largo)** → acorta el **rango temporal** en el diálogo.
- **BITalino no conecta** → emparejar Bluetooth; usar **Python ≤ 3.11**.

> **Idea clave:** *amplitud = cuánto se activa el músculo; frecuencia = fatiga.*
