"""A guided session of the one-muscle practical, run in the acquisition tab.

Driven end to end with the BITalino in software (`simulada`): real worker,
real thread, real EDF. The session is a short one built here, with phases of
a fraction of a second, so what is tested is the machinery every session
uses: the chooser and where it shows, «Start recording» arming the session,
the countdown, the phases marked in the file at their times, the tone and the
flash at each change, the automatic stop, Esc, a stop by hand, and the review
shading what the session measured.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from emgteach import cue
from emgteach.i18n import tr
from emgteach.io import read_edf_markers
from emgteach.sessions import (
    EFFORT,
    READY,
    REST,
    SessionPhase,
    SessionScript,
    end_marker,
    header_marker,
    parse_session_markers,
    span_end_marker,
    span_start_marker,
)
from tests.test_marcas_manuales import _pump, _stop, _until

pytestmark = pytest.mark.gui

#: Seconds of every phase of the test session, and of the countdown.
FASE_S = 0.6
CUENTA_S = 0.5


def _script(needs_mvc: bool = False) -> SessionScript:
    def paso(k: int) -> SessionPhase:
        return SessionPhase(
            f"step{k}", EFFORT, FASE_S, "Squeeze", "Squeeze now.", level=0.3 * k,
            opens=span_start_marker("GRAD", "step", k=k, pct=20 * k),
            closes=span_end_marker("GRAD", "step", k=k))

    return SessionScript(
        key="prueba", family="GRAD", title="Test session", slug="prueba",
        header=header_marker("GRAD", steps=2), needs_mvc=needs_mvc,
        phases=(SessionPhase("ready", READY, FASE_S, "Get ready"), paso(1),
                SessionPhase("rest", REST, FASE_S, "Rest", "Let go."), paso(2),
                SessionPhase("after", REST, FASE_S, "Rest", "Let go.", cue=False)),
    )


@pytest.fixture
def tonos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The tones the session asks for, instead of sounding them."""
    oidos: list[str] = []
    monkeypatch.setattr(cue, "beep", lambda: oidos.append("phase"))
    monkeypatch.setattr(cue, "beep_end", lambda: oidos.append("end"))
    return oidos


