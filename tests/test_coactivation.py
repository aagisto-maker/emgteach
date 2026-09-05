"""The Falconer-Winter co-activation index, and above all its safeguards.

The index measures *similarity of shape*, not amount of activation, which is
what makes it dangerous in a teaching tool: two muscles at rest have similar
baseline noise, so it climbs towards 100 % on a recording where nothing
happened. That is the same silent failure as auto-normalising against a
signal's own 95th percentile — a number that looks like a finding and is not.

``test_two_resting_muscles_are_not_reported`` is the one that guards it.
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.coactivation import (
    coactivation_by_window,
    coactivation_index,
    resting_level,
)

FS = 1000.0


def _t(seconds: float = 4.0) -> np.ndarray:
    return np.arange(int(FS * seconds)) / FS


def _rest(n: int, level: float = 1.0, seed: int = 0) -> np.ndarray:
    """Resting %MVC: a small positive wobble, as a real envelope is."""
    rng = np.random.default_rng(seed)
    return level + np.abs(rng.normal(0.0, level * 0.3, n))


class TestTheIndexItself:
    def test_identical_envelopes_give_100_percent(self) -> None:
        """The factor of two in the formula is what makes this come out at
        100 rather than 50."""
        env = 20.0 + 25.0 * np.sin(2 * np.pi * 0.5 * _t()) ** 2
        assert coactivation_index(env, env, FS).index == pytest.approx(100.0)

    def test_disjoint_activation_gives_zero(self) -> None:
        """One works while the other rests, in turn: nothing is shared."""
        t = _t()
        a = np.where(t < 2.0, 40.0, 0.0)
        b = np.where(t >= 2.0, 40.0, 0.0)
        assert coactivation_index(a, b, FS).index == pytest.approx(0.0, abs=0.5)

    def test_it_is_invariant_to_scale(self) -> None:
        """It is a ratio, so multiplying both envelopes cannot change it. This
        is also why a normalisation that is merely *consistent* still gives a
        usable index."""
        env_a = 10.0 + 30.0 * np.sin(2 * np.pi * 0.5 * _t()) ** 2
        env_b = 8.0 + 20.0 * np.cos(2 * np.pi * 0.5 * _t()) ** 2
        one = coactivation_index(env_a, env_b, FS).index
        many = coactivation_index(env_a * 7.0, env_b * 7.0, FS).index
        assert one == pytest.approx(many, rel=1e-9)

    def test_partial_overlap_lands_between(self) -> None:
        t = _t()
        a = 40.0 * (np.sin(2 * np.pi * 0.5 * t) ** 2)
        b = 40.0 * (np.sin(2 * np.pi * 0.5 * t + 0.8) ** 2)
        index = coactivation_index(a, b, FS).index
        assert 20.0 < index < 95.0, index


class TestTheSafeguards:
    def test_two_resting_muscles_are_not_reported(self) -> None:
        """**The one that matters.**

        Two muscles doing nothing have similar baseline noise, so the raw
        formula returns something close to 100 %. Reported as a number it
        would read as total co-contraction on a recording where the subject
        never moved.
        """
        n = int(FS * 4)
        result = coactivation_index(_rest(n, seed=1), _rest(n, seed=2), FS)
        assert result.index is None
        assert result.reason and "5" in result.reason

    def test_the_unguarded_formula_really_would_have_said_almost_100(
        self,
    ) -> None:
        """What the student would have been shown without the safeguards.

        Both are disabled here — no floor and no resting level subtracted —
        because that is the textbook formula, and it returns nearly total
        co-contraction for two muscles doing nothing at all. The test states
        the danger rather than assuming it.
        """
        n = int(FS * 4)
        a, b = _rest(n, seed=1), _rest(n, seed=2)
        naive = coactivation_index(
            a, b, FS, floor_pct=0.0, rest_1=0.0, rest_2=0.0
        )
        assert naive.index is not None and naive.index > 85.0, naive.index

    def test_subtracting_the_resting_level_already_halves_it(self) -> None:
        """The second safeguard on its own is not enough — hence the floor."""
        n = int(FS * 4)
        a, b = _rest(n, seed=1), _rest(n, seed=2)
        sin_suelo = coactivation_index(a, b, FS, floor_pct=0.0)
        assert sin_suelo.index is not None
        assert 30.0 < sin_suelo.index < 70.0, sin_suelo.index

    def test_one_active_one_below_the_floor_is_not_reported(self) -> None:
        """The reciprocal movement of the practical: no co-activation to
        measure, and the program says so instead of inventing a figure."""
        t = _t()
        active = 40.0 * (np.sin(2 * np.pi * 0.5 * t) ** 2)
        quiet = _rest(t.size, level=1.0, seed=3)
        result = coactivation_index(active, quiet, FS, name_2="Extensor")
        assert result.index is None
        assert "Extensor" in (result.reason or "")

    def test_a_high_baseline_cannot_sneak_past_the_floor(self) -> None:
        """Why the resting level is subtracted before anything else: a noisy
        baseline sitting at 8 % MVC would otherwise clear a 5 % floor without
        a single contraction."""
        n = int(FS * 4)
        noisy = _rest(n, level=8.0, seed=4)
        result = coactivation_index(noisy, _rest(n, level=8.0, seed=5), FS)
        assert result.index is None, result.index

    def test_the_means_are_reported_even_when_the_index_is_not(self) -> None:
        """They are the finding; the index only summarises it."""
        t = _t()
        active = 40.0 * (np.sin(2 * np.pi * 0.5 * t) ** 2)
        result = coactivation_index(active, _rest(t.size, seed=6), FS)
        assert result.index is None
        assert result.mean_1 > 5.0
        assert result.mean_2 < 5.0

    def test_resting_level_is_taken_over_the_whole_span(self) -> None:
        """Per window it would erase the very activation being measured: a
        window that is entirely grip has a high 10th percentile."""
        t = _t(12.0)
        env = np.where(t > 8.0, 40.0, 2.0)
        assert resting_level(env) == pytest.approx(2.0, abs=0.5)


class TestPerWindow:
    @staticmethod
    def _three_phase():
        """Flexion, extension, then grip — the practical's own protocol."""
        t = _t(12.0)
        flex = (t < 4.0).astype(float)
        ext = ((t >= 4.0) & (t < 8.0)).astype(float)
        grip = (t >= 8.0).astype(float)
        rest = 1.0
        a = rest + 40.0 * flex + 2.0 * ext + 38.0 * grip
        b = rest + 2.0 * flex + 40.0 * ext + 35.0 * grip
        markers = [(0.0, "Flexion"), (4.0, "Extension"), (8.0, "Grip")]
        return a, b, markers

    def test_one_row_per_marked_window(self) -> None:
        a, b, markers = self._three_phase()
        table, from_markers = coactivation_by_window(a, b, FS, markers)
        assert from_markers is True
        assert [r.label for r in table] == ["Flexion", "Extension", "Grip"]

    def test_the_reciprocal_phases_are_not_reported_and_the_grip_is(
        self,
    ) -> None:
        """That the first two rows say "not reported" is not a defect of the
        demonstration — it is the demonstration."""
        a, b, markers = self._three_phase()
        table, _ = coactivation_by_window(a, b, FS, markers)
        flexion, extension, grip = table
        assert flexion.index is None
        assert extension.index is None
        assert grip.index is not None and grip.index > 50.0, grip.index

    def test_without_markers_it_says_so(self) -> None:
        """One figure over a recording that mixes rest, flexion and grip is
        not a measurement of anything, so the caller is told to warn."""
        a, b, _ = self._three_phase()
        table, from_markers = coactivation_by_window(a, b, FS, None)
        assert from_markers is False
        assert len(table) == 1

    def test_windows_carry_their_own_times(self) -> None:
        """Markers arrive in the recording's own time; ``t0`` is where the
        analysed span begins, so a span that starts at 5 s has its first
        marker at 5 s and not at 0."""
        a, b, _ = self._three_phase()
        markers = [(5.0, "Flexion"), (9.0, "Extension"), (13.0, "Grip")]
        table, _ = coactivation_by_window(a, b, FS, markers, t0=5.0)
        assert [r.label for r in table] == ["Flexion", "Extension", "Grip"]
        assert table[0].window_s[0] == pytest.approx(5.0)
        assert table[-1].window_s[1] == pytest.approx(17.0)

    def test_markers_before_the_analysed_span_are_ignored(self) -> None:
        """A fragment selection can leave earlier marks outside the window."""
        a, b, _ = self._three_phase()
        markers = [(1.0, "before"), (9.0, "Extension")]
        table, from_markers = coactivation_by_window(
            a, b, FS, markers, t0=5.0
        )
        assert from_markers is True
        assert [r.label for r in table] == ["Extension"]


