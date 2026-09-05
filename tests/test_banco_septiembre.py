"""What the bench of 5 September 2026 showed, with the hardware.

Three recordings — one of the single-muscle practical, two of the kinematics
one — and a list: the analysis took the warm-up and the six maximal efforts
for contractions of the task; the muscle came back from the file as
«MA sculo»; the single-muscle practical offered no box for the muscle's name;
the accelerometer's panel of the review stayed blank and the «find the ACC
channel» diagnostic found nothing; the loads went missing once fragments were
selected; the electromechanical delay came out as zero; and there was no way
out of a calibration but to wait for it.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from emgteach.contractions import Contraction, contraction_table, load_of_each
from emgteach.i18n import tr
from emgteach.io import ChannelInfo, ascii_label
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE, mode_fixed_labels
from emgteach.phases import cal_end_marker, cal_start_marker, parse_phase_markers
from emgteach.selection import Segment

FS = 1000


class TestTheAnalysedSpanWithoutARecMark:
    """The single-muscle practical calibrates in the middle of its recording
    and writes no «REC start»; the task is what comes after."""

    def test_after_the_last_closed_calibration(self) -> None:
        m = [(0.0, "WARMUP start"),
             (12.6, cal_start_marker(0, 1)), (17.0, cal_end_marker(0, 1)),
             (56.5, cal_start_marker(0, 6)), (58.1, cal_end_marker(0, 6))]
        assert parse_phase_markers(m).rec_span(83.0) == (pytest.approx(58.1), 83.0)

    def test_a_second_before_the_first_load_of_the_wizard(self) -> None:
        """The kinematics recording has neither; its stray efforts before the
        wizard began stay out."""
        span = parse_phase_markers([]).rec_span(124.0, [(13.9, 2.0), (23.4, 2.0)])
        assert span == (pytest.approx(12.9), 124.0)

    def test_nothing_says_where_the_task_began(self) -> None:
        assert parse_phase_markers([(1.0, "Grip")]).rec_span(30.0) is None


class TestTheRowsAreTheFragments:
    def test_accepted_fragments_are_the_rows_in_their_order(self) -> None:
        """Detecting again inside the concatenation renumbered them."""
        t = np.arange(6 * FS) / FS
        raw = np.sin(2 * np.pi * 80 * t) * 0.01
        for a in (1.0, 3.0, 4.5):
            raw[int(a * FS):int((a + 0.6) * FS)] *= 30
        env = np.abs(raw)
        fragmentos = [Segment(0.9, 1.7, label="one"), Segment(2.9, 3.7, label="two"),
                      Segment(4.4, 5.2, label="three")]
        filas = contraction_table(fs=FS, emg_raw=raw, emg_filtered=raw, envelope=env,
                                  segments=fragmentos, name_1="FCR")
        assert [r.n for r in filas] == [1, 2, 3]
        # Each row is its fragment trimmed to the effort inside it: the
        # rest either side would have been counted into the RMS.
        for fila, frag, inicio in zip(filas, fragmentos, (1.0, 3.0, 4.5), strict=True):
            assert frag.start_s <= fila.start_s <= inicio + 0.05
            assert inicio + 0.5 <= fila.end_s <= frag.end_s

    def test_without_fragments_the_detector_still_runs(self) -> None:
        t = np.arange(4 * FS) / FS
        raw = np.sin(2 * np.pi * 80 * t) * 0.01
        raw[int(1.0 * FS):int(1.8 * FS)] *= 30
        filas = contraction_table(fs=FS, emg_raw=raw, emg_filtered=raw, envelope=np.abs(raw),
                                  name_1="FCR")
        assert len(filas) >= 1


class TestTheDelayAndTheVelocity:
    def _senales(self):
        n = 3 * FS
        env = np.full(n, 0.01)
        move = np.zeros(n)
        # The muscle rises from 1.00 s over 50 ms; the segment from 1.06 s.
        subida = np.linspace(0.0, 1.0, 50)
        env[1000:1050] += subida * 0.4
        env[1050:1500] += 0.4
        move[1060:1160] += np.linspace(0.0, 1.0, 100)
        move[1160:1600] += 1.0
        return env, move

    def test_a_window_that_begins_late_still_finds_both_onsets(self) -> None:
        """The detector's windows begin on the threshold crossing, with the
        muscle already up; searched forward from there, the delay was zero."""
        env, move = self._senales()
        raw = env * np.sign(np.sin(2 * np.pi * 80 * np.arange(env.size) / FS))
        filas = contraction_table(fs=FS, emg_raw=raw, emg_filtered=raw, envelope=env,
                                  segments=[Segment(1.05, 1.5)], movement=move, name_1="M",
                                  window_s=0.2)
        assert len(filas) == 1
        assert filas[0].emd_ms is not None
        assert 40.0 <= filas[0].emd_ms <= 80.0

    def test_the_velocity_is_the_peak_over_the_contraction(self) -> None:
        env, _move = self._senales()
        raw = env
        vel = np.zeros(env.size)
        vel[1100:1300] = np.linspace(0, -0.02, 200)   # sign is a direction
        filas = contraction_table(fs=FS, emg_raw=raw, emg_filtered=raw, envelope=env,
                                  segments=[Segment(1.0, 1.5)], velocity=vel, name_1="M")
        assert filas[0].velocity_au == pytest.approx(0.02)
        sin = contraction_table(fs=FS, emg_raw=raw, emg_filtered=raw, envelope=env,
                                segments=[Segment(1.0, 1.5)], name_1="M")
        assert sin[0].velocity_au is None


class TestTheLoadsSurviveTheFragments:
    def test_a_marker_just_before_a_tight_fragment_is_its_load(self) -> None:
        """The wizard's marker sits at the start of its window, before the
        effort; a fragment cut round the effort must still find it."""
        filas = [Contraction(1, 0.0, 2.5, "M", 0.1, None, None),
                 Contraction(2, 2.5, 5.0, "M", 0.1, None, None)]
        # As the worker rebases them: at the fragment's start.
        assert load_of_each(filas, [(0.0, 2.0), (2.5, 3.4)]) == [2.0, 3.4]


class TestTheLabelReachesTheFile:
    def test_accents_are_dropped_not_the_letters(self) -> None:
        assert ascii_label("Músculo") == "Musculo"
        assert ascii_label("Bíceps") == "Biceps"
        assert ascii_label("ACC (limb)") == "ACC (limb)"
        assert ascii_label("Flexor carpi radialis largo") == "Flexor carpi rad"

    def test_the_header_carries_the_ascii_form(self) -> None:
        cab = ChannelInfo("Músculo", sample_frequency=FS).to_pyedflib_header()
        assert cab["label"] == "Musculo"


class TestTheNameOfTheMuscle:
    def test_no_practical_imposes_a_name_any_more(self) -> None:
        for mode in (MODE_SINGLE, MODE_PAIR, MODE_KINEMATICS):
            assert mode_fixed_labels(mode) == ()


@pytest.fixture
def adq(qapp):
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    ajustes = QSettings("emgteach-test", "banco-sep")
    ajustes.clear()
    t = AcquisitionTab(LoggerWidget(), ajustes)
    yield t
    t.close()
    ajustes.clear()


class TestTheAcquisitionTabAfterTheBench:
    def test_one_muscle_gets_a_box_and_a_generic_name(self, adq) -> None:
        adq._n_channels = 1
        adq._apply_channel_visibility()
        adq._edit_labels[0].setText("")
        assert adq._active_labels() == [tr("Muscle")]
        adq._edit_labels[0].setText("Bíceps")
        assert adq._active_labels() == ["Bíceps"]

    def test_the_wiring_is_stated_not_chosen(self, adq) -> None:
        from emgteach.gui.tabs.acquisition import _ACC_INPUT

        adq.apply_mode(MODE_KINEMATICS, False)
        assert adq._combo_acc_channel.currentData() == _ACC_INPUT == 1
        assert adq._box_acc_wiring.isHidden()
        # The convention is stated inside the accelerometer block itself.
        assert adq._lbl_acc_wiring.parent() is adq._box_acc
        assert "A1" in adq._lbl_acc_wiring.text() and "A2" in adq._lbl_acc_wiring.text()

    def test_the_guide_can_be_cancelled(self, adq) -> None:
        """The button appears while a guide runs, and Esc lands on it."""
        assert adq._btn_cancelar_guia.isHidden()
        adq._mvc_active = True
        adq._btn_cancelar_guia.setVisible(True)
        adq._cancelar_guiado()
        assert not adq._mvc_active
        assert adq._btn_cancelar_guia.isHidden()
        assert "cancel" in adq._logger.toPlainText().lower() \
            or "cancelad" in adq._logger.toPlainText().lower()
