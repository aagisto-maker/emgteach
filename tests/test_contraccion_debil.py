"""A weak contraction among strong ones is measured (7 November 2026).

In a free recording of the one-muscle practical on the simulated board, the
fragment editor proposed three contractions (strong, weak, strong) and the
review drew three teal bars, but the analysis measured two: the weak one had
a bar and no measured stretch. The detector had found it; the contraction
table then dropped it, because its peak was under 10 % of the span's
strongest (9.6 %). That floor is there for windows the detector lets through
on the noise of a very quiet rest, and the weak contraction was nothing of
the kind: some forty noise deviations over rest, 5-7 % of the maximal
voluntary contraction.

Ángel's decision (7 November 2026): a window is noise only if its peak is
under that 10 % **and** it barely clears the detector's line, under its
baseline plus twice its margin over it (``contractions._NOISE_MARGIN``); and a
fragment the operator accepted in the editor is a row whatever its height.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.contractions import contraction_table
from emgteach.dsp import process_offline
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.selection import Segment

FS = 1000
#: Strong, weak, strong: the weak one at 8 % of the strongest's height.
ESFUERZOS = ((2.0, 4.0, 0.14), (6.0, 8.0, 0.014), (10.0, 12.0, 0.11))
DETECCION = dict(k=3.0, min_duration_s=0.5, merge_gap_s=1.0, prominence=0.25,
                 rest_fraction=0.05)


def _senal() -> np.ndarray:
    """14 s of rest noise with the three efforts in it, in millivolts."""
    rng = np.random.default_rng(3)
    t = np.arange(14 * FS) / FS
    amplitud = np.full(t.size, 0.004)
    for a, b, v in ESFUERZOS:
        amplitud[(t >= a) & (t < b)] = v
    return rng.normal(0.0, 1.0, t.size) * amplitud


def _tabla(x: np.ndarray, **kw) -> list:
    p = process_offline(x, FS)
    return contraction_table(fs=FS, emg_raw=x, emg_filtered=p["emg_filtered"],
                             envelope=p["emg_envelope"], **kw)


def _cerca(filas, esperados) -> bool:
    """One row per expected effort, each within 0.2 s of it."""
    return len(filas) == len(esperados) and all(
        abs(f.start_s - a) < 0.2 and abs(f.end_s - b) < 0.2
        for f, (a, b, *_v) in zip(filas, esperados, strict=True))


class TestTheTable:
    def test_the_weak_contraction_is_a_row(self) -> None:
        filas = _tabla(_senal(), **DETECCION)
        assert _cerca(filas, ESFUERZOS)
        debil = filas[1]
        assert debil.rms_mv < 0.2 * min(filas[0].rms_mv, filas[2].rms_mv)

    def test_a_window_on_the_resting_noise_is_still_no_row(self) -> None:
        """What the floor is for: windows over the rest, handed to the table
        as a guided session's or the lifts' would be, give no row."""
        reposo = [Segment(0.3, 1.7), Segment(4.6, 5.6), Segment(12.6, 13.6)]
        filas = _tabla(_senal(), segments=[*reposo, Segment(2.0, 4.0)], **DETECCION)
        assert [(round(f.start_s), round(f.end_s)) for f in filas] == [(2, 4)]

    def test_a_fragment_the_operator_chose_is_a_row_however_weak(self) -> None:
        reposo = [Segment(0.3, 1.7), Segment(4.6, 5.6), Segment(12.6, 13.6)]
        filas = _tabla(_senal(), segments=[*reposo, Segment(2.0, 4.0)], chosen=True,
                       **DETECCION)
        assert len(filas) == 4


# ── Through the analysis, as the review draws it ─────────────────────────


@pytest.fixture
def registro(tmp_path: Path) -> str:
    ruta = tmp_path / "debil.edf"
    with BufferedEdfWriter(str(ruta), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(_senal())
    return str(ruta)


def _analizar(qapp, ruta: str, **kw) -> dict:
    from emgteach.fragments import default_detection
    from emgteach.modes import MODE_SINGLE, mode_detection_k, mode_rest_fraction
    from emgteach.workers import AnalysisWorker

    w = AnalysisWorker(edf_path=ruta, channel_name="FCR", detection_kwargs=default_detection(
        mode_detection_k(MODE_SINGLE), mode_rest_fraction(MODE_SINGLE)), **kw)
    res: list[dict] = []
    w.result_ready.connect(res.append)
    w.run()
    qapp.processEvents()
    assert res, "the analysis gave no result"
    return res[0]


@pytest.mark.gui
def test_every_bar_of_the_review_has_its_measured_stretch(qapp, registro: str) -> None:
    """The editor's rows (the teal bars) and the measured stretches (the
    light green ones): three and three."""
    from emgteach.fragments import recording_proposal
    from emgteach.guided import measured_in_file
    from emgteach.modes import MODE_SINGLE, mode_detection_k, mode_rest_fraction

    filas = recording_proposal(registro, k=mode_detection_k(MODE_SINGLE),
                               rest_fraction=mode_rest_fraction(MODE_SINGLE))
    medidos = measured_in_file(_analizar(qapp, registro))
    assert len(filas) == len(medidos) == 3
    for f, (a, b) in zip(filas, medidos, strict=True):
        assert f.start_s <= a < b <= f.end_s


@pytest.mark.gui
def test_a_weak_fragment_accepted_in_the_editor_is_measured(qapp, registro: str) -> None:
    """Accepted alone, the resting second before the first effort is a row."""
    r = _analizar(qapp, registro, roi_segments=[(0.3, 1.7), (2.0, 4.0)])
    assert len(r["contractions"]) == 2
