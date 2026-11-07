"""A recording never ends without its review in silence (bench of
6 November 2026).

In a rehearsal with the simulated board, a recording sometimes ended with no
review in the acquisition tab, the application going on as usual and nothing
in the event log to say why. Every way a recording ends goes through
``AcquisitionTab._on_finished``, and some of them ended there without a word:
a recording that left no file (no sample arrived, a write failure), one that
ended after another had started, a file with no EMG channel, and an error
inside the review, which left it half drawn and the event log open.

Now each ends in the review or in a line «No review of <file>: <reason>.»;
an unexpected error is written to the error log too, and leaves the plots as
they were. Every practical and every recording, guided or free, ends there.
"""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from emgteach.i18n import tr
from emgteach.io import BufferedEdfWriter, ChannelInfo

pytestmark = pytest.mark.gui

FS = 1000


@pytest.fixture
def tab(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The one-muscle tab on the simulated board, saving where told."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    ajustes = QSettings("emgteach-test", "revision-sin-silencio")
    ajustes.clear()
    ajustes.setValue("app/mode", "single")
    ajustes.setValue("adquisicion/device_type", 0)
    ajustes.setValue("adquisicion/port", "simulada")
    ajustes.setValue("adquisicion/save_dir", str(tmp_path))
    log = LoggerWidget()
    pestana = AcquisitionTab(log, ajustes)
    pestana.apply_mode("single", False)
    pestana.next_path = tmp_path / "r.edf"
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(pestana.next_path), "")))
    # The error log, kept out of the user's folder.
    monkeypatch.setattr("emgteach.crash.log_path", lambda: tmp_path / "errores.log")
    yield pestana
    pestana.cleanup()
    pestana.deleteLater()
    log.deleteLater()
    qapp.processEvents()


def _registro(tab) -> str:
    return tab._local_log.toPlainText()


def _sin_revision(archivo: str, motivo: str) -> str:
    return tr("No review of {file}: {reason}.").format(file=archivo, reason=motivo)


def _edf(path: Path) -> str:
    senal = np.random.default_rng(3).normal(0.0, 0.01, 5 * FS)
    with BufferedEdfWriter(str(path), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(senal)
    return str(path)


def _hasta(qapp, condicion, segundos: float) -> bool:
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        qapp.processEvents()
        if condicion():
            return True
        time.sleep(0.005)
    return False


# ── Each way it ends without a review says why ────────────────────────────


def test_stopped_before_the_first_sample_it_says_so(qapp, tab) -> None:
    """Start and stop at once, before the board's first block: no file, and
    the log says there is no review and why (the one way the rehearsal's
    symptom could be brought about on purpose, 0.41 s of window)."""
    tab.connect_to("simulada")
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    tab._btn_grabar.setChecked(False)
    tab._toggle_grabacion()                      # «Stop», at once
    assert _hasta(qapp, lambda: not tab.is_recording(), 15.0)
    assert _hasta(qapp, lambda: tr("No review of") in _registro(tab), 5.0)
    assert _sin_revision(tr("this recording"), tr("no sample arrived from the board")) \
        in _registro(tab)
    assert not tab._trazado._revisando


def test_a_recording_that_ended_after_another_began_says_so(qapp, tab,
                                                            tmp_path: Path) -> None:
    ruta = _edf(tmp_path / "anterior.edf")
    tab._on_finished(ruta, worker=object())     # not the current worker
    assert _sin_revision("anterior.edf", tr("another recording had already started")) \
        in _registro(tab)


def test_a_worker_that_left_no_file_gives_its_reason(qapp, tab) -> None:
    @dataclasses.dataclass
    class _Hilo:
        motivo_sin_archivo: str

    hilo = _Hilo(tr("the file is incomplete after a write failure"))
    tab._on_finished("", worker=hilo)
    assert _sin_revision(tr("this recording"),
                         tr("the file is incomplete after a write failure")) in _registro(tab)


def test_a_file_with_no_emg_channel_says_so(qapp, tab, tmp_path: Path, monkeypatch) -> None:
    from emgteach.gui.acquisition import plots

    ruta = _edf(tmp_path / "sin_emg.edf")
    monkeypatch.setattr(plots, "list_edf_emg_channels", lambda path: [])
    tab._on_finished(ruta)
    assert _sin_revision("sin_emg.edf", tr("the file has no EMG channel")) in _registro(tab)


def test_an_unexpected_error_is_said_written_and_leaves_no_half_review(
    qapp, tab, tmp_path: Path, monkeypatch
) -> None:
    from emgteach.gui.acquisition import plots

    def falla(*a, **k):
        raise RuntimeError("a stretch the review did not expect")

    ruta = _edf(tmp_path / "raro.edf")
    monkeypatch.setattr(plots, "phase_spans", falla)
    tab._eventos_ruta = ruta
    tab._eventos = ["# the recording's event log"]
    tab._on_finished(ruta)                       # used to raise out of the slot
    texto = _registro(tab)
    assert tr("No review of") in texto and "RuntimeError" in texto
    assert "a stretch the review did not expect" in (tmp_path / "errores.log").read_text(
        encoding="utf-8")
    # The plots as they were, live, not half a review.
    assert not tab._trazado._revisando and tab._trazado._revision_items == []
    assert tab._trazado._plot_raw.plotItem.titleLabel.text != tr(
        "Recording just finished (review)")
    # And the event log closed beside the recording, as on any other end.
    assert tab._eventos is None
    assert Path(ruta).with_name("raro.eventos.txt").exists()


def test_a_recording_that_is_reviewed_says_nothing_of_the_kind(qapp, tab,
                                                               tmp_path: Path) -> None:
    tab._on_finished(_edf(tmp_path / "bien.edf"))
    assert tab._trazado._revisando
    assert tr("No review of") not in _registro(tab)
