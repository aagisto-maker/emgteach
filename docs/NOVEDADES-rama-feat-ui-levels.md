# Novedades de emgteach — rama `feat/ui-levels`

> **Nota del 3 de septiembre de 2026.** Este documento describe los primeros 14
> commits de la rama (agosto) y **está superado** en varios puntos: ya no hay
> casilla de «Opciones avanzadas» (el nivel es la práctica), la guía tiene cinco
> pasos y no catorce, la calibración pide tres esfuerzos máximos breves (y
> ninguno mantenido), y el análisis tiene tabla por contracción, fichas con rangos
> y tres cuadros abajo. La descripción al día es la sección «Unreleased» de
> [`CHANGELOG.md`](../CHANGELOG.md) y los manuales de `docs/`, revisados tras la
> pasada de banco del 3 de septiembre. Se conserva como registro de por qué se
> tomaron las decisiones de la primera tanda.

Material de trabajo para actualizar los manuales y la presentación de la
aplicación. Recoge lo que cambia **de cara al usuario** en los 14 commits de la
rama, sobre la v2.0.0.

Estado (22 de agosto): 329 tests, ruff limpio, mypy sin errores nuevos. Sin
probar con hardware y sin *push* ni PR.

---

## 1. La aplicación se configura eligiendo la práctica

**Lo más visible de la rama.** Antes, la pestaña de adquisición ofrecía 24
controles interactivos y la de análisis 14 más 12 casillas de paneles, cuando
registrar un bíceps necesita cinco. Ahora se elige **qué práctica** es y todo lo
demás se deriva de eso.

Tres modos, en el selector de la esquina superior:

| Modo | Canales | Acelerómetro |
|---|---|---|
| Contracción de un músculo | 1 | no |
| Contracción agonista / antagonista | 2 | no |
| Cinemática muscular | 1 | sí |

El modo **no es un filtro sobre la interfaz: decide lo que se registra**. Fija el
número de canales y si se usa el acelerómetro, y cada pestaña ofrece solo las
medidas que tienen sentido para esa práctica. Por eso desaparecieron de la
pantalla el selector de número de canales y la casilla del acelerómetro: solo
podían contradecir al modo elegido.

Aparte del modo, y ortogonal a él, una casilla **«Opciones avanzadas»** muestra
los controles finos que valen igual para las tres prácticas: frecuencias de
corte, umbrales de fatiga, región de interés y detección automática de inicio.

Dos reglas que conviene contar en el manual porque explican comportamientos que
si no parecen caprichosos:

- Lo que un modo oculta, lo **desmarca**; al volver al modo lo restaura. Un panel
  que quedara marcado se seguiría dibujando sin forma visible de quitarlo.
- Una función **que está funcionando no se oculta** aunque se apaguen las
  opciones avanzadas. Una difusión que nadie pueda parar es peor que un control
  de más.

**El registro manda sobre los canales.** Al abrir en modo agonista/antagonista un
EDF de dos canales, la comparación se activa sola. Si el fichero tiene un solo
canal, sale un aviso que dice cuántos canales tiene y propone el modo que le
corresponde.

→ *Manual: §4 (la interfaz) hay que rehacerla entera; §7 (flujos de trabajo)
pasa a organizarse por modo. La chuleta necesita una línea al principio: elegir
el modo es el primer paso.*

---

## 2. Guía interactiva

Un recorrido que señala cada control **sobre la propia pantalla** —oscurece el
resto, rodea el control y pone al lado qué es y qué significa
fisiológicamente— y va cambiando de pestaña solo.

**Sigue al modo:** 14 pasos en un músculo, 15 en agonista/antagonista, 17 en
cinemática. Explica el acelerómetro solo en la práctica que lo usa, y la
coordinación agonista/antagonista solo en la suya.

Se ofrece al arrancar, con una casilla **«Ofrecer esta guía la próxima vez»**
marcada por defecto: un ordenador de laboratorio ve un alumno distinto cada
sesión, así que la decisión de apagarla es de quien tiene el equipo, no de quien
lo abrió primero. El botón **«Guía»**, junto al `?`, la relanza cuando se quiera.
Se niega a arrancar si hay un registro en marcha.

→ *Manual: sección nueva, probablemente dentro de §4 o como §4.0. Merece captura.
Y §8 (idioma y configuración) debería mencionar la casilla, porque es un ajuste
que persiste.*

---

## 3. Seguimiento en móviles, ahora en todos los niveles

La difusión a móviles **ya no está detrás de «Opciones avanzadas»**. Seguir el
registro en el propio móvil es para lo que sirve la práctica, no un ajuste fino:
un laboratorio docente suele tener un único sensor, y esto es lo que convierte un
solo registro en algo que lee toda la clase a la vez.

La casilla se llama ahora **«Difundir a móviles (en laboratorio)»** y los
mensajes del registro de eventos hablan de **«modo seguimiento en móviles»**
(antes «modo aula», y con dos nombres distintos según dónde se mirara).

