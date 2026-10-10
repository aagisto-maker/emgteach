"""The event log survives a process that is killed mid-recording.

Ported from ecgteach 0.4.0 (bench of 5 October 2026, E7, «taskkill /F»): the
EDF and its .marcas.txt were left behind, and the .eventos.txt - the one file
meant to say what happened - was not, because it was written only when the
recording ended. emgteach 3.7.2 did the same. A child process records the
simulated board, writes a line it names, and is killed the way Task Manager's
«End task» on Details or «taskkill /F» kills it: ``Popen.kill`` is
TerminateProcess on Windows and SIGKILL elsewhere, and in both nothing of the
application runs after it.

The second test is the name reused: a new recording with the name of an
earlier one replaces its log, it does not append to it.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

_CHILD = textwrap.dedent(r'''
    import os, sys, time
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from emgteach.gui.tabs import acquisition as acq
    from emgteach.gui.widgets.logger import LoggerWidget
    target = sys.argv[1]
    acq.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (target, ""))
    settings = QSettings("emgteach-test", "crash-child")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/port", "simulada")
    tab = acq.AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("simulada")
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    end = time.monotonic() + 20
    while time.monotonic() < end and tab._total_samples < 500:
        app.processEvents(); time.sleep(0.01)
    tab._log("the last line before the crash 7f3a")
    print("READY", flush=True)
    while True:
        app.processEvents(); time.sleep(0.01)
''')


def test_the_event_log_is_there_after_the_process_is_killed(tmp_path: Path) -> None:
    from emgteach.gui.tabs.acquisition import events_path

    target = tmp_path / "crash.edf"
    child = subprocess.Popen(
        [sys.executable, "-c", _CHILD, str(target)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    try:
        line = child.stdout.readline() if child.stdout else ""
        assert line.strip() == "READY", "the child did not start recording"
    finally:
        child.kill()                    # TerminateProcess on Windows, SIGKILL here
        child.wait(30)
    log = events_path(target)
    assert target.exists(), "the EDF itself was not there"
    assert log.exists(), "no .eventos.txt after the crash"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# emgteach ")
    assert lines[-1].endswith("the last line before the crash 7f3a"), lines[-3:]


def test_a_reused_name_replaces_the_old_log(qapp, tmp_path: Path) -> None:
    """The log is opened for writing when the recording starts: the lines of
    an earlier recording with the same name are not left above the new ones."""
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab, events_path
    from emgteach.gui.widgets.logger import LoggerWidget

    target = tmp_path / "P07.edf"
    events_path(target).write_text("# emgteach old — P07.edf\n00:00:00  old line\n",
                                   encoding="utf-8")
    settings = QSettings("emgteach-test", "eventos-nombre-repetido")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)
    try:
        tab._eventos_ruta = str(target)
        tab._eventos = ["# emgteach new — P07.edf"]
        tab._abrir_eventos()
        tab._log("a line of the new recording")
        # Before the end: what is on disk is already the new log, alone.
        lines = events_path(target).read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# emgteach new — P07.edf", lines
        assert not any("old line" in ln for ln in lines), lines
        assert lines[-1].endswith("a line of the new recording"), lines
        tab._guardar_eventos()
        lines = events_path(target).read_text(encoding="utf-8").splitlines()
        assert not any("old line" in ln for ln in lines), lines
        assert lines[-1].endswith("a line of the new recording"), lines
    finally:
        tab.cleanup()
