"""Cuando algo se rompe, tiene que quedar constancia.

Hasta ahora no quedaba. Una excepción no capturada en una ranura de Qt se
imprime en una consola que la versión empaquetada no tiene, así que un fallo
en el banco dejaba al operador sin nada que contar salvo que había pasado, y a
nadie en condiciones de averiguar por qué. Ocurrió el 1 de septiembre y no hubo
manera de investigarlo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from emgteach import crash


@pytest.fixture
def registro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    destino = tmp_path / "emgteach-errores.log"
    monkeypatch.setattr(crash, "log_path", lambda: destino)
    return destino


def _falla() -> tuple:
    try:
        raise ValueError("el músculo no cabe en el canal")
    except ValueError:
        return sys.exc_info()


class TestTheTracebackSurvives:
    def test_it_is_written_to_the_file(self, registro: Path) -> None:
        devuelto = crash.record_exception(*_falla())
        assert devuelto == registro
        texto = registro.read_text(encoding="utf-8")
        assert "ValueError" in texto
        assert "el músculo no cabe en el canal" in texto
        # And the line of the code that raised, which is the point of it.
        assert "_falla" in texto

    def test_a_second_crash_does_not_erase_the_first(
        self, registro: Path
    ) -> None:
        """A fault that shows up once every few sessions is the one worth
        keeping, so the file accumulates instead of being replaced."""
        crash.record_exception(*_falla())
        crash.record_exception(*_falla())
        # Counted on the final line of each traceback: the word «ValueError»
        # itself appears twice per entry, once in the source line that raised.
        texto = registro.read_text(encoding="utf-8")
        assert texto.count("ValueError: el músculo") == 2

    def test_it_says_when_and_with_which_version(self, registro: Path) -> None:
        from emgteach import __version__

        crash.record_exception(*_falla())
        texto = registro.read_text(encoding="utf-8")
        assert __version__ in texto
        assert "20" in texto  # the date stamp

    def test_a_log_that_cannot_be_written_is_not_a_second_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A read-only home or a full disk must not turn a reportable error
        into an unreportable one."""
        monkeypatch.setattr(
            crash, "log_path", lambda: tmp_path / "no-existe" / "x.log"
        )
        assert crash.record_exception(*_falla()) is None


