"""Marking by hand while recording: the label, the «Mark (M)» button and the M key.

Gone in 3.0.0, back in 3.9.0 for experiments that need their own events
marked, as in ecgteach and eegteach. A mark by hand goes the way every other
mark goes — an EDF+ annotation, a line in the ``.marcas.txt`` mirror and one
in the event log — so what is tested here is what is new: the controls mark
with the label chosen, only while recording, never while a text field has the
key; the mark lands at the time it was made; the labels exist in both
languages and are never read as a phase, a load or a reference; and the
analysis draws them apart from the marks the application writes.

The recordings are driven end to end with the BITalino in software
(`simulada`): real worker, real thread, real EDF.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from emgteach import i18n
from emgteach.i18n import tr
from emgteach.manual_marks import MANUAL_MARK_LABELS, MARK_KEY, is_manual_mark

pytestmark = pytest.mark.gui

_SPANISH = {
    "Contraction start": "Inicio contracción",
    "Contraction end": "Fin contracción",
    "Fatigue": "Fatiga",
    "Rest": "Reposo",
    "Other": "Otro",
}


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


# ── The labels ─────────────────────────────────────────────────────────────

def test_the_five_labels_exist_in_both_languages() -> None:
    assert MANUAL_MARK_LABELS == tuple(_SPANISH)
    for english, spanish in _SPANISH.items():
        assert i18n._ES.get(english) == spanish, english
    assert i18n._ES["Mark (M)"] == "Marcar (M)"   # the button: an infinitive, and its key
    assert MARK_KEY == "M"


def test_a_manual_mark_is_recognised_in_either_language() -> None:
    for english, spanish in _SPANISH.items():
        assert is_manual_mark(english) and is_manual_mark(spanish)
    for written_by_the_application in (
        tr("Onset (auto)"), "Inicio (auto)", "REC start", "PREP start",
        "CAL start ch=1 rep=1", "FV load=5 kg", "Link: 3 frame(s) lost", "",
    ):
        assert not is_manual_mark(written_by_the_application), written_by_the_application


def test_no_manual_mark_is_read_as_a_phase_a_load_or_a_reference() -> None:
    from emgteach.force_velocity import parse_fv_load_markers
    from emgteach.mvc import parse_mvc_ref_markers
    from emgteach.phases import parse_phase_markers

    marks = [(1.0 + i, text) for i, text in
             enumerate([*_SPANISH, *_SPANISH.values()])]
    assert not parse_phase_markers(marks).has_phases
    assert parse_fv_load_markers(marks) == []
    assert parse_mvc_ref_markers(marks) == {}


# ── The controls ───────────────────────────────────────────────────────────

@pytest.fixture
def marker(qapp):
    """A ManualMarker on a window of its own, shown and active, so the M key
    goes through Qt's shortcut map as it does in the application."""
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

    from emgteach.gui.widgets.manual_marker import ManualMarker

    window = QWidget()
    layout = QVBoxLayout(window)
    window.text = QLineEdit()
    layout.addWidget(window.text)
    window.marker = ManualMarker(window)
    layout.addWidget(window.marker)
    window.marked = []
    window.marker.marked.connect(window.marked.append)
    window.show()
    window.activateWindow()
    QTest.qWaitForWindowExposed(window)
    yield window
    window.close()
    window.deleteLater()


def test_the_button_and_the_key_mark_with_the_label_chosen(qapp, marker) -> None:
    marker.marker.set_recording(True)
    marker.marker.combo.setCurrentIndex(MANUAL_MARK_LABELS.index("Fatigue"))
    QTest.mouseClick(marker.marker.button, Qt.MouseButton.LeftButton)
    marker.marker.combo.setCurrentIndex(MANUAL_MARK_LABELS.index("Rest"))
    marker.marker.button.setFocus()
    QTest.keyClick(marker.marker.button, Qt.Key.Key_M)
    assert marker.marked == [tr("Fatigue"), tr("Rest")]


def test_the_label_is_written_in_the_language_of_the_interface(qapp, marker) -> None:
    marker.marker.set_recording(True)
    marker.marker.combo.setCurrentIndex(MANUAL_MARK_LABELS.index("Contraction start"))
    previous = i18n.get_language()
    i18n.set_language("es")
    try:
        marker.marker.mark()
    finally:
        i18n.set_language(previous)
    assert marker.marked == ["Inicio contracción"]