class TestTheLastWindowEndsWithTheEffort:
    """Every marked window is closed by the operator's next mark — except the
    last, which ran to wherever the recording happened to be stopped.

    A student who marks the sustained grip, holds it, and then rests before
    reaching for the stop button got that rest inside the window. It pulls the
    mean down and can push it under the floor, so the one phase the practical
    is *about* came back as "not reported".
    """

    @staticmethod
    def _grip_then_rest(rest_s: float = 70.0, nivel: float = 12.0):
        """Ten seconds of a shared grip, then a long quiet tail.

        Twelve per cent MVC is an ordinary sustained grip, and seventy seconds
        of quiet is what a student leaves while writing down a reading before
        remembering to stop. Diluted over the eighty, the mean lands at 1.5 % —
        under the five-per-cent floor, so the effort is reported as not
        measured.
        """
        total = 10.0 + rest_s
        t = _t(total)
        agarre = (t < 10.0).astype(float)
        base = 1.0
        a = base + nivel * agarre
        b = base + (nivel - 2.0) * agarre
        return a, b, [(0.0, "Grip")]

    def test_the_pause_after_it_is_not_counted(self) -> None:
        """The phase the practical is about came back as "not reported"."""
        a, b, marks = self._grip_then_rest()
        (fila,), _ = coactivation_by_window(a, b, FS, marks)
        assert fila.index is not None, fila.reason
        assert fila.index > 50.0

    def test_the_window_says_where_it_really_ended(self) -> None:
        """Not a hidden trim: the table shows these seconds."""
        a, b, marks = self._grip_then_rest()
        (fila,), _ = coactivation_by_window(a, b, FS, marks)
        assert fila.window_s[1] == pytest.approx(10.5, abs=0.2)

    def test_the_means_are_the_efforts_and_not_the_pauses(self) -> None:
        a, b, marks = self._grip_then_rest()
        (fila,), _ = coactivation_by_window(a, b, FS, marks)
        # Ten seconds at twelve above rest, diluted by seventy of quiet,
        # reads 1.5 instead of about twelve.
        assert fila.mean_1 > 10.0

    def test_an_intermittent_effort_is_not_cut_at_its_first_dip(self) -> None:
        """The envelope of repeated contractions falls to rest between them,
        so "the first time both drop below the floor" would end the window in
        the middle of the work."""
        t = _t(20.0)
        rafagas = np.zeros(t.size)
        for inicio in (0.0, 3.0, 6.0, 9.0):
            rafagas[(t >= inicio) & (t < inicio + 1.0)] = 1.0
        a = 1.0 + 40.0 * rafagas
        b = 1.0 + 35.0 * rafagas
        (fila,), _ = coactivation_by_window(a, b, FS, [(0.0, "Grip")])
        assert fila.window_s[1] > 10.0

    def test_a_window_closed_by_the_next_mark_is_left_alone(self) -> None:
        """That boundary is the operator saying where the phase ended, and it
        is not this function's business to move it."""
        t = _t(20.0)
        primero = (t < 4.0).astype(float)
        ultimo = (t >= 10.0).astype(float)
        a = 1.0 + 40.0 * primero + 40.0 * ultimo
        b = 1.0 + 35.0 * primero + 35.0 * ultimo
        table, _ = coactivation_by_window(
            a, b, FS, [(0.0, "Flexion"), (10.0, "Grip")])
        # The first window holds four seconds of effort and six of quiet, and
        # keeps all ten.
        assert table[0].window_s == pytest.approx((0.0, 10.0))

    def test_a_window_with_no_activity_keeps_its_own_reason(self) -> None:
        """Trimming it to nothing would replace "below the floor" — which
        names the finding — with "window too short", which does not."""
        n = int(FS * 12)
        a, b = _rest(n), _rest(n, seed=1)
        (fila,), _ = coactivation_by_window(a, b, FS, [(0.0, "Grip")])
        assert fila.index is None
        assert "short" not in (fila.reason or "").lower()


