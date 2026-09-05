# emgteach — la sesión pasa a tener dos fases dentro del mismo archivo

Especificación de implementación. Escrita el 31 de agosto de 2026 sobre la rama `feat/ui-levels`,
commit 7234b02. Sustituye por completo al modelo de «archivo de calibración aparte».

**Léela entera antes de tocar nada.** No es una lista de arreglos: cambia el modelo de datos, y de ahí
se derivan los cambios de las tres pestañas. Si se implementa por partes en otro orden, quedan estados
intermedios incoherentes.

---

## 1. Qué está mal hoy

La calibración ya se usa en todos los análisis: la referencia viaja en el EDF como anotación y la
pestaña de Análisis la lee. Pero **la aplicación sigue anclada en el diseño anterior**, en el que la
calibración era un archivo distinto que el usuario elegía a mano. De ahí salen tres incoherencias:

1. La pestaña de Normalización CVM pide un «EDF de referencia» aunque el registro que tiene abierto ya
   lleve dentro las dos referencias. Enseña en rojo «auto, no es %CVM real» sobre un archivo calibrado.
   **Es un aviso falso**, y contradice a la pestaña de Análisis sobre el mismo fichero.
2. La calibración queda **mezclada** con el registro en el mismo tramo de señal. Separarla depende de
   que el usuario elija fragmentos a ojo, que es precisamente lo que no debe decidir a ojo.
3. Se ofrece calibrar en prácticas donde no se va a usar, y se ofrece analizar sin calibrar cosas que
   no significan nada sin ella.

## 2. El modelo nuevo, en una frase

**Una sesión es un archivo con dos fases marcadas: calibración y registro.** La aplicación las produce
en el mismo flujo y las escribe separadas en el EDF, sin que el usuario tenga que distinguirlas después.

Todo lo demás se deriva de eso.

---

## 3. La grabación

### 3.1 Cuándo se ofrece calibrar

Lo decide el **modo de práctica**, igual que ya decide los canales y el acelerómetro:

| Modo | Calibración |
|---|---|
| Contracción de un músculo | se ofrece |
| Contracción agonista / antagonista | **obligatoria** (sin ella no hay comparación posible entre los dos músculos) |
| Cinemática muscular | se ofrece |
| *Análisis libre / opciones avanzadas* | se puede omitir |

Cuando la práctica la necesita, el botón de grabar arranca el flujo completo; no hay que acordarse de
pulsar «Calibrar CVM» aparte.

### 3.2 El flujo, de una tirada

1. **Calibración.** El asistente pide las repeticiones que se hayan configurado, **tres por defecto**,
   de cada músculo por turno, con su cuenta atrás y su barra de esfuerzo, como ahora.
2. **Preparación.** Al terminar, la interfaz dice al usuario que se prepare para el registro y arranca
   una **cuenta atrás de 5 segundos** (configurable).
3. **Registro.** Empieza la fase de registro propiamente dicha.
4. Al detener, se guarda **un solo archivo** con las dos fases marcadas.

> **Decisión de ingeniería, importante: la adquisición NO se detiene entre las dos fases.**
> El usuario percibe una pausa, pero el flujo de datos sigue y el EDF es continuo. Detener de verdad
> obligaría a representar un hueco temporal, que EDF+ maneja mal, o a escribir dos ficheros y luego
> fusionarlos. La fase de preparación se marca como tal y se **excluye de todo análisis**; es señal
> registrada que no se usa. Cuesta unos segundos de disco y ahorra toda la complejidad de la
> discontinuidad.

### 3.3 Cómo se marca en el EDF

Anotaciones, con el mismo patrón que `fv_load_marker` y `mvc_ref_marker`. En un módulo nuevo
`phases.py`, libre de Qt, con sus parseadores y sus tests:

```
CAL start ch=1 rep=1
CAL end   ch=1 rep=1
...
PREP start
REC start
```

Y se conserva, al terminar la calibración, la anotación ya existente con el valor calculado:

```
MVC ref ch=1 value=0.124961 mV
```

