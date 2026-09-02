"""La pestaña de Normalización CVM sobre una sesión en dos fases.

Tres discrepancias medidas sobre el registro del 31-ago a las 18:29, con las
dos pestañas abiertas sobre el mismo fichero:

* **Referencias distintas.** Análisis recalculaba desde los tramos ``CAL``
  (0,0634 mV) y esta leía la anotación cacheada (0,0674 mV). El mismo fichero,
  dos varas de medir, un 6 % de diferencia.
* **Tramos distintos.** Análisis usaba los 15,2 s de la fase de registro; esta
  los 89 s enteros, calentamiento y seis esfuerzos máximos incluidos. El APDF
  de Jonsson describía así una mezcla de la tarea con la calibración: estático
  4 %, mediana 13 %, pico 84 %, cuando sobre la tarea sola son 6 / 18 / 145.
* **Una tercera vía que no debía existir.** Sin calibración se dividía la
  señal por su propio percentil 95, y entonces la tarea llega siempre a ~100 %
  y los límites de Jonsson declaran sobrecarga hiciera lo que hiciera el
  sujeto.

Lo que estas pruebas fijan es que la regla es **la misma que en Análisis**:
los tramos ``CAL`` son la fuente, ``MVC ref`` es la caché, y el tramo analizado
por defecto es ``REC``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QElapsedTimer

from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.mvc import mvc_ref_marker
from emgteach.phases import (
    FROM_CACHE,
    FROM_REPS,
    NO_CALIBRATION,
    cal_end_marker,
    cal_start_marker,
    prep_start_marker,
    rec_start_marker,
)

pytestmark = pytest.mark.gui

FS = 1000
DURACION = 50
CAL = [(4.0, 8.0, 1.00), (12.0, 16.0, 1.40), (20.0, 24.0, 1.20)]
PREP_S = 26.0
REC_S = 30.0
#: A value no repetition supports, so a result carrying it read the cache when
#: it should have recomputed.
REF_RANCIA = 0.011


def _sesion(path: Path, *, con_fases: bool = True, con_cache: bool = True) -> str:
    t = np.arange(DURACION * FS) / FS
    amp = np.full(t.size, 0.01)
    for a, b, valor in CAL:
        amp[int(a * FS) : int(b * FS)] = valor
    # The task: modest efforts, well inside the calibration.
    for a, b in ((32.0, 36.0), (40.0, 44.0)):
        amp[int(a * FS) : int(b * FS)] = 0.30
    senal = np.sin(2 * np.pi * 80 * t) * amp
    with BufferedEdfWriter(
        str(path),
        channels=[ChannelInfo("FCR", dimension="mV", sample_frequency=FS)],
    ) as w:
        w.add_samples(senal)
        if con_fases:
            for i, (a, b, _amp) in enumerate(CAL, start=1):
                w.add_annotation(a, cal_start_marker(0, i))
                w.add_annotation(b, cal_end_marker(0, i))
            w.add_annotation(PREP_S, prep_start_marker())
            w.add_annotation(REC_S, rec_start_marker())
        if con_cache:
            w.add_annotation(25.5, mvc_ref_marker(0, REF_RANCIA))
    return str(path)


def _normalizar(qapp, edf: str, **kw) -> dict:
    pytest.importorskip("mne")
    from emgteach.workers.mvc import MvcWorker

    worker = MvcWorker(edf_path=edf, channel_index=0, plot_duration_s=0, **kw)
    salida: list[dict] = []
    worker.result_ready.connect(salida.append)
    worker.error.connect(lambda m: salida.append({"error": m}))
    worker.start()
    # wait() first (it releases the GIL), then pump the queued result: a
    # processEvents() spin while the thread runs starved it on CI. See
    # test_analysis_phases._analizar.
    worker.wait(120000)
    reloj = QElapsedTimer()
    reloj.start()
    while not salida and reloj.elapsed() < 5000:
        qapp.processEvents()
    assert salida, "the normalisation produced no result"
    return salida[0]


class TestTheReferenceIsTheSameOneTheAnalysisUses:
    def test_the_spans_win_over_the_cached_annotation(
        self, qapp, tmp_path: Path
    ) -> None:
        """Both are in the file and they disagree; the spans are the source."""
        r = _normalizar(qapp, _sesion(tmp_path / "sesion.edf"))
        assert r["mvc_ref_source"] == FROM_REPS
        assert r["mvc_amplitude_ref"] != pytest.approx(REF_RANCIA)
        assert r["cal_reps_n"] == 3

    def test_the_best_repetition_is_the_reference(
        self, qapp, tmp_path: Path
    ) -> None:
        """Best of three, on the envelope — the carrier's amplitude is 1.40 and
        the rectified mean of a sine is 2/π of it."""
        r = _normalizar(qapp, _sesion(tmp_path / "sesion.edf"))
        assert r["mvc_amplitude_ref"] == pytest.approx(
            1.40 * 2 / np.pi, rel=0.05)

    def test_a_recording_from_before_the_flow_uses_its_annotation(
        self, qapp, tmp_path: Path
    ) -> None:
        """Every file already on the teacher's disk. It still opens, and it
        still gets a % MVC — from the only maximum it has."""
        r = _normalizar(qapp, _sesion(tmp_path / "vieja.edf", con_fases=False))
        assert r["mvc_ref_source"] == FROM_CACHE
        assert r["mvc_amplitude_ref"] == pytest.approx(REF_RANCIA)


class TestTheAnalysedSpanIsTheRecordingPhase:
    def test_the_calibration_falls_outside_without_being_asked(
        self, qapp, tmp_path: Path
    ) -> None:
        """It used to take the whole file unless the operator drew fragments by
        eye — on the one decision that must not be eyeballed, since the
        application knows exactly where the calibration was."""
        r = _normalizar(qapp, _sesion(tmp_path / "sesion.edf"))
        assert len(r["emg_raw"]) / r["fs"] == pytest.approx(
            DURACION - REC_S, abs=0.1)

    def test_the_load_is_the_tasks_and_not_the_calibrations(
        self, qapp, tmp_path: Path
    ) -> None:
        """Over the whole file the APDF describes three maximal efforts too,
        and reports a peak load that never happened during the work."""
        r = _normalizar(qapp, _sesion(tmp_path / "sesion.edf"))
        entero = _normalizar(
            qapp, _sesion(tmp_path / "sesion.edf"),
            roi_segments=[(0.0, float(DURACION))],
        )
        assert r["apdf"].peak.value < entero["apdf"].peak.value / 2

    def test_chosen_fragments_still_win(self, qapp, tmp_path: Path) -> None:
        """The phase is the default, not a lock: the fragment editor is how a
        single effort inside the recording gets looked at on its own."""
        r = _normalizar(
            qapp, _sesion(tmp_path / "sesion.edf"),
            roi_segments=[(32.0, 36.0)],
        )
        assert len(r["emg_raw"]) / r["fs"] == pytest.approx(4.0, abs=0.1)

    def test_a_recording_with_no_phases_is_analysed_whole(
        self, qapp, tmp_path: Path
    ) -> None:
        r = _normalizar(qapp, _sesion(tmp_path / "vieja.edf", con_fases=False))
        assert len(r["emg_raw"]) / r["fs"] == pytest.approx(DURACION, abs=0.1)


class TestWithoutACalibrationNothingIsInvented:
    def test_no_percentage_and_no_load(self, qapp, tmp_path: Path) -> None:
        r = _normalizar(qapp, _sesion(
            tmp_path / "pelada.edf", con_fases=False, con_cache=False))
        assert r["mvc_amplitude_ref"] is None
        assert r["mvc_ref_source"] == NO_CALIBRATION
        assert r["emg_norm"] is None
        assert r["apdf"] is None
        assert r["mean_norm"] is None

    def test_what_does_not_need_a_maximum_is_still_drawn(
        self, qapp, tmp_path: Path
    ) -> None:
        """The signal and its envelope are two of the three panels, and they
        do not depend on a reference. Refusing to open the file at all would
        teach the student nothing about what is missing."""
        r = _normalizar(qapp, _sesion(
            tmp_path / "pelada.edf", con_fases=False, con_cache=False))
        assert r["emg_envelope"].size
        assert r["emg_filtered"].size

    def test_the_report_survives_a_result_with_no_reference(
        self, qapp, tmp_path: Path
    ) -> None:
        """It is the document the student hands in; it has to say what is
        missing rather than fail to build."""
        pytest.importorskip("reportlab")
        from emgteach.reports import build_mvc_report

        r = _normalizar(qapp, _sesion(
            tmp_path / "pelada.edf", con_fases=False, con_cache=False))
        salida = tmp_path / "informe.pdf"
        build_mvc_report(str(salida), r, {"student": "X"})
        assert salida.exists() and salida.stat().st_size > 1000
