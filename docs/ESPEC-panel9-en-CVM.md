# emgteach — que el panel de envolventes superpuestas hable en %CVM

Especificación para implementar con Claude Code. Escrita el 30 de agosto de 2026 sobre la rama
`feat/ui-levels` tal como está en `C:\Users\aagis\Documents\EMG\...\emgteach\src`. Las líneas citadas se
han comprobado en ese árbol; si el fichero cambia, localizar por nombre de función, no por número.

---

## 1. El problema

El panel **9. Envolventes superpuestas (agonista/antagonista)** dibuja los dos músculos en **milivoltios**
(`gui/tabs/analysis.py`, bloque `--- Overlaid envelopes ---`, `ax.set_ylabel(tr("Amplitude (mV)"))`).

Es el único sitio de la aplicación donde se ponen dos músculos distintos en el mismo eje, y es
justamente donde los milivoltios no significan nada. La amplitud de superficie depende del grosor de la
piel y de la grasa que hay entre el músculo y el electrodo, así que un bíceps puede quedar por encima de
un tríceps por anatomía y no por activación. La propia aplicación enseña esto en el panel de entrada de
la pestaña CVM, y luego lo contradice en la figura que el alumno copia en su informe.

El monitor **en vivo** de la pestaña de adquisición sí lo hace bien: cada barra expresa su canal como
porcentaje de la CVM de ese músculo. El problema es solo del análisis desconectado.

## 2. Por qué hoy no puede hacerlo

`_mvc_ref[c]` se calcula en `_mvc_compute_muscle()` (`gui/tabs/acquisition.py`, hacia la línea 2208) y
**vive solo en memoria**. No se escribe en el EDF. Al cerrar la aplicación se pierde, y la pestaña de
análisis, que parte del fichero, no tiene forma de saber cuál era la referencia de cada músculo.

## 3. La solución, con precedente en la propia casa

El asistente guiado de fuerza-velocidad ya resolvió este mismo problema: escribe una anotación en el EDF
por cada carga (`fv_load_marker()` en `force_velocity.py:51`) y el estudio la relee después
(`parse_fv_load_markers()`, línea 56), de modo que la columna de cargas sale rellena sin que nadie la
teclee. **Hay que hacer lo mismo con la referencia de CVM.**

Es además la opción coherente con el principio de diseño de la aplicación: en el EDF solo se guarda la
señal en bruto y lo demás se recalcula. La referencia es un dato de la sesión, como la carga levantada,
y su sitio es la anotación.

### 3.1 Helpers nuevos en `mvc.py`

Copiar el patrón de `force_velocity.py` literalmente, para que el código se lea igual:

```python
# Anotación EDF escrita por el asistente de calibración de CVM, una por músculo,
# p. ej. "MVC ref ch=1 value=0.4213 mV". La pestaña de análisis las relee para
# poder expresar cada canal como porcentaje de su propio máximo.
_MVC_REF_RE = re.compile(
    r"MVC\s+ref\s+ch=\s*(\d+)\s+value=\s*([0-9]*\.?[0-9]+)", re.IGNORECASE
)


def mvc_ref_marker(channel_index: int, ref_mv: float) -> str:
    """Etiqueta de anotación EDF para la referencia de CVM de un canal.

    ``channel_index`` es 0-based; en la etiqueta se escribe 1-based, que es
    como el usuario ve los canales.
    """
    return f"MVC ref ch={channel_index + 1} value={ref_mv:.6g} mV"


def parse_mvc_ref_markers(
    markers: Iterable[tuple[float, str]],
) -> dict[int, float]:
    """Devuelve ``{indice_de_canal_0based: referencia_mV}`` leído de las anotaciones.

    Si un canal se calibró más de una vez en el mismo registro, **gana la
    última**: es la que el sujeto tenía puesta al final y la que corresponde a
    los electrodos tal como acabaron colocados.
    """
```

Añadir ambos a `__all__`.

### 3.2 Escribir la anotación (`gui/tabs/acquisition.py`)

En `_mvc_compute_muscle(c)`, justo después de fijar `self._mvc_ref[c]`:

```python
if self._mvc_ref[c] and self._worker and self._worker.isRunning():
    self._worker.add_marker(mvc_ref_marker(c, self._mvc_ref[c]))
```

**Caso que hay que cubrir:** la calibración puede hacerse antes de pulsar *Iniciar grabación*
(`_mvc_finish_all()` habilita el botón de grabar al terminar). Si la referencia existe pero no había
grabación, la anotación no se escribe y el registro sale sin ella. Solución: en el método que arranca la
grabación, volcar como anotaciones todas las referencias conocidas justo al empezar. Un bucle sobre
`range(self._n_channels)` con la misma llamada basta.

