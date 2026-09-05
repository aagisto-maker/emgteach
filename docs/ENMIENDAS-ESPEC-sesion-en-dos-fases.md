# Enmiendas a `ESPEC-sesion-en-dos-fases.md`

Escrito por Claude Code el 31 de agosto de 2026, tras revisar la especificación y hablarlo con Ángel.
**Se lee junto a la espec, no la sustituye.** La espec queda como se escribió; aquí está lo que cambia,
lo que ya estaba hecho antes de que la espec se escribiera, y una decisión nueva.

Estado del repo al escribir esto: rama `feat/ui-levels`, commit `4d83c00`, 511 tests en verde, ruff limpio.

---

## 0. Lo que ya está implementado — no volver a hacerlo

La espec se escribió sobre el commit `7234b02`. Después de ese punto entró `4d83c00`, que **ya resuelve
parte del §1.1 y del §5**:

- La pestaña de Normalización CVM **lee la referencia de la anotación `MVC ref` del propio fichero**.
  Precedencia implementada: fichero de referencia elegido a mano → calibración interna → auto.
- El aviso rojo falso «auto, no es %CVM real» **ya no sale sobre un archivo calibrado**. La incoherencia
  entre pestañas del §1.1 está cerrada.
- El botón «Calcular CVM» ya no exige un segundo fichero cuando el primero trae su calibración.
- Existe `io.read_edf_markers()`: lee la tabla de anotaciones **sin cargar una sola muestra**. Es la
  pieza de lectura que `phases.py` necesita; reutilizarla.
- La pestaña CVM acepta `roi_segments` y el worker recorta.

**Sobre el recorte, la espec tiene razón contra lo que se implementó.** El §1.2 dice que separar la
calibración del registro no debe depender de que el usuario elija fragmentos a ojo, y es cierto: la
aplicación sabe dónde estuvo la calibración. Ese uso lo sustituye el modelo `CAL`/`REC`. Lo que **no**
se tira es el editor de fragmentos: queda restringido al tramo `REC`, que es exactamente el §4.1.

---

## 1. Tres cambios a la especificación

### 1.1 El §5 va demasiado lejos al eliminar «la auto-normalización del programa»

Contradice al §9, que conserva el panel 2 —«% del máximo del propio registro»—, que es **la misma
operación con otro nombre** y honradamente etiquetada. Quitarla de un sitio y mantenerla en otro no
simplifica: deja una inconsistencia distinta.

**Redacción propuesta para el §5:** elimínese la ruta auto **del análisis de carga muscular (Jonsson)**,
por ninguna vía, tampoco contra la propia señal — eso es correcto y es el núcleo. Con ella se van
`_auto_aceptada`, el botón «Usar este registro», el sufijo rojo «(auto-normalizado)» y la casilla de
avanzadas que lo habilitaba. **Consérvese** «normalizado a su propio máximo» donde ya está y ya se llama
así (panel 2, y el eje del APDF cuando no hay referencia). El modo de fallo desaparece igual.

### 1.2 El §4.2 debe deshabilitar con motivo, no ocultar

La espec pide que las medidas sin calibración «no se muestren en gris ni con un aviso al pulsar, no
estén». Hay dos razones para no hacerlo así:

1. **El propio código ya lo tiene decidido.** Comentario en `mvc.py`: *«un botón deshabilitado que no
   dice por qué es lo peor de los dos mundos: la pestaña parece rota en vez de incompleta»*.
2. **La espec se pide a sí misma dos cosas distintas para el mismo caso:** ocultar en Análisis (§4.2),
   pero «aviso claro» en la pestaña CVM (§5).

Un alumno que olvidó calibrar y ve *una aplicación distinta* no puede saber por qué. Uno que ve el
control deshabilitado con «no hay calibración en este registro» aprende justo lo que la práctica quiere
enseñar. **Deshabilitado + motivo en las dos pestañas.** Es una línea de diferencia si más adelante se
prefiere lo contrario.

### 1.3 El §3.3 tiene un hueco que hay que cerrar antes de escribir el test 11.2

La regla «los tramos `CAL` son la fuente, `MVC ref` es caché» es correcta. Pero **la referencia
recalculada no va a coincidir exactamente con la anotada, aunque no se descarte ninguna repetición**:

- la del asistente sale de la **envolvente en línea** durante la adquisición;
- la recalculada sale de `process_offline` (**filtrado de fase cero**, y con el `f_env` que tenga la
  pestaña en ese momento).

