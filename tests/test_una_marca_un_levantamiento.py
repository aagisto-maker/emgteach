"""Each load marker of the guided force-velocity wizard is one lift, and only one.

The bench found the study averaging in lifts nobody asked for. With the
board, the subject lifted once right after the recording phase began, before
the first cue: the fragment editor proposed seven lifts for six markers. With
the simulated board, which went on lifting after the wizard had finished, it
proposed ten, and the study put two of the strays under the heaviest load —
the analysis copied each marker to every fragment starting within six and a
half seconds of it, and the table gave each contraction the last marker
before it.

Three places now share one rule (:func:`emgteach.force_velocity.marker_owners`):
the editor proposes one row per marker, the analysis gives each marker's load
to one contraction, and the tuned file writes one marker per fragment. A lift
no marker announced has no load, and the study starts it unticked.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.contractions import Contraction, load_of_each
from emgteach.force_velocity import lift_windows_s, marker_owners, markers_by_span

#: The six cues of the bench recording (3, 3, 5, 5, 7 and 7 kg), in seconds.
CUES = [(48.2, 3.0), (54.8, 3.0), (61.5, 5.0), (68.2, 5.0), (74.9, 7.0), (81.6, 7.0)]


def _fila(n: int, a: float, b: float) -> Contraction:
    return Contraction(n, a, b, "M", 0.1, None, None)


class TestMarkerOwners:
    def test_one_lift_per_marker_and_the_strays_are_nobodys(self) -> None:
        lifts = [(t + 0.3, t + 1.5) for t, _ in CUES]
        antes = (40.5, 41.3)                    # before the first cue
        despues = [(84.5, 86.5), (92.3, 94.7)]  # after the wizard finished
        spans = [antes, *lifts, *despues]
        duenos = marker_owners([t for t, _ in CUES], spans)
        assert duenos == [1, 2, 3, 4, 5, 6]

    def test_a_lift_drawn_a_little_before_its_cue_is_still_its(self) -> None:
        """It ends after the cue, so it is the one the cue announced — and
        not the previous cue's, which already has its own."""
        spans = [(48.5, 49.5), (54.6, 55.9)]
        assert marker_owners([48.2, 54.8], spans) == [0, 1]

    def test_a_cue_with_nothing_in_its_window_owns_nothing(self) -> None:
        """Rather than reaching into the next cue's lift."""
        assert marker_owners([10.0, 20.0], [(20.3, 21.0)]) == [None, 0]


class TestTheLoadOfEachContraction:
    def test_the_strays_have_no_load(self) -> None:
        filas = [_fila(1, 40.5, 41.3)]
        filas += [_fila(i + 2, t + 0.3, t + 1.5) for i, (t, _) in enumerate(CUES)]
        filas += [_fila(8, 84.5, 86.5), _fila(9, 92.3, 94.7)]
        assert load_of_each(filas, CUES) == [None, 3.0, 3.0, 5.0, 5.0, 7.0, 7.0, None, None]


class TestTheMarkersTravelWithOneFragment:
    def test_a_marker_inside_a_fragment_stays_in_it(self) -> None:
        """The whole recording phase is one fragment with every cue in it."""
        assert markers_by_span(CUES, [(40.0, 90.0)]) == {0: CUES}

    def test_a_marker_between_fragments_goes_to_one(self) -> None:
        fragmentos = [(t + 0.3, t + 1.5) for t, _ in CUES] + [(84.5, 86.5)]
        por = markers_by_span(CUES, fragmentos)
        assert sorted(por) == [0, 1, 2, 3, 4, 5]
        assert 6 not in por


class TestTheTunedFileAgrees:
    def test_a_stray_fragment_is_written_with_no_load(self) -> None:
        from emgteach.tuning import _cargas_por_tramo

        tramos = [(t + 0.3, t + 1.5) for t, _ in CUES[-2:]] + [(84.5, 86.5)]
        marcas = _cargas_por_tramo(CUES, tramos, rec_start_s=0.0)
        assert [m for _t, m in marcas] == ["FV load=7 kg", "FV load=7 kg"]