**Al reiniciar (`reset()`, y `_mvc_ref = [None] * MAX_CHANNELS`)** no hay nada que hacer: el registro
nuevo es otro fichero.

### 3.3 Releer y usar la referencia (`workers/analysis.py` y `gui/tabs/analysis.py`)

El worker de análisis ya lee las anotaciones del EDF (las dibuja como marcadores). Pasarlas por
`parse_mvc_ref_markers()` y añadir al diccionario de resultados:

```python
"mvc_refs": {0: 0.4213, 1: 0.2871}   # vacío si el registro no se calibró
```

En el bloque `--- Overlaid envelopes (agonist/antagonist) ---` de `gui/tabs/analysis.py`:

- **Si hay referencia para los dos canales que se dibujan:** dividir cada envolvente por su referencia y
  multiplicar por 100. Título `tr("9. Overlaid envelopes (agonist/antagonist), % MVC")`, eje
  `tr("Activation (% MVC)")`. Este es el caso bueno y es el que hay que conseguir que sea el habitual.
- **Si falta la referencia de alguno:** dejar los milivoltios como ahora, y **decirlo en la propia
  figura**, con un texto pequeño bajo el título:
  `tr("Millivolts are not comparable between two muscles. Calibrate MVC while recording to compare them.")`
  El aviso tiene que salir en la figura, no en un tooltip, porque la figura viaja sola dentro del PDF.

### 3.4 El informe PDF

`reports.py:171` mapea el panel 8 a `"9. Overlaid envelopes (agonist/antagonist)"`. El título y las
unidades del PDF tienen que seguir la misma regla que la pantalla, y el aviso del caso sin referencia
tiene que aparecer también ahí. Es el documento que entrega el alumno.

### 3.5 Lo que NO se toca

- **El panel 2 (`Envelope normalised to its maximum`) se queda como está.** Normaliza al máximo de la
  propia señal, que para el curso temporal de un solo canal es correcto y además está honradamente
  etiquetado. Cambiarlo aquí ampliaría el alcance sin necesidad.
- **La pestaña CVM se queda como está.** Podría prerrellenar la referencia desde la anotación, y sería
  una mejora, pero es otra tarea. Anotarla y dejarla para después.

## 4. Pruebas

1. `mvc_ref_marker()` / `parse_mvc_ref_markers()`: ida y vuelta, canal 1-based en la etiqueta y 0-based
   en el diccionario, tolerancia a decimales y a mayúsculas, y **la última calibración de un canal gana**.
2. Anotaciones ajenas (marcas del alumno, `FV load=...`) no deben producir entradas.
3. Un registro de dos canales **con** las dos referencias: el panel devuelve %CVM y el eje lo dice.
4. Un registro de dos canales **sin** referencias: el panel sigue en mV y aparece el aviso.
5. Un registro con referencia en un solo canal: se comporta como el caso sin referencias (no se mezclan
   unidades en el mismo eje bajo ningún concepto).

## 5. Cadenas para `i18n.py`

| Inglés (clave) | Español |
|---|---|
| `9. Overlaid envelopes (agonist/antagonist), % MVC` | `9. Envolventes superpuestas (agonista/antagonista), % CVM` |
| `9. Env. overlay (% MVC)` | `9. Env. superp. (% CVM)` |
| `Millivolts are not comparable between two muscles. Calibrate MVC while recording to compare them.` | `Los milivoltios no son comparables entre dos músculos. Calibre la CVM mientras graba para poder compararlos.` |

`Activation (% MVC)` / `Activación (% CVM)` ya existe y se reutiliza.

## 6. Por qué merece la pena hacerlo antes del envío

El artículo del Sourcebook desarrolla como práctica de ejemplo la coactivación agonista/antagonista. Con
el panel en milivoltios, la figura que cuenta el resultado obliga a un párrafo explicando qué no se puede
concluir de ella. Con el panel en %CVM, esa misma figura pasa a ser la que sostiene el argumento del
artículo: que la aportación de emgteach no es registrar EMG barato, que ya se sabía hacer, sino llevar al
alumnado hasta una medida normalizada y comparable en una sola sesión.

Es además la respuesta más limpia a la pregunta del Reviewer 1 sobre para qué sirve el botón de calibrar:
sirve para que todo lo que viene después tenga unidades con sentido, incluido el informe que se entrega.
