"""What a recording leaves behind: its event log, and a bounded number of pictures.

The log on screen died with the application, so a session that went wrong
without an exception left nothing to send; it is now saved beside the EDF
when the recording ends, well or badly. And the automatic screenshots, one
every three seconds, had no limit at all.

The recordings are driven end to end with the BITalino in software
(`simulada`): real worker, real thread, real EDF.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from emgteach import __version__
from emgteach.gui.tabs.acquisition import EVENTS_SUFFIX, AcquisitionTab, events_path
from emgteach.i18n import tr

pytestmark = pytest.mark.gui


def _pump(app: QApplication, ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def _until(app: QApplication, condition, timeout_s: float, what: str) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {what}")


@pytest.fixture
def tab(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An acquisition tab in the single-muscle practical, on the simulated board,
    with the save dialog answered by the test and every log line captured."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "eventos-y-capturas")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/port", "simulada")
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("simulada")
    tab.next_path = tmp_path / "a.edf"
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tab.next_path), "")))
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    yield tab
    tab.cleanup()
    _pump(qapp, 100)


def _record(qapp, tab, path: Path, seconds: float = 0.6) -> None:
    tab.next_path = path
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    _until(qapp, lambda: tab._worker is not None and tab._worker.is_streaming()
           and tab._total_samples > 300, 8.0, "the simulated signal")
    _pump(qapp, int(seconds * 1000))
    tab._btn_grabar.setChecked(False)
    tab._toggle_grabacion()
    _until(qapp, lambda: not tab.is_recording(), 5.0, "the recording to end")
    _until(qapp, lambda: tab._eventos is None, 5.0, "the event log to be saved")


def test_the_event_log_is_named_after_the_recording_and_holds_plain_text() -> None:
    beside = Path("Records") / "P07_2026-09-10_16-32.edf"
    assert events_path(beside) == Path("Records") / ("P07_2026-09-10_16-32" + EVENTS_SUFFIX)
    assert EVENTS_SUFFIX == ".eventos.txt"
    fake = SimpleNamespace(_eventos=[])
    AcquisitionTab._anotar_evento(fake, "<b>Calibration</b> &amp; <i>check</i>")
    assert re.fullmatch(r"\d\d:\d\d:\d\d  Calibration & check", fake._eventos[0])
    idle = SimpleNamespace(_eventos=None)
    AcquisitionTab._anotar_evento(idle, "between recordings")
    assert idle._eventos is None, "nothing is kept outside a recording"


def test_a_recording_leaves_its_event_log_beside_it(qapp, tab, tmp_path) -> None:
    path = tmp_path / "P07.edf"
    _record(qapp, tab, path)
    log = events_path(path)
    assert path.exists() and log.exists()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith(f"# emgteach {__version__} — P07.edf — ")
    assert all(re.match(r"\d\d:\d\d:\d\d  ", ln) for ln in lines[1:]), lines
    assert any(tr("Recording finished. File: {path}").format(path=path) in ln for ln in lines)
    assert not any("<span" in ln for ln in lines)
    said = tab._local_log.toPlainText()
    assert tr("Event log saved: {path}").format(path=log) in said


def test_a_recording_that_fails_leaves_its_event_log_too(qapp, tab, tmp_path, monkeypatch) -> None:
    from emgteach.workers import acquisition as wmod

    original = wmod.BufferedEdfWriter.add_samples
    calls = {"n": 0}

    def disk_full(self, *blocks):
        calls["n"] += 1
        if calls["n"] > 5:
            raise OSError(28, "No space left on device")
        return original(self, *blocks)

    monkeypatch.setattr(wmod.BufferedEdfWriter, "add_samples", disk_full)
    path = tmp_path / "full.edf"
    tab.next_path = path
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    _until(qapp, lambda: not tab.is_recording() and calls["n"] > 5, 8.0, "the failure")
    _until(qapp, lambda: tab._eventos is None, 5.0, "the event log to be saved")
    text = events_path(path).read_text(encoding="utf-8")
    assert tr("Error:") in text and "No space left on device" in text
    assert "incomplete" in text or "incompleto" in text


def test_each_recording_keeps_only_its_own_lines(qapp, tab, tmp_path) -> None:
    _record(qapp, tab, tmp_path / "first.edf")
    tab._log("a line between recordings")
    _record(qapp, tab, tmp_path / "second.edf")
    second = events_path(tmp_path / "second.edf").read_text(encoding="utf-8")
    assert "second.edf" in second
    assert "first.edf" not in second
    assert "a line between recordings" not in second
    first = events_path(tmp_path / "first.edf").read_text(encoding="utf-8")
    assert "second.edf" not in first


def test_automatic_screenshots_stop_at_the_limit_and_say_so_once(qapp, tmp_path, monkeypatch) -> None:
    from emgteach.gui import app as app_mod
    from emgteach.gui.app import MainWindow

    settings = QSettings("emgteach-test", "auto-captura-tope")
    settings.clear()
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    settings.setValue("app/tour_offer", False)
    win = MainWindow(settings)
    win.resize(900, 600)
    win.show()
    qapp.processEvents()
    try:
        monkeypatch.setattr(app_mod, "AUTO_CAPTURA_MAX", 3)
        monkeypatch.setattr(win._tab_adq, "is_recording", lambda: True)
        win._act_auto_captura.setChecked(True)
        for _ in range(6):
            win._tic_captura()
        assert len(list(tmp_path.glob("*.png"))) == 3
        limit = tr(
            "{n} automatic screenshots: the limit for one recording. No more until the "
            "next one; «Screenshot» or F12 still takes one by hand.").format(n=3)
        assert win._logger.toPlainText().count(limit) == 1

        monkeypatch.setattr(win._tab_adq, "is_recording", lambda: False)
        win._tic_captura()
        assert tr("{n} automatic screenshots saved with the recording.").format(n=3) in (
            win._logger.toPlainText().splitlines()[-1])

        # The next recording starts its own count.
        monkeypatch.setattr(win._tab_adq, "is_recording", lambda: True)
        win._tic_captura()
        assert len(list(tmp_path.glob("*.png"))) == 4
    finally:
        win._act_auto_captura.setChecked(False)
        settings.clear()
        win.close()
        win.deleteLater()
        qapp.processEvents()
