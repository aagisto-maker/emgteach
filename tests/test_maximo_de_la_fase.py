"""The task maximum is a maximum of the recording phase, not of the selection.

Read on the analysed span, the figure changed with the fragments chosen: a
burst outside them was not seen, and two fragments cut inside their
contractions and glued together lifted the envelope above either real peak.
It is now read on the recording phase uncut — REC start to the end of the
file, the whole file when there are no phases — whatever is analysed.

The fixture is a two-phase session with a movement on letting go after the
last manoeuvre: the strongest thing in the phase, and the one the editor's
fragments would leave out.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QElapsedTimer

from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.phases import (
    cal_end_marker,
    cal_start_marker,
    prep_start_marker,
    rec_start_marker,
)

pytestmark = pytest.mark.gui

FS = 1000
DURACION = 60
CAL = {
    0: [(2.0, 6.0, 1.00), (8.0, 12.0, 1.40), (14.0, 18.0, 1.20)],
    1: [(20.0, 24.0, 0.50), (26.0, 30.0, 0.70), (32.0, 36.0, 0.60)],
}
PREP_S = 37.0
REC_S = 39.0
#: Two efforts in the recording phase, and a stronger movement on letting go.
ESFUERZOS = ((42.0, 46.0), (50.0, 54.0))
SUELTA = (56.0, 58.0)


def _canal(amplitudes, *, con_suelta: bool = True) -> np.ndarray:
    t = np.arange(DURACION * FS) / FS
    portadora = np.sin(2 * np.pi * 80 * t)
    amp = np.full(t.size, 0.01)
    for a, b, valor in amplitudes:
        amp[int(a * FS): int(b * FS)] = valor
    for a, b in ESFUERZOS:
        amp[int(a * FS): int(b * FS)] = 0.30
    if con_suelta:
        amp[int(SUELTA[0] * FS): int(SUELTA[1] * FS)] = 0.50
    return portadora * amp


def _sesion(path: Path, *, con_fases: bool = True) -> str:
    canales = [
        ChannelInfo("FCR", dimension="mV", sample_frequency=FS),
        ChannelInfo("ECR", dimension="mV", sample_frequency=FS),
    ]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(_canal(CAL[0]), _canal(CAL[1], con_suelta=False))
        if con_fases:
            for canal, reps in CAL.items():
                for i, (a, b, _amp) in enumerate(reps, start=1):
                    w.add_annotation(a, cal_start_marker(canal, i))
                    w.add_annotation(b, cal_end_marker(canal, i))
            w.add_annotation(PREP_S, prep_start_marker())
            w.add_annotation(REC_S, rec_start_marker())
    return str(path)


def _analizar(qapp, edf: str, **kw) -> dict:
    pytest.importorskip("mne")
    from emgteach.workers import AnalysisWorker

    worker = AnalysisWorker(
        edf_path=edf, channel_name="FCR", channel_name_2="ECR", **kw
    )
    salida: list[dict] = []
    worker.result_ready.connect(salida.append)
    worker.start()
    worker.wait(120000)
    reloj = QElapsedTimer()
    reloj.start()
    while not salida and reloj.elapsed() < 5000:
        qapp.processEvents()
    assert salida, "the analysis produced no result"
    return salida[0]


class TestAMaximumOfThePhase:
    def test_fragments_that_leave_the_strongest_burst_out_still_see_it(
        self, qapp, tmp_path: Path
    ) -> None:
        edf = _sesion(tmp_path / "sesion.edf")
        entero = _analizar(qapp, edf)
        con_fragmentos = _analizar(
            qapp, edf, roi_segments=[(42.5, 45.5), (50.5, 53.5)],
            roi_labels=["Flexion", "Flexion"],
        )
        # The movement on letting go is the strongest thing in the phase.
        assert entero["task_peak_pct"]["FCR"] > 30.0
        assert con_fragmentos["task_peak_pct"]["FCR"] == pytest.approx(
            entero["task_peak_pct"]["FCR"], abs=0.05)
        assert con_fragmentos["task_peak_pct"]["ECR"] == pytest.approx(
            entero["task_peak_pct"]["ECR"], abs=0.05)
        # And the panels still show the fragments, not the phase.
        assert con_fragmentos["duration"] == pytest.approx(6.0, abs=0.05)
        assert con_fragmentos["task_peak_span_s"] == pytest.approx(
            (REC_S, DURACION), abs=0.05)

    def test_fragments_cut_inside_the_contractions_cannot_lift_it(
        self, qapp, tmp_path: Path
    ) -> None:
        """Glued activity against activity, the concatenation's envelope
        could exceed the real peak; the phase's cannot."""
        edf = _sesion(tmp_path / "sesion.edf")
        entero = _analizar(qapp, edf)
        pegados = _analizar(
            qapp, edf, roi_segments=[(43.0, 44.0), (51.0, 52.0), (56.5, 57.5)],
            roi_labels=["Flexion", "Flexion", "Grip"],
        )
        assert pegados["task_peak_pct"]["FCR"] == pytest.approx(
            entero["task_peak_pct"]["FCR"], abs=0.05)

    def test_a_window_is_a_selection_too(self, qapp, tmp_path: Path) -> None:
        edf = _sesion(tmp_path / "sesion.edf")
        entero = _analizar(qapp, edf)
        ventana = _analizar(qapp, edf, roi_start_s=41.0, roi_end_s=47.0)
        assert ventana["duration"] == pytest.approx(6.0, abs=0.05)
        assert ventana["task_peak_pct"]["FCR"] == pytest.approx(
            entero["task_peak_pct"]["FCR"], abs=0.05)

    def test_without_phases_the_phase_is_the_whole_file(
        self, qapp, tmp_path: Path
    ) -> None:
        """A recording made before the two-phase flow: the reference is its
        cached annotation and the phase is the file."""
        from emgteach.mvc import mvc_ref_marker

        path = tmp_path / "antiguo.edf"
        canales = [
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS),
            ChannelInfo("ECR", dimension="mV", sample_frequency=FS),
        ]
        with BufferedEdfWriter(str(path), channels=canales) as w:
            w.add_samples(_canal([]), _canal([], con_suelta=False))
            w.add_annotation(0.5, mvc_ref_marker(0, 0.5))
            w.add_annotation(0.6, mvc_ref_marker(1, 0.5))
        entero = _analizar(qapp, str(path))
        con_fragmentos = _analizar(
            qapp, str(path), roi_segments=[(42.5, 45.5)], roi_labels=["Flexion"])
        assert entero["task_peak_span_s"] == pytest.approx((0.0, DURACION), abs=0.05)
        assert con_fragmentos["task_peak_pct"]["FCR"] == pytest.approx(
            entero["task_peak_pct"]["FCR"], abs=0.05)