Diferencias de unos pocos por ciento. Si no se decide ahora aparecerá como un fallo, y además **el test
11.2 pasaría por el motivo equivocado**: basta con que los dos valores difieran para que «devuelve la
recalculada» parezca cierto.

**Decisión propuesta:** recalcular siempre que haya tramos `CAL`; mostrar la procedencia; y que el test
compare contra **un valor que el propio test calcula desde los tramos**, no contra «distinto de la
anotación». Documentar en `phases.py` que la discrepancia es esperada y por qué.

---

## 2. Decisión nueva (31-ago): las marcas se ponen **después** del registro

Acordado con Ángel. Motivo suyo, textual: *«el registro va más rápido del posible proceso de marcar
manualmente»*. Nunca ha usado el botón MARK en ninguna sesión.

### 2.1 El dato que obliga a decidirlo

De los **siete registros** de los días 30 y 31 de agosto, **ninguno tiene una sola marca de fase**. Todas
las anotaciones son `Onset (auto)` más las `MVC ref`. Por eso la tabla de coactivación ha dicho siempre
«Registro completo — marque las fases», y por eso **siguen faltando dos de los cuatro números del banco**
(pico del extensor en %CVM durante la presa, e índice de coactivación en esa maniobra).

**Lo automático solo no puede producirlos, nunca.** El detector dice *«aquí empezó una contracción»*; el
índice necesita *«esta ventana es la presa»*. La diferencia entre flexión, extensión y presa no está en
la forma de la envolvente: está en lo que se le pidió al sujeto. Ningún algoritmo va a nombrarla.

### 2.2 Qué se hace

| | Hoy | Nuevo |
|---|---|---|
| Adquisición | `_combo_etiqueta` (presets), botón **MARK**, atajo de teclado, lista editable de marcadores con «Borrar» | **fuera, entero** |
| Adquisición | casilla «Auto-onset» + `k` | **se queda**, configurable como está |
| Análisis | fragmentos sin nombre | fragmentos **con nombre**; los nombrados son las ventanas de la tabla de coactivación |

- Los **presets de marca** (`profile.marker_presets`) no se pierden: pasan a ser los nombres sugeridos en
  el editor de fragmentos.
- La **lista editable de marcadores** existe hoy explícitamente como *«el arreglo para un MARK pulsado por
  error»* (comentario en el código). Sin MARK, deja de tener razón de ser.
- `_marker_events` **se queda**: sigue alimentando el dibujo en vivo sobre las gráficas y el broadcast,
  ahora solo con los inicios automáticos.

### 2.3 Por qué no complica

El editor de fragmentos ya existe, con su geometría, su arrastre y su sugerencia automática de periodos
activos. **Añadirle un campo de nombre por fragmento es todo el trabajo.** Y la espec ya lo está
restringiendo al tramo `REC` (§4.1), así que es la misma pasada, no una nueva.

Además es mejor pedagógicamente: el alumno mira la traza y decide «esto es la presa». Ese acto de
interpretación *es* la práctica. Pulsar una tecla en el momento justo no enseña nada, y es una tercera
tarea mientras ya se vigilan el sujeto y la señal.

### 2.4 El único inconveniente, dicho en voz alta

Marcar en vivo tenía una ventaja real: se sabe en el momento qué se le pidió al sujeto. Marcando después
hay que reconocerlo en la traza. Para este protocolo no es problema —flexión, extensión y presa se
distinguen en el panel 9 por cuál de los dos músculos lidera— pero **conviene hacer siempre las maniobras
en el mismo orden** y decirlo en el protocolo de la práctica.

### 2.5 Dónde encaja

Es una línea añadida al **§4.1** de la espec: *«los fragmentos del tramo REC pueden llevar nombre, y los
nombrados son las ventanas de la tabla de coactivación»*.

- **Primera versión:** los nombres viven en la sesión de análisis y alimentan la tabla directamente. Sin
  tocar el fichero.
- **Después:** escribirlos de vuelta al EDF, que es el «EDF afinado» del §4.3.

---

## 3. Corrección de dato: el §8.3 ya está hecho, y el método que propone mide otra cosa

`coact_floor_pct` dejó de ser una estimación el 30 de agosto. Medido sobre `emg_2026-08-30_19-18.edf`,
con las dos referencias ya máximas, y anotado en `profiles.py`:

- ventana quieta: media de **0,2 % (FCR)** y **0,8 % (ECR)** de CVM **sobre reposo**;
- ventana activa: media de **19–30 %**;
- niveles de reposo propios: **2 % (FCR)** y **4 % (ECR)** de CVM.

