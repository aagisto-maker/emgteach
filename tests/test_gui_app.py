"""GUI test for the main window itself.

Marked ``gui`` (needs a QApplication). Constructing :class:`MainWindow`
exercises the whole start-up wiring — every tab, the shared logger and the
shared :class:`~emgteach.broadcast.BroadcastServer` — which the import-only
smoke tests cannot catch (e.g. passing the window positionally into
``BroadcastServer(http_port=...)`` crashed on launch but imported fine).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_main_window_constructs(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.broadcast import DEFAULT_HTTP_PORT, DEFAULT_WS_PORT
    from emgteach.gui.app import MainWindow

    settings = QSettings("emgteach-test", "main-window")
    settings.clear()
    win = MainWindow(settings)
    try:
        # The shared broadcast server got the default ports, not a widget.
        assert win._broadcast._http_port == DEFAULT_HTTP_PORT
        assert win._broadcast._ws_port == DEFAULT_WS_PORT
        assert win._broadcast.parent() is win
        # All three tabs share the one broadcast instance.
        assert win._tab_adq._broadcast is win._broadcast
        assert win._tab_ana._broadcast is win._broadcast
    finally:
        settings.clear()
        qapp.processEvents()   # flush deferred canvas draws before teardown
        win.close()


# ---------------------------------------------------------------------------
# The settings the tests themselves stand on
# ---------------------------------------------------------------------------


class TestTheSuiteSettingsAreItsOwn:
    """The store a GUI test writes must still be there when it reads it.

    This is what made one random GUI test fail per full run — a different one
    each time, all of them passing alone. The tests address their settings by
    organisation and application name, which on Windows means the registry,
    and every fixture clears the key and immediately writes into it.
    ``clear()`` deletes the registry key; Windows defers deleting a key that
    still has an open handle, and a window with three tabs always has one. The
    delete arrived late and took the following writes with it, leaving the
    store empty. The window then read no mode, fell back to ``single``, and a
    test that had laid it out for ``pair`` was checking the wrong practical.

    Measured before the fix: 19 of 25 window-build cycles lost the value
    through the registry, 0 of 25 through an INI file.
    """

    def test_the_suite_does_not_write_to_the_native_store(self) -> None:
        """An INI file, not the registry — and not the developer's real one."""
        from PySide6.QtCore import QSettings

        assert QSettings.defaultFormat() == QSettings.Format.IniFormat

    def test_a_written_setting_survives_building_a_window(self, qapp) -> None:
        """The exact sequence every GUI fixture performs, asserted."""
        from PySide6.QtCore import QSettings

        from emgteach.gui.app import MainWindow
        from emgteach.modes import MODE_PAIR

        settings = QSettings("emgteach-test", "settings-survival")
        settings.clear()
        settings.setValue("adquisicion/port", "COM5")
        settings.setValue("app/mode", MODE_PAIR)
        win = MainWindow(settings)
        try:
            win.resize(1400, 900)
            win.show()
            qapp.processEvents()
            assert settings.value("adquisicion/port") == "COM5"
            assert settings.value("app/mode") == MODE_PAIR
            # And the window agrees about which practical it is.
            assert win._mode() == MODE_PAIR
        finally:
            settings.clear()
            qapp.processEvents()
            win.close()
            win.deleteLater()
            qapp.processEvents()


class TestTheScreenshotButton:
    """«Una captura sin desviar la atención».

    Del banco: para llevar una figura al cuaderno había que usar la
    herramienta de recortes del sistema, que roba el foco y abre un diálogo
    preguntando dónde guardar, y las dos cosas pasan mientras alguien
    sostiene una contracción. De ahí que esto no pregunte nada.
    """

    @pytest.fixture
    def ventana(self, qapp, tmp_path):
        from PySide6.QtCore import QSettings

        from emgteach.gui.app import MainWindow

        s = QSettings("emgteach-test", "captura")
        s.clear()
        s.setValue("adquisicion/save_dir", str(tmp_path))
        s.setValue("app/tour_offer", False)
        win = MainWindow(s)
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()
        try:
            yield win
        finally:
            s.clear()
            win.close()
            win.deleteLater()
            qapp.processEvents()

    def test_it_is_one_key_from_anywhere(self, ventana) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeySequence

        atajo = ventana._atajo_captura
        assert atajo.key() == QKeySequence("F12")
        # De ventana, no del control que tenga el foco: durante una maniobra
        # el ratón está en otro sitio.
        assert atajo.context() == Qt.ShortcutContext.WindowShortcut

    def test_it_saves_a_picture_without_asking(self, ventana, tmp_path) -> None:
        ventana._guardar_captura()
        hechas = list(tmp_path.glob("*.png"))
        assert len(hechas) == 1
        assert hechas[0].stat().st_size > 0
        assert hechas[0].name.startswith("emgteach_captura_")

    def test_a_burst_does_not_overwrite_itself(self, ventana, tmp_path) -> None:
        """Tres capturas en el mismo segundo son tres archivos."""
        for _ in range(3):
            ventana._guardar_captura()
        assert len(list(tmp_path.glob("*.png"))) == 3

    def test_it_goes_where_the_recordings_go(self, ventana, tmp_path) -> None:
        """Y lo que manda es la casilla, no el ajuste guardado: el operador
        puede acabar de escribir una carpeta y no haber grabado todavía."""
        otra = tmp_path / "otra"
        otra.mkdir()
        ventana._tab_adq._edit_dir.setText(str(otra))
        assert ventana._carpeta_de_capturas() == otra
        ventana._guardar_captura()
        assert len(list(otra.glob("*.png"))) == 1
        assert not list(tmp_path.glob("*.png"))

    def test_it_says_so_in_every_log(self, ventana) -> None:
        """El registro compartido se ve en Análisis; cada pestaña tiene el
        suyo. La confirmación tiene que leerse desde donde se esté."""
        ventana._guardar_captura()
        for registro in (ventana._logger,
                         ventana._tab_adq._local_log,
                         ventana._tab_cvm._local_log):
            assert "emgteach_captura_" in registro.toPlainText()

    def test_a_folder_it_cannot_write_is_reported_not_raised(
        self, ventana, monkeypatch
    ) -> None:
        from pathlib import Path

        def revienta(*_a, **_k):
            raise OSError("disco lleno")

        monkeypatch.setattr(Path, "mkdir", revienta)
        ventana._guardar_captura()          # no levanta
        # El motivo, en el registro, en el idioma que toque.
        assert "disco lleno" in ventana._logger.toPlainText()
