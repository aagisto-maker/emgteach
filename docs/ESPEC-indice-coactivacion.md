# emgteach — índice de coactivación agonista/antagonista

Especificación para implementar. Escrita el 30 de agosto de 2026. **Depende de que esté hecho antes el
cambio de `ESPEC-panel9-en-CVM.md`**, porque el índice necesita las dos envolventes normalizadas cada una
a la CVM de su músculo.

---

## 1. Por qué este índice y no otro

El de **Falconer y Winter (1985)** es el más citado con diferencia, está acotado entre 0 y 100 %, no
obliga a decidir cuál de los dos músculos es el agonista, y es el más robusto frente a la elección del
método de normalización, cosa que importa en docencia porque el protocolo de CVM de un alumno no es el
de un laboratorio de investigación.

Se explica en dos frases: *de toda la actividad eléctrica registrada en el par de músculos, ¿qué
fracción es actividad compartida, ejercida por los dos a la vez? El índice es esa fracción, de 0 a
100 %.*

Existe una alternativa razonable, el índice de **Rudolph (2000)**, que pondera además la magnitud de la
activación y correlaciona mejor con la rigidez articular estimada. Es mejor si lo que se quiere enseñar
es coste energético o rigidez. **Recomendación: implementar solo Falconer-Winter.** Un índice bien
explicado vale más en clase que dos entre los que haya que elegir, y sus valores no son comparables
entre sí de todos modos.

## 2. La fórmula

```
CCI = 2 · ∫ EMG_low(t) dt  /  ∫ [EMG_1(t) + EMG_2(t)] dt   × 100
```

donde `EMG_1` y `EMG_2` son las dos envolventes **expresadas en %CVM de su propio músculo**, y
`EMG_low(t) = min(EMG_1(t), EMG_2(t))` muestra a muestra. Las integrales se calculan sobre la ventana de
análisis, no sobre el registro completo (ver §4).

El factor 2 es lo que hace que el índice llegue a 100 % cuando las dos envolventes son idénticas.

Interpretación: 0 % = activación puramente de uno de los dos, sin solapamiento. 100 % = las dos curvas
coinciden.

## 3. Dónde va el código

Módulo nuevo `coactivation.py`, hermano de `apda.py` y con la misma disciplina: **libre de Qt**, para que
lo usen igual el worker de análisis y cualquier uso desconectado, y con la referencia bibliográfica en el
docstring.

```python
@dataclass(frozen=True)
class CoactivationResult:
    index: float | None        # 0-100, None si no se puede calcular
    mean_1: float              # activación media del canal 1, %CVM
    mean_2: float              # activación media del canal 2, %CVM
    window_s: tuple[float, float]
    reason: str | None         # por qué no se pudo calcular, si index is None


def coactivation_index(
    env_1_pct_mvc, env_2_pct_mvc, fs, *, floor_pct=5.0,
) -> CoactivationResult:
    ...
```

Umbral en `profiles.SignalProfile`, junto a los de Jonsson:

```python
# -- coactivation (Falconer-Winter) --
coact_floor_pct: float = 5.0   # %CVM; por debajo, el índice no se informa
```

## 4. Las tres salvaguardas, que no son opcionales

Este índice tiene un modo de fallo silencioso **de la misma familia que el de la auto-normalización que
ya corregimos**: da un número alto que parece un hallazgo y no lo es. Hay que blindarlo igual.

### 4.1 Dos músculos callados dan coactivación máxima

Si los dos músculos están en reposo, sus envolventes son ruido de línea base parecido entre sí, `EMG_low`
es casi igual a los dos, y **el índice sale cercano al 100 %**. Está documentado: el índice mide
*parecido de forma*, no cantidad de activación, y sube «aunque la amplitud de ambas sea baja».

**Salvaguarda:** si la activación media de **cualquiera** de los dos canales queda por debajo de
`coact_floor_pct` en la ventana, no se informa el índice. Se devuelve `index=None` y un `reason`
traducible, y la interfaz muestra el motivo en lugar del número. Nunca un número gris o entre paréntesis:
o se informa o no se informa.

### 4.2 Hay que restar la línea base

Antes de integrar, restar de cada envolvente su propio nivel de reposo. Si el registro tiene una ventana
de reposo marcada, usarla; si no, el percentil 10 de la envolvente en la ventana analizada es una
aproximación razonable. Sin esto, la salvaguarda anterior se puede sortear con un ruido de línea base
alto.

### 4.3 El índice se calcula por ventana, nunca sobre el registro entero

El índice se concibió para ventanas cortas y cuasi-estacionarias. Aplicado a un registro completo que
mezcla reposo, flexión, extensión y presa, el resultado no significa nada y además pierde toda capacidad
de distinguir condiciones.

