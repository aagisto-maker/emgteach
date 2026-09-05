"""The rehearsal dialog: that it plays, narrates and ends where it says.

The fidelity of the *sequence* is tested in ``test_fv_rehearsal.py`` against
the real state machine. What is checked here is the player around it — that
every step is narrated, that the log says what the acquisition tab would say,
and that "open the study" really opens the study on a file the study can read.
"""

from __future__ import annotations

import pytest

from emgteach.fv_rehearsal import PHASE_DONE, PHASE_LIFT

pytestmark = pytest.mark.gui

LOADS = [2.0, 4.0, 6.0, 8.0]


@pytest.fixture
def dlg(qapp):
    from emgteach.gui.widgets.fv_rehearsal_dialog import (
        ForceVelocityRehearsalDialog,
    )

    d = ForceVelocityRehearsalDialog(LOADS, 1, 5.0, 1.5)
    yield d
    d.close()


def _play_to_end(d) -> None:
    for _ in range(len(d._cues)):
        d._next_step()


class TestItPlays:
    def test_it_starts_at_the_beginning_and_paused(self, dlg) -> None:
        """Nothing should move until it is asked to: the narration is meant to
        be read before the run starts."""
        assert dlg._t == 0.0
        assert not dlg._timer.isActive()

    def test_every_step_is_narrated(self, dlg) -> None:
        """A step with no explanation is a step the student has to guess."""
        seen = set()
        for _ in range(len(dlg._cues)):
            assert dlg._lbl_what.text().strip()
            assert dlg._lbl_why.text().strip()
            seen.add(dlg._lbl_what.text())
            dlg._next_step()
        # The prompts repeat per load, but the phases must not all share one
        # explanation.
        assert len(seen) >= 6

    def test_stepping_lands_on_the_start_of_each_cue(self, dlg) -> None:
        for cue in dlg._cues[1:]:
            dlg._next_step()
            assert dlg._t == pytest.approx(cue.start)

    def test_the_clock_stops_at_the_end(self, dlg) -> None:
        dlg._t = dlg._total - 0.01
        dlg._timer.start()
        for _ in range(10):
            dlg._tick()
        assert not dlg._timer.isActive()
        assert dlg._t == pytest.approx(dlg._total)

    def test_restart_clears_what_the_run_produced(self, dlg) -> None:
        _play_to_end(dlg)
        assert dlg._log.toPlainText()
        dlg._restart()
        assert dlg._t == 0.0
        assert dlg._log.toPlainText() == ""
        assert not dlg._btn_study.isEnabled()

    def test_speed_only_changes_the_clock_not_the_script(self, dlg) -> None:
        """The fastest setting is for reviewing; it must not drop or
        merge steps."""
        before = [(c.phase, c.load) for c in dlg._cues]
        dlg._combo_speed.setCurrentIndex(3)
        assert dlg._speed == 10.0
        assert [(c.phase, c.load) for c in dlg._cues] == before


class TestTheLog:
    def test_one_line_per_lift_naming_its_load(self, dlg) -> None:
        _play_to_end(dlg)
        text = dlg._log.toPlainText()
        for kg in LOADS:
            assert f"{kg:g} kg" in text

    def test_the_mvc_reference_is_a_real_number(self, dlg) -> None:
        """It comes from the synthetic maximum through the app's own
        mvc_from_reps, so a zero here means the maximum was not recorded."""
        assert dlg._mvc_ref > 0.0

    def test_nothing_is_logged_before_it_happens(self, dlg) -> None:
        assert dlg._log.toPlainText() == ""

    def test_the_study_button_waits_for_the_end(self, dlg) -> None:
        assert not dlg._btn_study.isEnabled()
        _play_to_end(dlg)
        assert dlg._btn_study.isEnabled()


