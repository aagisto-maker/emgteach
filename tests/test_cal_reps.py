"""Keeping or discarding calibration repetitions.

The reference is the yardstick every % MVC on screen is measured against, so
the question this asks is not "does the dialog remember the ticks" but "does
unticking a repetition actually move the number the whole analysis rests on".
Hence the two tests that carry the argument:

* discarding the **best** repetition lowers the reference to the best of what
  is left, and lifts every percentage in the same proportion;
* discarding the **weakest** changes nothing at all — which is the answer that
  makes the first one meaningful, and the one a "reference = mean of what is
  kept" implementation would fail.

The numbers come from the same fixture the phase tests use: three repetitions
of 1.00, 1.40 and 1.20 on the flexor, so the best is the middle one. That
ordering is deliberate — a subject who peaks on the second attempt and eases
off on the third is the common case on the bench, and it means "discard the
best" and "discard the last" are different actions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.phases import (
    FROM_REPS,
    RepValue,
    cal_end_marker,
    cal_start_marker,
    mvc_reference,
    parse_phase_markers,
    rep_values,
)
from emgteach.profiles import EMG_PROFILE

from .test_analysis_phases import CAL, FS, _analizar, _sesion

pytestmark = pytest.mark.gui


def _fases(reps: dict[int, list[tuple[float, float, float]]] | None = None):
    marcas: list[tuple[float, str]] = []
    for canal, lista in (reps or CAL).items():
        for i, (a, b, _amp) in enumerate(lista, start=1):
            marcas.append((a, cal_start_marker(canal, i)))
            marcas.append((b, cal_end_marker(canal, i)))
    return parse_phase_markers(marcas)


def _envelope(reps: list[tuple[float, float, float]], n: int) -> np.ndarray:
    env = np.full(n, 0.01)
    for a, b, amp in reps:
        env[int(a * FS) : int(b * FS)] = amp
    return env


class TestWhatEachRepetitionWasWorth:
    def test_they_come_back_in_the_order_performed(self) -> None:
        """Not sorted by value: a rising profile is the finding."""
        n = 40 * FS
        valores = rep_values(
            0, phases=_fases(), envelope=_envelope(CAL[0], n), fs=FS,
            percentile=EMG_PROFILE.mvc_percentile,
            window_s=EMG_PROFILE.mvc_peak_window_s,
        )
        assert [v.rep for v in valores] == [1, 2, 3]
        assert [round(v.value_mv, 2) for v in valores] == [1.00, 1.40, 1.20]

    def test_crosstalk_is_a_share_of_the_other_muscle_reference(self) -> None:
        """The antagonist at 0.35 mV against its own 0.70 mV is 50 %.

        Reported against the *other* channel's reference and not against this
        one, because "how hard was the other muscle working" is a question
        about that muscle.
        """
        n = 40 * FS
        otro = np.full(n, 0.35)
        valores = rep_values(
            0, phases=_fases(), envelope=_envelope(CAL[0], n), fs=FS,
            percentile=EMG_PROFILE.mvc_percentile,
            window_s=EMG_PROFILE.mvc_peak_window_s,
            other_envelope=otro, other_reference=0.70,
        )
        assert all(v.crosstalk_pct == pytest.approx(50.0, abs=1.0)
                   for v in valores)

    def test_without_the_other_channel_there_is_no_figure_invented(self) -> None:
        n = 40 * FS
        valores = rep_values(
            0, phases=_fases(), envelope=_envelope(CAL[0], n), fs=FS,
        )
        assert all(v.crosstalk_pct is None for v in valores)

    def test_a_recording_with_no_calibration_offers_nothing(self) -> None:
        assert rep_values(
            0, phases=parse_phase_markers([]), envelope=np.zeros(100), fs=FS,
        ) == ()


class TestTheSelectionMovesTheReference:
    """Through :func:`mvc_reference`, which is the one place that decides."""

    def _ref(self, keep=None) -> float:
        n = 40 * FS
        valor, fuente = mvc_reference(
            0, phases=_fases(), envelope=_envelope(CAL[0], n), fs=FS,
            keep=keep, percentile=EMG_PROFILE.mvc_percentile,
            window_s=EMG_PROFILE.mvc_peak_window_s,
        )
        assert fuente == FROM_REPS
        return valor

    def test_discarding_the_best_lowers_it_to_the_next(self) -> None:
        assert self._ref() == pytest.approx(1.40, abs=0.02)
        assert self._ref(keep={1, 3}) == pytest.approx(1.20, abs=0.02)

    def test_discarding_the_weakest_changes_nothing(self) -> None:
        assert self._ref(keep={2, 3}) == pytest.approx(self._ref(), abs=1e-9)

    def test_emptying_a_channel_is_refused_rather_than_answered(self) -> None:
        """A channel with no repetition kept is not a calibration with a
        smaller reference; it is no calibration, and saying so is the caller's
        job, not this function's."""
        with pytest.raises(ValueError):
            self._ref(keep=set())