**Salvaguarda:** el índice se calcula **entre marcadores**, una cifra por ventana marcada, y se presenta
como una tabla de condiciones. Si no hay marcadores, se usa la región de interés; si tampoco la hay, se
informa una sola cifra **con un aviso visible** de que corresponde al registro completo y de que eso rara
vez es lo que se quiere.

## 5. Cómo se presenta

En la pestaña de análisis, con el modo agonista/antagonista y dos canales cargados, debajo del panel 9:

| Ventana | Canal 1 (media %CVM) | Canal 2 (media %CVM) | Coactivación |
|---|---|---|---|
| Flexión de muñeca | 38 | 6 | no se informa (canal 2 por debajo del 5 %) |
| Extensión de muñeca | 7 | 41 | no se informa (canal 1 por debajo del 5 %) |
| Presa | 44 | 39 | **86 %** |

**Las dos medias van siempre al lado del índice, nunca el índice solo.** Es lo que impide leer un 86 %
como «los dos muy activos» cuando podría ser «los dos igual de callados», y es además lo que enseña de
verdad: el número del extensor en la presa es el hallazgo, el índice solo lo resume.

Que las dos primeras filas digan «no se informa» **no es un defecto de la demostración, es parte de la
demostración**: en un movimiento recíproco no hay coactivación que medir, y el programa lo dice en vez de
inventar una cifra.

El índice va también al informe PDF, con la misma tabla y las mismas medias.

## 6. Cadenas para `i18n.py`

| Inglés (clave) | Español |
|---|---|
| `Co-activation (Falconer-Winter)` | `Coactivación (Falconer-Winter)` |
| `Co-activation index` | `Índice de coactivación` |
| `Mean activation (% MVC)` | `Activación media (% CVM)` |
| `not reported — {name} below {floor:.0f} % MVC` | `no se informa — {name} por debajo del {floor:.0f} % de CVM` |
| `not reported — no MVC reference for both channels` | `no se informa — falta referencia de CVM en algún canal` |
| `Whole recording — mark the phases for a meaningful value` | `Registro completo — marca las fases para obtener un valor con sentido` |
| `Window` | `Ventana` |

## 7. Pruebas

1. Dos envolventes idénticas y por encima del umbral → índice 100 %.
2. Dos envolventes disjuntas en el tiempo (una activa mientras la otra está a cero) → índice 0 %.
3. **Dos envolventes de ruido de reposo → `index is None` y `reason` de umbral.** Es la prueba que
   protege del modo de fallo del §4.1 y la más importante de todas.
4. Un canal activo y el otro por debajo del umbral → `index is None`.
5. Sin referencia de CVM en algún canal → `index is None` con el `reason` correspondiente.
6. Índice invariante al escalado: multiplicar las dos envolventes por la misma constante no cambia el
   resultado (es un cociente).
7. Cálculo por ventanas: un registro sintético con tres fases marcadas devuelve tres cifras distintas, y
   la de la fase recíproca es menor que la de la fase simultánea.

## 8. Referencias para el docstring y para el artículo

- Falconer K, Winter DA. Quantitative assessment of co-contraction at the ankle joint in walking.
  *Electromyogr Clin Neurophysiol* 25: 135–149, 1985. PMID 3987606. **Sin DOI**, revista descatalogada.
- Carey HD, De Groote F, Sawers A. A comparative analysis of co-contraction indices using synthetic EMG
  data: implications for selection and interpretation. *PLoS One* 21: e0343081, 2026.
  doi:10.1371/journal.pone.0343081. Acceso abierto. **Es la que justifica la elección y de la que salen
  las salvaguardas.**
- Kellis E, Arabatzi F, Papadopoulos C. Muscle co-activation around the knee in drop jumping using the
  co-contraction index. *J Electromyogr Kinesiol* 13: 229–238, 2003. doi:10.1016/S1050-6411(03)00020-8.
  Cuatro métodos sobre los mismos datos dan del 13 % al 71 %: es el argumento de por qué hay que declarar
  qué índice se usa.
- Souissi H, Zory R, Bredin J, Gerus P. Comparison of methodologies to assess muscle co-contraction
  during gait. *J Biomech* 57: 141–145, 2017. doi:10.1016/j.jbiomech.2017.03.029. La coactivación
  eléctrica no es la cocontracción mecánica: el EMG no incorpora las relaciones fuerza-longitud ni el
  brazo de palanca.

> **No citar** el capítulo de IntechOpen «Hand Sign Classification Employing Myoelectric Signals of
> Forearm» (Tsujimura, Yamamoto e Izumi, 2012, doi:10.5772/51080). Trata de clasificación de gestos para
> una interfaz hombre-máquina; no usa índices de coactivación, no normaliza a CVM y no analiza pares
> agonista/antagonista. Su AIEMG es la media de la señal rectificada y suavizada, que es lo que emgteach
> ya calcula como iEMG.
