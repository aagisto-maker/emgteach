"""The guided tour: what it offers, and that every step has something to point at.

Marked ``gui`` (needs a QApplication).
"""

from __future__ import annotations

import pytest

from emgteach.gui.tour import build_tour
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE, MODES

pytestmark = pytest.mark.gui


def set_mode(win, qapp, mode: str) -> None:
    win._combo_mode.setCurrentIndex(MODES.index(mode))
    qapp.processEvents()


@pytest.fixture
def offer(monkeypatch):
    """Capture the start-up offer instead of blocking on it.

    What each dialog *said* is recorded, not the dialog itself: the message
    box is owned by the window and its C++ side goes away with it, so keeping
    the widget and reading it later dereferences freed memory.

    Answers "No" so no tour starts.
    """
    from PySide6.QtWidgets import QMessageBox

    raised: list[dict] = []

    def fake_exec(self):
        box = self.checkBox()
        raised.append({
            "text": self.text(),
            "has_checkbox": box is not None,
            "checked": box.isChecked() if box is not None else None,
        })
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return raised


# ── the start-up offer ─────────────────────────────────────────────────


def test_building_the_window_opens_no_dialog(main_window, offer) -> None:
    """A modal raised from the constructor blocks anything that creates a
    MainWindow without a user in front of it — it hung the test suite once.
    Offering the tour is start-up behaviour and belongs in main()."""
    assert offer == []


def test_offer_is_made_and_the_choice_is_stored(main_window, offer) -> None:
    main_window.maybe_offer_tour()
    assert len(offer) == 1

    # The tick box, not the answer, decides whether it comes back: a teaching
    # machine sees a different student most sessions.
    assert offer[0]["has_checkbox"]
    assert offer[0]["checked"]
    assert main_window._settings.value("app/tour_offer", True, type=bool)


