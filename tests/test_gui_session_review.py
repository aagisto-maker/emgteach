"""Al parar, la sesión entera en la misma pestaña donde se grabó.

Pedido desde el banco: «sería útil poder ver el registro y navegar por él en la
pestaña de registro, una vez terminado». La versión modesta — desplazarse y
verlo grosso modo — y no un segundo visor con filtros y paneles, que sería
duplicar la pestaña de análisis dentro de la de adquisición.

La decisión de diseño que estas pruebas fijan: **se relee el EDF**, no se
guarda la sesión en memoria. Las gráficas en vivo son un buffer circular de
30 s, así que la alternativa habría sido acumular la sesión en paralelo al
fichero; releerlo cuesta memoria cero y garantiza que lo que se revisa es
exactamente lo que se guardó, anotaciones incluidas.

Lo que se comprueba aquí es lo que se puede romper sin darse cuenta: que el
refresco en vivo no repinte el buffer circular encima de la sesión a los 33 ms,
y que grabar otra vez devuelva la pestaña a su estado de siempre.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.phases import (
    CALIBRATION,
    PREPARATION,
    RECORDING,
    WARMUP,
    cal_end_marker,
    cal_start_marker,
    parse_phase_markers,
    phase_spans,
    prep_start_marker,
    rec_start_marker,
    warmup_start_marker,
)

pytestmark = pytest.mark.gui

FS = 1000
DURACION = 40
CAL = {0: [(6.0, 9.0), (11.0, 14.0)], 1: [(17.0, 20.0), (22.0, 25.0)]}
PREP_S = 26.0
REC_S = 30.0


def _sesion(path: Path, *, con_fases: bool = True) -> str:
    t = np.arange(DURACION * FS) / FS
    amp = np.full(t.size, 0.01)
    for reps in CAL.values():
        for a, b in reps:
            amp[int(a * FS) : int(b * FS)] = 0.5
    amp[int(32.0 * FS) : int(35.0 * FS)] = 0.2
    senal = np.sin(2 * np.pi * 80 * t) * amp
    canales = [
        ChannelInfo("FCR", dimension="mV", sample_frequency=FS),
        ChannelInfo("ECR", dimension="mV", sample_frequency=FS),
    ]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(senal, senal * 0.5)
        if con_fases:
            w.add_annotation(0.1, warmup_start_marker())
            for canal, reps in CAL.items():
                for i, (a, b) in enumerate(reps, start=1):
                    w.add_annotation(a, cal_start_marker(canal, i))
                    w.add_annotation(b, cal_end_marker(canal, i))
            w.add_annotation(PREP_S, prep_start_marker())
            w.add_annotation(REC_S, rec_start_marker())
    return str(path)


class TestTheSessionIsDividedIntoItsStretches:
    """`phase_spans` — Qt-free, so it can be checked on its own terms."""

    def _fases(self):
        marcas = [(0.1, warmup_start_marker())]
        for canal, reps in CAL.items():
            for i, (a, b) in enumerate(reps, start=1):
                marcas += [(a, cal_start_marker(canal, i)),
                           (b, cal_end_marker(canal, i))]
        marcas += [(PREP_S, prep_start_marker()), (REC_S, rec_start_marker())]
        return parse_phase_markers(marcas)

    def test_every_stretch_the_session_had(self) -> None:
        tramos = phase_spans(self._fases(), float(DURACION),
                             channel_names={0: "FCR", 1: "ECR"})
        assert [t.kind for t in tramos] == [
            WARMUP, CALIBRATION, CALIBRATION, CALIBRATION, CALIBRATION,
            PREPARATION, RECORDING,
        ]

    def test_the_warm_up_ends_where_the_first_effort_starts(self) -> None:
        primero, segundo = phase_spans(self._fases(), float(DURACION))[:2]
        assert primero.end_s == pytest.approx(segundo.start_s)

    def test_the_rest_between_efforts_is_left_unshaded(self) -> None:
        """Shading it would fill the picture edge to edge and the efforts
        would stop standing out, which is the one thing the drawing is for."""
        tramos = phase_spans(self._fases(), float(DURACION))
        cal = [t for t in tramos if t.kind == CALIBRATION]
        assert cal[1].start_s > cal[0].end_s

    def test_each_effort_carries_its_muscle_and_its_number(self) -> None:
        tramos = phase_spans(self._fases(), float(DURACION),
                             channel_names={0: "FCR", 1: "ECR"})
        assert [t.label for t in tramos if t.kind == CALIBRATION] == [
            "FCR 1", "FCR 2", "ECR 1", "ECR 2"]

    def test_the_recording_runs_to_the_end_of_the_file(self) -> None:
        ultimo = phase_spans(self._fases(), float(DURACION))[-1]
        assert ultimo.kind == RECORDING
        assert ultimo.end_s == pytest.approx(DURACION)

    def test_a_recording_with_no_phases_has_no_stretches(self) -> None:
        """Every file made before the guided flow. Nothing to shade, and the
        review still shows the signal."""
        assert phase_spans(parse_phase_markers([]), 40.0) == ()

    def test_nothing_runs_past_the_end_of_a_truncated_file(self) -> None:
        """A recording cut short by a disconnection still has its REC start."""
        tramos = phase_spans(self._fases(), 31.0)
        assert all(t.end_s <= 31.0 for t in tramos)


class TestTheReviewOnTheAcquisitionTab:
    def _tab(self, qapp):
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.acquisition import AcquisitionTab
        from emgteach.gui.widgets.logger import LoggerWidget

        ajustes = QSettings("emgteach-test", "review")
        ajustes.clear()
        tab = AcquisitionTab(LoggerWidget(), ajustes)
        return tab

    def _extension(self, tab) -> float:
        """How many seconds the first curve spans.

        Not the number of points: the review turns on pyqtgraph's decimation,
        so what a curve hands back is what is being drawn, not what was given
        to it. The span is the thing under test anyway — the live window is
        thirty seconds and the session is forty.
        """
        x, _y = tab._curves_raw[0].getData()
        return 0.0 if x is None or not len(x) else float(x[-1])

    def test_stopping_puts_the_whole_session_on_the_plots(
        self, qapp, tmp_path: Path
    ) -> None:
        pytest.importorskip("mne")
        tab = self._tab(qapp)
        tab._on_finished(_sesion(tmp_path / "sesion.edf"))
        assert tab._revisando
        assert self._extension(tab) == pytest.approx(DURACION, abs=0.5)

    def test_the_live_refresh_does_not_paint_over_it(
        self, qapp, tmp_path: Path
    ) -> None:
        """It fires every 33 ms and its ring buffer holds the last 30 s. Left
        alone it would replace the session with its own tail on the next
        frame, and the review would last exactly one repaint."""
        pytest.importorskip("mne")
        tab = self._tab(qapp)
        tab._on_finished(_sesion(tmp_path / "sesion.edf"))
        antes = self._extension(tab)
        tab._new_data = True
        tab._refresh_plots(force=True)
        assert self._extension(tab) == pytest.approx(antes)

    def test_the_phases_are_shaded(self, qapp, tmp_path: Path) -> None:
        pytest.importorskip("mne")
        tab = self._tab(qapp)
        tab._on_finished(_sesion(tmp_path / "sesion.edf"))
        assert tab._revision_items

    def test_a_recording_without_phases_is_still_shown(
        self, qapp, tmp_path: Path
    ) -> None:
        pytest.importorskip("mne")
        tab = self._tab(qapp)
        tab._on_finished(_sesion(tmp_path / "vieja.edf", con_fases=False))
        assert tab._revisando
        assert self._extension(tab) == pytest.approx(DURACION, abs=0.5)

    def test_a_new_session_goes_back_to_the_live_view(
        self, qapp, tmp_path: Path
    ) -> None:
        pytest.importorskip("mne")
        tab = self._tab(qapp)
        tab._on_finished(_sesion(tmp_path / "sesion.edf"))
        tab.reset()
        assert not tab._revisando
        assert not tab._revision_items
        assert self._extension(tab) != pytest.approx(DURACION, abs=0.5)

    def test_the_next_recording_gets_its_own_axis_back(
        self, qapp, tmp_path: Path
    ) -> None:
        """Reported from the bench: after a new session the recording was
        "advancing over an empty canvas, very small".

        Showing the session sets an explicit X range, and in pyqtgraph that
        *turns auto-range off*. The live view has no range of its own — it
        relies on auto-range to follow its sliding window — so the next
        recording drew its five seconds inside the previous session's forty.
        """
        pytest.importorskip("mne")
        tab = self._tab(qapp)
        tab._on_finished(_sesion(tmp_path / "sesion.edf"))
        tab.reset()

        # One live window's worth of data, as the worker would deliver it —
        # including the sample count, which the worker also advances and which
        # is now what tells a cleared tab from one with a signal on it.
        for c in range(2):
            tab._buf_raw[c].extend(np.zeros(tab._n_visible))
            tab._buf_env[c].extend(np.zeros(tab._n_visible))
        tab._total_samples += tab._n_visible
        tab._new_data = True
        tab._refresh_plots(force=True)
        qapp.processEvents()

        izq, der = tab._plot_raw.getViewBox().viewRange()[0]
        assert der - izq < DURACION / 2, (
            "the live window is still drawn inside the session's axis")

    def test_a_file_it_cannot_read_loses_the_review_and_nothing_else(
        self, qapp, tmp_path: Path
    ) -> None:
        """The recording is on disk either way; a broken review must not take
        the tab down with it."""
        roto = tmp_path / "roto.edf"
        roto.write_bytes(b"not an edf at all")
        tab = self._tab(qapp)
        tab._on_finished(str(roto))
        assert not tab._revisando
