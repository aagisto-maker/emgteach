"""Which pair the practical is on, and what follows from it.

The engine knows no anatomy and never did; what had converged on the forearm
is everything the student is *told and shown* — the example after the rule of
the calibration, the pictures of where the electrodes go, the hint in each
label box. A teacher running the practical on biceps and triceps got the
forearm's instructions, and one running it on a pair of their own got them too.

Three pairs now: the guide's forearm, the arm of its written variant, and
«another pair», which is any pair at all and shows the rule without an example.
**No threshold moves with the pair** — that is the promise of this change, and
the last test here is the one that holds it.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from emgteach import i18n
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.modes import MODE_PAIR, MODE_SINGLE
from emgteach.pairs import (
    PAIR_ARM,
    PAIR_FOREARM,
    PAIR_OTHER,
    PAIRS,
    pair_calibration_cue,
    pair_hint,
    pair_image,
    pair_label,
    pair_warning,
)


@pytest.fixture
def tab(qapp):
    from emgteach.gui.tabs.acquisition import AcquisitionTab

    ajustes = QSettings("emgteach-test", "el-par")
    ajustes.clear()
    widget = AcquisitionTab(LoggerWidget(), ajustes)
    widget.apply_mode(MODE_PAIR, False)
    yield widget
    widget._watchdog_timer.stop()
    widget._mvc_timer.stop()
    widget._prep_timer.stop()
    widget._load_timer.stop()
    widget.close()


def _elegir(tab, par: str) -> None:
    tab._combo_par.setCurrentIndex(PAIRS.index(par))


class TestTheTable:
    def test_the_forearm_is_the_default_and_carries_what_it_always_did(self) -> None:
        assert PAIRS[0] == PAIR_FOREARM
        assert pair_image(PAIR_FOREARM, "electrodos") == "electrodos"
        assert "FCR" in pair_hint(PAIR_FOREARM, 0)
        assert "Wrist flexion" in pair_calibration_cue(PAIR_FOREARM, 0)
        assert pair_warning(PAIR_FOREARM) == ""      # the defaults are its own

    def test_the_arm_has_its_own_names_gestures_and_picture_names(self) -> None:
        assert "biceps" in pair_hint(PAIR_ARM, 0)
        assert "triceps" in pair_hint(PAIR_ARM, 1)
        assert "Elbow flexion" in pair_calibration_cue(PAIR_ARM, 0)
        assert pair_image(PAIR_ARM, "electrodos") == "electrodos_biceps"
        assert "forearm pair" in pair_warning(PAIR_ARM)

    def test_another_pair_is_the_rule_and_nothing_else(self) -> None:
        assert pair_calibration_cue(PAIR_OTHER, 0) == ""
        assert pair_image(PAIR_OTHER, "electrodos") is None
        assert "e.g." not in pair_hint(PAIR_OTHER, 0)
        assert "forearm pair" in pair_warning(PAIR_OTHER)

    def test_every_pair_has_a_name_in_both_languages(self) -> None:
        anterior = i18n.get_language()
        try:
            for idioma in ("en", "es"):
                i18n.set_language(idioma)
                nombres = {pair_label(p) for p in PAIRS}
                assert len(nombres) == len(PAIRS), nombres
        finally:
            i18n.set_language(anterior)


class TestTheTabFollowsIt:
    def test_the_selector_is_only_in_the_pair_practical(self, tab) -> None:
        assert tab._combo_par.isVisibleTo(tab)
        tab.apply_mode(MODE_SINGLE, False)
        assert not tab._combo_par.isVisibleTo(tab)

    def test_choosing_one_changes_the_hints_and_is_remembered(self, tab) -> None:
        _elegir(tab, PAIR_ARM)
        assert tab._par == PAIR_ARM
        assert "biceps" in tab._edit_labels[0].placeholderText()
        assert tab._settings.value("adquisicion/par") == PAIR_ARM
        _elegir(tab, PAIR_OTHER)
        assert "e.g." not in tab._edit_labels[0].placeholderText()

    def test_a_name_already_typed_is_not_touched(self, tab) -> None:
        """The hints are placeholders: what the operator wrote is theirs."""
        tab._edit_labels[0].setText("FCR")
        _elegir(tab, PAIR_ARM)
        assert tab._edit_labels[0].text() == "FCR"

    def test_the_instruction_of_the_effort_follows_the_pair(self, tab) -> None:
        _elegir(tab, PAIR_ARM)
        codo = tab._mvc_gesto(0).lower()
        assert "jerk" in codo and "elbow flexion" in codo and "wrist" not in codo
        _elegir(tab, PAIR_OTHER)
        otro = tab._mvc_gesto(0).lower()
        assert "jerk" in otro
        for anatomia in ("wrist", "elbow", "forearm", "fist"):
            assert anatomia not in otro, otro

    def test_the_pictures_are_the_pairs_or_none(self, tab) -> None:
        assert tab.imagen_del_par("calibracion") is not None       # the forearm's
        _elegir(tab, PAIR_OTHER)
        assert tab.imagen_del_par("calibracion") is None
        _elegir(tab, PAIR_ARM)
        # Until they are drawn there are none, and the interface shows none
        # rather than somebody else's arm.
        assert tab.imagen_del_par("calibracion") is None

    def test_the_warning_reaches_the_log(self, tab) -> None:
        _elegir(tab, PAIR_ARM)
        texto = tab._logger.toPlainText()
        assert "forearm pair" in texto or "antebrazo" in texto
        assert "no pictures" in texto or "imágenes" in texto

    def test_the_header_says_which_pair_it_was(self, tab) -> None:
        assert tab._protocolo().endswith("(forearm)")
        _elegir(tab, PAIR_ARM)
        assert tab._protocolo().endswith("(arm)")
        tab.apply_mode(MODE_SINGLE, False)
        assert "(" not in tab._protocolo()          # only the pair practical has one


class TestTheTourOfTheDefaultPairIsUntouched:
    def test_its_steps_are_word_for_word_and_picture_for_picture(
        self, main_window, monkeypatch
    ) -> None:
        """Figure 4 of the article is a capture of two of these steps."""
        from emgteach.gui.tour import build_tour

        monkeypatch.setattr(main_window, "_mode", lambda: MODE_PAIR)
        main_window._tab_adq._par = PAIR_FOREARM
        pasos = {s.title: s for s in build_tour(main_window)}
        electrodos = pasos[i18n.tr("Connecting the sensor")]
        assert electrodos.image_path().endswith(("electrodos_es.png",
                                                 "electrodos_en.png"))
        assert "forearm pair" not in electrodos.body
        assert "antebrazo:" not in electrodos.body

    def test_another_pair_shows_no_picture_and_says_why(
        self, main_window, monkeypatch
    ) -> None:
        from emgteach.gui.tour import build_tour

        monkeypatch.setattr(main_window, "_mode", lambda: MODE_PAIR)
        main_window._tab_adq._par = PAIR_OTHER
        pasos = {s.title: s for s in build_tour(main_window)}
        electrodos = pasos[i18n.tr("Connecting the sensor")]
        assert electrodos.image_path() is None
        assert ("forearm pair" in electrodos.body or "antebrazo" in electrodos.body)


def test_no_threshold_moves_with_the_pair() -> None:
    """The promise of the whole change, in one assertion.

    The co-activation floor, the channel-separation criterion and the ranges
    of the calibration checks were measured on the forearm pair, and they stay
    where they are for every pair — which is exactly why each other pair
    carries the line that says to check them on a test recording.
    """
    import ast
    import dataclasses
    import pathlib

    import emgteach.pairs as modulo
    from emgteach.profiles import EMG_PROFILE

    antes = dataclasses.asdict(EMG_PROFILE)
    for par in PAIRS:
        pair_hint(par, 0)
        pair_calibration_cue(par, 0)
        pair_warning(par)
    assert dataclasses.asdict(EMG_PROFILE) == antes

    # And it cannot move one even by mistake, because it never reads one: the
    # table imports the translator and nothing else.
    arbol = ast.parse(pathlib.Path(modulo.__file__).read_text(encoding="utf-8"))
    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    } | {
        alias.name
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Import)
        for alias in nodo.names
    }
    assert importados == {"__future__", "emgteach.i18n"}, importados
