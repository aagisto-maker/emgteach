"""«La calibración no capturó un máximo»: cuándo se dice y cuándo se calla.

The reference *is* the strongest half second of a maximal effort. So the test
is a definition, not a heuristic: if the task's own strongest half second beats
it, the effort was not maximal. What the threshold buys is only a margin for
the honest overshoot of a brisk contraction against an isometric maximum.

The margin is not fitted. Across twenty-one bench recordings, every session
whose calibration was sound peaked at 91-124 % of its own reference and every
session with a bad one peaked at 179-1308 %; 150 % sits in the empty gap.

This file exists because the earlier rule asked the wrong question. It fired
only when the recording spent more than a tenth of its time above the
threshold, which a burst task never does: on the session that exposed it the
flexor's reference was a third of what the muscle produced during the task,
the envelope reached 187 % — and the recording was above 150 % for 3 % of its
length, so nothing was said. Six of the twenty-one recordings were bad and
quiet enough to slip through in exactly that way.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QElapsedTimer

from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.mvc import mvc_ref_marker
from emgteach.profiles import EMG_PROFILE

pytestmark = pytest.mark.gui

FS = 1000
DURACION = 30


def _sesion(path: Path, *, pico_rel: float, ancho_s: float = 1.0) -> str:
    """A recording whose task peaks at ``pico_rel`` times its own reference.

    The burst is deliberately short: what is under test is a criterion that
    must not depend on how long the muscle stays up there.
    """
    ref = 0.10
    t = np.arange(DURACION * FS) / FS
    amp = np.full(t.size, 0.004)
    # A handful of ordinary efforts, well inside the reference…
    for a in (4.0, 8.0, 12.0, 16.0):
        amp[int(a * FS) : int((a + 1.5) * FS)] = ref * 0.6
    # …and one that beats it. Amplitude to envelope: the rectified mean of a
    # sine is 2/π of its amplitude, and that is what the reference measures.
    pico = pico_rel * ref * np.pi / 2.0
    amp[int(22.0 * FS) : int((22.0 + ancho_s) * FS)] = pico
    senal = np.sin(2 * np.pi * 80 * t) * amp

    canales = [ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(senal)
        w.add_annotation(0.5, mvc_ref_marker(0, ref))
    return str(path)


def _avisos(qapp, edf: str) -> tuple[list[str], dict]:
    pytest.importorskip("mne")
    from emgteach.workers import AnalysisWorker

    worker = AnalysisWorker(edf_path=edf, channel_name="FCR")
    salida: list[dict] = []
    registro: list[str] = []
    worker.result_ready.connect(salida.append)
    worker.log.connect(registro.append)
    worker.start()
    # wait() first (it releases the GIL), then pump the queued signals: a
    # processEvents() spin while the thread runs starved it on CI. See
    # test_analysis_phases._analizar.
    worker.wait(120000)
    reloj = QElapsedTimer()
    reloj.start()
    while not salida and reloj.elapsed() < 5000:
        qapp.processEvents()
    assert salida, "the analysis produced no result"
    return [m for m in registro if m.startswith("⚠")], salida[0]


class TestATaskThatBeatsItsOwnCalibration:
    def test_a_brief_peak_well_over_the_reference_is_reported(
        self, qapp, tmp_path: Path
    ) -> None:
        """One second in thirty. The old rule needed three."""
        avisos, r = _avisos(qapp, _sesion(tmp_path / "mala.edf", pico_rel=2.5))
        assert r.get("mvc_implausible")
        assert any("FCR" in m for m in avisos)

    def test_what_is_recorded_is_the_peak_it_reached(
        self, qapp, tmp_path: Path
    ) -> None:
        """Not the share of time, which is what the figure used to be — the
        overlay panel words its caption from this."""
        _, r = _avisos(qapp, _sesion(tmp_path / "mala.edf", pico_rel=2.5))
        assert r["mvc_implausible"] == pytest.approx(250, rel=0.1)

    def test_the_honest_overshoot_of_a_brisk_contraction_is_not(
        self, qapp, tmp_path: Path
    ) -> None:
        """110 % is a dynamic effort against an isometric maximum, not a bad
        calibration. Crying wolf here teaches the operator to ignore it."""
        avisos, r = _avisos(qapp, _sesion(tmp_path / "buena.edf", pico_rel=1.1))
        assert not r.get("mvc_implausible")
        assert not avisos

    def test_a_long_stretch_above_the_threshold_is_still_reported(
        self, qapp, tmp_path: Path
    ) -> None:
        """The case the old rule did catch has to keep being caught."""
        avisos, r = _avisos(
            qapp, _sesion(tmp_path / "peor.edf", pico_rel=2.5, ancho_s=8.0))
        assert r.get("mvc_implausible")
        assert avisos

    def test_the_threshold_lives_in_the_profile(self) -> None:
        assert EMG_PROFILE.mvc_implausible_pct == pytest.approx(150.0)
        assert not hasattr(EMG_PROFILE, "mvc_implausible_share"), (
            "the share condition was removed; it is strictly stronger than "
            "the peak test at the same threshold, so it never fired alone"
        )