class TestLiftWindows:
    def test_each_window_stops_before_the_next_cue(self) -> None:
        ventanas = lift_windows_s(CUES, 88.0)
        assert len(ventanas) == 6
        assert ventanas[0] == pytest.approx((48.2, 54.2))   # six seconds
        assert ventanas[-1] == pytest.approx((81.6, 87.6))
        # Half a second shy of a cue that comes sooner than six seconds.
        assert lift_windows_s([(0.0, 1.0), (4.0, 2.0)], 20.0) == pytest.approx(
            [(0.0, 3.5), (4.0, 10.0)])


FS = 1000
FILTROS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


def _senal(rafagas) -> np.ndarray:
    rng = np.random.default_rng(1)
    sig = rng.normal(0.0, 0.01, size=100 * FS)
    for a, b in rafagas:
        i0, i1 = int(a * FS), int(b * FS)
        t = np.arange(i1 - i0) / FS
        sig[i0:i1] += 0.5 * np.sin(2 * np.pi * 90.0 * t)
    return sig


@pytest.mark.gui
class TestTheEditorProposesOneRowPerLift:
    def test_the_strays_are_not_rows(self, qapp) -> None:
        from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

        subidas = [(t + 0.3, t + 1.3) for t, _ in CUES]
        extra = [(41.0, 42.0), (85.0, 86.0), (93.0, 94.0)]
        raw = _senal(subidas + extra)
        libre = FragmentSelectionDialog(raw, FS, FILTROS, naming=False)
        assert len(libre.selected_segments()) > 6       # the detector alone
        libre.deleteLater()
        dlg = FragmentSelectionDialog(raw, FS, FILTROS, naming=False,
                                      lifts=lift_windows_s(CUES, 100.0))
        filas = dlg.selected_segments()
        assert len(filas) == 6
        for (a, b), (t, _kg) in zip(filas, CUES, strict=True):
            assert t - 0.5 <= a < t + 1.0 and b > t
        dlg.deleteLater()

    def test_a_lift_with_nothing_detected_is_proposed_as_its_window(self, qapp) -> None:
        from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

        ventanas = lift_windows_s(CUES, 100.0)
        dlg = FragmentSelectionDialog(_senal([]), FS, FILTROS, naming=False,
                                      lifts=ventanas)
        filas = [(f.start_s, f.end_s) for f in dlg._por_levantamiento([])]
        assert filas == pytest.approx(ventanas, abs=0.01)
        dlg.deleteLater()

    def test_a_cue_before_the_lift_is_cut_off_the_preparation(self, qapp) -> None:
        """The detector joins picking up the weight to the lift."""
        from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

        raw = _senal([(44.0, 49.5)])
        dlg = FragmentSelectionDialog(raw, FS, FILTROS, naming=False,
                                      lifts=lift_windows_s(CUES[:1], 100.0))
        (a, b), = dlg.selected_segments()
        assert a == pytest.approx(47.7, abs=0.02)
        assert b > 48.2
        dlg.deleteLater()


@pytest.mark.gui
class TestTheStudyStartsTheStraysUnticked:
    def _dialogo(self, cargas):
        from emgteach.gui.widgets.force_velocity_dialog import ForceVelocityDialog

        filas = [
            Contraction(i + 1, float(i), float(i) + 0.5, "M", 0.1 + 0.01 * i, None, None,
                        velocity_au=0.05)
            for i in range(len(cargas))
        ]
        return ForceVelocityDialog("no-se-lee.edf", "EMG", "ACC", rows=filas, loads=cargas)

    def test_a_row_with_no_marker_starts_unticked_and_says_why(self, qapp) -> None:
        from PySide6.QtCore import Qt

        dlg = self._dialogo([None, 3.0, 3.0, 5.0, 5.0, 7.0, 7.0, None])
        marcadas = [dlg._table.item(i, 0).checkState() == Qt.CheckState.Checked
                    for i in range(dlg._table.rowCount())]
        assert marcadas == [False, True, True, True, True, True, True, False]
        assert not dlg._aviso_sin_carga.isHidden()
        assert "2" in dlg._aviso_sin_carga.text()
        dlg.deleteLater()

    def test_without_markers_every_row_is_typed_by_hand(self, qapp) -> None:
        from PySide6.QtCore import Qt

        dlg = self._dialogo([None, None, None])
        assert all(dlg._table.item(i, 0).checkState() == Qt.CheckState.Checked
                   for i in range(3))
        assert dlg._aviso_sin_carga.isHidden()
        dlg.deleteLater()
