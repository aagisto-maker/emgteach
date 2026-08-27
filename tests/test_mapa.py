"""The flow map: that a picture exists for every state, and that it is current.

The images are rendered ahead of time by ``tools/generar_mapa.py`` and
committed, which keeps matplotlib out of the help's path at run time but lets
them go stale. These tests are the guard: adding a practical, or a language,
fails here until the generator has been run again.
"""

from __future__ import annotations

import pytest

from emgteach.gui.mapa import ESTACIONES, MAPA_DIR, ruta_mapa
from emgteach.modes import MODES

IDIOMAS = ("es", "en")


@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("estacion", ESTACIONES)
def test_there_is_a_map_for_every_state(idioma, mode, estacion) -> None:
    """One picture per practical, tab and language — no gaps.

    A missing file is not a crash: the dialog says the map has not been
    generated. But it is a silent hole in the help, and the state most likely
    to have one is the practical someone just added.
    """
    ruta = ruta_mapa(mode, estacion, idioma)
    assert ruta.exists(), (
        f"missing {ruta.name} for {idioma}: run tools/generar_mapa.py"
    )
    assert ruta.stat().st_size > 4_000, f"{ruta.name} looks empty"


def test_no_maps_are_left_over() -> None:
    """A renamed or removed practical leaves its picture behind, and a stale
    map is worse than a missing one: it shows a route that no longer exists."""
    esperados = {
        ruta_mapa(mode, est, idioma).name
        for idioma in IDIOMAS for mode in MODES for est in ESTACIONES
    }
    for idioma in IDIOMAS:
        carpeta = MAPA_DIR / idioma
        if not carpeta.exists():
            continue
        sobrantes = {p.name for p in carpeta.glob("*.png")} - esperados
        assert not sobrantes, (
            f"{idioma}: maps for states that no longer exist: {sorted(sobrantes)}"
        )


class TestTheMapMatchesTheApplication:
    """The map is a drawing, so nothing stops it describing a different
    application from the one that ships. These pin the parts that would go
    quietly out of date."""

    def test_every_practical_is_drawn(self) -> None:
        from emgteach.gui.mapa import NODOS

        modos_dibujados = set()
        for n in NODOS():
            modos_dibujados.update(n.modos)
        assert modos_dibujados == set(MODES)

    def test_the_stations_are_the_tabs(self) -> None:
        """The ring is drawn around the node whose station matches the open
        tab, so the map's stations have to be the tab indices."""
        from emgteach.gui.mapa import NODOS

        estaciones = {n.estacion for n in NODOS() if n.estacion is not None}
        assert estaciones == set(ESTACIONES)

    def test_the_force_velocity_branch_needs_the_accelerometer(self) -> None:
        """It starts in acquisition and ends in its own study, and only the
        practicals that record an accelerometer have either."""
        from emgteach.gui.mapa import NODOS
        from emgteach.modes import mode_uses_acc

        for n in NODOS():
            if n.id in ("fv_asis", "fv_est"):
                assert set(n.modos) == {m for m in MODES if mode_uses_acc(m)}