def test_unticking_the_box_stops_it_coming_back(main_window, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    raised: list[str] = []

    def decline(self):
        raised.append(self.text())
        self.checkBox().setChecked(False)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", decline)

    main_window.maybe_offer_tour()
    assert len(raised) == 1
    assert main_window._settings.value("app/tour_offer", True, type=bool) is False

    main_window.maybe_offer_tour()
    assert len(raised) == 1          # not asked a second time


def test_the_offer_names_the_sensor_of_the_chosen_practical(
    main_window, qapp, offer
) -> None:
    """The welcome box named both sensors whatever the practical was, and the
    MyoWare board cannot record two channels or an accelerometer."""
    set_mode(main_window, qapp, MODE_SINGLE)
    main_window.maybe_offer_tour()
    assert "BITalino" in offer[0]["text"] and "MyoWare" in offer[0]["text"]

    for mode in (MODE_PAIR, MODE_KINEMATICS):
        offer.clear()
        set_mode(main_window, qapp, mode)
        main_window.maybe_offer_tour()
        assert "BITalino" in offer[0]["text"], mode
        assert "MyoWare" not in offer[0]["text"], mode


# ── the tour follows the mode ──────────────────────────────────────────


@pytest.mark.parametrize("mode", MODES)
def test_each_mode_names_the_device_it_can_be_recorded_with(
    main_window, qapp, mode
) -> None:
    """Only the single-muscle practical can be done with the Arduino board.

    The pair needs two channels and the kinematics practical the
    accelerometer, so offering that board there offers hardware that cannot
    record what is about to be recorded.
    """
    set_mode(main_window, qapp, mode)
    bodies = " ".join(step.body for step in build_tour(main_window))
    assert "BITalino" in bodies
    assert ("Arduino" in bodies) is (mode == MODE_SINGLE)


def test_steps_match_the_practical(main_window, qapp) -> None:
    steps: dict[str, list[str]] = {}
    for mode in MODES:
        set_mode(main_window, qapp, mode)
        steps[mode] = [s.title.lower() for s in build_tour(main_window)]

    def mentions(mode: str, word: str) -> bool:
        return any(word in title for title in steps[mode])

    assert not mentions(MODE_SINGLE, "accelerometer")
    assert not mentions(MODE_SINGLE, "antagonist")
    assert mentions(MODE_PAIR, "antagonist")
    assert not mentions(MODE_PAIR, "accelerometer")
    assert mentions(MODE_KINEMATICS, "accelerometer")
    assert mentions(MODE_KINEMATICS, "force-velocity")
    assert not mentions(MODE_KINEMATICS, "antagonist")


# ── running it ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", MODES)
def test_every_step_has_something_to_point_at(main_window, qapp, mode) -> None:
    """A step whose target is hidden still displays, centred — but being told
    about a control you cannot see is how tours become useless."""
    set_mode(main_window, qapp, mode)
    main_window.start_tour()
    qapp.processEvents()
    coach = main_window._coach

    for index in range(len(coach._steps)):
        coach._index = index
        coach._render()
        qapp.processEvents()
        assert coach._hole is not None, coach._steps[index].title
        # And the panel must stay inside the window.
        assert coach.rect().contains(coach._panel.geometry())
    coach.stop()


def test_navigation(main_window, qapp) -> None:
    set_mode(main_window, qapp, MODE_SINGLE)
    main_window.start_tour()
    qapp.processEvents()
    coach = main_window._coach

    assert coach.isVisible()
    assert coach.size() == main_window.size()
    assert not coach._btn_back.isEnabled()      # nothing before the first step

    coach.next()
    assert coach._index == 1
    assert coach._btn_back.isEnabled()
    coach.back()
    assert coach._index == 0

    coach._btn_skip.click()
    qapp.processEvents()
    assert not coach.isVisible()


def test_finishing_closes_it(main_window, qapp) -> None:
    set_mode(main_window, qapp, MODE_SINGLE)
    main_window.start_tour()
    qapp.processEvents()
    coach = main_window._coach

    for _ in range(len(coach._steps) - 1):
        coach.next()
    assert coach._btn_next.text() in ("Finish", "Terminar")
    coach.next()
    qapp.processEvents()
    assert not coach.isVisible()


def test_the_tour_visits_all_three_tabs(main_window, qapp) -> None:
    set_mode(main_window, qapp, MODE_SINGLE)
    main_window.start_tour()
    qapp.processEvents()
    coach = main_window._coach

    seen = set()
    for _ in range(len(coach._steps)):
        seen.add(main_window._tabs.currentIndex())
        coach.next()
        qapp.processEvents()
    assert seen == {0, 1, 2}


def test_it_refuses_while_recording(main_window, qapp, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    told: list = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: told.append(a)),
    )
    monkeypatch.setattr(main_window._tab_adq, "is_recording", lambda: True)
    main_window.start_tour()
    assert told
    assert not main_window._coach.isVisible()


class TestNothingIsClipped:
    """A wrapped QLabel only knows its height once its width is fixed, and a
    layout only asks through heightForWidth when the size policy says to. Get
    either wrong and the panel is sized from the unwrapped hint: every step
    lost its last lines, and the two-paragraph ones about six.
    """

    @pytest.mark.parametrize("language", ["en", "es"])
    @pytest.mark.parametrize("mode", MODES)
    def test_every_step_shows_all_of_its_text(
        self, main_window, qapp, mode, language
    ) -> None:
        from emgteach.i18n import get_language, set_language

        previous = get_language()
        set_language(language)
        try:
            set_mode(main_window, qapp, mode)
            main_window.start_tour()
            qapp.processEvents()
            coach = main_window._coach

            for index in range(len(coach._steps)):
                coach._index = index
                coach._render()
                qapp.processEvents()
                qapp.processEvents()
                for label in (coach._lbl_title, coach._lbl_body):
                    needed = label.heightForWidth(label.width())
                    assert needed <= label.height() + 1, (
                        f"{language}/{mode} — {coach._steps[index].title}: "
                        f"{needed - label.height()} px of text cut off"
                    )
                # And the panel itself has to stay inside the window.
                assert coach.rect().contains(coach._panel.geometry())
            coach.stop()
        finally:
            set_language(previous)