class TestAMarkedWindowAlwaysGetsARow:
    """It used to be dropped when it was shorter than two samples.

    The student marked something and the table did not mention it, which reads
    as the mark not having been registered at all — a fault in the recording
    rather than in the marking.
    """

    def test_a_mark_at_the_very_end_is_still_a_row(self) -> None:
        t = _t(12.0)
        a = 1.0 + 40.0 * (t < 8.0).astype(float)
        b = 1.0 + 35.0 * (t < 8.0).astype(float)
        marks = [(0.0, "Grip"), (12.0 - 0.5 / FS, "Late")]
        table, _ = coactivation_by_window(a, b, FS, marks)
        assert [r.label for r in table] == ["Grip", "Late"]

    def test_and_it_says_why_there_is_no_number(self) -> None:
        t = _t(12.0)
        a = 1.0 + 40.0 * (t < 8.0).astype(float)
        b = 1.0 + 35.0 * (t < 8.0).astype(float)
        marks = [(0.0, "Grip"), (12.0 - 0.5 / FS, "Late")]
        table, _ = coactivation_by_window(a, b, FS, marks)
        assert table[-1].index is None
        assert table[-1].reason


class TestItIsWiredIn:
    def test_the_floor_lives_in_the_signal_profile(self) -> None:
        """Beside the Jonsson limits, not hard-coded in the maths — it has to
        be adjustable against a real forearm baseline."""
        from emgteach.profiles import EMG_PROFILE

        assert EMG_PROFILE.coact_floor_pct == pytest.approx(5.0)

    def test_the_module_is_qt_free(self) -> None:
        """Like apda.py: usable by the worker and by an offline script alike."""
        import pathlib

        import emgteach.coactivation as mod

        source = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        assert "PySide6" not in source