class TestTheAnalysisHonoursTheSelection:
    """The wiring, not the helper: an :class:`AnalysisWorker` on a real file."""

    def test_the_repetitions_are_offered_for_both_channels(
        self, qapp, tmp_path: Path
    ) -> None:
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"))
        valores = r["cal_rep_values"]
        assert set(valores) == {0, 1}
        assert all(isinstance(v, RepValue) for v in valores[0])
        assert [v.rep for v in valores[1]] == [1, 2, 3]
        # Two channels analysed, so each repetition also carries what the
        # other muscle was doing during it.
        assert all(v.crosstalk_pct is not None for v in valores[0])
        # And each index says which muscle it is, so the report can name it
        # instead of numbering it.
        assert r["cal_channel_names"] == {
            0: r["channel_name"], 1: r["channel_name_2"],
        }

    def test_discarding_the_best_lifts_every_percentage(
        self, qapp, tmp_path: Path
    ) -> None:
        """The reference falls to the third repetition and the recording,
        unchanged, is now a larger share of it."""
        edf = _sesion(tmp_path / "sesion.edf")
        entera = _analizar(qapp, edf)
        recortada = _analizar(qapp, edf, cal_keep={0: {1, 3}})

        # In mV the reference is the envelope of the fixture's carrier, not
        # its amplitude, so what is asserted is the ratio the repetitions set:
        # the best of what is kept goes from the 1.40 repetition to the 1.20
        # one, and the reference follows it exactly.
        assert recortada["mvc_ref"] / entera["mvc_ref"] == pytest.approx(
            1.20 / 1.40, rel=0.02)
        assert recortada["mvc_ref_source"] == FROM_REPS
        # The other channel was not touched, and must not move.
        assert recortada["mvc_ref_2"] == pytest.approx(entera["mvc_ref_2"])

        pico_antes = float(np.max(entera["emg_envelope"])) / entera["mvc_ref"]
        pico_ahora = (float(np.max(recortada["emg_envelope"]))
                      / recortada["mvc_ref"])
        assert pico_ahora > pico_antes
        assert pico_ahora / pico_antes == pytest.approx(
            entera["mvc_ref"] / recortada["mvc_ref"], rel=0.01)

    def test_discarding_the_weakest_leaves_the_analysis_alone(
        self, qapp, tmp_path: Path
    ) -> None:
        edf = _sesion(tmp_path / "sesion.edf")
        entera = _analizar(qapp, edf)
        recortada = _analizar(qapp, edf, cal_keep={0: {2, 3}})
        assert recortada["mvc_ref"] == pytest.approx(entera["mvc_ref"])

    def test_a_selection_that_empties_a_channel_falls_back_to_all_of_it(
        self, qapp, tmp_path: Path
    ) -> None:
        """The dialog does not allow it, but a selection outlives the file it
        was made on. Answering with the whole calibration is a smaller lie
        than answering with none of it — and crashing is not an answer."""
        edf = _sesion(tmp_path / "sesion.edf")
        entera = _analizar(qapp, edf)
        rara = _analizar(qapp, edf, cal_keep={0: {17}})
        assert rara["mvc_ref"] == pytest.approx(entera["mvc_ref"])