→ *Manual: §4 y §7. La chuleta debería mencionarlo, que ahora está a la vista.*

---

## 4. Normalización CVM: se explica, y se marca cuando es automática

La pestaña recibe cada sesión con un **panel de entrada** que explica qué es una
contracción voluntaria máxima y por qué hace falta un registro de referencia. La
abreviatura aparecía en el título de la pestaña, en dos selectores de fichero, en
el botón de calcular y en los ejes de las gráficas, y no se expandía en ninguno.

La **auto-normalización ya no se ofrece** salvo con las opciones avanzadas
activadas, y donde se use **el resultado queda marcado como tal**: en pantalla, en
los títulos de los paneles y **en el PDF**, que es lo que entrega el alumno.
Dividir una señal por un percentil de sí misma deja sin sentido los límites de
Jonsson: una contracción sostenida los supera por construcción, así que la
pestaña pintaba de rojo un registro entero y parecía un hallazgo.

La pestaña tiene además **su propio registro de eventos**. El compartido solo
puede estar en un sitio, que era la pestaña de análisis, así que todo lo que esta
registraba se escribía donde no se veía — incluidos los avisos de canal plano y
canal saturado, que son el error más común de un alumno.

→ *Manual: §4.3 y §5. El apartado de interpretación debería decir explícitamente
que un resultado auto-normalizado no se lee contra Jonsson.*

---

## 5. Corrección de la ganancia del sensor (afecta a las amplitudes)

**Cambio numérico: las amplitudes en mV bajan un 0,90 %.**

La conversión trataba el canal como si el ADC leyera el biopotencial
directamente. No lo hace: lee la salida de un amplificador de ganancia 1009, así
que la función de transferencia tiene que dividir por ella.

```
EMG(mV) = (ADC / 2¹⁰ − 0,5) · VCC · 1000 / G      VCC = 3,3 V,  G = 1009
```

El fondo de escala pasa de ±1,65 mV a **±1,635 mV**. El error pasó desapercibido
porque la ganancia es casi 1000 y un voltio son 1000 mV: los dos errores casi se
cancelaban.

**Qué NO cambia:** todo lo que es un cociente. **%CVM, los niveles APDF de
Jonsson y las pendientes de fatiga son idénticos.** Solo cambian las amplitudes
absolutas en milivoltios.

**Registros anteriores:** llevan su propio rango físico en la cabecera EDF y se
releen con él. Se distinguen por ese valor — **1,65 mV = anterior, 1,635 mV =
corregido** — y el factor para corregir los antiguos es 1000/1009 = 0,99108.

→ *Manual: §2 (hardware) y §6 (formatos). Conviene una nota, porque cualquiera
que compare una medida vieja con una nueva verá la diferencia.*

---

## 6. Idioma

- **El español trata siempre de usted, o en impersonal.** Antes mezclaba las dos
  formas casi al 50 %, a veces dentro de una misma frase. El criterio ahora es
  infinitivo o «hay que» para instrucciones, «conviene» para recomendaciones, y
  tercera persona simple en los tooltips que describen lo que hace un control.
- **Los botones de los diálogos ya salen en español.** «Yes/No/OK/Cancel/Save»
  los dibuja Qt y los traduce de su propio catálogo: sin cargar su traductor, una
  interfaz en español seguía pidiendo pulsar *Yes*. Ahora dice **Sí, No, Aceptar,
  Cancelar, Guardar**.
- El texto del tutorial está revisado por el autor, en los dos idiomas.

→ *Los manuales en español deberían repasarse con el mismo criterio, que ahora
no coinciden con la aplicación.*

---

## 7. Documentación ya corregida en la rama

La sección **«Hardware backends»** del README decía que el BITalino necesita
`pip install "emgteach[bitalino]"` y **Python ≤ 3.11** por PyBluez. Es falso desde
la migración a pyserial: no existe tal extra, y ambos backends funcionan en
3.10–3.12. Estaba en **siete sitios** (README, CONTRIBUTING, packaging ×2, los
dos manuales, las dos chuletas) y está corregido.

`packaging/README.md` además afirmaba que con dirección MAC **no** se puede
conectar y había que poner el COM — lo contrario de lo que recomienda la
aplicación. Corregido.

---

## Pendiente de decidir

- **El README sigue describiendo la v1.1.0** en su sección «Status», cuando el
  paquete va por la **2.0.0**. Nunca se actualizó para la 2.0.0 (acelerómetro y
  cinemática), así que le faltan dos versiones, no una. Dice además «216 tests»
  y son **329**.
- Los **§4 y §7 de los dos manuales** describen una interfaz que ya no existe:
  hablan de controles que ahora dependen del modo o que han desaparecido.
- La **rúbrica de evaluación** y el **guion de prácticas** habría que revisarlos
  contra los tres modos, por si alguna práctica encaja mal en uno de ellos.
