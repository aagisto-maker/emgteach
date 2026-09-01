"""The map of a recording's journey — content, and where its images live.

The help shows a picture of the whole flow with the current practical's path
lit and the rest dimmed, so a partial map is read *inside* the global one
rather than as a separate drawing per practical. The station the user is
looking at is ringed.

Only the content is here. The drawing lives in ``tools/generar_mapa.py``,
which renders one PNG per (language, practical, station) into
:data:`MAPA_DIR`; the application only loads the file that matches its current
state. That split keeps matplotlib out of the help's path at run time and
keeps the wording in the package, where the i18n completeness test can see it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from emgteach.i18n import get_language, tr
from emgteach.modes import (
    MODE_KINEMATICS,
    MODE_PAIR,
    MODE_SINGLE,
    normalise_mode,
)

__all__ = [
    "ENLACES",
    "ESTACIONES",
    "MAPA_DIR",
    "NODOS",
    "Enlace",
    "Nodo",
    "ruta_mapa",
]

#: Where the rendered maps are kept, inside the package so a wheel carries
#: them (the same arrangement as ``web/dashboard.html``).
MAPA_DIR = Path(__file__).resolve().parent.parent / "resources" / "mapa"

#: The three tabs, in the order the recording passes through them. The index
#: is the tab index the application already uses.
ESTACIONES = (0, 1, 2)

TODOS = (MODE_SINGLE, MODE_PAIR, MODE_KINEMATICS)
CON_ACC = (MODE_KINEMATICS,)
UN_MUSCULO = (MODE_SINGLE,)


@dataclass(frozen=True)
class Nodo:
    """A box on the map.

    ``estacion`` ties a box to a tab so the "you are here" ring can be drawn
    around it; branches leave it at None.
    """

    id: str
    x: float
    y: float
    w: float
    h: float
    titulo: str
    lineas: tuple[str, ...] = ()
    modos: tuple[str, ...] = TODOS
    estacion: int | None = None
    rombo: bool = False


@dataclass(frozen=True)
class Enlace:
    """An arrow. ``puntos`` is a polyline, so an arrow can turn a corner."""

    puntos: tuple[tuple[float, float], ...]
    etiqueta: str = ""
    etiqueta_xy: tuple[float, float] | None = None
    modos: tuple[str, ...] = TODOS
    discontinuo: bool = False
    #: Width the label may use, when it is not the gap the arrow crosses.
    #: The two spine labels sit *above* the boxes rather than in the 95-unit
    #: gap between them, where nothing constrains them but the drawing edge.
    etiqueta_ancho: float | None = None


def _nodos() -> list[Nodo]:
    """Built on each call so the text follows the current language."""
    return [
        Nodo(
            "adq", 30, 60, 230, 92,
            tr("Acquisition"),
            (tr("connect · label · record"), tr("mark events")),
            estacion=0,
        ),
        Nodo(
            "ana", 355, 60, 230, 92,
            tr("Analysis"),
            (tr("panels follow the practical"), tr("window · fragments")),
            estacion=1,
        ),
        Nodo(
            "cvm", 680, 60, 230, 92,
            tr("MVC normalisation"),
            (tr("signal as % of the maximum"), tr("muscle load (Jonsson)")),
            estacion=2,
        ),
        Nodo(
            "fv_asis", 30, 206, 230, 62,
            tr("F-V wizard"),
            (tr("one contraction per load,"), tr("marked with its weight")),
            modos=CON_ACC,
        ),
        Nodo(
            "fv_est", 355, 206, 230, 62,
            tr("F-V study"),
            (tr("load-velocity · power"), tr("recruitment")),
            modos=CON_ACC,
        ),
        Nodo(
            "ref", 355, 322, 230, 56,
            tr("Reference recording"),
            (tr("the maximal effort, unloaded"),),
        ),
        Nodo(
            "q_musculo", 470, 424, 186, 58,
            tr("Two muscles?"),
            (tr("asks which, once"),),
            modos=UN_MUSCULO,
            rombo=True,
        ),
        Nodo(
            "q_ref", 795, 424, 186, 58,
            tr("A reference?"),
            (tr("if not, offers this one"),),
            rombo=True,
        ),
    ]


def _enlaces() -> list[Enlace]:
    return [
        # The spine labels ride above the row of boxes, not in the gap between
        # them: 95 units is not enough for a phrase, and shrinking one until
        # it fits only makes it unreadable instead of cramped.
        Enlace(
            ((260, 106), (349, 106)), tr("goes by itself"), (305, 52),
            etiqueta_ancho=250,
        ),
        Enlace(
            ((585, 106), (674, 106)),
            tr("goes by itself, with the chosen muscle"), (630, 52),
            etiqueta_ancho=250,
        ),
        Enlace(((145, 152), (145, 204)), modos=CON_ACC),
        Enlace(
            ((260, 244), (349, 244)), tr("loads"), (305, 232),
            modos=CON_ACC, discontinuo=True,
        ),
        Enlace(((470, 204), (470, 158)), modos=CON_ACC, discontinuo=True),
        Enlace(
            ((30, 130), (14, 130), (14, 350), (349, 350)),
            tr("another pass, same tab"), (175, 340), discontinuo=True,
        ),
        Enlace(
            ((585, 350), (795, 350), (795, 158)),
            tr("it is the 100 %"), (695, 340), discontinuo=True,
        ),
    ]


NODOS = _nodos
ENLACES = _enlaces


def ruta_mapa(mode: str, estacion: int, idioma: str | None = None) -> Path:
    """The rendered map for this practical, tab and language."""
    lang = idioma or get_language()
    return MAPA_DIR / lang / f"mapa-{normalise_mode(mode)}-{int(estacion)}.png"