@pytest.fixture
def tab(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tonos):
    """The single-muscle tab on the simulated board, with the test session
    offered and a countdown of half a second."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, "prueba", _script)
    settings = QSettings("emgteach-test", "sesion-guiada")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/port", "simulada")
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab._profile = dataclasses.replace(tab._profile, prep_countdown_s=CUENTA_S)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("simulada")
    tab.next_path = tmp_path / "a.edf"
    tab.pedido_nombre = ""

    def guardar(_parent, _title, nombre, *_a, **_k):
        tab.pedido_nombre = Path(nombre).name
        return (str(tab.next_path), "")

    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName", staticmethod(guardar))
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    yield tab
    tab.cleanup()
    _pump(qapp, 100)


def _choose(tab, key: str | None) -> None:
    tab._combo_sesion.setCurrentIndex(tab._combo_sesion.findData(key))


def _record(qapp, tab, path: Path) -> None:
    tab.next_path = path
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    _until(qapp, lambda: tab._worker is not None and tab._worker.is_streaming(),
           8.0, "the simulated signal")


# ── Where it is offered ─────────────────────────────────────────────────────


def test_the_chooser_opens_on_free_recording(tab) -> None:
    assert tab._combo_sesion.currentData() is None
    assert tab._combo_sesion.currentText() == tr("Free recording")
    assert tab._combo_sesion.findData("prueba") > 0
    assert not tab._combo_sesion.isHidden() and not tab._chk_tono.isHidden()


def test_only_the_one_muscle_practical_offers_it(tab) -> None:
    _choose(tab, "prueba")
    tab.apply_mode("pair", False)
    assert tab._combo_sesion.isHidden()
    # The tone is every practical's: the calibration and the guided task
    # are announced with it too (Ángel, 25 Oct 2026).
    assert not tab._chk_tono.isHidden()
    tab.apply_mode("single", False)
    assert not tab._combo_sesion.isHidden()
    # Changing practical is changing sequence: back to a free recording.
    assert tab._combo_sesion.currentData() is None


def test_with_no_session_written_yet_nothing_is_offered(qapp, tab, monkeypatch) -> None:
    from emgteach.gui.tabs import acquisition as acq_mod

    monkeypatch.setattr(acq_mod, "GUIDED_SESSIONS", {})
    tab.apply_mode("single", False)
    assert tab._combo_sesion.isHidden() and not tab._chk_tono.isHidden()


def test_it_takes_no_height(qapp, tab) -> None:
    """On the line of «Calibrate MVC», which this practical leaves half empty."""
    tab.resize(1400, 900)
    tab.show()
    _pump(qapp, 50)
    y = tab._btn_calibrar.mapTo(tab, tab._btn_calibrar.rect().center()).y()
    for w in (tab._combo_sesion, tab._chk_tono):
        assert abs(w.mapTo(tab, w.rect().center()).y() - y) <= 4
    tab.hide()


def test_the_proposed_name_carries_the_session() -> None:
    from emgteach.gui.tabs.acquisition import nombre_por_defecto

    assert nombre_por_defecto("P03", "2026-10-24_10-00-00", "gradacion") == (
        "P03_gradacion_2026-10-24_10-00-00.edf")
    assert nombre_por_defecto("", "2026-10-24_10-00-00", "fatiga") == (
        "emg_fatiga_2026-10-24_10-00-00.edf")
    assert nombre_por_defecto("P03", "2026-10-24_10-00-00") == "P03_2026-10-24_10-00-00.edf"


# ── The tone box ─────────────────────────────────────────────────────────────


def test_the_tone_is_on_by_default_and_remembered(qapp, tab, tonos) -> None:
    from emgteach.gui.tabs.acquisition import SESSION_TONE_KEY, AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    assert tab._chk_tono.isChecked()
    tab._chk_tono.setChecked(False)
    otra = AcquisitionTab(LoggerWidget(), tab._settings)
    assert not otra._chk_tono.isChecked()
    otra.cleanup()
    tab._chk_tono.setChecked(True)
    assert tab._settings.value(SESSION_TONE_KEY) in (True, "true")
    # Ticking it sounds it: the only way to know this machine can be heard.
    assert tonos == ["phase"]


# ── A whole session ──────────────────────────────────────────────────────────


def test_a_session_runs_marks_its_phases_and_stops_the_recording(
    qapp, tab, tmp_path: Path, tonos
) -> None:
    path = tmp_path / "sesion.edf"
    _choose(tab, "prueba")
    _record(qapp, tab, path)
    assert not tab._combo_sesion.isEnabled()        # chosen before, not during
    assert tab.pedido_nombre.startswith("emg_prueba_")
    _until(qapp, lambda: tab._session_runner is not None, 8.0, "the session to start")
    # One box per measured effort, none done yet.
    assert tab._mvc_overlay.steps_done() == [False, False]
    total = CUENTA_S + 5 * FASE_S
    _until(qapp, lambda: not tab.is_recording(), total + 10.0,
           "the recording to stop at the end of the session")
    # The panel stays its five seconds with every effort's box filled: the
    # count of what was done (Ángel, 25 Oct 2026).
    assert tab._mvc_overlay.steps_done() == [True, True]
    _until(qapp, lambda: tab._eventos is None, 5.0, "the event log to be saved")
    assert tab._combo_sesion.isEnabled()

    marcas = read_edf_markers(path)
    textos = [m for _t, m in marcas]
    assert "PREP start" in textos and "REC start" in textos
    rec = next(t for t, m in marcas if m == "REC start")
    prep = next(t for t, m in marcas if m == "PREP start")
    assert rec - prep == pytest.approx(CUENTA_S, abs=0.25)

    sesion = parse_session_markers(marcas)
    assert sesion is not None and sesion.completed and sesion.family == "GRAD"
    assert sesion.start_s == pytest.approx(rec, abs=0.15)
    # Each step opens where the script puts it, counted from the session's
    # start, and lasts its phase — within a tick or two of the runner.
    esperado = [(1 * FASE_S, 2 * FASE_S), (3 * FASE_S, 4 * FASE_S)]
    assert len(sesion.spans) == 2
    for tramo, (a, b), k in zip(sesion.spans, esperado, (1, 2), strict=True):
        assert tramo.number("k") == k and tramo.number("pct") == 20 * k
        assert tramo.start_s - sesion.start_s == pytest.approx(a, abs=0.35)
        assert tramo.end_s - sesion.start_s == pytest.approx(b, abs=0.35)
    assert sesion.end_s is not None
    assert sesion.end_s - sesion.start_s == pytest.approx(5 * FASE_S, abs=0.3)

    # A tone at the countdown, at the four announced phases (the last rest
    # only continues), then the end.
    assert tonos == ["phase"] * 5 + ["end"]
    from emgteach.gui.tabs.acquisition import events_path
    eventos = events_path(path).read_text(encoding="utf-8")
    assert tr("Guided session finished: {title}.").format(title=tr("Test session")) in eventos
    assert tr("Recording stopped automatically: guided session finished.") in eventos


def test_the_simulated_subject_does_what_each_phase_asks(qapp, tab, tmp_path: Path) -> None:
    _choose(tab, "prueba")
    _record(qapp, tab, tmp_path / "sujeto.edf")
    _until(qapp, lambda: tab._session_runner is not None, 8.0, "the session to start")
    sujeto = getattr(getattr(tab._worker._device, "_serial", None), "_subject", None)
    pedidos: list[float | None] = []
    while tab._session_runner is not None:
        fase = tab._session_runner.current_phase
        if fase is not None and sujeto is not None:
            nivel = sujeto._asked.get(0, (None, None))[0]
            if not pedidos or pedidos[-1] != nivel:
                pedidos.append(nivel)
        _pump(qapp, 20)
    if sujeto is None:
        pytest.skip("this board does not expose its synthetic subject")
    assert 0.3 in pedidos and 0.6 in pedidos and 0.0 in pedidos


def test_a_session_that_needs_the_mvc_calibrates_first(qapp, tab, tmp_path, monkeypatch) -> None:
    from emgteach.gui.tabs import acquisition as acq_mod

    monkeypatch.setitem(acq_mod.GUIDED_SESSIONS, "prueba", lambda: _script(needs_mvc=True))
    _choose(tab, "prueba")
    _record(qapp, tab, tmp_path / "cvm.edf")
    _until(qapp, lambda: tab._mvc_active, 8.0, "the calibration to start")
    assert tab._session_flow_pending and tab._session_runner is None
    _stop(qapp, tab)
    sesion = parse_session_markers(read_edf_markers(tmp_path / "cvm.edf"))
    assert sesion is None                         # it never got to start


def test_a_free_recording_writes_no_session(qapp, tab, tmp_path: Path) -> None:
    path = tmp_path / "libre.edf"
    _record(qapp, tab, path)
    _pump(qapp, CUENTA_S * 1000 + 600)
    assert tab._session_runner is None and not tab._prep_timer.isActive()
    _stop(qapp, tab)
    textos = [m for _t, m in read_edf_markers(path)]
    assert parse_session_markers(read_edf_markers(path)) is None
    assert "PREP start" not in textos and "REC start" not in textos
    assert not tab._btn_cancelar_guia.isVisible()


def test_esc_stops_the_session_and_the_recording_goes_on(qapp, tab, tmp_path: Path) -> None:
    path = tmp_path / "esc.edf"
    _choose(tab, "prueba")
    _record(qapp, tab, path)
    _until(qapp, lambda: tab._session_runner is not None
           and tab._session_runner.index >= 1, 8.0, "the first step")
    tab._cancelar_guiado()
    assert tab._session_runner is None
    _pump(qapp, 300)
    assert tab.is_recording()
    _stop(qapp, tab)
    marcas = read_edf_markers(path)
    assert end_marker("GRAD", stopped=True) in [m for _t, m in marcas]
    sesion = parse_session_markers(marcas)
    assert sesion is not None and not sesion.completed
    from emgteach.gui.tabs.acquisition import events_path
    assert tr("Guided session stopped; the recording goes on.") in events_path(
        path).read_text(encoding="utf-8")


def test_stopping_the_recording_stops_the_session_with_its_mark(
    qapp, tab, tmp_path: Path
) -> None:
    path = tmp_path / "parada.edf"
    _choose(tab, "prueba")
    _record(qapp, tab, path)
    _until(qapp, lambda: tab._session_runner is not None, 8.0, "the session to start")
    _stop(qapp, tab)
    assert tab._session_runner is None
    assert end_marker("GRAD", stopped=True) in [m for _t, m in read_edf_markers(path)]
    from emgteach.gui.tabs.acquisition import events_path
    assert tr("Guided session stopped with the recording.") in events_path(
        path).read_text(encoding="utf-8")


def test_the_review_shades_what_the_session_measured(qapp, tab, tmp_path: Path) -> None:
    import pyqtgraph as pg

    from emgteach.gui.tabs.acquisition import GUIDED

    _choose(tab, "prueba")
    _record(qapp, tab, tmp_path / "repaso.edf")
    _until(qapp, lambda: not tab.is_recording(), CUENTA_S + 5 * FASE_S + 10.0,
           "the session to end")
    _until(qapp, lambda: bool(tab._revision_items), 5.0, "the review")
    color = tab._COLORES_FASE[GUIDED]
    sombras = [it for pw, it in tab._revision_items
               if pw is tab._plot_env and isinstance(it, pg.LinearRegionItem)
               and it.brush.color().getRgb() == color]
    assert len(sombras) == 2


# ── After Ángel's trial of 25 October 2026 ──────────────────────────────────


def test_the_calibration_names_the_sessions_gesture(tab) -> None:
    """The calibration said «a brief, explosive jerk» and the session «squeeze
    your fist»: the same movement in two sets of words. With a session it is
    now said the session's way; without one, as before."""
    from emgteach.sessions import gradation_script

    regla = tr("A brief, explosive jerk — not a sustained push.")
    assert tab._mvc_gesto(0) == regla
    tab._session_script = gradation_script()
    assert tab._mvc_gesto(0) == tr("Clench your fist: a brief, explosive jerk.")


def test_the_warm_up_speaks_of_one_muscle_when_there_is_one(qapp, tab) -> None:
    tab._mvc_active = True
    tab._mvc_enter_warmup()
    tab._mvc_tick()
    assert tab._mvc_overlay._subtitle == tr("Two or three easy contractions.")
    tab._mvc_cancel()


@pytest.mark.parametrize("marcada", [True, False])
def test_the_calibration_is_announced_with_the_tone_when_ticked(qapp, tab, tonos, marcada) -> None:
    """The tone is every guided flow's, not the sessions' alone."""
    tab._chk_tono.blockSignals(True)
    tab._chk_tono.setChecked(marcada)
    tab._chk_tono.blockSignals(False)
    tonos.clear()
    tab._mvc_active = True
    tab._mvc_enter_warmup()
    tab._mvc_enter_ready()
    assert tonos == (["phase", "phase"] if marcada else [])
    tab._mvc_cancel()


def test_there_is_no_flash_any_more() -> None:
    from emgteach.gui.widgets.mvc_overlay import MvcOverlay

    assert not hasattr(MvcOverlay, "flash")