**Precedencia, y es una regla que hay que respetar en todo el código:** el valor de `MVC ref` es un
**resultado en caché**; los tramos `CAL` son **la fuente**. Si en la pestaña de Análisis se editan los
fragmentos de la calibración, la referencia se **recalcula** desde los tramos y el valor recalculado
manda. La anotación en caché solo se usa cuando no hay tramos marcados, que es el caso de los archivos
grabados antes de este cambio.

---

## 4. La pestaña de Análisis

### 4.1 Dos ediciones, y NO son la misma herramienta

Aquí hay una asimetría que conviene aprovechar, porque ahorra la mitad del trabajo.

**El registro se edita con fragmentos**, como ahora: se reutiliza `FragmentSelectionDialog` tal cual,
restringido al tramo `REC`. Es señal continua sin estructura previa, y ahí el editor libre es la
herramienta correcta.

**La calibración NO.** La calibración ya tiene estructura: son repeticiones discretas, cada una con su
`CAL start` y su `CAL end`. Editarla con un editor de fragmentos libre sería tratar como continuo algo
que ya viene troceado, y abre la puerta a recortes arbitrarios que inflan la referencia.

Lo que hace falta es **una lista de repeticiones con una casilla de conservar en cada una**:

```
Calibración del canal 1 · flexor radial del carpo
  ☑ rep 1   0,118 mV   (94 % del mejor)
  ☐ rep 2   0,061 mV   (49 %)          ← descartada
  ☑ rep 3   0,125 mV   (100 %)
  Referencia con la selección actual: 0,125 mV   (antes: 0,125 mV)
```

Ventajas, y son varias:

- **Es mucho más sencillo de implementar.** No hay geometría de fragmentos, ni arrastre, ni
  auto-sugerencia: es marcar y desmarcar sobre tramos que ya están delimitados.
- **Coincide con lo que pasó de verdad.** El alumno hizo tres repeticiones y una salió mal; la interfaz
  le ofrece exactamente esa decisión y ninguna otra.
- **El recálculo es trivial**, porque `mvc_from_reps` ya hace «mejor de N» sobre una lista de
  repeticiones: basta pasarle las conservadas.
- **Cubre el caso real.** En la sesión del 30 de agosto, el 34 % de diafonía del FCR salía solo de la
  primera repetición del ECR, que era además la más floja. Con esta lista se descarta en un clic.

**La asistencia al alumno va aquí:** cada repetición muestra su valor y su porcentaje respecto de la
mejor, y debajo se ve **la referencia resultante y la anterior**. Una repetición muy por debajo de las
demás se señala sola. No se impide descartar nada, ni se descarta nada automáticamente: se hace visible
lo que cambia la vara de medir, que es lo único que hay que garantizar.

**Debe quedar al menos una repetición conservada por canal.** Desmarcarlas todas equivale a quedarse sin
calibración, y eso se hace no calibrando, no vaciando la lista.

La fase de preparación no aparece en ninguna de las dos ediciones.

### 4.2 Qué se ofrece y qué no

Si el archivo **tiene calibración utilizable**, se ofrece todo. Si **no la tiene**, las medidas que
dependen de ella **no se ofrecen**: no se muestran en gris ni con un aviso al pulsar, no están. Eso
incluye el %CVM, el panel 9 en porcentaje, el índice de coactivación y el análisis de Jonsson.

Las que no dependen de ella siguen disponibles: señal en bruto, envolvente normalizada a su propio
máximo, espectro, MNF/MDF y fatiga.

Definición única, en `phases.py`, que usa todo el código:

```python
def mvc_reference(result, channel) -> tuple[float | None, str]:
    """Referencia utilizable del canal y su procedencia.

    Precedencia:
      1. recalculada de los tramos CAL, con los fragmentos vigentes  -> "calibración de este registro"
      2. anotación MVC ref en caché (archivos anteriores)            -> "calibración (registro previo)"
      3. ninguna                                                     -> (None, "sin calibración")
    """
```