def test_nothing_marks_outside_a_recording(qapp, marker) -> None:
    marker.marker.set_recording(False)
    assert not marker.marker.button.isEnabled()
    assert not marker.marker.combo.isEnabled()
    marker.marker.button.click()
    marker.marker.mark()
    QTest.keyClick(marker, Qt.Key.Key_M)
    assert marker.marked == []


def test_the_key_types_into_a_text_field_instead_of_marking(qapp, marker) -> None:
    """A name with an «m» in it, typed while recording, is a name: Qt gives a
    plain letter to the text field that has the focus before any shortcut."""
    marker.marker.set_recording(True)
    marker.text.setFocus()
    _until(qapp, marker.text.hasFocus, 2.0, "the text field to take the focus")
    QTest.keyClicks(marker.text, "Marta")
    QTest.keyClick(marker.text, Qt.Key.Key_M)
    assert marker.text.text() == "Martam"
    assert marker.marked == []
    # And the key does mark once the field lets go of the focus: the test
    # above is not passing because the shortcut never fires here.
    marker.marker.button.setFocus()
    QTest.keyClick(marker.marker.button, Qt.Key.Key_M)
    assert len(marker.marked) == 1


# ── In a recording ─────────────────────────────────────────────────────────

@pytest.fixture
def tab(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An acquisition tab in the single-muscle practical, on the simulated board,
    with the save dialog answered by the test."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "marcas-manuales")
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


def _start(qapp, tab, path: Path) -> None:
    tab.next_path = path
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    _until(qapp, lambda: tab._worker is not None and tab._worker.is_streaming()
           and tab._total_samples > 300, 8.0, "the simulated signal")


def _stop(qapp, tab) -> None:
    tab._btn_grabar.setChecked(False)
    tab._toggle_grabacion()
    _until(qapp, lambda: not tab.is_recording(), 5.0, "the recording to end")
    _until(qapp, lambda: tab._eventos is None, 5.0, "the event log to be saved")


def test_a_mark_reaches_the_edf_the_mirror_and_the_log_at_its_time(
    qapp, tab, tmp_path: Path
) -> None:
    from emgteach.gui.tabs.acquisition import events_path
    from emgteach.io import read_edf_markers
    from emgteach.recovery import sidecar_path

    path = tmp_path / "marcas.edf"
    assert not tab._marcador.is_recording()      # nothing before the recording
    _start(qapp, tab, path)
    assert tab._marcador.is_recording()

    worker = tab._worker
    fs = worker._device.fs
    tab._marcador.combo.setCurrentIndex(MANUAL_MARK_LABELS.index("Fatigue"))
    before = worker._n_samples_total / fs
    tab._marcador.button.click()
    after = worker._n_samples_total / fs
    _until(qapp, lambda: any(lbl == tr("Fatigue") for _t, lbl in tab._marker_events),
           2.0, "the mark to come back from the worker")
    t_mark = next(t for t, lbl in tab._marker_events if lbl == tr("Fatigue"))
    assert before <= t_mark <= after, (before, t_mark, after)

    # The mirror has it while the recording runs: it is what survives a crash.
    mirror = sidecar_path(path).read_text(encoding="utf-8")
    assert f"{t_mark:.4f}\t{tr('Fatigue')}" in mirror, mirror

    _pump(qapp, 300)
    _stop(qapp, tab)
    assert not tab._marcador.is_recording()       # and nothing after it

    marks = read_edf_markers(path)
    found = [t for t, lbl in marks if lbl == tr("Fatigue")]
    assert len(found) == 1 and abs(found[0] - t_mark) < 0.01, marks
    log = events_path(path).read_text(encoding="utf-8")
    assert tr("Marker added: t={t:.1f} s — {label}").format(
        t=t_mark, label=tr("Fatigue")) in log
    assert tr("Press M to mark quickly with the selected label.") in log


def test_marking_is_off_between_recordings(qapp, tab, tmp_path: Path) -> None:
    from emgteach.io import read_edf_markers

    path = tmp_path / "despues.edf"
    _start(qapp, tab, path)
    _stop(qapp, tab)
    tab._marcador.mark()
    tab._marcador.button.click()
    _pump(qapp, 200)
    assert not any(is_manual_mark(lbl) for _t, lbl in read_edf_markers(path))


# ── In the analysis ────────────────────────────────────────────────────────

def test_the_analysis_draws_manual_marks_apart(qapp) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.colors import to_hex
    from matplotlib.figure import Figure

    from emgteach.gui.tabs import analysis

    fake = SimpleNamespace(_markers=[
        (1.0, "Inicio (auto)"), (2.0, "REC start"), (3.0, "Fatiga"), (4.0, "Rest"),
    ])
    ax = Figure().add_subplot()
    ax.set_xlim(0, 5)
    analysis.AnalysisTab._dibujar_marcadores(fake, ax, 0.0, 5.0)
    color_at = {line.get_xdata()[0]: to_hex(line.get_color()) for line in ax.lines}
    manual = to_hex(analysis._COLOR_MARCA_MANUAL)
    assert color_at[3.0] == manual and color_at[4.0] == manual
    assert color_at[1.0] != manual and color_at[2.0] != manual
    labels = {t.get_text() for t in ax.texts}
    assert {"Fatiga", "Rest", "REC start"} <= labels
    assert "Inicio (auto)" not in labels           # the onsets stay unlabelled


# ── Out of a text field, back to the M ─────────────────────────────────────

@pytest.fixture
def shown_tab(qapp, tmp_path: Path):
    """An acquisition tab on screen and active, marking as if recording, with
    the marks it would send collected."""
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "marcas-foco")
    settings.clear()
    settings.setValue("app/mode", "single")
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode("single", False)
    tab.resize(1366, 768)
    tab.show()
    tab.activateWindow()
    QTest.qWaitForWindowExposed(tab)
    tab.marked = []
    tab._marcador.marked.connect(tab.marked.append)
    tab._marcador.set_recording(True)
    yield tab
    tab._marcador.set_recording(False)
    tab.cleanup()
    tab.close()
    _pump(qapp, 50)