class TestTheButtonInTheTab:
    """A grey control that says nothing about why is a bench session lost.

    These go through :meth:`AnalysisTab._on_result` rather than calling the
    helper, because the question is whether the *wiring* lights the button on
    a real analysis of a real file — which is the thing that cannot be checked
    from the outside once the app is running.
    """

    def _tab(self, qapp, edf: str):
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.analysis import AnalysisTab
        from emgteach.gui.widgets.logger import LoggerWidget

        ajustes = QSettings("emgteach-test", "cal-reps")
        ajustes.clear()
        registro = LoggerWidget()
        tab = AnalysisTab(registro, ajustes)
        tab._edit_path.setText(edf)
        return tab, registro

    def test_it_lights_on_a_session_that_carries_a_calibration(
        self, qapp, tmp_path: Path
    ) -> None:
        edf = _sesion(tmp_path / "sesion.edf")
        tab, registro = self._tab(qapp, edf)
        assert not tab._btn_reps.isEnabled()
        tab._on_result(_analizar(qapp, edf))
        assert tab._btn_reps.isEnabled()
        assert "3" in registro.toPlainText()

    def test_it_stays_off_and_says_why_on_a_recording_without_one(
        self, qapp, tmp_path: Path
    ) -> None:
        """Every file recorded before the guided flow, which is most of them
        on the teacher's disk."""
        edf = _sesion(tmp_path / "vieja.edf", con_fases=False, con_cache=False)
        tab, registro = self._tab(qapp, edf)
        tab._on_result(_analizar(qapp, edf))
        assert not tab._btn_reps.isEnabled()
        assert registro.toPlainText().strip()

    def test_a_disabled_button_says_why_it_is_disabled(
        self, qapp, tmp_path: Path
    ) -> None:
        """Three states, three different sentences.

        It shares its row with «Select fragments…», which lights as soon as a
        file is chosen; this one needs the analysis, because what the dialog
        offers is what each effort was *worth* and that is measured, not
        stored. The asymmetry reads as a fault unless the button explains it —
        as it did to the one person who had already been told.
        """
        edf = _sesion(tmp_path / "sesion.edf")
        tab, _ = self._tab(qapp, edf)

        sin_analizar = tab._btn_reps.toolTip()
        assert not tab._btn_reps.isEnabled()
        assert sin_analizar

        vieja = _sesion(tmp_path / "vieja.edf", con_fases=False,
                        con_cache=False)
        tab._edit_path.setText(vieja)
        tab._on_result(_analizar(qapp, vieja))
        sin_calibracion = tab._btn_reps.toolTip()
        assert not tab._btn_reps.isEnabled()
        assert sin_calibracion != sin_analizar

        tab._edit_path.setText(edf)
        tab._on_result(_analizar(qapp, edf))
        assert tab._btn_reps.isEnabled()
        assert tab._btn_reps.toolTip() not in (sin_analizar, sin_calibracion)

    def test_the_log_names_the_channels_and_counts_the_repetitions(
        self, qapp, tmp_path: Path
    ) -> None:
        edf = _sesion(tmp_path / "sesion.edf")
        tab, registro = self._tab(qapp, edf)
        tab._on_result(_analizar(qapp, edf))
        texto = registro.toPlainText()
        assert "FCR" in texto and "ECR" in texto


class TestTheDialog:
    def _dlg(self, qapp, keep=None):
        from emgteach.gui.widgets.calibration_reps import CalibrationRepsDialog

        valores = {
            0: (RepValue(1, 1.00, 18.0), RepValue(2, 1.40, 15.0),
                RepValue(3, 1.20, 16.0)),
        }
        return CalibrationRepsDialog(
            valores, {0: "FCR"}, references={0: 1.40}, keep=keep,
        )

    def test_it_opens_with_every_repetition_kept(self, qapp) -> None:
        assert self._dlg(qapp).keep() == {0: {1, 2, 3}}

    def test_it_reopens_on_the_previous_selection(self, qapp) -> None:
        assert self._dlg(qapp, keep={0: {1, 3}}).keep() == {0: {1, 3}}

    def test_it_promises_the_reference_the_analysis_will_compute(
        self, qapp
    ) -> None:
        """Best of what is kept, the same rule as ``mvc_from_reps``."""
        dlg = self._dlg(qapp, keep={0: {1, 3}})
        assert dlg.reference_for(0) == pytest.approx(1.20)

    def test_it_will_not_let_a_channel_be_emptied(self, qapp) -> None:
        from PySide6.QtWidgets import QDialogButtonBox

        dlg = self._dlg(qapp)
        ok = dlg._botones.button(QDialogButtonBox.StandardButton.Ok)
        assert ok.isEnabled()
        for rep in (1, 2, 3):
            dlg._casillas[(0, rep)].setChecked(False)
        assert not ok.isEnabled()
        dlg._casillas[(0, 2)].setChecked(True)
        assert ok.isEnabled()
