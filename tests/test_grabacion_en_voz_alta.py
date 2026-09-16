"""A recording fails out loud, and the tab keeps telling the truth.

Driven end to end with the BITalino in software (`simulada`): real worker,
real thread, real EDF. Four things that used to go wrong at the bench:

- a block the EDF could not take was noted in the log while the recording
  went on and was then announced as saved;
- stopping and starting again inside a second left the plots frozen on the
  previous file while the new one was being written;
- a disconnection in mid-recording ended with «connected (ready to record)»;
- a second recording carried the references of the first in its header.

And the simulated board's name reached the header as «BITalino lated».
"""

from __future__ import annotations

import time
from pathlib import Path

import pyedflib
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from emgteach.i18n import tr
from emgteach.io import EDF_RECORDING_IDENT_BUDGET, RecordingMetadata, _compact_equipment

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
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "grabacion-en-voz-alta")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/port", "simulada")
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("simulada")
    tab.lines: list[tuple[str, str]] = []
    log, err = tab._log, tab._err
    monkeypatch.setattr(tab, "_log", lambda m: (tab.lines.append(("log", m)), log(m)))
    monkeypatch.setattr(tab, "_err", lambda m: (tab.lines.append(("err", m)), err(m)))
    tab.saved: list[str] = []
    tab.recording_saved.connect(tab.saved.append)
    tab.next_path = tmp_path / "a.edf"
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tab.next_path), "")))
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    yield tab
    tab.cleanup()
    _pump(qapp, 100)


def _start(tab, path: Path) -> None:
    tab.next_path = path
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()


def _stop(tab) -> None:
    tab._btn_grabar.setChecked(False)
    tab._toggle_grabacion()


def _wait_streaming(qapp, tab) -> None:
    _until(qapp, lambda: tab._worker is not None and tab._worker.is_streaming()
           and tab._total_samples > 300, 8.0, "the simulated signal")


def test_stopping_and_starting_again_at_once_keeps_the_new_recording_live(qapp, tab, tmp_path):
    _start(tab, tmp_path / "first.edf")
    _wait_streaming(qapp, tab)
    old = tab._worker
    _stop(tab)
    _start(tab, tmp_path / "second.edf")          # the student's second click
    assert tab._worker is not old
    assert not old.isRunning(), "«Start» waits for the previous thread"
    _pump(qapp, 500)                               # the old thread's signals arrive
    assert tab.is_recording()
    assert tab._btn_grabar.isChecked() and tab._btn_grabar.text() == tr("Stop recording")
    assert tab._lbl_estado.text() == tr("Status: recording…")
    assert not tab._revisando, "the plots follow the new recording, not the old file"
    assert tab._render_timer.isActive() and tab._load_timer.isActive()
    n = tab._total_samples
    _pump(qapp, 400)
    assert tab._total_samples > n
    assert tab.saved == [str(tmp_path / "first.edf")], "the first file still goes to the analysis"
    _stop(tab)
    _until(qapp, lambda: not tab.is_recording(), 5.0, "the second recording to end")
    _pump(qapp, 300)
    assert tab.saved[-1] == str(tmp_path / "second.edf")


def test_a_disconnection_in_mid_recording_says_disconnected(qapp, tab, tmp_path):
    _start(tab, tmp_path / "cut.edf")
    _wait_streaming(qapp, tab)
    tab._btn_conectar.setChecked(False)
    tab._toggle_conexion()
    _until(qapp, lambda: not tab.is_recording(), 5.0, "the thread to end")
    _pump(qapp, 400)                               # its «finished» is delivered
    assert not tab._btn_conectar.isChecked()
    assert tab._lbl_estado.text() == tr("Status: disconnected")
    assert tab._btn_grabar.text() == tr("Start recording")


def test_a_block_the_edf_cannot_take_stops_the_recording_with_an_error(
    qapp, tab, tmp_path, monkeypatch
):
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
    _start(tab, path)
    _until(qapp, lambda: any(k == "err" for k, _m in tab.lines), 8.0, "the write error")
    _until(qapp, lambda: not tab.is_recording(), 5.0, "the recording to stop by itself")
    _pump(qapp, 400)
    errors = [m for k, m in tab.lines if k == "err"]
    assert any(path.name in m and str(tmp_path) in m for m in errors), errors
    assert tab.saved == [], "an incomplete file is not sent to the analysis"
    assert tab._btn_grabar.text() == tr("Start recording") and not tab.is_recording()
    assert path.exists(), "what was written before the failure stays on disk"
    assert any("incomplete" in m or "incompleto" in m for _k, m in tab.lines)
    assert calls["n"] == 6, "the worker stops at the first failed block"


def test_a_second_recording_does_not_inherit_the_references_of_the_first(qapp, tab, tmp_path):
    tab._mvc_ref[0] = 0.42                         # as if calibrated in a previous recording
    path = tmp_path / "second_session.edf"
    _start(tab, path)
    assert tab._mvc_ref[0] is None, "a recording starts with no reference"
    _wait_streaming(qapp, tab)
    _stop(tab)
    _until(qapp, lambda: not tab.is_recording(), 5.0, "the recording to end")
    _pump(qapp, 300)
    with pyedflib.EdfReader(str(path)) as f:
        labels = list(f.readAnnotations()[2])
    assert not any(str(t).startswith("MVC ref") for t in labels), labels


def test_the_simulated_board_keeps_its_name_in_the_header() -> None:
    assert _compact_equipment("BITalino (simulated)") == "BITalino simulated"
    assert _compact_equipment("BITalino (98:D3:91:FE:44:E4)") == "BITalino 44:E4"
    # Room for the compacted name and not for the full one: the header used
    # to say «BITalino lated».
    protocol = "p" * (EDF_RECORDING_IDENT_BUDGET - len("BITalino simulated"))
    meta, _notices = RecordingMetadata(
        protocol=protocol, equipment="BITalino (simulated)"
    ).fit_to_edf_budget()
    assert meta.equipment == "BITalino simulated"
