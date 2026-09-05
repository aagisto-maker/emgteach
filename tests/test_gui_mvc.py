"""GUI regression tests for the MVC tab.

Marked ``gui`` because they build real widgets, so they need a
``QApplication`` (provided by the shared ``qapp`` fixture) and run on a
headless runner thanks to the offscreen Qt platform set in ``conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QElapsedTimer

from emgteach.io import BufferedEdfWriter, ChannelInfo

pytestmark = pytest.mark.gui


def _make_edf(path: Path, fs: int = 1000, secs: int = 12) -> str:
    n = fs * secs
    t = np.arange(n) / fs
    emg = 0.2 * np.sin(2 * np.pi * 80 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t))
    ch = ChannelInfo("EMG", dimension="mV", sample_frequency=fs)
    with BufferedEdfWriter(str(path), channels=[ch]) as writer:
        writer.add_samples(emg.reshape(-1, 1).astype(float))
    return str(path)


def test_compute_does_not_hang_and_fills_load_panel(qapp, tmp_path: Path) -> None:
    """Computing the MVC must start the worker (no stale-attribute crash in
    ``_iniciar_calculo``) and the worker -> ``_on_result`` path must hide the
    progress bar and fill the muscle-load data panel.

    Regression for the bug where ``_iniciar_calculo`` still referenced the
    removed summary labels, so the click raised before the worker started and
    the progress bar span forever ("se queda pensando").
    """
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.mvc import MvcTab
    from emgteach.gui.widgets.logger import LoggerWidget

    edf = _make_edf(tmp_path / "test.edf")
    tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "mvc"))
    tab._edit_path.setText(edf)
    tab._populate_channels(edf)

    done: list = []
    orig = tab._on_result
    tab._on_result = lambda r: (orig(r), done.append(r))

    tab._iniciar_calculo()  # must not raise

    timer = QElapsedTimer()
    timer.start()
    while not done and timer.elapsed() < 20000:
        qapp.processEvents()

    assert done, "MvcWorker did not produce a result"
    assert not tab._progress.isVisible()        # not stuck 'thinking'
    assert len(tab._axes_list) == 3             # three time-series panels
    assert tab._d_static.text() != "—"          # load data panel filled
    assert "apdf" in tab._last_result
    tab.cleanup()


def test_the_minimap_and_the_panels_speak_of_the_same_recording(
    qapp, tmp_path: Path
) -> None:
    """The bar under the panels is the whole recording, not its first 10 s.

    The worker's ``plot_duration_s`` defaults to 10 s and this tab never
    overrode it, so on a 110 s forearm recording the panels could only ever
    reach t = 10 s while the data panel reported a duration of 110 s — and
    the minimap drew the whole 110 s envelope against an axis that ended at
    10, which is what made the shape under the selection disagree with the
    shape in the panels.
    """
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.mvc import MvcTab
    from emgteach.gui.widgets.logger import LoggerWidget

    secs = 25                                   # longer than the old 10 s cap
    edf = _make_edf(tmp_path / "long.edf", secs=secs)
    tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "mvc"))
    tab._edit_path.setText(edf)
    tab._populate_channels(edf)

    done: list = []
    orig = tab._on_result
    tab._on_result = lambda r: (orig(r), done.append(r))
    tab._iniciar_calculo()

    timer = QElapsedTimer()
    timer.start()
    while not done and timer.elapsed() < 20000:
        qapp.processEvents()
    assert done, "MvcWorker did not produce a result"

    r = done[0]
    # The plotted axis covers every sample the numbers were computed from.
    assert r["n_plot"] == r["emg_envelope"].size
    assert r["t_plot"][-1] == pytest.approx(secs, abs=0.01)
    # And the minimap is scaled to that same recording, so the envelope it
    # draws lines up with the selection rectangle.
    assert tab._duracion_total == pytest.approx(secs, abs=0.01)
    assert tab._time_range._total == pytest.approx(secs, abs=0.01)
    # It still opens on a window narrow enough to read a raw trace in.
    assert tab._duracion_s == pytest.approx(10.0)
    tab.cleanup()


# ---------------------------------------------------------------------------
# The reference the recording brings with it, and the fragments the muscle-load
# analysis is measured over. Both come from the same bench observation: a
# session that calibrates with the recording already running has its maximum
# *inside the file*, and everything before the task is calibration.
# ---------------------------------------------------------------------------


def _calibrated_edf(path: Path, fs: int = 1000, secs: int = 30) -> str:
    """A recording shaped like a real session: three maximal efforts, then work.

    The first 12 s are the calibration (amplitude 1.0) and the rest is the task
    (amplitude 0.2), with the wizard's own annotation carrying the reference.
    """
    from emgteach.mvc import mvc_ref_marker

    n = fs * secs
    t = np.arange(n) / fs
    carrier = np.sin(2 * np.pi * 80 * t)
    amp = np.where(t < 12.0, 1.0, 0.2)
    ch = ChannelInfo("EMG", dimension="mV", sample_frequency=fs)
    with BufferedEdfWriter(str(path), channels=[ch]) as writer:
        writer.add_samples((carrier * amp).reshape(-1, 1).astype(float))
        writer.add_annotation(12.0, mvc_ref_marker(0, 0.70))
    return str(path)


def _run(tab, qapp) -> dict:
    done: list = []
    orig = tab._on_result
    tab._on_result = lambda r: (orig(r), done.append(r))
    tab._iniciar_calculo()
    timer = QElapsedTimer()
    timer.start()
    while not done and timer.elapsed() < 20000:
        qapp.processEvents()
    assert done, "MvcWorker did not produce a result"
    return done[0]


def _tab(edf: str):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.mvc import MvcTab
    from emgteach.gui.widgets.logger import LoggerWidget

    tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "mvc"))
    tab._edit_path.setText(edf)
    tab._populate_channels(edf)
    tab._refresh_compute_enabled()
    return tab


def test_the_recordings_own_calibration_is_the_reference(qapp, tmp_path: Path) -> None:
    """It used to ask for a second file to say what the first one already knew,
    and print "auto (not a real %MVC)" in red over a perfectly real one."""
    from emgteach.phases import FROM_CACHE

    tab = _tab(_calibrated_edf(tmp_path / "calibrado.edf"))
    r = _run(tab, qapp)
    assert r["mvc_amplitude_ref"] == pytest.approx(0.70)
    # A token, never a translated sentence: the interface branches on this.
    assert r["mvc_ref_source"] == FROM_CACHE
    tab.cleanup()


def test_without_a_calibration_there_is_no_percentage_and_no_load(
    qapp, tmp_path: Path
) -> None:
    """There used to be a third way — divide the recording by its own 95th
    percentile — and it produced a number for every panel that was wrong in
    the same direction: a task reaches about 100 % of itself, so the Jonsson
    limits reported an overloaded subject whatever the subject did.

    What survives is what does not need a maximum: the signal and its
    envelope.
    """
    from emgteach.phases import NO_CALIBRATION

    tab = _tab(_make_edf(tmp_path / "sin_calibrar.edf"))
    r = _run(tab, qapp)
    assert r["mvc_amplitude_ref"] is None
    assert r["mvc_ref_source"] == NO_CALIBRATION
    assert r["emg_norm"] is None
    assert r["apdf"] is None
    assert r["emg_envelope"].size
    tab.cleanup()


def test_the_compute_button_says_what_the_recording_will_not_give(
    qapp, tmp_path: Path
) -> None:
    """It is enabled either way — two of the three panels need no reference —
    but a recording with no calibration says so before it is pressed, not
    after."""
    from emgteach.modes import MODE_PAIR

    tab = _tab(_calibrated_edf(tmp_path / "calibrado.edf"))
    tab.apply_mode(MODE_PAIR, False)
    assert tab._btn_calcular.isEnabled()
    assert not tab._lbl_calcular_bloqueado.isVisible()
    tab.cleanup()

    sin = _tab(_make_edf(tmp_path / "pelado.edf"))
    sin.apply_mode(MODE_PAIR, False)
    assert sin._btn_calcular.isEnabled()
    assert sin._lbl_calcular_bloqueado.text()
    assert sin._lbl_calcular_bloqueado.toolTip()
    sin.cleanup()


def test_the_muscle_load_can_leave_the_calibration_out(qapp, tmp_path: Path) -> None:
    """The Jonsson APDF is about the task. Over the whole file it describes
    three maximal efforts as well, and reports a peak load that never happened
    during the work."""
    edf = _calibrated_edf(tmp_path / "calibrado.edf")

    entero = _tab(edf)
    r_todo = _run(entero, qapp)
    entero.cleanup()

    solo_trabajo = _tab(edf)
    solo_trabajo._selected_segments = [(13.0, 30.0)]
    r_tarea = _run(solo_trabajo, qapp)

    # Same reference — it comes from the annotation, which is outside the
    # analysed span. That is the point: trimming must not cost the %MVC.
    assert r_tarea["mvc_amplitude_ref"] == pytest.approx(r_todo["mvc_amplitude_ref"])
    # But the load is now the task's, not the calibration's.
    assert r_tarea["apdf"].peak.value < r_todo["apdf"].peak.value / 2
    assert r_tarea["t_plot"][-1] < 18.0
    solo_trabajo.cleanup()


def test_too_little_kept_is_refused_rather_than_analysed(
    qapp, tmp_path: Path
) -> None:
    """Below a second the DSP pipeline has nothing to pad from; the analysis
    tab refuses it in the same words."""
    tab = _tab(_calibrated_edf(tmp_path / "calibrado.edf"))
    tab._selected_segments = [(13.0, 13.4)]
    errors: list[str] = []
    tab._worker = None
    tab._iniciar_calculo()
    tab._worker.error.connect(errors.append)
    timer = QElapsedTimer()
    timer.start()
    while not errors and timer.elapsed() < 20000:
        qapp.processEvents()
    assert errors and "1 s" in errors[0]
    tab.cleanup()


def test_a_new_recording_clears_the_previous_selection(qapp, tmp_path: Path) -> None:
    """Fragments belong to a file, and so does its calibration."""
    tab = _tab(_calibrated_edf(tmp_path / "calibrado.edf"))
    tab._selected_segments = [(13.0, 30.0)]
    assert tab._refs_en_fichero
    tab._populate_channels(_make_edf(tmp_path / "otro.edf"), ask=False)
    assert tab._selected_segments == []
    assert tab._refs_en_fichero == {}
    tab.cleanup()
