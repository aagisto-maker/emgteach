"""El asistente acompañaba la calibración y dejaba solo al alumno en la tarea.

Llevaba calentamiento → calibración → preparación → `REC start`, y ahí se
acababa: justo donde empieza lo que produce los datos. Ahora son cuatro
cuadros, uno por fase, con una fila de casillas que es el mapa de lo que
falta — una por acción, del color del músculo que la lleva — y un imperativo
por cuadro.

Lo que estas pruebas guardan es, sobre todo, **que la fase de las maniobras
no puede dejar de acabar**: acaba al contar las seis y quedarse el músculo en
reposo, o cuando lo dice el alumno, y el botón sigue ahí todo el rato para el
día en que el detector se salte una.
"""
from __future__ import annotations

import numpy as np
import pytest

from emgteach.gui.tabs.acquisition import (
    _CHANNEL_COLORS,
    COACT_HOLD_S,
    COACT_REPS,
    COLOR_COACT,
    FS,
    MANIOBRA_CADA_S,
    MANIOBRA_REPOSO_S,
    MANIOBRA_SIN_NOVEDAD_S,
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


def _colores(tab, fila: int = 0) -> list[tuple[int, int, int]]:
    return [(c.red(), c.green(), c.blue())
            for c, _hecho in tab._mvc_overlay._steps[fila] if c is not None]


def _con_referencia(tab, grupo: int = 0) -> None:
    """La fase de maniobras con las dos referencias medidas.

    El conteo va en **% de la CVM de cada músculo**, así que sin ellas no
    cuenta nada: es lo mismo que le pasaría a una sesión sin calibrar.
    """
    tab._mvc_ref[0] = tab._mvc_ref[1] = 1.0
    tab._guia_maniobras(grupo)


def _reposo(tab, bloques: int = 12, n: int = 200) -> None:
    """Reposo con ruido: los primeros bloques son la línea base del detector."""
    rng = np.random.default_rng(3)
    for _ in range(bloques):
        tab._guia_detecta([rng.normal(0.01, 0.002, n),
                           rng.normal(0.01, 0.002, n)])


def _quieto(tab, segundos: float) -> None:
    """Reposo liso, por debajo de cualquier umbral, en bloques de 100 ms."""
    n = int(0.1 * FS)
    for _ in range(max(1, round(segundos / 0.1))):
        tab._guia_detecta([np.full(n, 0.004), np.full(n, 0.004)])


def _contraccion(tab, canal: int = 0) -> None:
    """Una contracción al 50 % de la referencia de ese músculo."""
    alto, bajo = np.full(400, 0.5), np.full(400, 0.01)
    tab._guia_detecta([alto, bajo] if canal == 0 else [bajo, alto])


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
        _con_referencia(adq)
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
        _con_referencia(adq)
        _reposo(adq)
        adq._man_hechas = [MANIOBRAS_POR_MUSCULO, 0]
        for i in range(MANIOBRAS_POR_MUSCULO):
            adq._mvc_overlay.mark_step(i)
        _contraccion(adq, 0)
        hechas = adq._mvc_overlay.steps_done()
        assert hechas[:MANIOBRAS_POR_MUSCULO] == [True] * MANIOBRAS_POR_MUSCULO
        assert hechas[MANIOBRAS_POR_MUSCULO:] == [False] * MANIOBRAS_POR_MUSCULO
        assert adq._man_hechas[0] == MANIOBRAS_POR_MUSCULO
        assert adq._man_grupo == 0, "una contracción de más no pasa de fase"


class TestTheManoeuvresEndWhenTheyAreDoneOrWhenTheStudentSaysSo:
    """El requisito que evita el desastre, escrito como debía estarlo.

    El guion pide seis flexiones **libres**, al ritmo del alumno, y el
    artículo describe esa libertad; así que las casillas solo pueden
    rellenarse detectando. Un detector se salta una antes o después, y si la
    fase dependiera de las doce casillas, el alumno se quedaría encerrado.

    De ahí no se sigue que el botón tenga que ser la **única** salida, que
    es lo que estuvo siendo un día: se sigue que tiene que existir. La fase
    acaba al contar lo que pedía —y quedarse el músculo en reposo, para no
    cortarle la cola a la última— o cuando lo dice el alumno. Lo que nunca
    puede pasar es que no acabe.
    """

    def test_the_six_and_a_second_of_quiet_move_it_on(self, adq) -> None:
        adq._n_channels = 2
        _con_referencia(adq)
        _reposo(adq)
        for _ in range(MANIOBRAS_POR_MUSCULO):
            _contraccion(adq, 0)
            _quieto(adq, 1.5)          # el hueco que el conteo exige
        assert adq._man_hechas[0] == MANIOBRAS_POR_MUSCULO
        assert adq._man_grupo == 1, "no pasó al segundo músculo"

    def test_and_not_before_the_second_is_up(self, adq) -> None:
        adq._n_channels = 2
        _con_referencia(adq)
        _reposo(adq)
        for _ in range(MANIOBRAS_POR_MUSCULO - 1):
            _contraccion(adq, 0)
            _quieto(adq, 1.5)
        _contraccion(adq, 0)
        assert adq._man_hechas[0] == MANIOBRAS_POR_MUSCULO
        _quieto(adq, 0.4)
        assert adq._man_grupo == 0, "cuatro décimas no son un segundo"
        _quieto(adq, 0.8)
        assert adq._man_grupo == 1

    def test_the_last_contraction_on_its_own_does_not(self, adq) -> None:
        """Pasar en el instante de la sexta le cortaría su propia cola."""
        adq._n_channels = 2
        _con_referencia(adq)
        _reposo(adq)
        for _ in range(MANIOBRAS_POR_MUSCULO - 1):
            _contraccion(adq, 0)
            _quieto(adq, 1.5)
        _contraccion(adq, 0)
        assert adq._man_hechas[0] == MANIOBRAS_POR_MUSCULO
        assert adq._man_grupo == 0

    def test_a_missed_onset_leaves_the_button_as_the_way_out(self, adq) -> None:
        """Cinco de seis y todo el reposo del mundo: la fase no acaba sola,
        y por eso el botón está a la vista mientras dura."""
        adq._n_channels = 2
        _con_referencia(adq)
        _reposo(adq)
        for _ in range(MANIOBRAS_POR_MUSCULO - 1):
            _contraccion(adq, 0)
            _quieto(adq, 1.5)
        _quieto(adq, 5 * MANIOBRA_REPOSO_S)   # menos que el límite
        assert adq._man_grupo == 0
        assert adq._btn_paso_hecho.isVisible()
        adq._paso_siguiente()
        assert adq._man_grupo == 1

    def test_the_second_muscle_moves_on_to_the_grip_the_same_way(
        self, adq
    ) -> None:
        adq._n_channels = 2
        _con_referencia(adq)
        _con_referencia(adq, 1)
        _reposo(adq)
        adq._man_hechas[1] = MANIOBRAS_POR_MUSCULO
        _quieto(adq, MANIOBRA_REPOSO_S)
        assert adq._guia_fase == "coact"
        assert not adq._btn_paso_hecho.isVisible()

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


class TestWhatTheRealBoardFound:
    """El primer ensayo con la placa de verdad: el mapa mentía.

    Contaba **seis inicios para cuatro contracciones** —la envolvente baja
    en mitad de un esfuerzo y medio segundo de refractario no lo tapa— y la
    diafonía del otro músculo disparaba también. Con las casillas llenas de
    mentira, la fase se quedó esperando dos contracciones que ya había
    contado, y hubo que pasar con el botón.
    """

    def test_one_effort_that_wobbles_in_the_middle_counts_once(self, adq) -> None:
        """Justo lo que pasó: dos inicios a medio segundo, un solo gesto. La
        envolvente baja en mitad del esfuerzo y vuelve a subir, y mientras no
        cruce hacia abajo el suelo con holgura sigue siendo el mismo."""
        adq._n_channels = 2
        _con_referencia(adq)
        alto = np.concatenate([np.full(300, 0.5), np.full(150, 0.08),
                               np.full(300, 0.5)])
        adq._guia_detecta([alto, np.full(alto.size, 0.01)])
        assert adq._man_hechas[0] == 1

    def test_and_two_separated_by_rest_are_two(self, adq) -> None:
        adq._n_channels = 2
        _con_referencia(adq)
        _contraccion(adq, 0)
        _quieto(adq, 0.6)
        _contraccion(adq, 0)
        assert adq._man_hechas[0] == 2, "sin refractario que se las coma"

    def test_a_rebound_is_too_short_to_count(self, adq) -> None:
        """Lo que sobraba tras cada esfuerzo en el registro de verdad duró
        0,28 s y 0,04 s; las contracciones, de 0,64 a 0,97 s. Lo que las
        separa es el tiempo, no la amplitud: una flexión libre es el gesto
        más flojo de la práctica y vive en la misma banda que un rebote."""
        adq._n_channels = 2
        _con_referencia(adq)
        adq._guia_detecta([np.full(280, 0.5), np.full(280, 0.01)])
        assert adq._man_hechas[0] == 0, "0,28 s no es una contracción"
        _quieto(adq, 0.6)
        _contraccion(adq, 0)
        assert adq._man_hechas[0] == 1

    def test_a_gentle_flexion_still_counts(self, adq) -> None:
        """El suelo va por debajo de la más floja: las flexiones son libres
        y sin resistencia a propósito, y dejar fuera un tercio de las que el
        guion pide no sería un suelo, sería otro protocolo."""
        adq._n_channels = 2
        _con_referencia(adq)
        adq._guia_detecta([np.full(500, 0.13), np.full(500, 0.01)])
        assert adq._man_hechas[0] == 1, "un 13 % sostenido es una contracción"

    def test_the_other_muscle_is_not_even_looked_at(self, adq) -> None:
        """La diafonía no infla la cuenta en vivo: en el turno de uno, el
        otro canal ni se mira. Lo que lee, entre un cuarto y un tercio de su propia referencia, es real y donde importan es en
        el análisis."""
        adq._n_channels = 2
        _con_referencia(adq)
        adq._guia_detecta([np.full(600, 0.01), np.full(600, 0.9)])
        assert adq._man_hechas == [0, 0]

    def test_and_the_phase_ends_even_if_the_count_never_gets_there(
        self, adq
    ) -> None:
        """Con una regla de conteo más estricta el cuelgue no desaparece: se
        muda del reposo a la cuenta. El límite es lo que hace verdadero que
        la fase **no pueda no terminar**; el botón solo hace que se pueda."""
        adq._n_channels = 2
        _con_referencia(adq)
        _contraccion(adq, 0)
        _quieto(adq, MANIOBRA_SIN_NOVEDAD_S + 1.0)
        assert adq._man_hechas[0] == 1, "solo se contó una de las seis"
        assert adq._man_grupo == 1, "y aun así pasó de fase"

    def test_and_the_limit_does_not_ask_for_rest(self, adq) -> None:
        """Un límite atado al reposo no es un límite: si el reposo no llega
        —el fallo mismo que esto viene a tapar— los dos caminos se quedarían
        colgados del mismo clavo. Aquí la señal nunca baja del 10 %."""
        adq._n_channels = 2
        _con_referencia(adq)
        ruido = np.full(int(0.5 * FS), 0.12)      # 12 % sin llegar a ser nada
        for _ in range(int(MANIOBRA_SIN_NOVEDAD_S / 0.5) + 2):
            adq._guia_detecta([ruido, ruido])
            if adq._man_grupo:
                break
        assert adq._man_grupo == 1, "no terminó sin reposo"

    def test_two_efforts_a_second_apart_are_two(self, adq) -> None:
        """Sin refractario, lo que mantiene unido un esfuerzo es la
        histéresis; dos de verdad, con su valle en medio, son dos. El ritmo
        lo pone el alumno y puede ir más rápido que el del ensayo."""
        adq._n_channels = 2
        _con_referencia(adq)
        _contraccion(adq, 0)
        _quieto(adq, 0.5)
        _contraccion(adq, 0)
        assert adq._man_hechas[0] == 2

    def test_the_rest_starts_when_the_signal_drops_not_when_the_box_fills(
        self, adq
    ) -> None:
        """La casilla se llena a los 0,3 s de empezar el esfuerzo, que es
        mejor —se ve contar mientras se aprieta—, pero la fase no puede
        darse por terminada con la sexta todavía en marcha."""
        adq._n_channels = 2
        _con_referencia(adq)
        adq._man_hechas = [MANIOBRAS_POR_MUSCULO - 1, 0]
        for i in range(MANIOBRAS_POR_MUSCULO - 1):
            adq._mvc_overlay.mark_step(i)
        # La sexta, sostenida mucho más de un segundo: se cuenta enseguida y
        # la fase no debe pasar mientras dure.
        for _ in range(4):
            adq._guia_detecta([np.full(400, 0.5), np.full(400, 0.01)])
        assert adq._man_hechas[0] == MANIOBRAS_POR_MUSCULO
        assert adq._man_grupo == 0, "no se pasa con el esfuerzo en marcha"
        _quieto(adq, 1.2)
        assert adq._man_grupo == 1

    def test_and_without_a_reference_nothing_is_counted(self, adq) -> None:
        """El conteo va en % de la CVM: sin calibrar no hay porcentaje."""
        adq._n_channels = 2
        _con_referencia(adq)
        adq._mvc_ref[0] = None
        _contraccion(adq, 0)
        assert adq._man_hechas[0] == 0


class TestTheHoldRunsOnTheClock:
    def test_the_bar_fills_and_the_box_is_marked_at_the_end(self, adq) -> None:
        adq._n_channels = 2
        adq._guia_coactivacion()
        # La cuenta atrás no enseña casillas: no llena ninguna. El mapa sale
        # con la presa, que es la que llena la suya.
        assert adq._mvc_overlay.steps_rows() == 0
        adq._coact_elapsed = MVC_READY_S
        adq._coact_tick()
        assert adq._coact_fase == "hold"
        assert adq._mvc_overlay.steps_done() == [False] * COACT_REPS
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

    def test_no_panel_shows_boxes_it_will_not_fill(self, adq, monkeypatch) -> None:
        """Una fila de casillas vacías que no se llena es una promesa que ese
        cuadro no cumple. Ni el calentamiento ni la cuenta atrás llenan
        ninguna —y la cuenta atrás lleva además el pictograma, que es lo que
        hay que mirar ahí—, así que el mapa lo trae **la primera repetición
        cerrada**, que es la que llena la primera."""
        from emgteach.profiles import EMG_PROFILE

        adq._iniciar_calibracion(auto_flow=False)
        try:
            adq._mvc_phase = "warmup"
            adq._mvc_elapsed = 0.0
            adq._mvc_tick()
            assert adq._mvc_overlay.steps_done() == [], "el calentamiento"
            adq._mvc_elapsed = EMG_PROFILE.warmup_s
            adq._mvc_tick()                       # se acaba el calentamiento
            assert adq._mvc_phase == "ready"
            assert adq._mvc_overlay.steps_done() == [], "la cuenta atrás"
            monkeypatch.setattr(adq, "_write_phase_marker", lambda *_a: None)
            monkeypatch.setattr(adq, "_instruct_device", lambda *_a, **_k: None)
            monkeypatch.setattr(adq, "_mvc_compute_muscle", lambda *_a: None)
            adq._mvc_muscle, adq._mvc_rep = 0, 0
            adq._mvc_cur_buf, adq._mvc_cross_buf = [1.0], {}
            adq._mvc_finish_rep()                 # la primera, cerrada
            hechas = adq._mvc_overlay.steps_done()
            assert len(hechas) == adq._n_channels * adq._mvc_reps
            assert hechas[0] is True, "sale con una llena, no vacío"
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


class TestTheGripBoxDoesNotHideWhatItTellsYouToWatch:
    """El cuadro flota justo encima de las barras de carga, y el guion manda
    mirarlas: «manténgalo firme pero submáximo, **guiándose por la barra de
    carga hacia el 50-60 %**». Un panel que esconde aquello a lo que apunta la
    instrucción es peor que ningún panel, así que las lleva dentro.
    """

    def test_the_hold_shows_each_muscle_in_its_own_colour(self, adq) -> None:
        from emgteach.gui.tabs.acquisition import COACT_ZONA

        adq._n_channels = 2
        adq._guia_coactivacion()
        adq._coact_fase = "hold"
        adq._carga_inst = [55.0, 48.0] + [0.0] * (len(adq._carga_inst) - 2)
        adq._coact_elapsed = 1.0
        adq._coact_tick()
        ov = adq._mvc_overlay
        assert len(ov._loads) == 2
        assert ov._loads[0] == (pytest.approx(0.55), _CHANNEL_COLORS[0])
        assert ov._loads[1] == (pytest.approx(0.48), _CHANNEL_COLORS[1])
        assert ov._zone == COACT_ZONA, "la banda a la que se apunta"

    def test_and_nothing_else_carries_them(self, adq) -> None:
        """Solo la presa: en las demás fases el cuadro no tapa esas barras."""
        adq._n_channels = 2
        adq._guia_maniobras(0)
        assert adq._mvc_overlay._loads == []
        adq._mvc_overlay.show_relax("x")
        assert adq._mvc_overlay._loads == []

    def test_the_box_stays_off_the_load_bars(self, adq) -> None:
        """Y lo que no puede tapar son las barras, no las gráficas.

        De todo lo que hay en esta pantalla, las barras son lo que el guion
        manda mirar y de donde se lee cada % CVM; la traza en bruto es lo
        único que se puede tapar unos segundos sin que nadie pierda el
        hilo. El cuadro empieza dentro del área de gráficas, así que todo
        lo que hay por encima queda libre.
        """
        adq._n_channels = 2
        for arranque in (lambda: adq._guia_maniobras(0),
                         adq._guia_coactivacion):
            arranque()
            ov = adq._mvc_overlay
            assert ov.y() >= adq._grp_plots.geometry().top(), adq._guia_fase
