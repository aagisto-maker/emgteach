"""La segunda ronda del banco del 5-sep-2026, con el exe.

La cinemática ya funcionaba de principio a fin —doce levantamientos con sus
cargas, el acelerómetro dentro del fichero— y lo que quedaba era cómo se ve y
cómo se cuenta:

* los pasos de la secuencia, en un cartel oscuro volante sobre el control que
  nombran, como ya hacía la pestaña de análisis, y no en letra pequeña dentro
  de la caja;
* la caja de fuerza-velocidad en **dos líneas**: los dos botones arriba, los
  umbrales debajo, y la tercera línea («3 · Iniciar grabación…») explicada en
  la ayuda, que es donde se puede leer entera;
* la de marcadores, en dos también: la explicación al lado de la casilla;
* el registro de eventos ocupando su caja entera, en las dos pestañas que
  llevan uno;
* la fila de «analizar solo una región», fuera;
* y, después del estudio F-V, el aviso de guardar el EDF afinado, que es lo
  único que conserva las decisiones tomadas en pantalla.

Y una decisión de fondo: **se quitan las contracciones mantenidas de la
calibración**. Estaban ahí porque la referencia se medía sobre la meseta;
medida sobre el pico de 0,2 s, una sacudida da lo mismo y cuesta la cuarta
parte de fatiga.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from emgteach.i18n import tr
from emgteach.modes import MODE_KINEMATICS, MODE_SINGLE

pytestmark = pytest.mark.gui


@pytest.fixture
def adq(qapp):
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    t = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "tarde"))
    t._settings.clear()
    t.apply_mode(MODE_KINEMATICS, True)
    yield t
    t._mvc_timer.stop()
    t._fv_timer.stop()
    t._load_timer.stop()
    t._watchdog_timer.stop()
    t.close()


class TestThePlanTheStudentIsGiven:
    """One lift per load is one number per load, with nothing to say how much
    of it is the subject and how much is the attempt."""

    def test_the_dialog_opens_on_three_lifts_six_seconds_and_one(self, qapp) -> None:
        from emgteach.gui.widgets.force_velocity_plan_dialog import (
            ForceVelocityPlanDialog,
        )

        dlg = ForceVelocityPlanDialog()
        try:
            assert dlg.reps() == 3
            assert dlg.prep_seconds() == pytest.approx(6.0)
            assert dlg.window_seconds() == pytest.approx(1.0)
        finally:
            dlg.deleteLater()

    def test_the_recording_assumes_the_same(self, adq) -> None:
        """A plan with only the loads typed in still runs those numbers."""
        adq._settings.setValue("adquisicion/fv_loads", "2, 4")
        loads, reps, prep_s, lift_s = adq._plan_fv_guardado()
        assert loads == [2.0, 4.0]
        assert (reps, prep_s, lift_s) == (3, 6.0, 1.0)

    def test_reopening_it_shows_the_plan_that_is_set(self, qapp) -> None:
        """Finding every field back at its default is how a plan gets
        retyped wrongly."""
        from emgteach.gui.widgets.force_velocity_plan_dialog import (
            ForceVelocityPlanDialog,
        )

        dlg = ForceVelocityPlanDialog(
            loads="2, 3.4, 5", reps=2, prep_s=8.0, lift_s=1.5)
        try:
            assert dlg.loads() == [2.0, 3.4, 5.0]
            assert dlg.reps() == 2
            assert dlg.prep_seconds() == pytest.approx(8.0)
            assert dlg.window_seconds() == pytest.approx(1.5)
        finally:
            dlg.deleteLater()


class TestTheCalibrationIsBriefEffortsOnly:
    def test_in_every_practical(self, adq) -> None:
        from emgteach.profiles import EMG_PROFILE

        for modo in (MODE_SINGLE, MODE_KINEMATICS):
            adq.apply_mode(modo, True)
            adq._worker = None
            adq._mvc_reps = 0
            adq._iniciar_calibracion(auto_flow=True)   # no worker: it returns
            # The count is set before anything else can stop it.
            assert adq._mvc_reps in (0, EMG_PROFILE.mvc_bursts)

    def test_the_profile_no_longer_carries_a_hold_time(self) -> None:
        """`apda_calib_s` was the duration of the held maximum. With no held
        maximum it described nothing, and a setting that describes nothing is
        worse than one that is missing."""
        from emgteach.profiles import EMG_PROFILE

        assert not hasattr(EMG_PROFILE, "apda_calib_s")


class TestTheStepsFloatOverTheirControl:
    """«Los pasos los marque un cuadro oscuro volante, como en la pestaña de
    análisis»: the same signal, the same panel and the same rule — only on a
    change of step, and never while recording."""

    def _pasos(self, adq) -> list:
        recogido: list = []
        adq.coach_step.connect(lambda *a: recogido.append(a))
        return recogido

    def test_with_no_plan_it_points_at_the_parameters(self, adq) -> None:
        pasos = self._pasos(adq)
        adq._btn_conectar.setChecked(True)
        adq._actualizar_paso_guiado()
        assert len(pasos) == 1
        titulo, cuerpo, control = pasos[0]
        assert titulo == tr("Next step")
        assert control is adq._btn_fv_guided
        assert tr("F-V parameters…") in cuerpo

    def test_with_a_plan_it_points_at_the_record_button(self, adq) -> None:
        pasos = self._pasos(adq)
        adq._settings.setValue("adquisicion/fv_loads", "2, 4")
        adq._btn_conectar.setChecked(True)
        adq._actualizar_paso_guiado()
        assert pasos and pasos[-1][2] is adq._btn_grabar

    def test_it_says_nothing_twice(self, adq) -> None:
        pasos = self._pasos(adq)
        adq._btn_conectar.setChecked(True)
        for _ in range(4):
            adq._actualizar_paso_guiado()
        assert len(pasos) == 1

    def test_nothing_before_the_device_is_connected(self, adq) -> None:
        """The tour has just offered itself; a third panel in a row is
        noise."""
        pasos = self._pasos(adq)
        adq._actualizar_paso_guiado()
        assert pasos == []

    def test_nothing_in_the_other_practicals(self, adq) -> None:
        pasos = self._pasos(adq)
        adq.apply_mode(MODE_SINGLE, False)
        adq._btn_conectar.setChecked(True)
        adq._actualizar_paso_guiado()
        assert pasos == []

    def test_the_window_floats_it_over_the_tab_that_asked(
        self, main_window, qapp
    ) -> None:
        """Both tabs emit the same signal now, so the panel has to know which
        one has to be in front for it to make any sense."""
        adq = main_window._tab_adq
        main_window._tabs.setCurrentIndex(1)          # the analysis tab
        qapp.processEvents()
        main_window._mostrar_paso_guiado(
            "t", "c", adq._btn_grabar, adq)
        assert not main_window._coach.isVisible()     # kept, not shown
        assert main_window._paso_pendiente is not None
        main_window._tabs.setCurrentIndex(0)
        qapp.processEvents()
        assert main_window._coach.isVisible()
        main_window._coach.stop()


class TestTheBoxesAreTwoLines:
    def test_the_force_velocity_box_is_one_row_of_controls(self, adq) -> None:
        """Both buttons on the same line, the parameters first: the rehearsal
        is second although the guide teaches it first, because by the time
        anyone needs the box they have either rehearsed or decided not to."""
        fila = adq._box_fv_guided.layout()
        orden = [fila.itemAt(i).widget() for i in range(fila.count())]
        assert orden[0] is adq._btn_fv_guided
        assert orden[1] is adq._btn_fv_rehearse
        assert not hasattr(adq, "_lbl_fv_paso3")

    def test_the_wizard_commentary_is_out_of_the_layout(self, adq) -> None:
        """It is on the floating panel instead, in large type. In the box it
        widened the window on one line and made it three times taller on
        four."""
        assert adq._lbl_load_info.parent() is not None
        assert adq._lbl_load_info.isHidden()
        caja = adq._box_fv_guided.parentWidget()
        alto = caja.sizeHint().height()
        adq._lbl_load_info.setText("x" * 400)
        assert caja.sizeHint().height() == alto

    def test_the_markers_box_explains_k_beside_the_control(self, adq) -> None:
        fila = adq._box_autoonset.parentWidget().layout().itemAt(0).layout()
        widgets = [fila.itemAt(i).widget() for i in range(fila.count())]
        assert adq._box_autoonset in widgets
        assert adq._lbl_k_explica in widgets


class TestTheLogFillsItsBox:
    def test_it_has_no_ceiling_of_its_own(self, qapp) -> None:
        """Three lines was a ceiling, and the box around it is taller than
        three lines in both tabs that carry one."""
        from PySide6.QtWidgets import QSizePolicy

        from emgteach.gui.widgets.logger import LoggerWidget

        log = LoggerWidget()
        try:
            assert log.maximumHeight() > 10_000        # QWIDGETSIZE_MAX
            assert log.minimumHeight() > 0
            assert (log.sizePolicy().verticalPolicy()
                    is QSizePolicy.Policy.Ignored)
        finally:
            log.deleteLater()

    def test_the_mvc_tab_does_not_put_one_back(self, main_window) -> None:
        cvm = main_window._tab_cvm
        assert cvm._local_log.maximumHeight() > 10_000


class TestWhatTheAnalysisAsksForNext:
    def test_the_region_of_interest_is_gone_from_the_screen(
        self, main_window, qapp
    ) -> None:
        ana = main_window._tab_ana
        for avanzado in (False, True):
            ana.apply_mode(MODE_KINEMATICS, avanzado)
            qapp.processEvents()
            assert ana._box_roi.isHidden()

    def test_after_the_study_it_asks_for_the_tuned_recording(
        self, main_window
    ) -> None:
        """Everything the study rests on was decided on screen and none of it
        is in the file."""
        ana = main_window._tab_ana
        recogido: list = []
        ana.coach_step.connect(lambda *a: recogido.append(a))
        ana._btn_afinado.setEnabled(True)
        ana._paso_mostrado = ""
        ana._ofrecer_afinado()
        assert recogido and recogido[-1][2] is ana._btn_afinado
        assert tr("Save tuned EDF…") in recogido[-1][1]
        # And once only.
        ana._ofrecer_afinado()
        assert len(recogido) == 1

    def test_the_mvc_tab_says_which_file_to_open(self, main_window) -> None:
        cvm = main_window._tab_cvm
        texto = cvm._lbl_afinado.text()
        assert "_tuned" in texto
        assert tr("Compute MVC") in texto

    def test_a_second_recording_does_not_inherit_the_first_ones_numbers(
        self, main_window
    ) -> None:
        """Opening the tuned recording left the previous file's panels, load
        distribution and summary card on screen, under the new file's name in
        the path box and the old one's inside the card. Seen on the bench of
        5 September with the tuned recording of 18:13 open and the original's
        142 s still being shown."""
        cvm = main_window._tab_cvm
        cvm._last_result = {"cualquier": "cosa"}
        cvm._d_file.setText("emg_2026-09-05_18-13.edf")
        cvm._d_duration.setText("142.0 s")
        cvm._btn_guardar.setEnabled(True)
        cvm._olvidar_resultado()
        assert cvm._last_result is None
        assert cvm._d_file.text() == "—"
        assert cvm._d_duration.text() == "—"
        assert not cvm._btn_guardar.isEnabled()
