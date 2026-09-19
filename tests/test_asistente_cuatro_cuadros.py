"""El asistente acompañaba la calibración y dejaba solo al alumno en la tarea.

Llevaba calentamiento → calibración → preparación → `REC start`, y ahí se
acababa: justo donde empieza lo que produce los datos. Ahora son cuatro
cuadros, uno por fase, con una fila de casillas que es el mapa de lo que
falta — una por acción, del color del músculo que la lleva — y un imperativo
por cuadro.

Lo que estas pruebas guardan es, sobre todo, **que el mapa informa y no
gobierna**: la fase de las maniobras termina cuando lo dice el alumno, no
cuando se llenan las doce casillas, porque un detector que se salte una no
puede dejar a nadie encerrado en una fase que no acaba.
"""
from __future__ import annotations

import numpy as np
import pytest

from emgteach.gui.tabs.acquisition import (
    _CHANNEL_COLORS,
    COACT_HOLD_S,
    COACT_REPS,
    COLOR_COACT,
    MANIOBRA_CADA_S,
    MANIOBRAS_POR_MUSCULO,
    MVC_READY_S,
    MVC_TICK_MS,
)
from emgteach.modes import MODE_PAIR

pytestmark = pytest.mark.gui


@pytest.fixture
def adq(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    s = QSettings("emgteach-test", "cuatro-cuadros")
    s.clear()
    s.setValue("app/mode", MODE_PAIR)
    s.setValue("adquisicion/save_dir", str(tmp_path))
    tab = AcquisitionTab(LoggerWidget(), s)
    tab.set_mode(MODE_PAIR) if hasattr(tab, "set_mode") else None
    tab.resize(1200, 760)
    tab.show()
    qapp.processEvents()
    try:
        yield tab
    finally:
        tab._coact_timer.stop()
        tab._mvc_timer.stop()
        tab._prep_timer.stop()
        s.clear()
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


def _colores(tab) -> list[tuple[int, int, int]]:
    return [(c.red(), c.green(), c.blue())
            for c, _hecho in tab._mvc_overlay._steps]


class TestTheFourPhasesComeInOrder:
    def test_the_warm_up_counts_nothing(self, adq) -> None:
        """No hay acciones que contar: el calentamiento es tiempo, no gestos."""
        adq._guia_mapa("")
        assert adq._mvc_overlay.steps_done() == []

    def test_the_calibration_maps_three_per_muscle(self, adq) -> None:
        adq._n_channels = 2
        adq._mvc_reps = 3
        adq._guia_mapa("cal")
        assert len(adq._mvc_overlay.steps_done()) == 6
        assert _colores(adq) == [_CHANNEL_COLORS[0]] * 3 + [_CHANNEL_COLORS[1]] * 3

    def test_the_manoeuvres_map_six_per_muscle(self, adq) -> None:
        adq._n_channels = 2
        adq._guia_mapa("maniobras")
        assert len(adq._mvc_overlay.steps_done()) == 2 * MANIOBRAS_POR_MUSCULO
        assert _colores(adq) == (
            [_CHANNEL_COLORS[0]] * MANIOBRAS_POR_MUSCULO
            + [_CHANNEL_COLORS[1]] * MANIOBRAS_POR_MUSCULO)

    def test_the_co_activation_has_its_own_colour(self, adq) -> None:
        """Los dos músculos tienen el suyo y esta maniobra no es de ninguno."""
        adq._guia_mapa("coact")
        assert _colores(adq) == [COLOR_COACT] * COACT_REPS
        assert COLOR_COACT not in _CHANNEL_COLORS


class TestTheMapIsFilledAsItGoes:
    def test_the_calibration_fills_one_box_per_closed_repetition(
        self, adq, monkeypatch
    ) -> None:
        """Una por repetición cerrada, y ninguna antes: aquí el asistente
        manda el ritmo, así que sabe cuándo termina cada una."""
        adq._n_channels = 2
        adq._mvc_reps = 3
        adq._guia_mapa("cal")
        monkeypatch.setattr(adq, "_write_phase_marker", lambda *_a: None)
        monkeypatch.setattr(adq, "_instruct_device", lambda *_a, **_k: None)
        monkeypatch.setattr(adq, "_mvc_compute_muscle", lambda *_a: None)
        adq._mvc_muscle, adq._mvc_rep = 0, 0
        adq._mvc_cur_buf, adq._mvc_cross_buf = [1.0], {}
        assert adq._mvc_overlay.steps_done() == [False] * 6
        adq._mvc_finish_rep()
        assert adq._mvc_overlay.steps_done() == [True] + [False] * 5

    def test_a_detected_contraction_fills_one_of_the_manoeuvres(self, adq) -> None:
        adq._n_channels = 2
        adq._guia_maniobras(0)
        assert adq._mvc_overlay.steps_done()[0] is False
        # Un bloque en reposo para la línea base, y otro con una contracción.
        rng = np.random.default_rng(3)
        for _ in range(12):
            adq._guia_detecta([rng.normal(0.01, 0.002, 200),
                               rng.normal(0.01, 0.002, 200)])
        adq._guia_detecta([np.full(400, 0.5), np.full(400, 0.01)])
        assert adq._mvc_overlay.steps_done()[0] is True
        assert adq._man_hechas[0] == 1

    def test_more_contractions_than_boxes_are_dropped_not_complained_about(
        self, adq
    ) -> None:
        adq._n_channels = 2
        adq._guia_maniobras(0)
        adq._man_hechas = [MANIOBRAS_POR_MUSCULO, 0]
        for i in range(MANIOBRAS_POR_MUSCULO):
            adq._mvc_overlay.mark_step(i)
        rng = np.random.default_rng(4)
        for _ in range(12):
            adq._guia_detecta([rng.normal(0.01, 0.002, 200),
                               rng.normal(0.01, 0.002, 200)])
        adq._guia_detecta([np.full(400, 0.5), np.full(400, 0.01)])
        hechas = adq._mvc_overlay.steps_done()
        assert hechas[:MANIOBRAS_POR_MUSCULO] == [True] * MANIOBRAS_POR_MUSCULO
        assert hechas[MANIOBRAS_POR_MUSCULO:] == [False] * MANIOBRAS_POR_MUSCULO
        assert adq._man_hechas[0] == MANIOBRAS_POR_MUSCULO


class TestTheManoeuvresEndWhenTheStudentSaysSo:
    """El requisito que evita el desastre.

    El guion pide seis flexiones **libres**, al ritmo del alumno, y el
    artículo describe esa libertad; así que las casillas solo pueden
    rellenarse detectando. Un detector se salta una antes o después, y si la
    fase dependiera de las doce casillas, el alumno se quedaría encerrado.
    """

    def test_it_goes_on_with_the_boxes_empty(self, adq) -> None:
        adq._n_channels = 2
        adq._guia_maniobras(0)
        assert adq._man_grupo == 0
        assert not any(adq._mvc_overlay.steps_done())
        adq._paso_siguiente()
        assert adq._man_grupo == 1, "no se pasó al segundo músculo"
        adq._paso_siguiente()
        assert adq._guia_fase == "coact", "no se pasó a la coactivación"
        assert not any(adq._mvc_overlay.steps_done()[:12])

    def test_and_the_button_is_only_there_while_it_can_be_pressed(
        self, adq
    ) -> None:
        assert not adq._btn_paso_hecho.isVisible()
        adq._n_channels = 2
        adq._guia_maniobras(0)
        assert adq._btn_paso_hecho.isVisible()
        adq._paso_siguiente()
        adq._paso_siguiente()          # a la coactivación, que sí es a reloj
        assert not adq._btn_paso_hecho.isVisible()

    def test_pressing_it_outside_that_phase_does_nothing(self, adq) -> None:
        adq._guia_fase = ""
        adq._paso_siguiente()
        assert adq._guia_fase == ""


class TestTheHoldRunsOnTheClock:
    def test_the_bar_fills_and_the_box_is_marked_at_the_end(self, adq) -> None:
        adq._n_channels = 2
        adq._guia_coactivacion()
        adq._coact_fase = "hold"
        adq._coact_elapsed = 0.0
        pasos = int(COACT_HOLD_S / (MVC_TICK_MS / 1000.0))
        adq._coact_tick()
        assert 0.0 < adq._mvc_overlay._running < 0.2
        # Un par de tics de más: el reloj suma décimas en coma flotante y
        # lo que se comprueba es que la casilla se marca al acabar, no en
        # qué tic exacto cae el redondeo.
        for _ in range(pasos + 1):
            adq._coact_tick()
        assert adq._mvc_overlay.steps_done()[0] is True
        assert adq._coact_rep == 1

    def test_and_the_session_says_so_when_the_last_one_is_done(self, adq) -> None:
        adq._n_channels = 2
        adq._guia_coactivacion()
        adq._coact_rep = COACT_REPS - 1
        adq._coact_fase = "hold"
        adq._coact_elapsed = COACT_HOLD_S
        adq._coact_tick()
        assert adq._guia_fase == ""
        assert not adq._coact_timer.isActive()
        assert adq._mvc_overlay._mode == "done"


class TestNoSubtitleWrapsWhileSomethingIsBeingDone:
    """Un imperativo y nada más: lo que se lee mientras se hace algo cabe en
    una línea, y la explicación va donde hay tiempo —el recorrido, el manual,
    la hoja de puesto—."""

    @pytest.mark.parametrize("idioma", ["en", "es"])
    def test_one_line_each(self, adq, idioma) -> None:
        from emgteach.i18n import get_language, set_language

        antes = get_language()
        try:
            set_language(idioma)
            adq._n_channels = 2
            ov = adq._mvc_overlay
            textos = []
            # La cuenta atrás del esfuerzo, que era la única que pasaba de
            # una línea: decía la regla y después el gesto. Ahora dice el
            # gesto, y la regla la lleva el pictograma de al lado y el
            # título del propio esfuerzo.
            for canal in (0, 1):
                textos.append(adq._mvc_gesto(canal))
            adq._guia_maniobras(0)
            textos.append(ov._subtitle)
            adq._coact_fase = "hold"
            adq._guia_fase = "coact"
            adq._coact_elapsed = 1.0
            adq._coact_tick()
            textos.append(ov._subtitle)
            ov.show_relax(adq.tr("Next one in a moment")
                          if hasattr(adq, "tr") else "")
            adq._guia_fin()
            textos.append(ov._subtitle)
            una = ov.text_height("x")
            for texto in textos:
                assert texto
                assert ov.text_height(texto) <= una, (idioma, texto)
        finally:
            set_language(antes)


class TestWhatTheRehearsalFound:
    """Cuatro cosas que solo se ven ensayando, y ninguna prueba veía.

    Ángel pasó la sesión entera con la placa simulada y salieron: casillas
    vacías en el calentamiento que no se llenaban nunca, una cuenta atrás que
    solo era un número, las contracciones del primer músculo sin contar, y la
    presa que no llegaba al registro.
    """

    def test_the_warm_up_shows_no_boxes_it_will_not_fill(self, adq) -> None:
        """Una fila de casillas vacías que no se llena es una promesa que la
        fase no cumple; el mapa de la calibración sale con la primera cuenta
        atrás, que es lo primero que llena una."""
        from emgteach.profiles import EMG_PROFILE

        adq._iniciar_calibracion(auto_flow=False)
        try:
            adq._mvc_phase = "warmup"
            adq._mvc_elapsed = 0.0
            adq._mvc_tick()
            assert adq._mvc_overlay.steps_done() == []
            adq._mvc_elapsed = EMG_PROFILE.warmup_s
            adq._mvc_tick()                       # se acaba el calentamiento
            assert adq._mvc_phase == "ready"
            assert len(adq._mvc_overlay.steps_done()) == (
                adq._n_channels * adq._mvc_reps)
        finally:
            if adq._mvc_active:
                adq._mvc_cancel()

    def test_the_countdown_is_also_a_bar_and_not_the_green_one(self, adq) -> None:
        """El número dice *ahora* y la barra dice *cuánto falta*; en azul,
        que en este panel es el tiempo, y nunca en el verde del esfuerzo."""
        from emgteach.gui.widgets.mvc_overlay import _ACCENT, _EFFORT

        ov = adq._mvc_overlay
        ov.show_ready("x", 2, "y", waiting=0.4)
        assert ov._waiting == pytest.approx(0.4)
        ov.show_contract("x", 1.0, 0.5, 0.5)
        assert ov._waiting is None, "el esfuerzo no lleva cuenta atrás"
        assert _ACCENT != _EFFORT

    def test_each_muscle_gets_a_resting_second_before_it_is_asked(
        self, adq
    ) -> None:
        """El detector mide su reposo en el primer segundo que ve, así que la
        fase abre con uno. Sin él, el primer músculo contaba **cero** de sus
        seis y el segundo los seis: el segundo se había pasado el turno del
        primero en reposo, de modo que su línea base era de verdad."""
        pedidos = []
        adq._instruct_device = lambda c, lv, **k: pedidos.append(
            (c, lv, k.get("repeat_s")))
        adq._n_channels = 2
        adq._guia_maniobras(0)
        assert all(nivel == 0.0 for _c, nivel, _r in pedidos), pedidos
        assert all(rep is None for _c, _n, rep in pedidos), pedidos
        pedidos.clear()
        adq._maniobras_en_marcha(0)               # pasado el segundo
        assert (0, 0.5, MANIOBRA_CADA_S) in pedidos, pedidos
        assert (1, 0.0, None) in pedidos, "el otro músculo, en reposo"

    def test_and_nothing_is_asked_if_the_phase_moved_on_meanwhile(
        self, adq
    ) -> None:
        pedidos = []
        adq._instruct_device = lambda c, lv, **k: pedidos.append((c, lv))
        adq._n_channels = 2
        adq._guia_maniobras(0)
        adq._guia_fase = ""
        pedidos.clear()
        adq._maniobras_en_marcha(0)
        assert pedidos == []

    def test_the_co_activation_asks_for_both_muscles_at_once(self, adq) -> None:
        """La maniobra que da el índice. Con la instrucción de antes —un
        músculo, el otro forzado a reposo— no se podía pedir, y un ensayo se
        quedaba sin presa ninguna en el registro."""
        pedidos = []
        adq._instruct_device = lambda c, lv, **k: pedidos.append((c, lv))
        adq._n_channels = 2
        adq._guia_coactivacion()
        adq._coact_fase = "ready"
        adq._coact_elapsed = MVC_READY_S
        pedidos.clear()
        adq._coact_tick()
        assert adq._coact_fase == "hold"
        assert sorted(pedidos) == [(0, 0.4), (1, 0.4)], pedidos
