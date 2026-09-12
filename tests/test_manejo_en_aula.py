"""Manejo en el aula: lo que cuesta tiempo con el equipo delante, no el cálculo.

La envolvente en vivo, el guardado en una carpeta que ya no existe, el informe
en los móviles, los avisos de red y la selección de picos. La instancia única
tiene su propio fichero, ``test_instancia.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gui


# ---------------------------------------------------------------------------
# La envolvente en vivo no se sale por arriba de sus ejes
# ---------------------------------------------------------------------------


def _techo(adq) -> float:
    return float(adq._plot_env.getViewBox().viewRange()[1][1])


def _al_final(adq, valores) -> None:
    """Los valores al final del búfer: lo último que se ve, a la derecha."""
    for v in valores:
        for c in range(adq._n_channels):
            adq._buf_env[c].append(float(v))
    adq._total_samples += len(valores)
    adq._new_data = True


@pytest.fixture
def adq_limpia(main_window):
    adq = main_window._tab_adq
    adq._reset_buffers()
    adq._reset_y_scales()
    adq._total_samples = 0
    return adq


class TestTheLiveEnvelopeStaysInsideItsAxes:
    """La envolvente se salía por arriba en el escritorio mientras en el móvil
    cabía: la vista remota seguía al pico y el escritorio no. Es el panel que
    se mira mientras se contrae."""

    def test_a_peak_above_the_scale_raises_the_top(self, adq_limpia) -> None:
        adq = adq_limpia
        base = _techo(adq)
        _al_final(adq, [0.0] * 50 + [base * 4] + [0.0] * 50)
        adq._refresh_plots(force=True)
        assert _techo(adq) >= base * 4

    def test_once_the_peak_has_gone_it_falls_back_to_the_base(
        self, adq_limpia
    ) -> None:
        adq = adq_limpia
        base = _techo(adq)
        _al_final(adq, [base * 4])
        adq._refresh_plots(force=True)
        alto = _techo(adq)
        # El pico sale de la ventana visible.
        _al_final(adq, [0.0] * (adq._n_visible + 10))
        for _ in range(120):
            adq._refresh_plots(force=True)
        assert _techo(adq) < alto
        assert _techo(adq) == pytest.approx(base, rel=1e-6)

    def test_the_arrows_still_widen_the_scale(self, adq_limpia) -> None:
        adq = adq_limpia
        base = _techo(adq)
        _al_final(adq, [base * 0.1])
        adq._refresh_plots(force=True)
        adq._y_zoom(1, zoom_in=False)
        assert _techo(adq) == pytest.approx(base * 1.5, rel=1e-6)

    def test_zooming_in_cannot_cut_the_peak_off(self, adq_limpia) -> None:
        adq = adq_limpia
        base = _techo(adq)
        _al_final(adq, [base * 0.9])
        adq._refresh_plots(force=True)
        adq._y_zoom(1, zoom_in=True)
        assert _techo(adq) >= base * 0.9


# ---------------------------------------------------------------------------
# Guardar en una carpeta que ya no existe
# ---------------------------------------------------------------------------


class TestSavingToAFolderThatIsGone:
    """Se reproduce guardando en una carpeta que no existe —un pendrive
    retirado, una carpeta que alguien borró—: el diálogo devuelve la ruta
    igual y el escritor fallaba con «no such file or directory», sin decir
    qué archivo ni dónde."""

    def test_a_missing_folder_is_simply_created(self, tmp_path) -> None:
        from emgteach.gui.tabs.acquisition import preparar_carpeta

        ruta = tmp_path / "pendrive" / "sesion" / "P01.edf"
        assert preparar_carpeta(str(ruta)) is None
        assert ruta.parent.is_dir()

    def test_when_it_cannot_be_made_the_message_says_what_and_where(
        self, tmp_path, monkeypatch
    ) -> None:
        from emgteach.gui.tabs.acquisition import preparar_carpeta

        def revienta(self, *_a, **_k):
            raise FileNotFoundError(2, "No such file or directory")

        monkeypatch.setattr(Path, "mkdir", revienta)
        ruta = tmp_path / "unidad_retirada" / "P01.edf"
        mensaje = preparar_carpeta(str(ruta))
        assert mensaje is not None
        assert "P01.edf" in mensaje
        assert str(ruta.parent) in mensaje
        assert "No such file or directory" in mensaje

    def test_the_writer_failure_names_the_file_and_the_folder(
        self, tmp_path
    ) -> None:
        """Lo que decía la biblioteca era el mensaje entero."""
        from emgteach.io import BufferedEdfWriter, ChannelInfo
        from emgteach.workers.acquisition import mensaje_fallo_guardado

        ruta = tmp_path / "no_existe" / "P01.edf"
        with pytest.raises(OSError) as fallo:
            with BufferedEdfWriter(
                str(ruta), channels=[ChannelInfo("EMG", sample_frequency=1000)]
            ) as w:
                w.add_samples([0.0] * 1000)
        mensaje = mensaje_fallo_guardado(ruta, fallo.value)
        assert "P01.edf" in mensaje
        assert str(ruta.parent) in mensaje

    def test_recordings_go_to_documents_until_someone_chooses(self) -> None:
        """No al directorio de trabajo: lanzado desde un acceso directo puede
        ser una carpeta del sistema donde un alumno no puede escribir."""
        from emgteach.gui.tabs.acquisition import carpeta_por_defecto

        assert Path(carpeta_por_defecto()).is_dir()

    def test_without_a_documents_folder_it_falls_back_to_home(
        self, tmp_path, monkeypatch
    ) -> None:
        """Un Linux sin carpetas XDG no tiene Documentos, y el diálogo se
        abría sobre una ruta que no existe."""
        import emgteach.gui.tabs.acquisition as mod

        monkeypatch.setattr(mod, "_documentos", lambda: str(tmp_path / "no_hay"))
        assert mod.carpeta_por_defecto() == str(Path.home())
        monkeypatch.setattr(mod, "_documentos", lambda: str(tmp_path))
        assert mod.carpeta_por_defecto() == str(tmp_path)


# ---------------------------------------------------------------------------
# El móvil ofrece el informe PDF, y primero
# ---------------------------------------------------------------------------


class _Difusion:
    """Lo que la pestaña de análisis ve del servidor, sin abrir puertos."""

    def __init__(self, en_marcha: bool = True) -> None:
        self.en_marcha = en_marcha
        self.descargas: list[tuple[str, str, str]] = []
        self.mensajes: list[dict] = []

    def is_running(self) -> bool:
        return self.en_marcha

    def register_download(self, path, data, content_type, filename) -> None:
        self.descargas.append((path, content_type, filename))

    def broadcast(self, payload: dict) -> None:
        self.mensajes.append(payload)


class TestThePhonesGetTheReport:
    """Un CSV aporta poco a quien sigue la práctica desde el móvil; lo útil es
    el informe, que ya se genera y trae los paneles, las tablas y el veredicto."""

    @pytest.fixture
    def ana(self, main_window, monkeypatch, tmp_path):
        from emgteach.gui.tabs import analysis as mod

        ana = main_window._tab_ana

        def informe(out, r, meta, panels=None, time_range=None):
            Path(out).write_bytes(b"%PDF-1.4 prueba")

        def csv(r, ruta):
            Path(ruta).write_text("t_s,rms_mv\n", encoding="utf-8")

        monkeypatch.setattr(mod, "build_session_report", informe)
        monkeypatch.setattr(mod, "write_analysis_csv", csv)
        ana._resultado_prueba = {"edf_path": str(tmp_path / "P03.edf")}
        ana._last_result = ana._resultado_prueba
        return ana

    def test_each_analysis_offers_the_report_first(self, ana, monkeypatch) -> None:
        dif = _Difusion()
        monkeypatch.setattr(ana, "_broadcast", dif)
        ana._ofrecer_descargas(ana._resultado_prueba)
        tipos = [m["kind"] for m in dif.mensajes if m.get("t") == "download"]
        assert tipos[0] == "report"
        assert "csv" in tipos
        _ruta, tipo, nombre = dif.descargas[0]
        assert tipo == "application/pdf"
        assert nombre.startswith("P03")

    def test_without_the_broadcast_nothing_is_made(self, ana, monkeypatch) -> None:
        dif = _Difusion(en_marcha=False)
        monkeypatch.setattr(ana, "_broadcast", dif)
        ana._ofrecer_descargas(ana._resultado_prueba)
        assert dif.descargas == []

    def test_a_result_already_replaced_is_not_offered(self, ana, monkeypatch) -> None:
        """Se prepara después de pintar los paneles; si para entonces ya hay
        otro análisis, el informe del anterior no se ofrece como si fuera el
        nuevo."""
        dif = _Difusion()
        monkeypatch.setattr(ana, "_broadcast", dif)
        ana._ofrecer_descargas({"edf_path": "otro.edf"})
        assert dif.descargas == []

    def test_the_phone_page_puts_the_report_before_the_csv(self) -> None:
        from emgteach.broadcast import _load_dashboard_html

        html = _load_dashboard_html().decode("utf-8")
        assert html.index('id="results"') < html.index('id="tools"')
        assert "box.prepend(a)" in html
        assert "El informe en PDF aparecerá aquí" in html


# ---------------------------------------------------------------------------
# La red: que el profesor no se quede a ciegas
# ---------------------------------------------------------------------------


class TestTheTeacherIsNotLeftGuessing:
    """Que el ordenador y los móviles se vean depende de la red del aula, que
    puede no alcanzar al equipo o aislar a los clientes entre sí. Nada de eso
    se arregla desde el programa; lo que sí se puede es no dejar un panel
    vacío sin explicación."""

    def test_with_no_interface_there_is_no_usable_network(self, monkeypatch) -> None:
        import emgteach.broadcast as difusion

        monkeypatch.setattr(difusion, "lan_ipv4", lambda: "127.0.0.1")
        assert difusion.hay_red_utilizable() is False
        monkeypatch.setattr(difusion, "lan_ipv4", lambda: "192.168.1.20")
        assert difusion.hay_red_utilizable() is True

    @pytest.fixture
    def adq(self, main_window, monkeypatch):
        adq = main_window._tab_adq
        servidor = adq._broadcast
        # Sin abrir puertos de verdad.
        monkeypatch.setattr(servidor, "start", lambda: True)
        monkeypatch.setattr(servidor, "stop", lambda: None)
        monkeypatch.setattr(servidor, "broadcast", lambda payload: None)
        monkeypatch.setattr(
            servidor, "follower_url", lambda: "http://10.0.0.5:8070/?k=abc"
        )
        errores: list[str] = []
        monkeypatch.setattr(adq, "_err", errores.append)
        adq._errores_prueba = errores
        return adq

    def test_with_no_network_it_says_so_at_once(self, adq, monkeypatch) -> None:
        import emgteach.gui.tabs.acquisition as mod

        monkeypatch.setattr(mod, "hay_red_utilizable", lambda: False)
        adq._on_toggle_broadcast(True)
        assert adq._errores_prueba == [mod.aviso_sin_red()]

    def test_with_a_network_it_waits_for_someone_to_join(
        self, adq, monkeypatch
    ) -> None:
        import emgteach.gui.tabs.acquisition as mod

        monkeypatch.setattr(mod, "hay_red_utilizable", lambda: True)
        adq._on_toggle_broadcast(True)
        assert adq._timer_sin_seguidores.isActive()
        assert adq._timer_sin_seguidores.interval() == mod.ESPERA_SEGUIDORES_MS
        assert adq._errores_prueba == []

        monkeypatch.setattr(adq._broadcast, "is_running", lambda: True)
        monkeypatch.setattr(adq._broadcast, "client_count", lambda: 0)
        adq._avisar_sin_seguidores()
        assert adq._errores_prueba == [mod.aviso_sin_seguidores()]

    def test_the_first_follower_disarms_the_warning(self, adq, monkeypatch) -> None:
        import emgteach.gui.tabs.acquisition as mod

        monkeypatch.setattr(mod, "hay_red_utilizable", lambda: True)
        adq._on_toggle_broadcast(True)
        adq._on_broadcast_clients(1)
        assert not adq._timer_sin_seguidores.isActive()

    def test_stopping_the_broadcast_disarms_it(self, adq, monkeypatch) -> None:
        import emgteach.gui.tabs.acquisition as mod

        monkeypatch.setattr(mod, "hay_red_utilizable", lambda: True)
        adq._on_toggle_broadcast(True)
        adq._on_toggle_broadcast(False)
        assert not adq._timer_sin_seguidores.isActive()

    def test_both_warnings_name_the_way_that_always_works(self) -> None:
        from emgteach.gui.tabs.acquisition import aviso_sin_red, aviso_sin_seguidores
        from emgteach.i18n import get_language, set_language

        anterior = get_language()
        try:
            for idioma, clave in (("en", "Mobile hotspot"),
                                  ("es", "Zona con cobertura inalámbrica móvil")):
                set_language(idioma)
                assert clave in aviso_sin_red()
                assert clave in aviso_sin_seguidores()
        finally:
            set_language(anterior)


# ---------------------------------------------------------------------------
# La selección de picos: es la que decide el número que se publica
# ---------------------------------------------------------------------------

FS = 1000
FK = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


def _serie(debil: float | None = None, seed: int = 0):
    """Dos contracciones claras y, si se pide, una débil entre ellas."""
    import numpy as np

    rng = np.random.default_rng(seed)
    s = rng.normal(0.0, 0.01, size=10 * FS)
    tramos = [((2.0, 3.5), 0.5), ((6.0, 7.5), 0.5)]
    if debil is not None:
        tramos.append(((4.3, 5.0), debil))
    for (a, b), amp in tramos:
        i0, i1 = int(a * FS), int(b * FS)
        t = np.arange(i1 - i0) / FS
        s[i0:i1] += amp * np.sin(2 * np.pi * 90.0 * t)
    return s


def _dialogo(raw=None, **kw):
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

    return FragmentSelectionDialog(_serie() if raw is None else raw, FS, FK, **kw)


def _par(**kw):
    """Dos músculos; el segundo, a un 30 %: la aplicación propone el primero."""
    return _dialogo(raw_2=_serie(seed=1) * 0.3, name_1="FCR", name_2="ECR", **kw)


class TestKIsThePracticalsOwnAndPartOfTheResult:
    """k decide qué se marca, y con ello el índice de coactivación: se ajusta
    antes que nada, parte del valor de cada práctica y queda escrito."""

    def test_the_pair_opens_on_4_4_and_the_rest_on_the_core_default(self) -> None:
        from emgteach.modes import (
            MODE_KINEMATICS,
            MODE_PAIR,
            MODE_SINGLE,
            mode_detection_k,
            mode_expected_contractions,
        )
        from emgteach.selection import DEFAULT_DETECTION

        assert mode_detection_k(MODE_PAIR) == pytest.approx(4.4)
        assert mode_detection_k(MODE_SINGLE) == DEFAULT_DETECTION["k"]
        assert mode_detection_k(MODE_KINEMATICS) == DEFAULT_DETECTION["k"]
        assert mode_expected_contractions(MODE_PAIR) == (6, 6, 1)
        assert mode_expected_contractions(MODE_SINGLE) == ()

    def test_the_editor_opens_on_it_and_reset_goes_back_to_it(self, qapp) -> None:
        dlg = _dialogo(default_k=4.4)
        assert dlg._sld_k.value() == 44
        dlg._sld_k.setValue(20)
        dlg._reset_detection()
        assert dlg.detection_kwargs()["k"] == pytest.approx(4.4)
        assert dlg._sld_k.value() == 44
        dlg.deleteLater()

    def test_where_it_was_left_wins_over_the_practicals(self, qapp) -> None:
        dlg = _dialogo(detection={"k": 3.5}, default_k=4.4)
        assert dlg._sld_k.value() == 35
        dlg.deleteLater()

    def test_the_sensitivity_comes_before_the_plot(self, qapp) -> None:
        dlg = _dialogo()
        lay = dlg.layout()
        orden = [lay.itemAt(i).widget() for i in range(lay.count())]
        assert orden.index(dlg._sld_k.parentWidget()) < orden.index(dlg._canvas)
        dlg.deleteLater()

    def test_without_opening_the_editor_the_analysis_uses_it_too(
        self, main_window
    ) -> None:
        from emgteach.modes import MODE_PAIR, MODE_SINGLE

        ana = main_window._tab_ana
        anterior = ana._mode
        try:
            ana._mode = MODE_PAIR
            assert ana._deteccion_por_defecto()["k"] == pytest.approx(4.4)
            ana._mode = MODE_SINGLE
            assert ana._deteccion_por_defecto()["k"] == pytest.approx(3.0)
        finally:
            ana._mode = anterior

    def test_the_csv_says_which_k(self, tmp_path) -> None:
        from emgteach.exports import write_analysis_csv
        from emgteach.i18n import tr

        ruta = tmp_path / "P01.csv"
        write_analysis_csv({"edf_path": "P01.edf", "detection": {"k": 4.4}}, ruta)
        texto = ruta.read_text(encoding="utf-8-sig")
        assert f"# {tr('Detection sensitivity (k)')}: 4.4" in texto

    def test_the_report_says_which_k(self, tmp_path, monkeypatch) -> None:
        import numpy as np

        import emgteach.reports as informes
        from emgteach.i18n import tr

        t = np.arange(3000) / FS
        sig = 0.3 * np.sin(2 * np.pi * 80.0 * t)
        resultado = {
            "times": t, "emg_filtered": sig, "emg_envelope": np.abs(sig),
            "markers": [], "channel_name": "FCR", "edf_path": "P01.edf",
            "duration": 3.0, "rms_global": 0.2, "mnf": 95.0, "mdf": 88.0,
            "iemg": 1.2, "fat_slope_sign": 0, "fat_verdict": "inconclusive",
            "mdf_slope": 0.0, "fs": FS, "detection": {"k": 4.4},
        }
        tablas: list[list[list[str]]] = []
        original = informes._styled_table

        def espia(data):
            tablas.append(data)
            return original(data)

        monkeypatch.setattr(informes, "_styled_table", espia)
        informes.build_session_report(str(tmp_path / "P01.pdf"), resultado)
        filas = [f for tabla in tablas for f in tabla]
        assert [tr("Detection sensitivity (k)"), "4.4"] in filas


class TestTheCounter:
    """«Flexiones: 5 de 6 esperadas» atrapa el fallo sin que nadie tenga que
    darse cuenta: la práctica tiene una estructura conocida de antemano."""

    def test_it_counts_each_kind_against_the_protocol(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = _par(expected=(6, 6, 1))
        textos = [etiqueta.text() for _c, etiqueta, _s in dlg._contadores]
        assert textos == ["FCR: 2 /", "ECR: 0 /", f"{tr('Co-activation')}: 0 /"]
        assert dlg.expected_counts() == (6, 6, 1)
        _c, fcr, spin = dlg._contadores[0]
        assert fcr.toolTip(), "dos de seis y sin aviso"
        spin.setValue(2)
        assert fcr.toolTip() == ""
        assert dlg.expected_counts() == (2, 6, 1)
        dlg.deleteLater()

    def test_dropping_a_row_takes_it_off_the_count(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = _dialogo(expected=(2,))
        etiqueta = dlg._contadores[0][1]
        assert etiqueta.text() == f"{tr('Contractions')}: 2 /"
        dlg._clic_en(2.5)
        dlg._eliminar()
        assert etiqueta.text() == f"{tr('Contractions')}: 1 /"
        assert etiqueta.toolTip()
        dlg.deleteLater()

    def test_without_a_target_it_just_counts(self, qapp) -> None:
        dlg = _dialogo()
        etiqueta = dlg._contadores[0][1]
        assert dlg.expected_counts() == (0,)
        assert etiqueta.toolTip() == ""
        dlg.deleteLater()

    def test_a_changed_practical_forgets_the_old_targets(self, main_window) -> None:
        from emgteach.modes import MODE_PAIR, MODE_SINGLE

        ana = main_window._tab_ana
        anterior, avanzado = ana._mode, ana._advanced
        try:
            ana.apply_mode(MODE_PAIR, avanzado)
            ana._esperadas = (5, 6, 1)
            ana.apply_mode(MODE_PAIR, avanzado)
            assert ana._esperadas == (5, 6, 1), "la misma práctica los conserva"
            ana.apply_mode(MODE_SINGLE, avanzado)
            assert ana._esperadas is None
        finally:
            ana.apply_mode(anterior, avanzado)


class TestGoingThroughThePeaksKeepsTheScreenStill:
    """Navegar entre picos no reorganiza la pantalla: lo único que cambia es
    cuál está seleccionado, y eso se ve por resalte."""

    @staticmethod
    def _resaltes(dlg):
        return [p for p in dlg._ax.patches
                if not p.get_fill() and p.get_linewidth() == pytest.approx(2.0)]

    def test_the_axes_hold_still_and_the_highlight_moves(self, qapp) -> None:
        dlg = _par()
        x0, y0 = dlg._ax.get_xlim(), dlg._ax.get_ylim()
        assert self._resaltes(dlg) == []
        dlg._siguiente()
        assert dlg._fila_actual == 0
        assert len(self._resaltes(dlg)) == 1
        dlg._siguiente()
        assert dlg._fila_actual == 1
        assert dlg._table.currentRow() == 1
        assert dlg._ax.get_xlim() == x0
        assert dlg._ax.get_ylim() == y0
        dlg._anterior()
        assert dlg._fila_actual == 0
        dlg.deleteLater()

    def test_confirming_is_one_click_and_moves_on(self, qapp) -> None:
        dlg = _par()
        dlg._siguiente()
        assert dlg._btns_nombre["FCR"].isChecked()
        dlg._btns_nombre["ECR"].click()
        assert dlg._row_widgets[0]["label"].currentText() == "ECR"
        assert dlg._fila_actual == 1
        assert dlg._btns_nombre["FCR"].isChecked()
        assert [etiqueta.text() for _c, etiqueta, _s in dlg._contadores][:2] == [
            "FCR: 1 /", "ECR: 1 /",
        ]
        dlg.deleteLater()

    def test_a_row_picked_in_the_table_is_the_one_reviewed(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = _par()
        dlg._table.setCurrentCell(1, 3)
        assert dlg._fila_actual == 1
        assert dlg._lbl_nav.text() == tr("Contraction {i} of {n}").format(i=2, n=2)
        dlg.deleteLater()

    def test_one_muscle_has_no_name_buttons(self, qapp) -> None:
        dlg = _dialogo()
        assert dlg._btns_nombre == {}
        dlg.deleteLater()


class TestADottedCandidateIsOneClickAway:
    """Borrar una marca mal puesta junto a una contracción que el detector no
    marcó dejaba esa contracción sin representar. Sin arrastre: lo que el
    umbral deja fuera se ve punteado, y un clic lo promueve."""

    @staticmethod
    def _debil(**kw):
        # A k = 4,4 la contracción débil queda bajo el umbral; a la mitad, no.
        return _dialogo(_serie(0.008), detection={"k": 4.4}, **kw)

    @staticmethod
    def _punteados(dlg):
        return [p for p in dlg._ax.patches
                if not p.get_fill() and p.get_linestyle() == ":"]

    def test_the_contraction_under_the_line_is_drawn_dotted(self, qapp) -> None:
        dlg = self._debil()
        assert len(dlg.selected_segments()) == 2
        (candidato,) = dlg._candidatos_libres()
        assert 4.2 < candidato.start_s < candidato.end_s < 5.1
        assert len(self._punteados(dlg)) == 1
        dlg.deleteLater()

    def test_a_click_on_it_makes_it_a_row_in_its_place(self, qapp) -> None:
        dlg = self._debil(expected=(3,))
        assert dlg._contadores[0][1].toolTip(), "dos de tres: avisa"
        dlg._clic_en(4.7)
        filas = dlg.selected_segments()
        assert len(filas) == 3
        assert 4.2 < filas[1][0] < 5.1
        assert dlg._candidatos_libres() == []
        assert self._punteados(dlg) == []
        assert dlg._fila_actual == 1, "la promovida queda seleccionada"
        assert dlg._contadores[0][1].toolTip() == "", "tres de tres"
        dlg.deleteLater()

    def test_a_promoted_one_is_edited_like_the_rest(self, qapp) -> None:
        dlg = self._debil()
        dlg._clic_en(4.7)
        dlg._clic_en(4.7)
        assert len(dlg.selected_segments()) == 3, "el segundo clic selecciona"
        assert dlg._fila_actual == 1
        dlg._eliminar()
        assert len(dlg.selected_segments()) == 2
        assert len(dlg._row_widgets) == 3, "descartada, no borrada"
        dlg._clic_en(4.7)
        dlg._mantener()
        assert len(dlg.selected_segments()) == 3
        dlg.deleteLater()

    def test_moving_a_wrong_mark_never_places_one_by_hand(self, qapp) -> None:
        """La marca mal puesta, sobre reposo junto a la contracción débil, se
        retira; la débil se promueve. Nunca hay un marcador en un punto libre."""
        dlg = self._debil(segments=[(2.0, 3.5), (3.6, 4.2), (6.0, 7.5)])
        assert len(dlg._candidatos_libres()) == 1
        dlg._clic_en(3.9)
        dlg._eliminar()
        dlg._clic_en(4.7)
        filas = dlg.selected_segments()
        assert len(filas) == 3
        assert not any(3.6 <= a < 4.2 for a, _b in filas)
        assert any(4.2 < a < 5.1 for a, _b in filas)
        dlg.deleteLater()

    def test_a_click_where_there_is_nothing_does_nothing(self, qapp) -> None:
        dlg = self._debil()
        dlg._clic_en(9.0)
        assert len(dlg._row_widgets) == 2
        dlg.deleteLater()

    def test_the_rise_and_fall_of_a_marked_one_are_not_candidates(
        self, qapp
    ) -> None:
        dlg = _dialogo(detection={"k": 4.4})
        assert dlg._candidatos_libres() == []
        dlg.deleteLater()

    def test_in_the_pair_a_promoted_one_comes_named(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = _dialogo(_serie(0.008), raw_2=_serie(seed=1) * 0.3,
                       name_1="FCR", name_2="ECR", detection={"k": 4.4})
        dlg._clic_en(4.7)
        assert len(dlg._row_widgets) == 3
        nombre = dlg._row_widgets[1]["label"].currentText()
        assert nombre in {"FCR", "ECR", tr("Co-activation")}
        dlg.deleteLater()


def _dos_seguidas():
    """Dos contracciones con medio segundo de reposo entre ellas: la primera
    en el primer canal y la segunda en el segundo."""
    import numpy as np

    rng = np.random.default_rng(3)
    c1 = rng.normal(0.0, 0.01, size=8 * FS)
    c2 = rng.normal(0.0, 0.01, size=8 * FS)
    for canal, (a, b) in ((c1, (2.0, 3.0)), (c2, (3.5, 4.5))):
        i0, i1 = int(a * FS), int(b * FS)
        t = np.arange(i1 - i0) / FS
        canal[i0:i1] += 0.5 * np.sin(2 * np.pi * 90.0 * t)
    return c1, c2


class TestSplitFragment:
    """Una fila que guarda dos contracciones se corta por el valle que se ve
    entre ellas, no por donde caiga la mano."""

    @staticmethod
    def _env(*picos, fs=100, dur=4.0):
        import numpy as np

        t = np.arange(int(dur * fs)) / fs
        env = np.zeros_like(t)
        for centro, alto in picos:
            env += alto * np.exp(-0.5 * ((t - centro) / 0.15) ** 2)
        return env

    def test_two_contractions_are_cut_at_the_valley(self) -> None:
        from emgteach.selection import split_fragment

        env = self._env((1.5, 1.0), (2.5, 0.8))
        (a0, a1), (b0, b1) = split_fragment([env], [0.0], 100, 0.5, 3.5)
        assert (a0, b1) == (0.5, 3.5), "los extremos no se mueven"
        assert 1.5 < a1 < b0 < 2.5, "cada mitad, recortada a su esfuerzo"

    def test_a_single_contraction_is_not_cut(self) -> None:
        from emgteach.selection import split_fragment

        assert split_fragment([self._env((2.0, 1.0))], [0.0], 100, 0.5, 3.5) is None

    def test_a_tail_is_not_a_second_contraction(self) -> None:
        from emgteach.selection import split_fragment

        cola = self._env((1.5, 1.0), (2.4, 0.3))
        assert split_fragment([cola], [0.0], 100, 0.5, 3.5) is None

    def test_a_shallow_valley_is_one_contraction(self) -> None:
        from emgteach.selection import split_fragment

        meseta = self._env((1.6, 1.0), (2.05, 0.9))
        assert split_fragment([meseta], [0.0], 100, 0.5, 3.5) is None

    def test_either_muscle_can_lead_either_half(self) -> None:
        from emgteach.selection import split_fragment

        uno, otro = self._env((1.5, 1.0)), self._env((2.5, 3.0))
        assert split_fragment([uno, otro], [0.0, 0.0], 100, 0.5, 3.5) is not None


class TestEditingOneContraction:
    """Un clic sobre una contracción la selecciona, como ◀ ▶, y tres botones
    deciden: mantenerla, eliminarla o dividirla."""

    def test_a_click_selects_and_drops_nothing(self, qapp) -> None:
        dlg = _dialogo()
        dlg._clic_en(2.5)
        assert dlg._fila_actual == 0
        assert len(dlg.selected_segments()) == 2
        assert dlg._btn_mantener.isChecked()
        assert not dlg._btn_eliminar.isChecked()
        dlg.deleteLater()

    def test_keep_and_drop_decide_and_move_on(self, qapp) -> None:
        dlg = _dialogo()
        dlg._clic_en(2.5)
        dlg._eliminar()
        assert not dlg._row_widgets[0]["keep"].isChecked()
        assert dlg._fila_actual == 1
        dlg._anterior()
        assert dlg._btn_eliminar.isChecked()
        dlg._mantener()
        assert dlg._row_widgets[0]["keep"].isChecked()
        assert dlg._fila_actual == 1
        dlg.deleteLater()

    def test_with_nothing_under_review_there_is_nothing_to_decide(
        self, qapp
    ) -> None:
        dlg = _dialogo()
        assert not dlg._btn_mantener.isEnabled()
        assert not dlg._btn_eliminar.isEnabled()
        assert not dlg._btn_dividir.isEnabled()
        dlg._eliminar()
        assert len(dlg.selected_segments()) == 2
        dlg.deleteLater()

    def test_a_row_holding_two_contractions_splits_in_two(self, qapp) -> None:
        c1, c2 = _dos_seguidas()
        dlg = _dialogo(c1, raw_2=c2, name_1="FCR", name_2="ECR",
                       segments=[(1.8, 4.7)], labels=["FCR"])
        dlg._clic_en(3.0)
        assert dlg._btn_dividir.isEnabled()
        dlg._dividir()
        filas = dlg.selected_segments()
        assert len(filas) == 2, "dos filas, que no se vuelven a unir"
        (a0, a1), (b0, b1) = filas
        assert a0 == pytest.approx(1.8)
        assert b1 == pytest.approx(4.7)
        assert 2.9 < a1 < b0 < 3.6
        assert [w["label"].currentText() for w in dlg._row_widgets] == ["FCR", "ECR"]
        assert dlg._fila_actual == 0
        dlg.deleteLater()

    def test_a_single_contraction_offers_no_split(self, qapp) -> None:
        dlg = _dialogo()
        dlg._clic_en(2.5)
        assert not dlg._btn_dividir.isEnabled()
        dlg._dividir()
        assert len(dlg._row_widgets) == 2
        dlg.deleteLater()

    def test_the_cut_is_drawn_before_it_is_made(self, qapp) -> None:
        c1, c2 = _dos_seguidas()
        dlg = _dialogo(c1, raw_2=c2, name_1="FCR", name_2="ECR",
                       segments=[(1.8, 4.7)])
        punteada = [ln for ln in dlg._ax.get_lines() if ln.get_linestyle() == "-."]
        assert punteada == []
        dlg._clic_en(3.0)
        cortes = [ln for ln in dlg._ax.get_lines() if ln.get_linestyle() == "-."]
        assert len(cortes) == 1
        assert 3.0 < cortes[0].get_xdata()[0] < 3.5
        dlg.deleteLater()


class TestTheSplitSurvivesTheTable:
    def test_pieces_a_sample_apart_are_not_joined_again(
        self, qapp, monkeypatch
    ) -> None:
        """La tabla guarda centésimas: dos mitades a una muestra de distancia
        se redondeaban a la misma y el análisis las volvía a unir."""
        dlg = _dialogo(segments=[(1.8, 4.3)])
        dlg._ir_a(0)
        monkeypatch.setattr(dlg, "_corte", lambda _i: ((1.8, 3.1234), (3.1244, 4.3)))
        dlg._dividir()
        filas = dlg.selected_segments()
        assert len(filas) == 2
        assert filas[0][1] < filas[1][0]
        dlg.deleteLater()


def _raton(dlg, x):
    """Lo que matplotlib entrega en un evento de ratón sobre el gráfico."""
    from types import SimpleNamespace

    return SimpleNamespace(inaxes=dlg._ax, xdata=x, button=1)


def _arrastrar(dlg, desde, hasta, pasos=5):
    dlg._on_click(_raton(dlg, desde))
    for j in range(1, pasos + 1):
        dlg._on_motion(_raton(dlg, desde + (hasta - desde) * j / pasos))
    dlg._on_release(_raton(dlg, hasta))


class TestDraggingAMark:
    """La marca se puede desplazar arrastrándola, y al soltarla encaja en la
    actividad sobre la que cae: nunca en un punto libre."""

    @staticmethod
    def _con_marca_mal_puesta():
        # Una marca sobre reposo (3,6 a 4,2 s), junto a una contracción débil
        # (4,3 a 5,0 s) que el umbral dejó fuera.
        return _dialogo(_serie(0.008), detection={"k": 4.4},
                        segments=[(2.0, 3.5), (3.6, 4.2), (6.0, 7.5)])

    def test_dropped_on_the_missed_contraction_it_takes_its_bounds(
        self, qapp
    ) -> None:
        dlg = self._con_marca_mal_puesta()
        (candidata,) = dlg._candidatos_libres()
        _arrastrar(dlg, 3.9, 4.6)
        filas = dlg.selected_segments()
        assert len(filas) == 3
        a, b = filas[1]
        assert a == pytest.approx(candidata.start_s, abs=0.011)
        assert b == pytest.approx(candidata.end_s, abs=0.011)
        assert dlg._fila_actual == 1
        assert dlg._candidatos_libres() == []
        dlg.deleteLater()

    def test_dropped_over_rest_it_goes_back(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = self._con_marca_mal_puesta()
        antes = dlg.selected_segments()
        _arrastrar(dlg, 6.5, 9.2)
        assert dlg.selected_segments() == antes
        assert dlg._lbl_nav.text() == tr(
            "There is no activity there: the mark stays where it was."
        )
        dlg.deleteLater()

    def test_barely_moved_it_stays_as_it_was(self, qapp) -> None:
        dlg = self._con_marca_mal_puesta()
        antes = dlg.selected_segments()
        _arrastrar(dlg, 6.5, 6.9)
        assert dlg.selected_segments() == antes
        dlg.deleteLater()

    def test_a_trembling_click_is_still_a_click(self, qapp) -> None:
        dlg = self._con_marca_mal_puesta()
        antes = dlg.selected_segments()
        _arrastrar(dlg, 2.5, 2.52)
        assert dlg.selected_segments() == antes
        assert dlg._fila_actual == 0
        dlg.deleteLater()

    def test_while_dragging_the_landing_is_drawn(self, qapp) -> None:
        dlg = self._con_marca_mal_puesta()
        dlg._on_click(_raton(dlg, 3.9))
        dlg._on_motion(_raton(dlg, 4.6))
        destinos = [p for p in dlg._ax.patches
                    if not p.get_fill() and p.get_linewidth() == pytest.approx(2.5)]
        assert len(destinos) == 1
        dlg._on_release(_raton(dlg, 4.6))
        dlg.deleteLater()

    def test_a_moved_mark_in_the_pair_is_named_again(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = _dialogo(_serie(0.008), raw_2=_serie(seed=1) * 0.3,
                       name_1="FCR", name_2="ECR", detection={"k": 4.4},
                       segments=[(2.0, 3.5), (3.6, 4.2), (6.0, 7.5)],
                       labels=["FCR", "ECR", "FCR"])
        _arrastrar(dlg, 3.9, 4.6)
        assert len(dlg.selected_segments()) == 3
        nombre = dlg._row_widgets[1]["label"].currentText()
        assert nombre in {"FCR", "ECR", tr("Co-activation")}
        dlg.deleteLater()


class TestTheCalibrationHelpDescribesTheProtocolTheCodeRuns:
    """El texto de ayuda de la calibración siguió contando tres esfuerzos
    mantenidos y tres breves, seis en total, cuando el asistente ya pedía tres
    breves. Se ha desfasado dos veces; esta prueba lo vigila."""

    @pytest.mark.parametrize("idioma", ["en", "es"])
    def test_it_gives_the_numbers_the_wizard_uses(self, idioma) -> None:
        from emgteach.gui.help_texts import text
        from emgteach.gui.tabs.acquisition import MVC_READY_S, MVC_REST_S
        from emgteach.i18n import get_language, set_language
        from emgteach.profiles import EMG_PROFILE

        anterior = get_language()
        try:
            set_language(idioma)
            _titulo, cuerpo = text("acq.load")
        finally:
            set_language(anterior)
        p = EMG_PROFILE
        for x in (p.warmup_s, p.mvc_burst_s, MVC_READY_S, MVC_REST_S,
                  p.mvc_peak_window_s):
            cifra = f"{x:g}"
            if idioma == "es":
                cifra = cifra.replace(".", ",")
            assert f"{cifra} s" in cuerpo, cifra
        assert f" {p.mvc_bursts} " in cuerpo
        for viejo in ("six", "sustained", "squeez", "held",
                      "seis", "mantenid", "sacudid"):
            assert viejo not in cuerpo.lower(), viejo

    def test_no_help_text_counts_six_maximal_efforts(self) -> None:
        from emgteach.gui.help_texts import keys, text

        for clave in keys():
            _titulo, cuerpo = text(clave)
            c = cuerpo.lower()
            assert "six maximal" not in c, clave
            assert "sustained maximal" not in c, clave


def _prefijo_paso(k):
    from emgteach.i18n import tr

    return tr("<b>Step {k} of 3</b> · {text}").format(k=k, text="")


class TestTheEditorSaysWhichStepThisIs:
    """Para que nadie se pierda: una línea encima del gráfico dice en qué paso
    se está y qué pide, y el botón que lo aplica se pone en negrita al final."""

    def test_it_opens_on_step_one_with_what_the_count_is_missing(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = _par(expected=(6, 6, 1))
        guia = dlg._lbl_guia.text()
        assert guia.startswith(_prefijo_paso(1))
        assert tr("{name} {n} of {m}").format(name="FCR", n=2, m=6) in guia
        dlg.deleteLater()

    def test_going_through_them_is_step_two_and_the_end_is_step_three(
        self, qapp
    ) -> None:
        dlg = _dialogo(expected=(2,))
        assert dlg._lbl_guia.text().startswith(_prefijo_paso(1))
        dlg._siguiente()
        assert dlg._lbl_guia.text().startswith(_prefijo_paso(2))
        assert "1" in dlg._lbl_guia.text()
        assert dlg._btn_ok.styleSheet() == ""
        dlg._siguiente()
        assert dlg._lbl_guia.text().startswith(_prefijo_paso(3))
        assert "bold" in dlg._btn_ok.styleSheet()
        dlg.deleteLater()

    def test_everything_reviewed_but_the_count_off_stays_on_step_two(
        self, qapp
    ) -> None:
        dlg = _dialogo(expected=(3,))
        dlg._siguiente()
        dlg._siguiente()
        assert dlg._lbl_guia.text().startswith(_prefijo_paso(2))
        dlg.deleteLater()

    def test_without_a_target_the_end_just_asks_to_apply(self, qapp) -> None:
        from emgteach.i18n import tr

        dlg = _dialogo()
        dlg._siguiente()
        dlg._siguiente()
        assert dlg._lbl_guia.text().endswith(
            tr("Everything reviewed: press «Use these fragments».")
        )
        dlg.deleteLater()

    def test_the_second_half_of_a_split_is_left_to_review(self, qapp) -> None:
        c1, c2 = _dos_seguidas()
        dlg = _dialogo(c1, raw_2=c2, name_1="FCR", name_2="ECR",
                       segments=[(1.8, 4.7)])
        dlg._clic_en(3.0)
        assert dlg._lbl_guia.text().startswith(_prefijo_paso(3))
        dlg._dividir()
        assert dlg._lbl_guia.text().startswith(_prefijo_paso(2))
        dlg.deleteLater()

    def test_a_row_at_the_start_of_the_stretch_is_pointed_out(self, qapp) -> None:
        from emgteach.i18n import tr

        aviso = tr(
            "This one starts right where the analysed stretch does: it may "
            "be the end of an earlier effort, such as the last maximal one."
        )
        dlg = _dialogo(span=(2.2, 9.0))
        dlg._ir_a(0)
        assert aviso in dlg._lbl_guia.text()
        dlg._ir_a(1)
        assert aviso not in dlg._lbl_guia.text()
        dlg.deleteLater()

    def test_the_editor_has_its_own_help(self, qapp) -> None:
        from emgteach.gui.widgets.help_button import help_buttons

        dlg = _dialogo()
        assert "help:ana.fragments" in {b.objectName() for b in help_buttons(dlg)}
        dlg.deleteLater()

    def test_in_spanish_it_speaks_spanish(self, qapp) -> None:
        from emgteach.i18n import get_language, set_language

        anterior = get_language()
        try:
            set_language("es")
            dlg = _dialogo()
            assert dlg._lbl_guia.text().startswith("<b>Paso 1 de 3</b>")
            assert dlg._btn_mantener.text() == "Mantener"
            dlg.deleteLater()
        finally:
            set_language(anterior)


class TestRowsThatTouchStayApart:
    def test_touching_proposals_are_kept_as_two_fragments(self) -> None:
        from emgteach.gui.widgets.fragment_selection import _en_centesimas
        from emgteach.selection import Segment, normalise_segments

        filas = _en_centesimas([Segment(1.0, 2.0005), Segment(2.0, 3.0)])
        assert len(filas) == 2
        assert filas[1].start_s > filas[0].end_s
        assert len(normalise_segments(filas, 10.0)) == 2

    def test_the_editor_shows_as_many_rows_as_the_analysis_gets(self, qapp) -> None:
        dlg = _dialogo()
        assert len(dlg._row_widgets) == len(dlg.selected_segments())
        dlg.deleteLater()


class TestKinematicsCountsTheLifts:
    """En cinemática lo esperado es un levantamiento por marca de carga del
    asistente: es el registro de lo que se pidió."""

    def test_one_contraction_expected_per_marked_lift(
        self, main_window, tmp_path
    ) -> None:
        from emgteach.fv_rehearsal import synthetic_trial, write_rehearsal_edf
        from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE

        ruta = tmp_path / "fv.edf"
        write_rehearsal_edf(synthetic_trial([2.0, 4.0], reps=2), ruta)
        ana = main_window._tab_ana
        anterior = ana._mode
        try:
            ana._mode = MODE_KINEMATICS
            assert ana._esperadas_de_la_sesion(str(ruta)) == (4,)
            ana._mode = MODE_PAIR
            assert ana._esperadas_de_la_sesion(str(ruta)) == (6, 6, 1)
            ana._mode = MODE_SINGLE
            assert ana._esperadas_de_la_sesion(str(ruta)) == ()
        finally:
            ana._mode = anterior

    def test_a_new_recording_forgets_the_previous_targets(self, main_window) -> None:
        ana = main_window._tab_ana
        ana._esperadas = (9,)
        ana._olvidar_lo_elegido()
        assert ana._esperadas is None


class TestTheTourShowsWhatToDo:
    """Tres de las cinco alumnas pidieron imágenes de qué hacer en cada
    momento: dónde van los electrodos y qué hacer cuando aparece FCR o ECR."""

    def test_both_pictures_exist_in_both_languages(self) -> None:
        from PySide6.QtGui import QImage

        import emgteach.gui.tour as tour

        for nombre in ("electrodos", "calibracion"):
            for idioma in ("es", "en"):
                ruta = tour._IMAGENES / f"{nombre}_{idioma}.png"
                assert ruta.is_file(), ruta
                assert QImage(str(ruta)).width() >= 800, ruta

    def test_the_picture_follows_the_language(self) -> None:
        from emgteach.gui.tour import imagen
        from emgteach.i18n import get_language, set_language

        anterior = get_language()
        try:
            set_language("es")
            assert imagen("electrodos").endswith("electrodos_es.png")
            set_language("en")
            assert imagen("electrodos").endswith("electrodos_en.png")
        finally:
            set_language(anterior)
        assert imagen("no_existe") is None

    def test_the_pair_tour_carries_them_and_the_others_do_not(
        self, main_window, monkeypatch
    ) -> None:
        from emgteach.gui.tour import build_tour
        from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE

        monkeypatch.setattr(main_window, "_mode", lambda: MODE_PAIR)
        rutas = [s.image_path() for s in build_tour(main_window)]
        assert [r is not None for r in rutas].count(True) == 2
        assert any("electrodos" in r for r in rutas if r)
        assert any("calibracion" in r for r in rutas if r)
        for modo in (MODE_SINGLE, MODE_KINEMATICS):
            monkeypatch.setattr(main_window, "_mode", lambda m=modo: m)
            assert all(s.image_path() is None for s in build_tour(main_window))

    def test_the_panel_shows_the_picture_and_widens_for_it(self, main_window) -> None:
        from emgteach.gui.tour import imagen
        from emgteach.gui.widgets.coach import CoachMark, CoachStep

        marca = CoachMark(main_window)
        marca.start([CoachStep("t", "b", image=lambda: imagen("electrodos"))])
        assert not marca._lbl_img.isHidden()
        assert marca._panel.width() > 430
        assert marca._panel.height() > marca._lbl_img.height()
        assert marca._lbl_img.height() <= main_window.height() * 0.5 + 1
        marca.stop()
        marca.start([CoachStep("t", "b")])
        assert marca._lbl_img.isHidden()
        assert marca._panel.width() == 430
        marca.stop()
        marca.deleteLater()

    def test_the_build_carries_them(self) -> None:
        raiz = Path(__file__).resolve().parents[1]
        spec = (raiz / "packaging" / "emgteach.spec").read_text(encoding="utf-8")
        assert '"gui", "assets", "recorrido"' in spec
        prueba = (raiz / "packaging" / "run_emgteach.py").read_text(encoding="utf-8")
        assert "tour picture missing" in prueba


def _luminancia(color: str) -> float:
    canales = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
               for c in canales)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a: str, b: str) -> float:
    claro, oscuro = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


class TestTheEditorButtonsReadInAnyStyle:
    """En Windows un botón pulsado se pinta con el azul del sistema, y el
    color del músculo encima como texto —rojo sobre azul— no se leía."""

    def test_every_pressed_state_is_drawn_with_enough_contrast(self, qapp) -> None:
        import re

        dlg = _par()
        for b in (dlg._btn_mantener, dlg._btn_eliminar, *dlg._btns_nombre.values()):
            m = re.search(
                r"QPushButton:checked \{ background: (#[0-9A-Fa-f]{6}); "
                r"color: (#[0-9A-Fa-f]{6});",
                b.styleSheet(),
            )
            assert m, b.text()
            assert _contraste(m.group(1), m.group(2)) >= 4.5, b.text()
        dlg.deleteLater()

    def test_the_rest_of_the_bar_shares_the_look(self, qapp) -> None:
        dlg = _par()
        for b in (dlg._btn_prev, dlg._btn_next, dlg._btn_dividir):
            assert "QPushButton {" in b.styleSheet()
        dlg.deleteLater()


class TestTheCredits:
    @pytest.mark.parametrize("idioma, texto", [
        ("en", "Department of Physiology. Faculty of Pharmacy. UCM"),
        ("es", "Departamento de Fisiología. Facultad de Farmacia. UCM"),
    ])
    def test_the_about_box_names_the_department_and_the_faculty(
        self, main_window, monkeypatch, idioma, texto
    ) -> None:
        import emgteach.gui.app as app_mod
        from emgteach.i18n import get_language, set_language

        visto: dict[str, str] = {}

        class _Caja:
            @staticmethod
            def about(_padre, _titulo, cuerpo):
                visto["cuerpo"] = cuerpo

        monkeypatch.setattr(app_mod, "QMessageBox", _Caja)
        anterior = get_language()
        try:
            set_language(idioma)
            main_window._show_about()
        finally:
            set_language(anterior)
        assert texto in visto["cuerpo"]