class TestAWarningIsNotACrash:
    """The crash dialogue that came out of a Qt *warning*.

    Qt's messages are routed through a handler of ours, which wrote them to
    stderr. The windowed build has no console and PyInstaller leaves stderr
    set to None there, so the write raised AttributeError inside the handler
    — and the operator was shown «the application hit an error it did not
    expect» while the thing being reported was a warning nobody needed to
    see. It happened twice on the bench of 5 September, both times at the
    end of a recording.
    """

    def test_a_message_with_no_console_does_not_raise(
        self, registro: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from emgteach.gui import app as gui

        monkeypatch.setattr(sys, "stderr", None)
        monkeypatch.setattr(gui, "_qt_message_to_log", lambda m: None)
        gui.qt_message(None, None, "QWindowsWindow::setGeometry: no cabe")

    def test_with_no_console_it_is_kept_in_the_log(
        self, registro: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silently dropping it would throw away the one diagnostic that
        says why the window would not fit."""
        from emgteach.gui import app as gui

        monkeypatch.setattr(sys, "stderr", None)
        gui.qt_message(None, None, "QWindowsWindow::setGeometry: no cabe")
        assert "setGeometry" in registro.read_text(encoding="utf-8")

    def test_with_a_console_it_still_goes_to_stderr(
        self, registro: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import io

        from emgteach.gui import app as gui

        falso = io.StringIO()
        monkeypatch.setattr(sys, "stderr", falso)
        gui.qt_message(None, None, "algo que decir")
        assert "algo que decir" in falso.getvalue()
        assert not registro.exists()

    def test_the_noisy_font_warning_is_still_dropped(
        self, registro: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import io

        from emgteach.gui import app as gui

        falso = io.StringIO()
        monkeypatch.setattr(sys, "stderr", falso)
        gui.qt_message(None, None, "QFont::setPointSize: Point size <= 0 (-1)")
        assert falso.getvalue() == ""

    def test_a_log_that_cannot_be_written_is_not_a_crash_either(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from emgteach.gui import app as gui

        monkeypatch.setattr(
            crash, "log_path", lambda: tmp_path / "no-existe" / "x.log"
        )
        monkeypatch.setattr(sys, "stderr", None)
        gui.qt_message(None, None, "y ahora tampoco hay disco")


class TestTheHookIsInstalled:
    def test_it_chains_to_whatever_was_there(
        self, registro: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        llamado: list[str] = []
        monkeypatch.setattr(
            sys, "excepthook", lambda *a: llamado.append("anterior")
        )
        crash.install_crash_log()
        sys.excepthook(*_falla())
        assert llamado == ["anterior"]
        assert "ValueError" in registro.read_text(encoding="utf-8")

    def test_ctrl_c_is_left_alone(
        self, registro: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Interrupting from the console is not a crash and must not be
        reported as one."""
        monkeypatch.setattr(sys, "excepthook", lambda *a: None)
        crash.install_crash_log()
        sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        assert not registro.exists()


@pytest.mark.gui
class TestASecondRunNeverStartsOverTheFirst:
    """The crash that a crash log cannot catch.

    Both tabs reassign ``self._worker`` when they launch. If the previous
    QThread were still running, dropping the last reference to it destroys a
    live thread, and that kills the process from the C++ side: no traceback, no
    log, the window simply goes away. The Analyse button is disabled while a
    run is in flight, so this only became reachable when the fragment and
    repetition dialogues started re-analysing on accept.
    """

    def test_the_analysis_tab_refuses(self, qapp) -> None:
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.analysis import AnalysisTab
        from emgteach.gui.widgets.logger import LoggerWidget

        tab = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "crash"))

        class Ocupado:
            def isRunning(self) -> bool:
                return True

        tab._worker = ocupado = Ocupado()
        tab._iniciar_analisis()
        # The worker is untouched: no new one was built over it.
        assert tab._worker is ocupado
        tab.deleteLater()

    def test_the_mvc_tab_refuses(self, qapp) -> None:
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.mvc import MvcTab
        from emgteach.gui.widgets.logger import LoggerWidget

        tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "crash2"))

        class Ocupado:
            def isRunning(self) -> bool:
                return True

        tab._worker = ocupado = Ocupado()
        tab._iniciar_calculo()
        assert tab._worker is ocupado
        tab.deleteLater()


@pytest.mark.gui
class TestTheWarningNeverBlocksAnything:
    """A modal warning waits for a click, and the one thing you cannot count
    on while reporting a crash is somebody there to click it.

    The first version of this file used ``exec()``. It hung the test suite:
    an earlier test had left a window on screen, so the box came up, and
    nothing could close it. The same would have happened on the build server
    and in any script that drives the application. So the box is modeless — and
    this is the test that says so, because the failure it prevents does not
    look like a failure, it looks like the program stopping.
    """

    def test_it_returns_even_with_a_window_on_screen(self, qapp) -> None:
        from PySide6.QtWidgets import QWidget

        w = QWidget()
        w.show()
        qapp.processEvents()
        try:
            assert crash._hay_alguien_delante() is True
            # The point of the test: this call returns. With exec() it would
            # not, and the suite would stop here rather than fail.
            crash._avisar(ValueError("x"), None)
            qapp.processEvents()
        finally:
            for caja in list(crash._abiertas):
                caja.close()
            crash._abiertas.clear()
            w.close()
            w.deleteLater()
            qapp.processEvents()

    def test_with_nothing_on_screen_it_says_nothing(
        self, qapp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asked directly rather than by looking at the screen: run inside the
        whole suite, some earlier test still has a window up, and a test whose
        result depends on that is measuring the suite, not the code."""
        monkeypatch.setattr(crash, "_hay_alguien_delante", lambda: False)
        crash._avisar(ValueError("x"), None)
        assert crash._abiertas == []

    def test_the_hook_still_logs_when_it_cannot_warn(
        self, registro: Path, qapp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silence on screen must not mean silence on disk."""
        monkeypatch.setattr(sys, "excepthook", lambda *a: None)
        crash.install_crash_log()
        sys.excepthook(*_falla())
        assert "ValueError" in registro.read_text(encoding="utf-8")