El umbral del 5 % cae en un hueco de un factor treinta. **La conversión que propone el §8.3** —pasar los
3,4 y 10,8 µV de reposo a %CVM— **daría 2,1 % y 3,6 %**, que parece rozar el umbral y sugeriría subirlo;
pero es la cantidad equivocada: el suelo se aplica a la media **con el reposo ya restado**, no al reposo
en bruto. Subirlo por esa vía tumbaría ventanas buenas.

Los otros dos puntos del §8 siguen vivos y son correctos, sobre todo el 2 (ventanas de menos de dos
muestras descartadas en silencio), que es de la misma familia que todo lo demás.

---

## 4. Notas de implementación

1. **Tramos `CAL` sin cerrar.** Si se detiene a mitad de una repetición queda un `CAL start` huérfano.
   `phases.py` debe descartar pares incompletos, y hay que probarlo.
2. **Alternativa a start/end:** `BufferedEdfWriter.add_annotation()` escribe hoy duración `-1` fija;
   añadirle el parámetro de duración permitiría **una sola anotación por repetición**. Se mantiene
   start/end por coherencia con `fv_load_marker`, pero que sea una decisión y no un descuido.
3. **La lista de repeticiones del §4.1 debería llevar una columna más: la diafonía de cada repetición.**
   Ya se calcula (`_mvc_crosstalk` en `acquisition.py`). En la sesión del 30-ago la repetición mala del
   ECR se identificaba tanto por floja (72 % de su referencia) como por su diafonía (34 %, frente al 16 %
   de las otras dos). Con las dos columnas la decisión de descartar está informada; con una sola, es
   media decisión.
4. **El §4.3 (EDF afinado) es el momento de arreglar el `patientname`.** La cabecera lleva el nombre del
   alumno (`io.py:166`), y el fichero derivado es el que acabará circulando: debe escribir el **código**,
   no el nombre. Y tiene que reescribirse con `BufferedEdfWriter`, no a mano — es exactamente el fallo
   del artículo de la escritura tamponada.

---

## 5. Orden de construcción revisado

El del §10 es correcto; el único ajuste es que el beneficio del paso 3 (cerrar la incoherencia entre
pestañas) **ya está entregado**, así que el punto de parada seguro se mueve hacia adelante.

1. **`phases.py`** — anotaciones de fase, parseadores y `mvc_reference()` con su regla de precedencia.
   Sin tocar interfaz. Se prueba solo.
2. **Escritura de las fases en la grabación** — calibración → PREP → registro, sin detener la adquisición.
3. **Lectura en Análisis** — usar `mvc_reference()`, mostrar procedencia, deshabilitar con motivo (§1.2).
4. **Lista de repeticiones** con recálculo y columna de diafonía. ← **buen punto de parada:** aquí está
   el valor visible para el alumno.
5. **Nombres en los fragmentos del tramo REC** (§2 de este documento) y ventanas de coactivación.
6. **Pestaña CVM:** fuera el selector de referencia y la ruta auto de Jonsson (§1.1).
7. **EDF afinado** con trazabilidad y el `patientname`.
8. Los dos pendientes vivos del §8.

**Tamaño honesto:** cinco a siete sesiones de trabajo con prueba de hardware entre medias, no una. Toca
adquisición, formato de fichero, tres pestañas, informes, exportaciones e i18n. El §13 tiene razón en que
es el momento y en que debe ser el último cambio de arquitectura antes de la release.

---

## 6. Para el artículo, y no es menor

En el traspaso del 30-ago se cuentan tres casos «de la misma familia». Son **cuatro**, y tienen forma:

> *un cálculo que devuelve un número cuando su condición previa no se cumple.*

| Medida | Condición previa ausente | Qué devolvía |
|---|---|---|
| Auto-normalización | no hay contracción máxima de referencia | %CVM que no son %CVM |
| Panel 9 en milivoltios | no hay escala común entre dos músculos | dos curvas incomparables |
| Veredicto de fatiga | no hay contracción mantenida | «Fatiga: DETECTADA, MDF −26,4 %» |
| Índice de coactivación | no hay calibración (§4.2 de la espec) | un índice sobre referencias falsas |

Formulado como **principio de diseño** —«toda medida declara su condición previa y se niega a producir un
número sin ella»— es una contribución del artículo. Formulado como cuatro erratas corregidas, es una
tabla de resolución de problemas. Sugerencia: el principio en §3.3, junto al umbral R² ≥ 0,30 del
veredicto de fatiga; la tabla, para el detalle.