# ── The whole way through: recording → EDF → analysis → table ─────────────

def _forearm_edf(path, fs: int = 1000, secs: int = 24, *, refs=True,
                 phases=True) -> str:
    """A forearm recording with rest, flexion, extension and grip.

    The extensor is the smaller muscle, as it is on a real forearm; the point
    of the practical is that it nevertheless shows up during the grip.
    """
    from emgteach.io import BufferedEdfWriter, ChannelInfo
    from emgteach.mvc import mvc_ref_marker

    n = fs * secs
    t = np.arange(n) / fs
    rng = np.random.default_rng(5)

    def phase(a, b):
        return ((t >= a) & (t < b)).astype(float)

    flex, ext, grip = phase(3, 9), phase(9, 15), phase(15, 21)
    c1 = rng.normal(0, 1, n) * (0.45 * flex + 0.03 * ext + 0.40 * grip)
    c2 = rng.normal(0, 1, n) * (0.03 * flex + 0.30 * ext + 0.26 * grip)
    c1 += rng.normal(0, 0.004, n)
    c2 += rng.normal(0, 0.004, n)
    chans = [
        ChannelInfo("Flexor", dimension="mV", sample_frequency=fs),
        ChannelInfo("Extensor", dimension="mV", sample_frequency=fs),
    ]
    with BufferedEdfWriter(str(path), channels=chans) as w:
        for i in range(0, n, fs):
            w.add_samples(c1[i:i + fs], c2[i:i + fs])
        if refs:
            w.add_annotation(0.5, mvc_ref_marker(0, 0.30))
            w.add_annotation(0.6, mvc_ref_marker(1, 0.20))
        if phases:
            for at, label in ((3.0, "Flexion"), (9.0, "Extension"),
                              (15.0, "Grip")):
                w.add_annotation(at, label)
    return str(path)


