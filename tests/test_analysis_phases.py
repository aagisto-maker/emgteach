"""Reading a two-phase recording: which span is analysed, and whose maximum.

Step 3. The acquisition now writes the shape of the session into the file
(step 2) and :mod:`emgteach.phases` knows how to read it (step 1); this is
where the analysis starts obeying it. Two things have to be true of a
recording made with the new flow:

* **the analysed span is the recording phase.** The calibration and the pause
  before it are in the file and out of the analysis, by construction rather
  than by the operator trimming them off by eye;
* **the reference comes from the calibration spans**, not from the cached
  annotation — which is what makes discarding a repetition, later, able to
  move every %MVC in the recording.

The fixture writes a session shaped like a real one, with the two muscles
calibrated in turn, and a **stale** ``MVC ref`` annotation: a value no
repetition in the file supports. A worker that read the cache would return it,
and every assertion about provenance would still pass on a wrong number.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QElapsedTimer

from emgteach.dsp import process_offline
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.mvc import mvc_from_reps, mvc_ref_marker
from emgteach.phases import (
    FROM_CACHE,
    FROM_REPS,
    NO_CALIBRATION,
    cal_end_marker,
    cal_start_marker,
    parse_phase_markers,
    prep_start_marker,
    rec_start_marker,
    slice_reps,
)
from emgteach.profiles import EMG_PROFILE

pytestmark = pytest.mark.gui

FS = 1000
DURACION = 60
#: (start, end, amplitude) per repetition. Deliberately unequal, and the two
#: muscles calibrated one after the other, as the wizard does it.
CAL = {
    0: [(2.0, 6.0, 1.00), (8.0, 12.0, 1.40), (14.0, 18.0, 1.20)],
    1: [(20.0, 24.0, 0.50), (26.0, 30.0, 0.70), (32.0, 36.0, 0.60)],
}
PREP_S = 37.0
REC_S = 39.0
#: A value no repetition supports: if the analysis returns this, it read the
#: cache when it should have recomputed.
REF_RANCIA = 0.011


def _canal(amplitudes, arranca_activo: bool = False,
           pausa_ruidosa: bool = False) -> np.ndarray:
    t = np.arange(DURACION * FS) / FS
    portadora = np.sin(2 * np.pi * 80 * t)
    amp = np.full(t.size, 0.01)
    for a, b, valor in amplitudes:
        amp[int(a * FS) : int(b * FS)] = valor
    # a couple of bursts in the recording phase, well below the maxima
    for a, b in ((42.0, 46.0), (50.0, 54.0)):
        amp[int(a * FS) : int(b * FS)] = 0.30
    if arranca_activo:
        # The subject starts the moment the countdown ends, which is what the
        # countdown told them to do. The opening second of the analysed span
        # then holds the ramp into the first contraction.
        i0 = int(REC_S * FS)
        rampa = np.linspace(0.01, 0.30, int(1.0 * FS))
        amp[i0 : i0 + rampa.size] = rampa
        amp[i0 + rampa.size : int((REC_S + 3.0) * FS)] = 0.30
    if pausa_ruidosa:
        # The subject kept working through the countdown. Then there really
        # is no rest in the file, and saying so is the right answer.
        amp[int(PREP_S * FS) : int(REC_S * FS)] = 0.30
    return portadora * amp


def _sesion(path: Path, *, con_fases: bool = True, con_cache: bool = True,
            arranca_activo: bool = False, pausa_ruidosa: bool = False) -> str:
    canales = [
        ChannelInfo("FCR", dimension="mV", sample_frequency=FS),
        ChannelInfo("ECR", dimension="mV", sample_frequency=FS),
    ]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(                                   # one block per channel
            _canal(CAL[0], arranca_activo=arranca_activo,
                   pausa_ruidosa=pausa_ruidosa),
            _canal(CAL[1], arranca_activo=arranca_activo,
                   pausa_ruidosa=pausa_ruidosa),
        )
        if con_fases:
            for canal, reps in CAL.items():
                for i, (a, b, _amp) in enumerate(reps, start=1):
                    w.add_annotation(a, cal_start_marker(canal, i))
                    w.add_annotation(b, cal_end_marker(canal, i))
            w.add_annotation(PREP_S, prep_start_marker())
            w.add_annotation(REC_S, rec_start_marker())
        if con_cache:
            w.add_annotation(36.5, mvc_ref_marker(0, REF_RANCIA))
            w.add_annotation(36.6, mvc_ref_marker(1, REF_RANCIA))
        w.add_annotation(44.0, "Grip")
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
    reloj = QElapsedTimer()
    reloj.start()
    while not salida and reloj.elapsed() < 30000:
        qapp.processEvents()
    worker.wait(5000)
    assert salida, "the analysis produced no result"
    return salida[0]


def _referencia_esperada(edf: str, canal: str, indice: int) -> float:
    """What the calibration spans of this file actually say, computed here.

    Deliberately independent of the worker: asserting only "different from the
    stale annotation" would pass for a reference that was wrong in some other
    way.
    """
    from emgteach.io import read_edf_mne

    datos = read_edf_mne(edf, canal)
    env = process_offline(datos["emg_raw"], datos["sfreq"])["emg_envelope"]
    fases = parse_phase_markers(datos.get("markers", []))
    trozos = slice_reps(env, datos["sfreq"], fases.reps_for(indice))
    return mvc_from_reps(
        trozos, EMG_PROFILE.mvc_percentile,
        window_samples=round(EMG_PROFILE.mvc_peak_window_s * datos["sfreq"]),
    )


class TestTheAnalysedSpanIsTheRecordingPhase:
    def test_the_calibration_falls_outside(self, qapp, tmp_path: Path) -> None:
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"))
        assert r["duration"] == pytest.approx(DURACION - REC_S, abs=0.1)
        assert r["duration"] < DURACION / 2

    def test_a_recording_with_no_phases_is_analysed_whole(
        self, qapp, tmp_path: Path
    ) -> None:
        """Everything recorded before this change still opens, and still gets
        the whole file analysed."""
        r = _analizar(qapp, _sesion(tmp_path / "vieja.edf", con_fases=False))
        assert r["duration"] == pytest.approx(DURACION, abs=0.1)

    def test_chosen_fragments_still_win(self, qapp, tmp_path: Path) -> None:
        """The recording phase is a default, not a cage: an operator who picks
        fragments has looked at the trace and decided."""
        r = _analizar(
            qapp, _sesion(tmp_path / "sesion.edf"),
            roi_segments=[(42.0, 46.0)],
        )
        assert r["duration"] == pytest.approx(4.0, abs=0.1)

    def test_the_preparation_pause_is_not_analysed_either(
        self, qapp, tmp_path: Path
    ) -> None:
        """It is signal, it is in the file, and nobody looks at it. That is the
        whole trade for not stopping the acquisition."""
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"))
        assert r["duration"] < DURACION - PREP_S


class TestWhoseMaximumTheReferenceIs:
    def test_it_is_recomputed_from_the_spans_not_read_from_the_cache(
        self, qapp, tmp_path: Path
    ) -> None:
        edf = _sesion(tmp_path / "sesion.edf")
        r = _analizar(qapp, edf)
        assert r["mvc_ref_source"] == FROM_REPS
        assert r["mvc_ref"] != pytest.approx(REF_RANCIA)
        assert r["mvc_ref"] == pytest.approx(
            _referencia_esperada(edf, "FCR", 0), rel=0.02
        )

    def test_the_second_muscle_gets_its_own(self, qapp, tmp_path: Path) -> None:
        """Comparing two muscles is comparing two percentages of two different
        maxima. One reference used for both is the bug this replaces."""
        edf = _sesion(tmp_path / "sesion.edf")
        r = _analizar(qapp, edf)
        assert r["mvc_ref_source_2"] == FROM_REPS
        assert r["mvc_ref_2"] == pytest.approx(
            _referencia_esperada(edf, "ECR", 1), rel=0.02
        )
        assert r["mvc_ref_2"] < r["mvc_ref"]      # the extensor was weaker here

    def test_a_file_with_only_the_cached_value_still_has_a_reference(
        self, qapp, tmp_path: Path
    ) -> None:
        """Recorded before the two-phase flow: the number is right, the
        repetitions are simply not there to inspect."""
        r = _analizar(
            qapp, _sesion(tmp_path / "vieja.edf", con_fases=False)
        )
        assert r["mvc_ref_source"] == FROM_CACHE
        assert r["mvc_ref"] == pytest.approx(REF_RANCIA)

    def test_a_file_with_no_calibration_at_all_says_so(
        self, qapp, tmp_path: Path
    ) -> None:
        r = _analizar(
            qapp,
            _sesion(tmp_path / "pelada.edf", con_fases=False, con_cache=False),
        )
        assert r["mvc_ref"] is None
        assert r["mvc_ref_source"] == NO_CALIBRATION

    def test_the_repetitions_travel_with_the_result(
        self, qapp, tmp_path: Path
    ) -> None:
        """Step 4 will offer them as a list to keep or discard; without them in
        the result there is nothing to offer."""
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"))
        assert len(r["cal_reps"][0]) == 3
        assert len(r["cal_reps"][1]) == 3
        assert r["rec_start_s"] == pytest.approx(REC_S, abs=0.1)


class TestThePhasesAreNotEventsInTheRecording:
    def test_they_do_not_reach_the_marker_list(self, qapp, tmp_path: Path) -> None:
        """Left in, each would draw a line across every panel and open a window
        in the co-activation table, which reports one row per marked phase."""
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"))
        etiquetas = [str(d) for _t, d in r["markers"]]
        assert not any(
            e.startswith(("CAL ", "PREP", "REC ")) for e in etiquetas
        ), etiquetas

    def test_the_students_own_mark_survives_and_is_rebased(
        self, qapp, tmp_path: Path
    ) -> None:
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"))
        marcas = {str(d): float(t) for t, d in r["markers"]}
        assert "Grip" in marcas
        # written at t=44 in the file, which is 5 s into the recording phase
        assert marcas["Grip"] == pytest.approx(44.0 - REC_S, abs=0.2)


class TestTheBaselineComesFromThePause:
    """The flow creates the problem the baseline check exists to warn about.

    The analysed span begins at ``REC start``, and the countdown before it
    tells the subject the recording is starting — so they start. The opening
    second then holds the ramp into the first contraction, its spread is large,
    and the resting threshold lands above everything that follows: nothing is
    detected, and the application advises "record a couple of quiet seconds
    first", which it has itself made impossible.

    The preparation pause is quiet by design and already in the file.
    """

    def test_a_session_that_starts_working_at_once_still_has_a_baseline(
        self, qapp, tmp_path: Path
    ) -> None:
        r = _analizar(
            qapp, _sesion(tmp_path / "arranca.edf", arranca_activo=True)
        )
        assert r["emg_baseline_usable"] is True
        assert r["emg_baseline_usable_2"] is True

    def test_a_pause_that_was_not_quiet_rescues_nothing(
        self, qapp, tmp_path: Path
    ) -> None:
        """The other half. Without it the test above would pass on a change
        that simply stopped reporting the problem: if the subject worked
        through the countdown there is no rest anywhere in the file, and
        saying so is the right answer."""
        r = _analizar(
            qapp,
            _sesion(tmp_path / "sin_pausa.edf", arranca_activo=True,
                    pausa_ruidosa=True),
        )
        assert r["emg_baseline_usable"] is False

    def test_a_quiet_start_is_fine_either_way(self, qapp, tmp_path: Path) -> None:
        assert _analizar(
            qapp, _sesion(tmp_path / "sesion.edf")
        )["emg_baseline_usable"] is True
