# Material del artículo para *Advances in Physiology Education*

Lo que hay aquí es **material publicable**, distinto del de
[`../informe-sourcebook/`](../informe-sourcebook/), que es el adjunto del
informe interno. Las tres diferencias son deliberadas:

- **En inglés**, porque es el idioma del artículo. La interfaz decide el
  idioma del PDF y del CSV, así que se genera con la aplicación en inglés.
- **Ventana de 1150 px**, no de 1920, **y recortes**. Esto hay que decirlo con
  el número delante, porque la revisión pedía 1100–1200 px para llegar a 8
  puntos y con eso no se llega: ver «Legibilidad» más abajo.
- **Sin rutas personales.** La aplicación se conduce desde
  `C:\Records\ejemplo.edf`, de modo que ni la barra de archivo de las capturas
  ni la cabecera del CSV enseñan una ruta de usuario. El sujeto se identifica
  como `P01`, que es lo que imprime el PDF en «Test identifier».

## Cómo se regenera

```
python tools/informe_material.py --articulo
python tools/figura6.py --edf C:\Records\<registro>_tuned.edf
```

Ninguna de las dos toca el código de la aplicación: la conducen y guardan lo
que ella dibuja, para que ninguna figura pueda discrepar de los números del
artículo.

## Legibilidad: el número, no la impresión

Una captura de `A` píxeles de ancho impresa a 6,5 pulgadas se ve a `A/6,5`
puntos por pulgada, y el texto de la interfaz mide 13 px. De ahí sale todo:

| Lo que se imprime | Ancho | Texto en la página |
|---|---|---|
| Ventana entera a 1920 px | 1920 px | **2,9 pt** |
| Ventana entera a 1150 px | 1150 px | **5,3 pt** |
| Ventana en su mínimo (880 px) | 880 px | **6,9 pt** |
| Lo que haría falta para 8 pt | ≤ 702 px | 8,0 pt |

O sea: **ninguna captura de ventana entera llega a 8 puntos**, ni siquiera
encogiendo la ventana hasta su mínimo, que son 880 px y no se puede bajar de
ahí. A 8 puntos solo se llega **recortando**, y por eso cada figura trae
también su recorte. El generador imprime los puntos de cada archivo que hace y
avisa cuando alguno se queda corto, de modo que esto se comprueba, no se
supone.

Las capturas de ventana entera siguen aquí porque valen para ver la
disposición general; las que tienen que leerse son los recortes.

## Qué es cada archivo

| Archivo | Figura | Ancho → pt | Qué enseña |
|---|---|---|---|
| `fig3a_practica_single.png` | 3 (izq.) | 1150 → 5,3 | Adquisición en «Single-muscle contraction» |
| `fig3b_practica_par.png` | 3 (der.) | 1150 → 5,3 | La misma pantalla en «Agonist / antagonist contraction» |
| `fig3?_..._selector.png` | 3 | 334 → 18,2 | El selector de práctica con su banda de nivel: la causa |
| `fig3?_..._carga.png` | 3 | 577 → 10,5 | El recuadro de carga: una barra frente a dos, «Agonist» y «Antagonist». La consecuencia |
| `fig4a_guia_agonista.png` | 4 | 1150 → 5,3 | La guía en «Agonist and antagonist», sobre un análisis real |
| `fig4a_guia_agonista_recorte.png` | 4 | 450 → 13,5 | El panel de ese paso y el control al que apunta |
| `fig4b_guia_normalizar.png` | 4 (alt.) | 1150 → 5,3 | La guía en «Why normalise at all», sobre la normalización calculada |
| `fig4b_guia_normalizar_recorte.png` | 4 (alt.) | 725 → 8,4 | El panel de ese paso y su control |
| `fig7_apdf.png` | 7 | 1150 → 5,3 | La pestaña de normalización con la APDF abajo |
| `fig7_apdf_recorte.png` | 7 | 752 → 8,1 | La curva APDF con P10, P50 y P90 |
| `fig7_datos_recorte.png` | 7 | 394 → 15,4 | Los números de carga muscular con sus rangos normales |
| `figura6.png` / `.pdf` | 6 | 6,5 × 4 in | Del patrón recíproco a la coactivación, en matplotlib |
| `ejemplo_informe.pdf` | — | — | Informe de sesión de la aplicación, en inglés |
| `ejemplo_analisis.csv` | — | — | Exportación de análisis, en inglés |

Para la figura 3, los dos recortes se apilan: arriba el selector, abajo el
recuadro de carga, una columna por práctica. Es la forma de enseñar que la
elección de arriba es lo que cambia lo de abajo.

Las tres capturas de pantalla completa (`captura_adquisicion.png`,
`captura_analisis.png`, `captura_normalizacion.png`) son las mismas tres del
informe, aquí en inglés y a 1150 px.

## Lo que no sale de aquí

- **La figura 5** (el registro en vivo durante la presa, con las dos trazas y
  las dos barras de carga altas a la vez) necesita a alguien apretando. Se
  toma con el botón de captura de la propia aplicación, o con F12, que guarda
  la ventana junto al registro sin abrir ningún diálogo — que es justo lo que
  hacía falta para no soltar el puño.
- **La figura 6 definitiva** necesita un registro con las tres maniobras
  nombradas como fragmentos. Con el registro del 3 de septiembre, que no los
  tiene, `figura6.py` dibuja el tramo entero y lo dice: sirve para probar la
  herramienta, no como figura.