La procedencia se muestra siempre al usuario. Es lo que sustituye al viejo campo `MVC source:`.

### 4.3 Guardar un EDF afinado

Botón nuevo: guardar un archivo nuevo con la selección vigente de las dos fases.

**Requisitos de trazabilidad, no negociables:**

- **Nunca sobrescribe el original.** Nombre propuesto con sufijo, y si existe no se pisa.
- El archivo derivado **dice que lo es**, en la cabecera EDF y en una anotación: de qué archivo procede,
  qué fragmentos se conservaron de cada fase y cuándo se generó.
- Conserva las fases marcadas y la referencia recalculada.

Sin esto se acaba con ficheros «afinados» de origen desconocido, que es peor que no tener la función.

---

## 5. La pestaña de Normalización CVM

**Desaparece la pregunta por un archivo de referencia.** Se supone hecha la calibración y se trabaja
sobre el archivo que ya la lleva.

Al abrir un archivo:

- **Con calibración utilizable:** se calcula todo, con la procedencia a la vista.
- **Sin calibración:** aviso claro de que los resultados no son fiables, y **no se permite el análisis
  de Jonsson, ni siquiera auto-normalizado contra la propia señal**. Se pueden seguir viendo la señal y
  su envolvente, que no dependen de una referencia.

**Esto elimina la auto-normalización del programa.** Con ella se van sus avisos, su marcado en rojo, el
sufijo «(auto-normalizado)» de los títulos y la casilla de opciones avanzadas que la habilitaba. Es la
mayor simplificación del lote: el modo de fallo desaparece en vez de quedar señalizado.

---

## 6. Controles que se van

Que quede explícito, porque parte del valor del cambio es este:

- Selector «EDF de referencia CVM (opcional)» y su botón «Quitar».
- Toda la ruta de auto-normalización y su marcado.
- El botón «Calibrar CVM» suelto, cuando el modo ya lleva la calibración dentro del flujo de grabado.
- El campo `MVC source:` con sus valores viejos, sustituido por la procedencia del §4.2.

Y se añaden: la elección de repeticiones de calibración, la cuenta atrás de preparación, la segunda
entrada al editor de fragmentos y el botón de guardar el EDF afinado.

---

## 7. Compatibilidad con lo ya grabado

Tres clases de archivo, y las tres tienen que abrirse sin romper nada:

| Archivo | Qué tiene | Qué se ofrece |
|---|---|---|
| Grabado con este cambio | tramos `CAL` + `REC` + `MVC ref` | todo, y los fragmentos de calibración son editables |
| Grabado ayer | solo `MVC ref` | todo menos editar la calibración; procedencia «registro previo» |
| Anterior a ayer | nada | solo lo que no depende de referencia |

---

## 8. Lo pendiente de la revisión de las especs anteriores

Va aquí porque toca los mismos ficheros y conviene hacerlo en la misma pasada.

1. **La última ventana de coactivación llega hasta el final del registro.** Si el alumno marca la presa
   sostenida y luego deja reposo antes de parar, ese reposo entra en la ventana, baja la media y puede
   tumbarla por debajo del umbral. Poner un tope de duración de ventana, o cerrarla con el final de la
   actividad detectada.
2. **Las ventanas de menos de dos muestras se descartan en silencio** (`coactivation.py`,
   `i1 - i0 < 2: continue`). El alumno marcó algo y no ve fila. Emitir la fila con el motivo «ventana
   demasiado corta», que ya existe.
3. **`coact_floor_pct = 5,0` sigue siendo una estimación.** Ajustarlo con datos reales: en el registro
   del 30-ago el reposo fue 3,4 µV en el FCR y 10,8 µV en el ECR; convertido a %CVM con las referencias
   de ese archivo sale el umbral que corresponde. Dejar anotado en el código de dónde sale el número.

## 9. Lo que NO se toca

- El panel 2 (envolvente normalizada a su propio máximo) sigue como está: para el curso temporal de un
  canal es correcto y está honradamente etiquetado.
