"""The pictures of the practical, found by name and by language.

They were drawn for the guided tour (``tools/imagenes_recorrido.py`` builds
them from one base image) and live beside it in ``assets/recorrido``. They are
not the tour's, though: the same picture of the calibration that the tour shows
while explaining the wizard is the one the wizard itself should show while
asking for the effort, and a panel of the acquisition tab has no business
importing from the tour to reach it.

One entry point, :func:`imagen`, which resolves the language and falls back to
English — an interface in a language whose picture nobody has drawn yet shows
the English one rather than nothing.
"""

from __future__ import annotations

from pathlib import Path

from emgteach.i18n import get_language

__all__ = ["imagen"]

_IMAGENES = Path(__file__).resolve().parent / "assets" / "recorrido"


def imagen(nombre: str) -> str | None:
    """The picture ``nombre`` in the interface's language, else in English,
    else None."""
    for idioma in (get_language(), "en"):
        ruta = _IMAGENES / f"{nombre}_{idioma}.png"
        if ruta.is_file():
            return str(ruta)
    return None
