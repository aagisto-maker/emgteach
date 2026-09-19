"""The picture of the gesture, where the gesture is being asked for.

The two pictures of the pair practical — the electrodes and the calibration —
were drawn for the guided tour, and the tour is offered once, at the first
start, and after that only from the «Guide» button. During the exercise what
is on screen is the calibration panel, and that panel could not show a
picture: title, countdown, bars and text.

So the figure existed, and was not there at the moment the student needs it,
which is when the application asks for the jerk. Now the panel takes one, the
tab passes it where the gesture is asked for, and the pictures stop belonging
to the tour: :func:`emgteach.gui.imagenes.imagen` is where both read them.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QWidget

from emgteach import i18n
from emgteach.gui.imagenes import imagen
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.gui.widgets.mvc_overlay import MvcOverlay


class TestThePicturesAreNotTheTours:
    def test_they_are_read_from_one_place_in_both_languages(self) -> None:
        anterior = i18n.get_language()
        try:
            for idioma in ("es", "en"):
                i18n.set_language(idioma)
                for nombre in ("calibracion", "electrodos"):
                    ruta = imagen(nombre)
                    assert ruta is not None and ruta.endswith(f"{nombre}_{idioma}.png")
        finally:
            i18n.set_language(anterior)

    def test_a_picture_nobody_drew_is_none(self) -> None:
        assert imagen("no_existe") is None

    def test_the_tour_reads_them_from_there_too(self) -> None:
        """Moved, not copied: one resolver for the tour and for the panel."""
        from emgteach.gui import tour

        assert tour.imagen is imagen


class TestThePanelTakesOne:
    @pytest.fixture
    def panel(self, qapp):
        host = QWidget()
        host.resize(900, 600)
        overlay = MvcOverlay(host)
        yield overlay
        host.close()

    def test_without_a_picture_nothing_about_the_panel_changes(self, panel) -> None:
        panel.show_ready("Get ready", 3, "a subtitle")
        alto_sin = panel.height()
        assert panel.image_rect() == (0, 0, 0, 0)
        panel.show_ready("Get ready", 3, "a subtitle", None)
        assert panel.height() == alto_sin
        panel.show_ready("Get ready", 3, "a subtitle", "no_existe.png")
        assert panel.height() == alto_sin, "a path that is not a picture is no picture"

    def test_with_one_the_panel_is_taller_and_keeps_its_width(self, panel) -> None:
        panel.show_ready("Get ready", 3, "a subtitle")
        alto_sin, ancho = panel.height(), panel.width()
        panel.show_ready("Get ready", 3, "a subtitle", imagen("calibracion"))
        assert panel.height() > alto_sin
        assert panel.width() == ancho, "the tab centres the panel by its width"

    def test_the_picture_sits_between_the_countdown_and_the_message(self, panel) -> None:
        panel.show_ready("Get ready", 3, "a subtitle", imagen("calibracion"))
        x, y, w, h = panel.image_rect()
        assert w > 0 and h > 0
        assert x == pytest.approx((panel.width() - w) / 2, abs=1)   # centred
        assert y + h <= panel.message_rect()[1]                     # above the text

    def test_the_effort_and_the_rest_show_none(self, panel) -> None:
        """While squeezing, the student watches the bar; a taller panel would
        cover the plots just then."""
        panel.show_ready("Get ready", 3, "a subtitle", imagen("calibracion"))
        assert panel.image_rect()[2] > 0
        panel.show_contract("FCR", 1.2, 0.5, 0.8)
        assert panel.image_rect() == (0, 0, 0, 0)
        panel.show_ready("Get ready", 3, "a subtitle", imagen("calibracion"))
        panel.show_relax("rest")
        assert panel.image_rect() == (0, 0, 0, 0)


class TestTheWizardPassesIt:
    @pytest.fixture
    def tab(self, qapp):
        from emgteach.gui.tabs.acquisition import AcquisitionTab

        widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "imagen-ejercicio"))
        widget._n_channels = 1
        yield widget
        widget._watchdog_timer.stop()
        widget._mvc_timer.stop()
        widget._prep_timer.stop()
        widget._load_timer.stop()
        widget.close()

    def test_the_countdown_of_an_effort_shows_the_calibration_picture(self, tab) -> None:
        from emgteach.gui.tabs.acquisition import MVC_READY_S

        tab._iniciar_calibracion(auto_flow=False)
        try:
            tab._mvc_muscle = 0
            tab._mvc_rep = 0
            tab._mvc_phase = "ready"
            tab._mvc_elapsed = MVC_READY_S / 2.0
            tab._mvc_tick()
            assert tab._mvc_overlay.image_rect()[2] > 0
        finally:
            tab._mvc_cancel()