- El veredicto de fatiga y su umbral R² ≥ 0,30, recién corregidos, no entran en este cambio.
- El editor de fragmentos no se reescribe: se reutiliza con un parámetro de fase.

---

## 10. En qué orden construirlo

Importa, porque hay estados intermedios que no se sostienen. Cada punto deja el programa en un estado
coherente y probable; **no se pasa al siguiente sin que el anterior tenga sus tests en verde**.

1. **`phases.py`**: las anotaciones de fase, sus parseadores y `mvc_reference()` con su regla de
   precedencia. Sin tocar ninguna interfaz. Es la base de todo lo demás y se prueba sola.
2. **Escritura de las fases en la grabación**: el flujo calibración → preparación → registro, con la
   adquisición sin detenerse. Al terminar este punto ya se producen archivos del modelo nuevo, y los
   viejos siguen abriéndose.
3. **Lectura en la pestaña de Análisis**: usar `mvc_reference()`, mostrar la procedencia, y ofrecer o
   no las medidas dependientes. Aquí desaparece la incoherencia entre pestañas.
4. **Lista de repeticiones** y recálculo de la referencia.
5. **Pestaña CVM**: quitar el selector de archivo de referencia y toda la ruta de auto-normalización.
6. **Guardar el EDF afinado**, con su trazabilidad.
7. Los tres pendientes del §8.

Si hay que parar a mitad, **los puntos 1 a 3 son un buen sitio**: dejan el programa coherente y ya
resuelven el aviso falso de la pestaña CVM. Del 4 en adelante son mejoras.

## 11. Pruebas

Además de las que pidan los módulos nuevos:

1. Ida y vuelta de las anotaciones de fase: escribir, cerrar el EDF, reabrir, recuperar los tramos.
2. **Un archivo con tramos `CAL` y una anotación `MVC ref` desactualizada devuelve la referencia
   recalculada, no la de la anotación.** Es la regla de precedencia del §3.3.
3. Descartar una repetición cambia la referencia y, con ella, todos los %CVM derivados. Descartar la
   peor de tres apenas la mueve; descartar la mejor la baja de forma visible.
3b. No se puede dejar un canal sin ninguna repetición conservada.
4. Un archivo sin calibración: las medidas dependientes no se ofrecen, y Jonsson no se calcula por
   ninguna vía, tampoco contra la propia señal.
5. Los tres tipos de archivo del §7 se abren sin excepción y ofrecen lo que les toca.
6. La fase de preparación queda fuera de todo análisis.
7. El EDF afinado conserva las fases, lleva su trazabilidad y no sobrescribe el original.

## 12. Prueba con hardware, obligatoria antes de dar esto por bueno

Una sesión completa de principio a fin: calibrar tres repeticiones de cada músculo, preparación,
registro con las maniobras marcadas, detener, abrir en Análisis, **descartar una repetición de
calibración y editar un fragmento del registro**, comprobar que la referencia se mueve y que los %CVM
la siguen, guardar el EDF afinado, cerrarlo, reabrirlo, y comprobar en la pestaña CVM que sale lo mismo.

---

## 13. Dos avisos para Ángel, no para el implementador

**Esto es más grande que las dos especificaciones anteriores juntas.** Toca adquisición, el formato del
archivo, las tres pestañas, los informes y las exportaciones. El diseño es el correcto y el momento de
hacerlo es antes de publicar la versión que describe el artículo, no después. Pero **conviene que sea el
último cambio de arquitectura antes de la release**: después, solo corrección de errores. El pilotaje es
en semanas y la carta a la editora promete una versión publicada con DOI.

**Y cambia el artículo.** La práctica de ejemplo deja de necesitar dos registros: la sesión es una sola,
con su calibración dentro. Eso simplifica el §4.7 del manuscrito y lo hace mejor, pero hay que reescribir
el procedimiento, la tabla de datos y probablemente el §4.8. No se toca el manuscrito hasta que esto
esté implementado y probado con hardware, por la misma razón de siempre: no describir software que no
existe.