class TestItEndsInTheRealStudy:
    def test_the_recording_is_an_edf_the_study_can_read(self, dlg) -> None:
        from emgteach.io import find_edf_acc_channel, list_edf_channels

        _play_to_end(dlg)
        dlg._open_study()
        assert dlg._edf is not None
        assert "EMG" in list_edf_channels(dlg._edf)
        _label, placement = find_edf_acc_channel(dlg._edf)
        # On the moving segment: on the muscle the velocity would be ~0, which
        # is the mistake the plan dialog warns about — a rehearsal must not
        # demonstrate it.
        assert placement == "limb"
        dlg._study.close()

    def test_the_loads_arrive_pre_filled(self, dlg) -> None:
        """The whole reason the wizard writes markers: nobody types loads."""
        _play_to_end(dlg)
        dlg._open_study()
        table = dlg._study._table
        assert table.rowCount() == len(LOADS)
        got = [table.item(r, 2).text() for r in range(table.rowCount())]
        assert got == [f"{kg:g}" for kg in LOADS]
        dlg._study.close()

    def test_the_study_finds_no_reason_to_warn(self, dlg) -> None:
        """The accelerometer warning must stay hidden: the rehearsal's subject
        did move, so a visible warning would teach a false alarm."""
        _play_to_end(dlg)
        dlg._open_study()
        assert not dlg._study._acc_warn.isVisible()
        dlg._study.close()


class TestTheButtonInTheApp:
    @pytest.fixture
    def tab(self, qapp):
        from PySide6.QtCore import QSettings

        from emgteach.gui.tabs.acquisition import AcquisitionTab
        from emgteach.gui.widgets.logger import LoggerWidget

        t = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "rehearse"))
        yield t
        t.close()

    def test_rehearsing_never_needs_the_hardware(self, tab) -> None:
        """It is enabled with nothing connected — that is the whole point —
        and so is the plan beside it, which is set before anything is
        connected.

        The two buttons no longer carry their number in their label: the
        box is one line and the sequence is told by the floating panel and
        the «?», not by the buttons. The rehearsal is the second of the two
        on the line although the guide teaches it first, because by the time
        anyone needs the box they have either rehearsed or decided not to.
        """
        assert tab._btn_fv_rehearse.isEnabled()
        assert tab._btn_fv_guided.isEnabled()
        assert not tab._btn_fv_rehearse.text()[0].isdigit()

    def test_the_tour_step_points_at_a_button_that_exists(
        self, main_window, qapp
    ) -> None:
        """The tour resolves its targets lazily and swallows failures, so a
        renamed button turns that step into a panel pointing at nothing
        instead of an error. Only a test notices."""
        from emgteach.gui.tour import build_tour
        from emgteach.modes import MODE_KINEMATICS, MODES

        main_window._combo_mode.setCurrentIndex(MODES.index(MODE_KINEMATICS))
        qapp.processEvents()
        wanted = main_window._tab_adq._btn_fv_rehearse
        assert any(
            s.target is not None and s.target() is wanted
            for s in build_tour(main_window)
        )


class TestTheCuePanelIsTheRealOne:
    def test_it_is_the_acquisition_tabs_own_widget(self, dlg) -> None:
        """Not a look-alike: a copy would drift from what the subject sees."""
        from emgteach.gui.widgets.mvc_overlay import MvcOverlay

        assert isinstance(dlg._overlay, MvcOverlay)

    def test_each_phase_puts_the_panel_in_a_different_mode(self, dlg) -> None:
        modes = set()
        for _ in range(len(dlg._cues)):
            modes.add(dlg._overlay._mode)
            dlg._next_step()
        assert {"ready", "contract", "relax", "action", "done"} <= modes

    def test_the_lift_cue_names_its_load(self, dlg) -> None:
        lift = next(i for i, c in enumerate(dlg._cues) if c.phase == PHASE_LIFT)
        dlg._apply_cue(lift)
        assert "2" in dlg._overlay._title

    def test_the_last_cue_says_it_is_done(self, dlg) -> None:
        last = next(i for i, c in enumerate(dlg._cues) if c.phase == PHASE_DONE)
        dlg._apply_cue(last)
        assert dlg._overlay._mode == "done"