def _type_in_the_identifier(qapp, tab) -> None:
    field = tab._edit_student_code
    assert field.isVisible() and field.isEnabled()
    field.setFocus()
    _until(qapp, field.hasFocus, 2.0, "the identifier to take the focus")
    QTest.keyClicks(field, "mmm")
    assert field.text() == "mmm" and tab.marked == []


@pytest.mark.parametrize("way_out", [Qt.Key.Key_Return, Qt.Key.Key_Escape],
                         ids=["Enter", "Esc"])
def test_enter_or_esc_in_a_field_gives_the_m_back(qapp, shown_tab, way_out) -> None:
    _type_in_the_identifier(qapp, shown_tab)
    QTest.keyClick(shown_tab._edit_student_code, way_out)
    _until(qapp, lambda: not shown_tab._edit_student_code.hasFocus(), 2.0,
           "the field to let go of the focus")
    QTest.keyClick(QApplication.focusWidget() or shown_tab, Qt.Key.Key_M)
    assert len(shown_tab.marked) == 1
    assert shown_tab._edit_student_code.text() == "mmm"


def _plots_box(tab):
    from PySide6.QtWidgets import QGroupBox

    box = tab._plot_raw.parentWidget()
    while not isinstance(box, QGroupBox):
        box = box.parentWidget()
    return box


@pytest.mark.parametrize("where", ["plot", "plots box"])
def test_a_click_in_the_live_plots_gives_the_m_back(qapp, shown_tab, where) -> None:
    """The bench: «clicked on the live plot and the M still did not mark».

    A click on the plot itself hands the focus to the plot, which takes it.
    A click on what surrounds it — the box, its title, the legend — reached no
    widget that takes the focus, so the field kept it: the tab takes it now.
    """
    _type_in_the_identifier(qapp, shown_tab)
    if where == "plot":
        target = shown_tab._plot_raw.viewport()
        pos = target.rect().center()
    else:
        target = _plots_box(shown_tab)
        assert target.focusPolicy() == Qt.FocusPolicy.NoFocus
        pos = target.rect().topLeft() + QPoint(4, 4)
        assert target.childAt(pos) is None, "the click must land on the box itself"
    QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=pos)
    _until(qapp, lambda: not shown_tab._edit_student_code.hasFocus(), 2.0,
           "the field to let go of the focus")
    QTest.keyClick(QApplication.focusWidget() or shown_tab, Qt.Key.Key_M)
    assert len(shown_tab.marked) == 1
    assert shown_tab._edit_student_code.text() == "mmm"

def test_the_button_says_its_key(qapp) -> None:
    from PySide6.QtWidgets import QWidget

    from emgteach.gui.widgets.manual_marker import ManualMarker

    owner = QWidget()
    marker = ManualMarker(owner)
    assert marker.button.text() == tr("Mark (M)")
    previous = i18n.get_language()
    i18n.set_language("es")
    try:
        assert tr("Mark (M)") == "Marcar (M)"
    finally:
        i18n.set_language(previous)
    owner.deleteLater()


