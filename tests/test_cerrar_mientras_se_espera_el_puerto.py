"""Closing the window while «Retry» waits for the port starts nothing.

«Retry» after the board did not answer wires the end of the thread that still
holds the port (Windows' opening of a Bluetooth port can take most of a
minute) to the start of the recording asked for. If the window was closed in
the meantime and Windows let the port go during the five seconds closeEvent
waits for that thread, the start came after the window had gone: a «Save as»
dialog nobody asked for, and a recording on a tab that no longer exists.
Found with a MainWindow under app.exec() on 22 October 2026; cleanup now
disarms that start first.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.test_la_placa_que_no_responde import _esperar, _grabar, pestana_que_tarda  # noqa: F401


def _pump(seconds: float) -> None:
    app = QApplication.instance()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


@pytest.mark.gui
@pytest.mark.parametrize("when", ["during_the_wait", "after_the_close"])
def test_closing_while_retry_waits_for_the_port_starts_no_recording(
    qapp, request, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, when: str
) -> None:
    from emgteach.gui.tabs import acquisition as acq_mod

    tab = request.getfixturevalue("pestana_que_tarda")
    dialogs: list[float] = []

    def save_as(*args, **kwargs):
        dialogs.append(time.monotonic())
        return str(tmp_path / "a.edf"), ""

    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName", staticmethod(save_as))
    _grabar(tab)
    _esperar(lambda: tab._aviso_conexion is not None, "the warning that the board did not answer")
    tab._tras_aviso_conexion(QMessageBox.StandardButton.Retry)
    assert tab._esperando_puerto, "the retry is not waiting for the port"
    old = tab._worker
    before = len(dialogs)

    if when == "during_the_wait":
        tab.primera.soltar.set()          # Windows lets go just as the window closes
        time.sleep(0.3)
    tab.cleanup()                         # what MainWindow.closeEvent does
    if when == "after_the_close":
        tab.primera.soltar.set()          # Windows lets go once the window is gone
    _pump(1.0)                            # the events the loop still delivers

    assert len(dialogs) == before, "a «Save as» dialog came after the window closed"
    assert tab._worker is old, "a recording started after the window closed"
    assert not tab._esperando_puerto
    assert not old.isRunning(), "the thread that held the port did not end"
