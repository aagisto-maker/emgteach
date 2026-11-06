"""The stage every guided flow plays on, as a piece of its own (step 4 of
docs/PLAN-partir-AcquisitionTab.md): `FlowStage` is built with ways to ask
for the current worker, the number of channels and whether the tone box is
ticked, and the label under the panel — nothing else. What the flows do
with it is covered by their own tests (the calibration, the pair's task,
the force-velocity study, the guided sessions).
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from emgteach import cue
from emgteach.gui.acquisition.stage import FlowStage

pytestmark = pytest.mark.gui


class _Hilo:
    """A worker that records what it is told instead of telling a board."""

    def __init__(self, corriendo: bool = True) -> None:
        self.corriendo = corriendo
        self.pedidos: list[tuple[int, float | None, float | None]] = []
        self.marcas: list[str] = []

    def isRunning(self) -> bool:
        return self.corriendo

    def instruct(self, channel_index, level, *, repeat_s=None) -> None:
        self.pedidos.append((channel_index, level, repeat_s))

    def add_marker(self, label: str) -> None:
        self.marcas.append(label)


@pytest.fixture
def escenario(qapp, monkeypatch):
    estado = {"hilo": _Hilo(), "n": 2, "tono": True}
    oidos: list[str] = []
    monkeypatch.setattr(cue, "beep", lambda: oidos.append("phase"))
    monkeypatch.setattr(cue, "beep_end", lambda: oidos.append("end"))
    etiqueta = QLabel()
    stage = FlowStage(
        worker=lambda: estado["hilo"], n_channels=lambda: estado["n"],
        tone_on=lambda: estado["tono"], info_label=etiqueta,
    )
    stage.estado, stage.oidos, stage.etiqueta = estado, oidos, etiqueta
    yield stage
    etiqueta.deleteLater()


def test_each_muscle_is_told_what_is_asked_of_it(escenario) -> None:
    escenario.ask_subject({0: 0.3}, repeat_s=1.5)
    # The one not named is asked to rest, and only an effort repeats.
    assert escenario.estado["hilo"].pedidos == [(0, 0.3, 1.5), (1, 0.0, None)]
    escenario.estado["hilo"].pedidos.clear()
    escenario.ask_subject({})
    assert escenario.estado["hilo"].pedidos == [(0, 0.0, None), (1, 0.0, None)]


def test_letting_go_gives_every_muscle_back_to_itself(escenario) -> None:
    escenario.release_subject()
    assert escenario.estado["hilo"].pedidos == [(0, None, None), (1, None, None)]


def test_the_channels_and_the_worker_are_asked_for_each_time(escenario) -> None:
    escenario.estado["n"] = 1
    escenario.release_subject()
    otro = _Hilo()
    escenario.estado["hilo"] = otro
    escenario.ask_subject({0: 0.5})
    assert otro.pedidos == [(0, 0.5, None)]


def test_with_no_recording_running_nothing_is_told_or_written(escenario) -> None:
    for hilo in (None, _Hilo(corriendo=False)):
        escenario.estado["hilo"] = hilo
        escenario.ask_subject({0: 0.3})
        escenario.release_subject()
        escenario.instruct_device(0, 0.2)
        escenario.write_phase_marker("CAL start ch=1 rep=1")     # must not raise
        if hilo is not None:
            assert hilo.pedidos == [] and hilo.marcas == []


def test_a_phase_mark_goes_into_the_recording(escenario) -> None:
    escenario.write_phase_marker("REC start")
    assert escenario.estado["hilo"].marcas == ["REC start"]


def test_the_tone_sounds_only_with_its_box_ticked(escenario) -> None:
    escenario.tone()
    escenario.tone(final=True)
    assert escenario.oidos == ["phase", "end"]
    escenario.estado["tono"] = False
    escenario.tone()
    escenario.tone(final=True)
    assert escenario.oidos == ["phase", "end"]


def test_the_line_under_the_panel(escenario) -> None:
    escenario.info("Get ready to record: 3")
    assert escenario.etiqueta.text() == "Get ready to record: 3"


def test_the_tab_gives_it_its_box_and_its_line(qapp, monkeypatch) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    oidos: list[str] = []
    monkeypatch.setattr(cue, "beep", lambda: oidos.append("phase"))
    ajustes = QSettings("emgteach-test", "escenario")
    ajustes.clear()
    log = LoggerWidget()
    tab = AcquisitionTab(log, ajustes)
    try:
        assert isinstance(tab._escenario, FlowStage)
        tab._escenario.info("x")
        assert tab._lbl_load_info.text() == "x"
        tab._chk_tono.setChecked(False)
        oidos.clear()
        tab._escenario.tone()
        assert oidos == []                               # the box is asked, each time
        tab._chk_tono.setChecked(True)                   # ticking it sounds a sample
        oidos.clear()
        tab._escenario.tone()
        assert oidos == ["phase"]
        tab._n_channels = 2                              # asked for when used
        assert tab._escenario._n_channels == 2
    finally:
        tab.cleanup()
        tab.deleteLater()
        log.deleteLater()
        qapp.processEvents()
