# Acelerómetro (ACC) + sEMG en emgteach — informe de investigación

> Nota de investigación (no forma parte del repo publicado). Generada con búsqueda
> en profundidad multi-fuente + verificación adversarial: 22 fuentes → 85
> afirmaciones → 25 verificadas por votación (21 confirmadas, 4 refutadas).

## Conclusión breve

Emparejar el canal **ACC del BITalino con el sEMG es técnicamente directo y
pedagógicamente sólido**. El ACC se lee como una entrada analógica más, con el
**mismo reloj y frecuencia de muestreo** que el EMG → quedan **sincronizados a
nivel de muestra sin trigger externo**. Aporta tres cosas robustas y bien
fundadas: (a) **cinemática/fases del movimiento** para docencia, (b) **referencia
de artefacto de movimiento**, y (c) **mecanomiografía (MMG)** — la respuesta
*mecánica* del músculo como "hermana" del EMG *eléctrico*.

## 1. Usos docentes (confianza alta)

- Registrar **sEMG + cinemática articular a la vez** para identificar fases de
  contracción (agonista/antagonista, concéntrica/excéntrica, isométrica/isotónica)
  es un formato docente validado. El clásico es EMG del bíceps en un "pulso" con
  goniómetro en el codo — el ACC del BITalino sustituye al goniómetro.
  ([Adv Physiol Educ 2019](https://journals.physiology.org/doi/full/10.1152/advan.00029.2019);
  [currículo EMG 2024/26](https://journals.physiology.org/doi/full/10.1152/advan.00237.2024);
  [lab EMG alumnos](https://pubmed.ncbi.nlm.nih.gov/10644259/))
- Combinar sEMG con acelerometría da "una imagen más completa de la función
  muscular" en distintas tareas — afirmación *mainstream*, no exótica.
  ([Frontiers Neurol 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7594523/))
- Encaja con lo que ya haces: **CVM/%MVC, fatiga y principio de Henneman** se
  enseñan con EMG en tiempo real; el ACC añade el eje mecánico.

## 2. Técnicas de señal

- **Rechazo de artefacto de movimiento (alta).** El artefacto de EMG concentra su
  potencia **<20 Hz**; el estándar es un **paso-alto Butterworth de 20 Hz,
  12 dB/oct**, que golpea mucho más al artefacto que a la señal. Un acelerómetro
  **pegado junto al electrodo** es un método validado para **monitorizar/marcar**
  los tramos con movimiento. ⚠️ El filtro **atenúa, no elimina** (solape espectral).
  ([De Luca et al. 2010](https://www.bu.edu/nmrc/files/2010/06/103.pdf);
  [Frontiers Neurol 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7594523/))
- **Mecanomiografía / MMG (alta).** El acelerómetro sobre el vientre muscular capta
  la vibración de la contracción. La **duración/timing sEMG y MMG son equivalentes**
  (cuádriceps en sentadilla: 2.552±0.589 s vs 2.560±0.576 s, p=0.82), la banda
  **<5 Hz segmenta las fases del movimiento**, y la **amplitud RMS de MMG es más
  sensible a la carga** que la del EMG en dinámico. ⚠️ En dinámico la MMG **se
  contamina** con artefacto en su misma banda (~5–20 Hz) y hay que filtrarla.
  ([Kim et al. 2023](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10346542/);
  [Sensors 23:7969](https://www.mdpi.com/1424-8220/23/18/7969);
  [arXiv 2508.20602](https://arxiv.org/pdf/2508.20602))
- **Onset (alta).** Los métodos **automáticos de onset son poco sensibles** ante
  eventos breves; se recomienda **detección visual**, mejorada con acondicionamiento
  **TKEO**. El ACC *podría* aportar un evento cinemático de referencia (retardo
  electromecánico) — plausible pero **no probado** por la fuente.
  ([Crotty et al. 2021, Physiol Meas](https://iopscience.iop.org/article/10.1088/1361-6579/abef56))

## 3. Temblor y cadencia (media)

- Un **eje del ACC + FFT** estima con fiabilidad la **frecuencia** del temblor (la
  amplitud es menos fiable). Sirve para demostrar el pico (fisiológico ~8–12 Hz vs
  patológico ~4–6 Hz).
  ([Frontiers, wearables tremor](https://www.frontiersin.org/articles/680011))
- Conteo de repeticiones/cadencia y contexto postural: usos directos del ACC
  (segmentación por umbral en banda baja).

## 4. Viabilidad en BITalino/emgteach (alta)

- El **ACC es una entrada analógica estándar (A5)**, digitalizada por el **mismo ADC
  y reloj** que el EMG. Basta indicar `srate` y la lista de canales en **una sola
  llamada** (`device.start(srate, [canales])`) → **sincronía a nivel de muestra**,
  sin hardware extra.
  ([BITalino lab guide](https://github.com/BITalinoWorld/python-lab-guides/blob/master/BITalino%20Hands-on/README.md);
  [PLUX OpenSignals](https://support.pluxbiosignals.com/knowledge-base/how-to-set-up-my-bitalino-in-opensignals-device-manager/))
- ⚠️ **Dos avisos de resolución/muestreo:** (1) el `srate` (1/10/100/1000 Hz) es
  **común a todos los canales**; (2) al usar **5–6 canales**, A5/A6 **caen a 6-bit**
  (vs 10-bit en A1–A4), así que el ACC tendría menos resolución que el EMG. Conviene
  **limitar el nº de canales** si quieres MMG/temblor finos.

## ❌ Lo que NO conviene afirmar (refutado en la verificación)

- MMG como **proxy lineal de fuerza** (R²=0.94) — refutado 0-3.
- **Onset de MMG fiable entre días** (ICC≈0.78) — refutado.
- **Cancelación activa** del artefacto de EMG con acelerómetro MEMS colocado —
  refutado (demostrado en EEG/ECG, no en EMG).
- Que EMG+inercial dé la **mejor discriminación de patrones de temblor** —
  refutado 0-3.

## Propuesta concreta para emgteach (por esfuerzo/valor)

1. **Canal ACC opcional en Adquisición** (bajo): añadir A5, graficarlo bajo el EMG
   y guardarlo como canal extra en el EDF. Ya tienes infraestructura multicanal.
2. **Segmentación de fases + marcador de artefacto** (medio): banda <5 Hz del ACC →
   detectar inicio de movimiento, marcar fases y **sombrear/avisar** tramos de EMG
   con artefacto (ACC alto).
3. **Práctica "EMG eléctrico vs MMG mecánico"** (medio, alto valor docente):
   envolvente RMS de EMG vs RMS de MMG en la misma contracción — demostración muy
   visual del acoplamiento electromecánico.
4. **Demo de temblor** (bajo): FFT de un eje del ACC en contracción sostenida → pico
   de frecuencia, que complementa el descenso de MDF en la práctica de fatiga.

## Caveats

- La equivalencia sEMG/sMMG se apoya en estudios con **N pequeño** y **sin test
  formal de equivalencia** (TOST); la MMG y la carga tienen muestras limitadas
  (solo varones en el estudio de carga).
- El "rechazo" por paso-alto es **atenuación**, no eliminación total.
- **Resolución de 6-bit** del ACC con 5–6 canales: tenerlo en cuenta para MMG/temblor.
- Fechas: el paper de currículo (advan.00237.2024) figura 2026 y el de filtrado MMG
  (arXiv) es preprint 2025 — verificar versión final.

## Fuentes principales

| Fuente | Tipo | Uso |
|---|---|---|
| [Adv Physiol Educ 2024/26 — EMG en currículo](https://journals.physiology.org/doi/full/10.1152/advan.00237.2024) | Primaria | Docencia, Henneman, fatiga |
| [Adv Physiol Educ 2019 — arm-wrestling + goniómetro](https://journals.physiology.org/doi/full/10.1152/advan.00029.2019) | Primaria | EMG + cinemática |
| [Lab EMG alumnos (PubMed 10644259)](https://pubmed.ncbi.nlm.nih.gov/10644259/) | Primaria | Formato docente |
| [Frontiers Neurol 2020 — revisión sEMG](https://pmc.ncbi.nlm.nih.gov/articles/PMC7594523/) | Primaria | Artefacto <20 Hz; combinar con ACC |
| [De Luca et al. 2010 — filtrado sEMG](https://www.bu.edu/nmrc/files/2010/06/103.pdf) | Primaria | 20 Hz Butterworth; ACC junto al sensor |
| [Kim et al. 2023 (PMC10346542)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10346542/) | Primaria | Equivalencia timing sEMG/MMG |
| [Sensors 23:7969 (2023)](https://www.mdpi.com/1424-8220/23/18/7969) | Primaria | <5 Hz segmenta fases; RMS MMG vs carga |
| [arXiv 2508.20602 (2025)](https://arxiv.org/pdf/2508.20602) | Primaria | Filtrado MMG dinámica |
| [Crotty et al. 2021 (Physiol Meas)](https://iopscience.iop.org/article/10.1088/1361-6579/abef56) | Primaria | Onset visual + TKEO |
| [Frontiers — wearables tremor](https://www.frontiersin.org/articles/680011) | Secundaria | Frecuencia de temblor por ACC |
| [BITalino lab guide (GitHub)](https://github.com/BITalinoWorld/python-lab-guides/blob/master/BITalino%20Hands-on/README.md) | Primaria | ACC = A5; API síncrona |
| [PLUX OpenSignals](https://support.pluxbiosignals.com/knowledge-base/how-to-set-up-my-bitalino-in-opensignals-device-manager/) | Primaria | srate común; canales |