@pytest.mark.gui
class TestTheTableInTheApplication:
    @staticmethod
    def _analyse(qapp, monkeypatch, edf):
        import sys
        from pathlib import Path as _P

        sys.path.insert(0, str(_P(__file__).parent))
        from test_units import _run_analysis

        return _run_analysis(qapp, monkeypatch, edf)

    def test_the_session_annotations_are_not_phases(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        """The MVC references are facts about the session, not phases of it.

        Left in, they would open a window of their own in the table *and* draw
        a marker line across every panel — a regression introduced the moment
        the reference started travelling in the file.
        """
        edf = _forearm_edf(tmp_path / "forearm.edf")
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            assert [label for _t, label in r["markers"]] == [
                "Flexion", "Extension", "Grip"
            ]
            assert [row.label for row in r["coactivation"]] == [
                "Flexion", "Extension", "Grip"
            ]
        finally:
            tab.cleanup()

    def test_the_grip_co_activates_and_the_reciprocal_phases_do_not(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        """The teaching result, end to end and through the real pipeline."""
        edf = _forearm_edf(tmp_path / "forearm.edf")
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            flexion, extension, grip = r["coactivation"]
            assert grip.index is not None and grip.index > 70.0, grip.index
            # In the reciprocal phases one muscle carries the movement…
            assert flexion.mean_1 > 5 * flexion.mean_2
            assert extension.mean_2 > 5 * extension.mean_1
            # …and in the grip both work, which is the finding.
            assert grip.mean_1 > 20.0 and grip.mean_2 > 20.0
            assert tab._tbl_coact.rowCount() == 3
            assert not tab._box_coact.isHidden()
        finally:
            tab.cleanup()

    def test_without_mvc_references_there_is_no_table(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        """No index on millivolts: the pair cannot be compared at all."""
        edf = _forearm_edf(tmp_path / "noref.edf", refs=False)
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            assert "coactivation" not in r
            assert r.get("coactivation_reason")
            assert tab._box_coact.isHidden()
        finally:
            tab.cleanup()

    def test_without_phase_markers_the_panel_says_nothing_yet(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        """The whole-recording row is still computed, and still not shown.

        This is the state right after a file is opened, now that opening one
        analyses it: the student has done nothing, so there is nothing to warn
        them about. The single row would be a co-activation index over rest and
        flexion and extension together, and the red line under it would be a
        warning about a number they cannot see. Both wait.
        """
        edf = _forearm_edf(tmp_path / "nomarks.edf", phases=False)
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            assert r["coactivation_from_markers"] is False
            assert len(r["coactivation"]) == 1
            assert not tab._selected_segments
            assert tab._lbl_coact_aviso.isHidden()
            assert tab._box_coact.isHidden()
        finally:
            tab.cleanup()

    def test_but_once_fragments_are_chosen_and_unnamed_it_does(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        """Clearing every name is deliberate, and has a consequence worth
        stating: the table has no windows to measure."""
        edf = _forearm_edf(tmp_path / "nomarks2.edf", phases=False)
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            tab._selected_segments = [(1.0, 2.0)]
            tab._refresh_coactivation(r)
            assert not tab._lbl_coact_aviso.isHidden()
            assert tab._lbl_coact_aviso.text()
        finally:
            tab.cleanup()


@pytest.mark.gui
class TestAutomaticMarkersAreNotPhases:
    """Found on the first real session: with auto-onset on, every burst wrote
    a marker, and the table grew one row per burst — seventeen of them in a
    56-second recording, each looking like a measured condition.

    Automatic onsets are events the program found. Phases are what the
    operator declared by pressing MARK.
    """

    @staticmethod
    def _analyse(qapp, monkeypatch, edf):
        import sys
        from pathlib import Path as _P

        sys.path.insert(0, str(_P(__file__).parent))
        from test_units import _run_analysis

        return _run_analysis(qapp, monkeypatch, edf)

    def _edf_with(self, path, marks) -> str:
        from emgteach.io import BufferedEdfWriter, ChannelInfo
        from emgteach.mvc import mvc_ref_marker

        fs, secs = 1000, 20
        n = fs * secs
        t = np.arange(n) / fs
        rng = np.random.default_rng(4)

        def phase(a, b):
            return ((t >= a) & (t < b)).astype(float)

        c1 = rng.normal(0, 1, n) * (0.4 * phase(4, 9) + 0.35 * phase(13, 18))
        c2 = rng.normal(0, 1, n) * (0.05 * phase(4, 9) + 0.30 * phase(13, 18))
        c1 += rng.normal(0, 0.004, n)
        c2 += rng.normal(0, 0.004, n)
        chans = [ChannelInfo("FCR", dimension="mV", sample_frequency=fs),
                 ChannelInfo("ECR", dimension="mV", sample_frequency=fs)]
        with BufferedEdfWriter(str(path), channels=chans) as w:
            for i in range(0, n, fs):
                w.add_samples(c1[i:i + fs], c2[i:i + fs])
            w.add_annotation(0.5, mvc_ref_marker(0, 0.45))
            w.add_annotation(0.6, mvc_ref_marker(1, 0.34))
            for at, label in marks:
                w.add_annotation(at, label)
        return str(path)

    def test_auto_onsets_do_not_open_windows(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        edf = self._edf_with(tmp_path / "auto.edf", [
            (4.1, "Onset (auto) — FCR"), (4.6, "Onset (auto) — FCR"),
            (13.2, "Onset (auto) — ECR"), (13.9, "Onset (auto) — FCR"),
        ])
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            # No operator phases: one row for the whole span, and the warning.
            assert r["coactivation_from_markers"] is False
            assert len(r["coactivation"]) == 1
        finally:
            tab.cleanup()

    def test_the_operators_own_marks_still_open_windows(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        """The exclusion must be surgical: it drops what the program wrote,
        not what the operator did."""
        edf = self._edf_with(tmp_path / "mixed.edf", [
            (4.0, "Flexion"), (4.6, "Onset (auto) — FCR"),
            (13.0, "Grip"), (13.9, "Onset (auto) — FCR"),
        ])
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            assert r["coactivation_from_markers"] is True
            assert [row.label for row in r["coactivation"]] == ["Flexion", "Grip"]
        finally:
            tab.cleanup()

    def test_the_spanish_label_is_excluded_too(
        self, qapp, monkeypatch, tmp_path
    ) -> None:
        """A file recorded in Spanish carries «Inicio (auto)»; both languages
        share the "(auto)" the exclusion keys on."""
        edf = self._edf_with(tmp_path / "es.edf", [
            (4.1, "Inicio (auto) — FCR"), (13.2, "Inicio (auto) — ECR"),
        ])
        tab, r = self._analyse(qapp, monkeypatch, edf)
        try:
            assert r["coactivation_from_markers"] is False
        finally:
            tab.cleanup()


@pytest.mark.gui
def test_the_table_is_as_tall_as_its_rows(qapp, tmp_path) -> None:
    """It had a fixed 150 px whatever it held.

    The practical produces three rows at most and usually one, so most of that
    height was blank table taking room the raw traces needed — and with two
    muscles there are two of those to fit. What the rows set now is a floor:
    beyond it the table fills its box, which sits in a band with two others.
    """
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget

    ajustes = QSettings("emgteach-test", "coact-alto")
    ajustes.clear()
    tab = AnalysisTab(LoggerWidget(), ajustes)
    tab.show()
    qapp.processEvents()
    try:
        tab._ajustar_alto_coact()
        vacia = tab._tbl_coact.minimumHeight()
        tab._tbl_coact.setRowCount(3)
        tab._ajustar_alto_coact()
        tres = tab._tbl_coact.minimumHeight()
        assert tres > vacia, "three rows do not make it taller than none"
        assert tres <= 160, "it grew past the ceiling that keeps it on screen"
        # And nothing pins it: the box it is in can hand it more.
        assert tab._tbl_coact.maximumHeight() > 1000
    finally:
        tab.cleanup()
