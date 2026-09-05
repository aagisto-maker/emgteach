"""Lo que la aplicación enseñaba en pantalla y no debía.

Nueve arreglos salidos de capturar la aplicación tal como la ve el alumno
—1400x900, en español, los tres modos— y mirar. Ninguno se veía leyendo el
código, y cada uno tiene aquí la prueba que lo habría cazado.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from emgteach.io import BufferedEdfWriter, ChannelInfo

pytestmark = pytest.mark.gui

FS = 1000


def _ventana(qapp, modo: str):
    from emgteach.gui.app import MainWindow

    ajustes = QSettings("emgteach-test", f"pantalla-{modo}")
    ajustes.clear()
    ajustes.setValue("adquisicion/port", "COM5")
    ajustes.setValue("app/mode", modo)
    win = MainWindow(ajustes)
    win.resize(1366, 768)
    win.show()
    qapp.processEvents()
    return win


def _cierra(qapp, win) -> None:
    qapp.processEvents()
    win.close()
    win.deleteLater()
    qapp.processEvents()
    qapp.processEvents()


class TestItFitsALaboratoryLaptop:
    """The window's minimum width was 1380 px in the kinematics practical.

    A 1366x768 laptop — which is what a teaching laboratory tends to have —
    could not show it whole. The culprit was one row of the MVC tab: channel,
    fragments, cut-off, three buttons and the panel boxes, all on a line that
    cannot wrap. It is two rows now.
    """

    @pytest.mark.parametrize("modo", ["single", "pair", "kinematics"])
    def test_the_minimum_width_is_under_1366(self, qapp, modo: str) -> None:
        from PySide6.QtGui import QFontDatabase

        # Without real fonts every glyph is a box wider than a letter, and the
        # width measured is the width of the missing fonts, not the layout's.
        if not QFontDatabase.families():
            pytest.skip("no fonts available to the offscreen platform")
        win = _ventana(qapp, modo)
        try:
            # El mínimo del diseño, no el de la ventana: la ventana ya no
            # deja que el diseño le imponga nada (nunca puede quedar más
            # ancha que la pantalla), así que preguntarle a ella no
            # cazaría un diseño que no cabe.
            ancho = win.layout_minimum_size().width()
            assert ancho <= 1366, f"{modo}: mínimo {ancho} px"
        finally:
            _cierra(qapp, win)

    def test_no_wizard_sentence_moves_the_load_box(self, qapp) -> None:
        """The running commentary of the two wizards cannot push the box.

        On the bench of 5 September the force-velocity wizard finished, wrote
        «4 loads recorded. Stop recording, then open…» into the small grey
        label beside the load bars, and that one sentence took the window's
        minimum width from 1091 to 1404 px — past the edge of the screen it
        was running on. The window went off the display and Qt said so in a
        warning that the windowed build could not print, which is how the
        operator got a crash dialogue out of a resize.

        The label is out of the layout now and the same sentences are on the
        floating panel instead, so this measures both axes: neither the
        window's minimum width nor the height of the box the label used to
        live in may move when the wizard speaks. Every sentence it is given,
        in both languages.
        """
        from PySide6.QtGui import QFontDatabase

        from emgteach.i18n import get_language, set_language, tr

        if not QFontDatabase.families():
            pytest.skip("no fonts available to the offscreen platform")

        antes = get_language()

        frases = [
            ("Force-velocity: {n} loads recorded. Stop recording, then open "
             "the Force-velocity study in the Analysis tab.", {"n": 4}),
            ("Relax. The maximum starts in {s:.0f} s.", {"s": 3}),
            ("Hold the maximum! {s:.0f} s", {"s": 3}),
            ("Force-velocity: {kg:g} kg — lift {r} of {rn}.",
             {"kg": 3.4, "r": 2, "rn": 3}),
        ]
        try:
            for idioma in ("es", "en"):
                set_language(idioma)
                win = _ventana(qapp, "kinematics")
                try:
                    adq = win._tab_adq
                    caja = adq._box_fv_guided.parentWidget()
                    vacia = win.layout_minimum_size().width()
                    alto = caja.sizeHint().height()
                    for plantilla, args in frases:
                        try:
                            texto = tr(plantilla).format(**args)
                        except (KeyError, IndexError):
                            texto = tr(plantilla)
                        adq._lbl_load_info.setText(texto)
                        qapp.processEvents()
                        ancho = win.layout_minimum_size().width()
                        # Ni un píxel, en ninguno de los dos ejes. Con margen
                        # la prueba pasaría en Windows y no en Linux, que es
                        # justo lo que pasó la primera vez.
                        assert ancho <= vacia, (
                            f"{idioma}: «{texto[:40]}…» ensancha la ventana "
                            f"de {vacia} a {ancho} px"
                        )
                        assert caja.sizeHint().height() <= alto, (
                            f"{idioma}: «{texto[:40]}…» hace más alta la caja "
                            f"de carga, de {alto} a "
                            f"{caja.sizeHint().height()} px"
                        )
                finally:
                    _cierra(qapp, win)
        finally:
            # El idioma es global: dejarlo cambiado le cambia el resultado a
            # cualquier prueba que corra después (y el orden es aleatorio).
            set_language(antes)


class TestTheAxesSayMillivolts:
    """The envelope axis read «mV (x0.000)» with ticks 0-500 on every screen.

    pyqtgraph picks an SI prefix for a small-valued axis by itself. And the
    order matters: turned off *after* the first setYRange, the x1000 already
    chosen stays, because the axis only recomputes the scale while the option
    is on. The first version of the fix did exactly that and changed nothing
    visible.
    """

    def test_no_axis_carries_a_hidden_scale_factor(self, qapp) -> None:
        win = _ventana(qapp, "single")
        try:
            adq = win._tab_adq
            for nombre, pw in (("raw", adq._plot_raw), ("env", adq._plot_env)):
                eje = pw.getAxis("left")
                assert eje.autoSIPrefixScale == 1.0, (
                    f"el eje {nombre} multiplica por {eje.autoSIPrefixScale}"
                )
        finally:
            _cierra(qapp, win)


class TestTheRawRangeIsTheDevices:
    """The raw plot was drawn to ±3.3 mV whatever the device.

    A BITalino cannot exceed ±1.635 mV, so the trace lived in the middle half
    of the panel; the Arduino front end reaches ±12.5 mV and was clipped by
    the same number. The full scale is the device's, and it is read off the
    device class.
    """

    def test_bitalino_gets_its_own_full_scale(self, qapp) -> None:
        from emgteach.devices.bitalino import BitalinoDevice

        win = _ventana(qapp, "single")
        try:
            adq = win._tab_adq
            adq._combo_device_type.setCurrentIndex(0)
            qapp.processEvents()
            esperado = BitalinoDevice._V_REF / 2.0 * 1000.0 / BitalinoDevice._GAIN_EMG
            assert adq._y_ranges_init[0][1] == pytest.approx(esperado, rel=1e-6)
            assert adq._y_ranges_init[0][1] < 2.0   # and not the old 3.3
        finally:
            _cierra(qapp, win)

    def test_arduino_gets_its_wider_one(self, qapp) -> None:
        from emgteach.devices.arduino import ArduinoDevice

        win = _ventana(qapp, "single")
        try:
            adq = win._tab_adq
            adq._combo_device_type.setCurrentIndex(1)
            qapp.processEvents()
            esperado = ArduinoDevice._V_REF / 2.0 * 1000.0 / ArduinoDevice._GAIN
            assert adq._y_ranges_init[0][1] == pytest.approx(esperado, rel=1e-6)
            assert adq._y_ranges_init[0][1] > 10.0
        finally:
            _cierra(qapp, win)


class TestTheFolderFieldHasAName:
    def test_a_label_says_folder(self, qapp) -> None:
        from PySide6.QtWidgets import QLabel

        from emgteach.i18n import tr

        win = _ventana(qapp, "single")
        try:
            textos = {w.text() for w in win._tab_adq.findChildren(QLabel)}
            assert tr("Output path and file:") in textos
        finally:
            _cierra(qapp, win)


class TestTheContextualStepLeavesWithTheTab:
    """Seen on the bench: the «next step» panel raised over the analysis tab
    stayed up when the student went back to Acquisition, dimming the session
    review and pointing at a button that was no longer on screen."""

    def test_it_closes_when_the_tab_changes(self, qapp) -> None:
        from emgteach.gui.widgets.coach import CoachStep

        win = _ventana(qapp, "pair")
        try:
            win._tabs.setCurrentWidget(win._tab_ana)
            win._coach.start([CoachStep("t", "b", target=lambda: win._tab_ana._btn_reps)])
            qapp.processEvents()
            assert win._coach.isVisible()
            win._tabs.setCurrentWidget(win._tab_adq)
            qapp.processEvents()
            assert not win._coach.isVisible()
        finally:
            _cierra(qapp, win)

    def test_but_the_tour_which_changes_tabs_itself_survives(self, qapp) -> None:
        from emgteach.gui.widgets.coach import CoachStep

        win = _ventana(qapp, "pair")
        try:
            pasos = [CoachStep("a", "b", target=lambda: win._tab_adq._btn_grabar, tab=0),
                     CoachStep("c", "d", target=lambda: win._tab_ana._btn_reps, tab=1)]
            win._coach.start(pasos, on_tab=win._tabs.setCurrentIndex)
            qapp.processEvents()
            win._coach.next()          # the tour itself moves to tab 1
            qapp.processEvents()
            assert win._coach.isVisible(), "el cambio de pestaña del propio tour la cerró"
            win._coach.stop()
        finally:
            _cierra(qapp, win)


class TestTheAppNoLongerContradictsItself:
    def test_the_tour_does_not_mention_a_free_analysis(self, qapp) -> None:
        from emgteach.gui.tour import build_tour

        win = _ventana(qapp, "single")
        try:
            cuerpos = " ".join(p.body for p in build_tour(win)).lower()
            assert "free analysis" not in cuerpos and "análisis libre" not in cuerpos
        finally:
            _cierra(qapp, win)

    def test_the_mvc_entry_panel_does_not_ask_for_two_recordings(
        self, qapp
    ) -> None:
        """The entry panel said «you need two recordings» while the tour, on
        the same tab, said the maximum is inside the recording. The tour was
        right."""
        from PySide6.QtWidgets import QLabel

        win = _ventana(qapp, "single")
        try:
            textos = " ".join(w.text() for w in win._tab_cvm.findChildren(QLabel)).lower()
            assert "two recordings" not in textos and "dos registros" not in textos
            assert "inside the session" in textos or "dentro de la propia sesión" in textos
        finally:
            _cierra(qapp, win)

    def test_the_entry_text_has_a_readable_measure(self, qapp) -> None:
        """Wrapped to the window, each line ran to some 250 characters."""
        from PySide6.QtWidgets import QLabel

        win = _ventana(qapp, "single")
        try:
            largos = [w for w in win._tab_cvm.findChildren(QLabel)
                      if len(w.text()) > 200 and w.wordWrap()]
            assert largos, "no encuentro los párrafos del panel de entrada"
            assert all(w.maximumWidth() <= 800 for w in largos)
        finally:
            _cierra(qapp, win)


def _registro_par(path: Path) -> str:
    t = np.arange(8 * FS) / FS
    canales = [ChannelInfo("FCR", dimension="mV", sample_frequency=FS),
               ChannelInfo("ECR", dimension="mV", sample_frequency=FS)]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(np.sin(2 * np.pi * 80 * t) * 0.1, np.sin(2 * np.pi * 80 * t) * 0.05)
    return str(path)


class TestTheReviewNamesTheLanesAfterTheFile:
    """The lanes said «EMG1 / EMG2» while the shading beside them read
    «FCR 1 … ECR 3»: two names for one muscle on one screen."""

    def test_the_lanes_take_the_files_names(self, qapp, tmp_path: Path) -> None:
        pytest.importorskip("mne")
        win = _ventana(qapp, "pair")
        try:
            adq = win._tab_adq
            adq._mostrar_registro(_registro_par(tmp_path / "par.edf"))
            qapp.processEvents()
            nombres = [adq._lane_labels[0][c].toPlainText().strip() for c in range(2)]
            assert nombres == ["FCR", "ECR"], nombres
            adq._salir_revision()
            qapp.processEvents()
            # And back to the boxes' names on the way out.
            assert adq._lane_labels[0][0].toPlainText().strip() != "FCR"
        finally:
            _cierra(qapp, win)


class TestTheAdvancedPracticalFoldsItsExtraPanels:
    """Twelve panel boxes did not fit on a row at 1400 px and overflowed into
    a scroll bar — a developer's menu, not a student's. The advanced practical
    now shows its own six and folds the rest behind «More panels…»."""

    def _visibles(self, tab) -> list[str]:
        return [c.text() for c in tab._chk_paneles if c.isVisibleTo(tab)]

    def test_kinematics_starts_with_its_own_six(self, qapp) -> None:
        win = _ventana(qapp, "kinematics")
        try:
            vis = self._visibles(win._tab_ana)
            assert len(vis) == 6, vis
            assert win._tab_ana._btn_mas_paneles.isVisibleTo(win._tab_ana)
        finally:
            _cierra(qapp, win)

    def test_more_reveals_the_other_six_and_folds_them_back(self, qapp) -> None:
        win = _ventana(qapp, "kinematics")
        try:
            ana = win._tab_ana
            ana._btn_mas_paneles.setChecked(True)
            qapp.processEvents()
            # Every box there is: thirteen, since the raw trace comes twice
            # (one per muscle) on top of the twelve numbered panels.
            assert len(self._visibles(ana)) == len(ana._chk_paneles)
            ana._btn_mas_paneles.setChecked(False)
            qapp.processEvents()
            assert len(self._visibles(ana)) == 6
        finally:
            _cierra(qapp, win)

    @pytest.mark.parametrize("modo", ["single", "pair"])
    def test_the_other_practicals_can_reveal_the_rest_too(self, qapp, modo) -> None:
        """Curiosity is not confined to the advanced practical: each opens on
        its own set (the pair adds the spectrum and the fatigue trend of both
        muscles) and «More panels…» shows the rest, minus what the recording
        cannot support."""
        win = _ventana(qapp, modo)
        try:
            ana = win._tab_ana
            assert ana._btn_mas_paneles.isVisibleTo(ana)
            assert len(self._visibles(ana)) == {"single": 3, "pair": 5}[modo]
            ana._btn_mas_paneles.setChecked(True)
            qapp.processEvents()
            # Single: no second-muscle panels, no accelerometer ones (13 - 5).
            # Pair: everything but the accelerometer three (13 - 3).
            assert len(self._visibles(ana)) == {"single": 8, "pair": 10}[modo]
        finally:
            _cierra(qapp, win)


class TestTheMvcTabComputesOnArrival:
    """Same as the analysis tab since it started analysing on open: a tab that
    receives a recording and waits for a button press to show anything."""

    def test_adopting_a_recording_starts_the_computation(
        self, qapp, tmp_path: Path, monkeypatch
    ) -> None:
        win = _ventana(qapp, "pair")
        try:
            cvm = win._tab_cvm
            lanzados: list[str] = []
            monkeypatch.setattr(cvm, "_iniciar_calculo", lambda: lanzados.append("va"))
            cvm.adopt_recording(_registro_par(tmp_path / "par.edf"), "FCR")
            assert lanzados == ["va"]
        finally:
            _cierra(qapp, win)
