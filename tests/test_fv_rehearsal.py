"""The force-velocity rehearsal: that it shows what the wizard actually does.

A rehearsal is only worth running if it is faithful. The danger is not that it
breaks — it is that someone changes the wizard's timing or its order of phases
and the rehearsal quietly goes on teaching last year's procedure, which is
worse than no rehearsal at all. So the central test here drives the *real*
state machine and compares what it does to the script the rehearsal plays.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.fv_rehearsal import (
    PHASE_DONE,
    PHASE_LIFT,
    PHASE_MVC_CONTRACT,
    PHASE_MVC_READY,
    PHASE_MVC_REST,
    PHASE_PREPARE,
    PHASE_REST,
    Cue,
    cue_script,
    synthetic_trial,
    total_seconds,
)

LOADS = [2.0, 4.0, 6.0, 8.0]


class TestTheScript:
    def test_it_opens_on_a_maximum_with_no_load(self) -> None:
        """The MVC comes first and carries no weight — it is the 100 % every
        later contraction is read against."""
        cues = cue_script(LOADS)
        assert [c.phase for c in cues[:3]] == [
            PHASE_MVC_READY, PHASE_MVC_CONTRACT, PHASE_MVC_REST
        ]
        assert all(c.load == 0.0 for c in cues[:3])

    def test_every_load_gets_a_lift_in_the_order_listed(self) -> None:
        lifts = [c for c in cue_script(LOADS) if c.is_lift]
        assert [c.load for c in lifts] == LOADS

    def test_repetitions_multiply_the_lifts_not_the_maximum(self) -> None:
        cues = cue_script(LOADS, reps=3)
        assert len([c for c in cues if c.is_lift]) == len(LOADS) * 3
        assert len([c for c in cues if c.phase == PHASE_MVC_CONTRACT]) == 1

    def test_there_is_no_dangling_rest_after_the_last_lift(self) -> None:
        """The wizard finishes on the last lift; a rest cue after it would have
        the rehearsal wait for a contraction that never comes."""
        cues = cue_script(LOADS)
        assert cues[-1].phase == PHASE_DONE
        assert cues[-2].is_lift

    def test_the_cues_tile_the_run_without_gaps(self) -> None:
        cues = cue_script(LOADS, reps=2)
        for a, b in zip(cues, cues[1:]):
            assert a.end == pytest.approx(b.start)
        assert total_seconds(cues) == pytest.approx(cues[-1].end)

    def test_a_single_load_still_produces_a_run(self) -> None:
        """The plan dialog requires two loads, but nothing should explode if
        the script is asked for one."""
        cues = cue_script([5.0])
        assert len([c for c in cues if c.is_lift]) == 1


class TestItMatchesTheRealWizard:
    """Drive the acquisition tab's own state machine and compare.

    The methods are taken off the class and run against a stand-in, so this
    tests the shipping state machine without a window, a device or a Qt event
    loop — and therefore keeps working when those change.
    """

    @staticmethod
    def _run_real_wizard(loads, reps, prep_s, lift_s):
        from emgteach.gui.tabs.acquisition import MVC_TICK_MS, AcquisitionTab

        class Overlay:
            def show_ready(self, *a, **k): pass
            def show_contract(self, *a, **k): pass
            def show_relax(self, *a, **k): pass
            def show_action(self, *a, **k): pass
            def show_done(self, *a, **k): pass

        class Stub:
            _fv_current_load = AcquisitionTab._fv_current_load
            _fv_progress = AcquisitionTab._fv_progress
            _fv_finish_contract = AcquisitionTab._fv_finish_contract
            _fv_tick = AcquisitionTab._fv_tick

            def __init__(self):
                self._fv_loads = list(loads)
                self._fv_reps = reps
                self._fv_prep_s = prep_s
                self._fv_window_s = lift_s
                self._fv_idx = 0
                self._fv_rep = 0
                self._fv_elapsed = 0.0
                self._fv_phase = "mvc_ready"
                self._fv_mvc_cur = 0.0
                self._fv_mvc_peak = 1.0
                self._mvc_overlay = Overlay()
                self.seen: list[tuple[str, float]] = []

            def _fv_info(self, text): pass
            def _fv_compute_mvc(self): pass

            def _fv_begin_contract(self, kg):
                self._fv_phase = "contract"
                self._fv_elapsed = 0.0

            def _fv_finish_all(self):
                self._fv_phase = PHASE_DONE

        stub = Stub()
        dt = MVC_TICK_MS / 1000.0
        # Generous ceiling: the run is ~48 s, and a state machine that fails to
        # advance should end the test rather than hang it.
        for _ in range(int(600 / dt)):
            if stub._fv_phase == PHASE_DONE:
                break
            phase, kg = stub._fv_phase, stub._fv_current_load()
            stub.seen.append((phase, kg))
            stub._fv_tick()
        else:                                    # pragma: no cover
            pytest.fail("the wizard never reached its end")
        return stub.seen, dt

    def _observed_cues(self, loads, reps, prep_s, lift_s) -> list[Cue]:
        """Collapse the tick-by-tick trace into one entry per phase entered."""
        seen, dt = self._run_real_wizard(loads, reps, prep_s, lift_s)
        out: list[Cue] = []
        for phase, kg in seen:
            if out and out[-1].phase == phase and out[-1].load == kg:
                out[-1] = Cue(phase, out[-1].seconds + dt, kg,
                              start=out[-1].start)
            else:
                start = out[-1].end if out else 0.0
                out.append(Cue(phase, dt, kg, start=start))
        return out

    @pytest.mark.parametrize(
        ("loads", "reps", "prep_s", "lift_s"),
        [
            (LOADS, 1, 5.0, 1.5),
            ([3.0, 6.0], 2, 2.0, 1.0),
            ([1.0, 2.0, 3.0], 1, 1.0, 0.5),
        ],
    )
    def test_the_order_of_phases_is_the_wizards_own(
        self, loads, reps, prep_s, lift_s
    ) -> None:
        observed = self._observed_cues(loads, reps, prep_s, lift_s)
        expected = [c for c in cue_script(loads, reps, prep_s, lift_s)
                    if c.phase != PHASE_DONE]
        assert [c.phase for c in observed] == [c.phase for c in expected]

    def test_each_lift_is_announced_with_the_right_load(self) -> None:
        observed = self._observed_cues(LOADS, 1, 5.0, 1.5)
        assert [c.load for c in observed if c.is_lift] == LOADS

    def test_the_timing_is_the_wizards_own(self) -> None:
        """Within one tick: the rehearsal is a preview of how long each step
        lasts, so 'prepare' being 5 s there and 2 s in the app would mislead.
        """
        from emgteach.gui.tabs.acquisition import MVC_TICK_MS

        observed = self._observed_cues(LOADS, 1, 5.0, 1.5)
        expected = [c for c in cue_script(LOADS, 1, 5.0, 1.5)
                    if c.phase != PHASE_DONE]
        for got, want in zip(observed, expected, strict=True):
            assert got.seconds == pytest.approx(
                want.seconds, abs=1.5 * MVC_TICK_MS / 1000.0
            ), f"phase {got.phase}"


class TestTheSyntheticSubject:
    """The rehearsal ends on real curves, so the fake subject has to obey the
    physiology the study is there to demonstrate."""

    @staticmethod
    def _study(loads, reps=1):
        from emgteach.dsp import process_offline
        from emgteach.force_velocity import (
            force_velocity_curves,
            parse_fv_load_markers,
            rep_metrics,
            velocity_from_acc,
            windows_from_markers,
        )

        trial = synthetic_trial(loads, reps)
        fs = trial["fs"]
        env = np.asarray(
            process_offline(trial["emg_raw"], fs, f_env=5.0)["emg_envelope"],
            dtype=float,
        )
        vel = velocity_from_acc(trial["acc_raw"], fs)
        windows, kg = windows_from_markers(
            parse_fv_load_markers(trial["markers"]), fs, env.size
        )
        emg, peak = rep_metrics(env, vel, windows)
        return np.asarray(kg), emg, peak, force_velocity_curves(
            np.asarray(kg), peak
        )

    def test_one_marker_per_lift_and_nothing_for_the_maximum(self) -> None:
        """The opening maximum is not a load, so it must not become a rep in
        the study — it would sit at the top of every curve as a phantom point.
        """
        trial = synthetic_trial(LOADS)
        assert len(trial["markers"]) == len(LOADS)

    def test_the_windows_the_study_finds_are_the_lifts(self) -> None:
        kg, _emg, _peak, _c = self._study(LOADS)
        assert list(kg) == LOADS

    def test_heavier_loads_move_more_slowly(self) -> None:
        """Hill: this is the whole point of the force-velocity curve."""
        _kg, _emg, peak, _c = self._study(LOADS)
        assert np.all(np.diff(peak) < 0), peak

    def test_heavier_loads_need_more_activation(self) -> None:
        """Henneman's size principle — the recruitment panel."""
        _kg, emg, _peak, _c = self._study(LOADS)
        assert np.all(np.diff(emg) > 0), emg

    def test_power_peaks_at_an_intermediate_load(self) -> None:
        """Neither the lightest nor the heaviest: the teaching point of the
        power panel, and the one an idealised drawing would get for free but a
        synthetic recording has to actually produce."""
        _kg, _emg, _peak, c = self._study(LOADS)
        best = int(np.argmax(c["power"]))
        assert 0 < best < len(LOADS) - 1, c["power"]

    def test_the_isometric_maximum_produces_no_movement(self) -> None:
        """It is held, not lifted. An accelerometer that moved during it would
        teach that a static maximum has a velocity."""
        from emgteach.force_velocity import velocity_from_acc

        trial = synthetic_trial(LOADS)
        fs = trial["fs"]
        vel = np.abs(velocity_from_acc(trial["acc_raw"], fs))
        cues = trial["cues"]
        mvc = next(c for c in cues if c.phase == PHASE_MVC_CONTRACT)
        lift = next(c for c in cues if c.is_lift)
        during_mvc = vel[int(mvc.start * fs):int(mvc.end * fs)].max()
        during_lift = vel[int(lift.start * fs):int(lift.end * fs)].max()
        assert during_mvc < 0.1 * during_lift

    def test_it_is_reproducible(self) -> None:
        """Same plan, same recording: two students rehearsing side by side
        should not be comparing different subjects."""
        a = synthetic_trial(LOADS)["emg_raw"]
        b = synthetic_trial(LOADS)["emg_raw"]
        assert np.array_equal(a, b)

    def test_the_prepare_and_rest_phases_are_quiet(self) -> None:
        trial = synthetic_trial(LOADS)
        fs = trial["fs"]
        emg = np.abs(trial["emg_raw"])
        rest = next(c for c in trial["cues"] if c.phase == PHASE_REST)
        prep = next(c for c in trial["cues"] if c.phase == PHASE_PREPARE)
        lift = next(c for c in trial["cues"] if c.is_lift)
        loud = emg[int(lift.start * fs):int(lift.end * fs)].max()
        for quiet in (rest, prep):
            seg = emg[int(quiet.start * fs):int(quiet.end * fs)]
            assert seg.max() < 0.15 * loud, quiet.phase
