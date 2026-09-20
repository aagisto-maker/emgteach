"""El asistente era dos asistentes: uno con mapa y otro sin él.

La práctica del par llevaba su fila de casillas —una por acción, del color
del músculo que la lleva— y el estudio de fuerza-velocidad no llevaba
ninguna, así que la misma aplicación se veía terminada en una práctica y
pobre en la otra. El panel ofrece ahora **lo mismo y con el mismo formato**
en las dos: título, mapa de la fase, barra de lo que corre y barras de
carga; lo que cambia es con qué se rellenan, no la forma.

Y la condición para que eso no retrase la etiqueta: **una lista plana sigue
siendo una fila**. Las tres fases de la práctica del artículo no cambian ni
su llamada ni un píxel de su aspecto, y aquí está escrito con la fórmula que
tenían antes.
"""
from __future__ import annotations

import pytest

from emgteach.gui.tabs.acquisition import (
    _CHANNEL_COLORS,
    COLOR_COACT,
    FV_INTRO_S,
)
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR

pytestmark = pytest.mark.gui


@pytest.fixture
def overlay(qapp):
    from emgteach.gui.widgets.mvc_overlay import MvcOverlay

    widget = MvcOverlay()
    yield widget
    widget.close()


@pytest.fixture
def adq(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    s = QSettings("emgteach-test", "asistente-uniforme")
    s.clear()
    s.setValue("app/mode", MODE_KINEMATICS)
    s.setValue("adquisicion/save_dir", str(tmp_path))
    tab = AcquisitionTab(LoggerWidget(), s)
    tab.resize(1200, 760)
    tab.show()
    qapp.processEvents()
    try:
        yield tab
    finally:
        tab._fv_timer.stop()
        tab._coact_timer.stop()
        tab._mvc_timer.stop()
        tab._prep_timer.stop()
        s.clear()
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


def _estudio(tab, cargas=(2.0, 4.0, 6.0), reps=2):
    """El estudio guiado, sin el reloj: los tics se dan a mano.

    Se deja correr hasta la primera cuenta atrás, que es la que arma el
    mapa: el aviso del principio no llena ninguna casilla.
    """
    tab._fv_start(list(cargas), reps, 1.0, 1.0, con_maximo=False)
    tab._fv_timer.stop()
    tab._fv_elapsed = FV_INTRO_S
    tab._fv_tick()
    return tab._mvc_overlay


def _colores(fila) -> list:
    return [None if c is None else (c.red(), c.green(), c.blue())
            for c, _hecho in fila]


class TestThePairPracticalDoesNotNotice:
    """La generalización es aditiva o no es."""

    def test_a_flat_list_is_still_one_row(self, overlay) -> None:
        overlay.set_steps([_CHANNEL_COLORS[0]] * 6)
        assert overlay.steps_rows() == 1
        assert overlay.steps_done() == [False] * 6

    def test_and_says_the_same_as_that_row_spelled_out(self, overlay) -> None:
        overlay.set_steps([_CHANNEL_COLORS[0]] * 3)
        plana = (overlay.steps_rect(), overlay.height_for_text(),
                 _colores(overlay._steps[0]))
        overlay.set_steps([[_CHANNEL_COLORS[0]] * 3])
        assert (overlay.steps_rect(), overlay.height_for_text(),
                _colores(overlay._steps[0])) == plana

    def test_the_footer_sits_where_it_always_did(self, overlay) -> None:
        """La fórmula de antes, tal cual, para que se note si se mueve."""
        overlay.set_steps([COLOR_COACT] * 6)
        n = 6
        ancho = n * overlay._STEP_W + (n - 1) * overlay._STEP_GAP
        assert overlay.steps_rect() == (
            (overlay._W - ancho) // 2,
            overlay.height() - overlay._BOTTOM - overlay._STEP_H,
            ancho, overlay._STEP_H,
        )

    def test_and_the_panel_grows_by_exactly_what_it_grew(self, overlay) -> None:
        overlay.show_phase("x", "y")
        sin_pie = overlay.height_for_text()
        overlay.set_steps([COLOR_COACT] * 6)
        assert overlay.height_for_text() - sin_pie == (
            overlay._STEP_H + overlay._STEP_TOP_GAP)

    @pytest.mark.parametrize("fase", ["cal", "maniobras", "coact"])
    def test_the_three_phases_of_the_pair_map_one_row(
        self, qapp, tmp_path, fase
    ) -> None:
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.acquisition import AcquisitionTab
        from emgteach.gui.widgets.logger import LoggerWidget

        s = QSettings("emgteach-test", "asistente-uniforme-par")
        s.clear()
        s.setValue("app/mode", MODE_PAIR)
        s.setValue("adquisicion/save_dir", str(tmp_path))
        tab = AcquisitionTab(LoggerWidget(), s)
        try:
            tab._n_channels = 2
            tab._guia_mapa(fase)
            assert tab._mvc_overlay.steps_rows() == 1
            assert all(c is not None
                       for c, _h in tab._mvc_overlay._steps[0]), "sin huecos"
        finally:
            tab._coact_timer.stop()
            s.clear()
            tab.close()
            tab.deleteLater()
            qapp.processEvents()


class TestTheStudyHasTheSameBoxes:
    def test_two_rows_the_load_in_hand_and_the_whole_thing(self, adq) -> None:
        ov = _estudio(adq, (2.0, 4.0, 6.0), reps=2)
        assert ov.steps_rows() == 2
        assert ov.steps_done(0) == [False] * 2, "la carga que se está haciendo"
        assert ov.steps_done(1) == [False] * 6, "las tres cargas, seis subidas"

    def test_the_loads_are_told_apart_by_a_gap_not_by_a_colour(
        self, adq
    ) -> None:
        """Una escala de colores de cargas competiría con la del canal, que
        es la del trazo y la de su barra; el hueco separa igual y no compite."""
        ov = _estudio(adq, (2.0, 4.0, 6.0), reps=2)
        assert _colores(ov._steps[1]) == [
            _CHANNEL_COLORS[0], _CHANNEL_COLORS[0], None,
            _CHANNEL_COLORS[0], _CHANNEL_COLORS[0], None,
            _CHANNEL_COLORS[0], _CHANNEL_COLORS[0],
        ]
        assert ov._grupos[1] == (0, 1), "la primera carga, perfilada"

    def test_a_lift_fills_a_box_in_both_rows(self, adq) -> None:
        ov = _estudio(adq, (2.0, 4.0), reps=3)
        adq._fv_finish_contract()
        assert ov.steps_done(0) == [True, False, False]
        assert ov.steps_done(1) == [True, False, False, False, False, False]

    def test_a_new_load_starts_the_top_row_over_and_moves_the_outline(
        self, adq
    ) -> None:
        ov = _estudio(adq, (2.0, 4.0), reps=2)
        for _ in range(2):
            adq._fv_finish_contract()
        assert adq._fv_idx == 1, "se pasó a la carga siguiente"
        assert ov.steps_done(0) == [False, False], "la de arriba, otra vez"
        assert ov.steps_done(1) == [True, True, False, False], "y la de abajo no"
        assert ov._grupos[1] == (2, 3)

    def test_the_map_goes_when_the_study_does(self, adq) -> None:
        ov = _estudio(adq, (2.0, 4.0), reps=1)
        adq._fv_finish_contract()
        adq._fv_finish_contract()
        assert not adq._fv_active
        assert ov.steps_rows() == 0

    def test_and_when_it_is_cancelled(self, adq) -> None:
        ov = _estudio(adq, (2.0, 4.0), reps=1)
        adq._fv_cancel()
        assert ov.steps_rows() == 0


class TestNoBoxPromisesWhatItDoesNotFill:
    """El aviso del principio enseñaba el mapa entero vacío, y no llena
    ninguna casilla: la que las llena es la cuenta atrás de cada carga, que
    es cuando sale. Es la misma regla que sigue el calentamiento del par."""

    def test_the_announcement_shows_no_boxes(self, adq) -> None:
        adq._fv_start([2.0, 4.0], 2, 1.0, 1.0, con_maximo=False)
        adq._fv_timer.stop()
        adq._fv_tick()
        assert adq._fv_phase == "intro"
        assert adq._mvc_overlay.steps_rows() == 0

    def test_and_the_first_countdown_brings_them(self, adq) -> None:
        ov = _estudio(adq, (2.0, 4.0), reps=2)
        assert adq._fv_phase == "ready"
        assert ov.steps_rows() == 2


class TestTheTopRowSitsOverItsOwnGroup:
    """Centrada, la fila corta se pone encima de las casillas de la larga que
    caigan en medio, y el ojo empareja las que no son."""

    def test_the_first_load_starts_where_the_row_starts(self, adq) -> None:
        ov = _estudio(adq, (2.0, 4.0, 6.0), reps=3)
        assert ov.steps_rect(0)[0] == ov.steps_rect(1)[0]

    def test_and_the_boxes_are_the_same_size_or_they_would_not_line_up(
        self, adq
    ) -> None:
        ov = _estudio(adq, (2.0, 4.0, 6.0), reps=3)
        assert ov._row_metrics(0)[:2] == ov._row_metrics(1)[:2]
        assert ov._row_metrics(0)[2] > ov._row_metrics(1)[2], "la de arriba, más alta"

    def test_and_it_moves_with_the_load(self, adq) -> None:
        ov = _estudio(adq, (2.0, 4.0, 6.0), reps=3)
        x_inicial = ov.steps_rect(1)[0]
        caja, hueco, _alto = ov._row_metrics(1)
        for _ in range(3):
            adq._fv_finish_contract()
        assert adq._fv_idx == 1
        # Tres casillas y el hueco que separa una carga de la siguiente.
        assert ov.steps_rect(0)[0] == x_inicial + 4 * (caja + hueco)


class TestALongRowStaysInsideThePanel:
    """Ocho cargas de cinco subidas son cuarenta casillas, y el mapa tiene
    que estar entero: casillas más estrechas siguen leyéndose como una fila,
    y unas que se salgan del panel no."""

    def test_forty_boxes_and_their_gaps_fit(self, overlay) -> None:
        fila: list = []
        for i in range(8):
            if i:
                fila.append(None)
            fila.extend([_CHANNEL_COLORS[0]] * 5)
        overlay.set_steps([[_CHANNEL_COLORS[0]] * 5, fila])
        x, _y, ancho, _alto = overlay.steps_rect(1)
        assert x >= 0
        assert ancho <= overlay._W - 2 * overlay._SUB_MARGIN
        assert len(overlay.steps_done(1)) == 40

    def test_and_the_short_row_above_keeps_its_size(self, overlay) -> None:
        fila: list = [_CHANNEL_COLORS[0]] * 47
        overlay.set_steps([[_CHANNEL_COLORS[0]] * 5, fila])
        assert overlay._row_metrics(0)[0] == overlay._STEP_W
        assert overlay._row_metrics(1)[0] < overlay._STEP_W
