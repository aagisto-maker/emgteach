"""Recording modes: what each practical records, and what it puts on screen.

The mode is not a filter over the interface, it *drives* what is recorded.
Hiding the channel selector without setting the channel count was a real bug —
a two-muscle set-up survived into a screen that could neither show nor change
it, so the labels and load bars claimed two muscles while the rest of the tab
behaved as if there were one.

The level of detail belongs to the practical too. There used to be a separate
"advanced options" tick, orthogonal to the mode, and holding two independent
axes in mind to explain why a control was on screen is what made the interface
hard to follow. The fine controls now live in a fourth mode of their own.

Marked ``gui`` (needs a QApplication).
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt

from emgteach.modes import (
    MODE_KINEMATICS,
    MODE_PAIR,
    MODE_SINGLE,
    MODES,
    mode_complexity,
    mode_complexity_colour,
    mode_shows_fine_controls,
)

pytestmark = pytest.mark.gui

#: Practicals, as opposed to the free mode, which makes no teaching claim.
PRACTICALS = (MODE_SINGLE, MODE_PAIR, MODE_KINEMATICS)


def shown(widget) -> bool:
    """Whether this widget is shown at the current mode.

    ``isVisible()`` is False for everything on a tab that is not the current
    one, so it cannot answer this; the widget's own flag can.
    """
    return not widget.isHidden()


def set_mode(win, qapp, mode: str) -> None:
    win._combo_mode.setCurrentIndex(MODES.index(mode))
    qapp.processEvents()


def make_edf(path, n_channels: int, fs: int = 1000, secs: int = 12) -> str:
    from emgteach.io import BufferedEdfWriter, ChannelInfo

    t = np.arange(fs * secs) / fs
    sig = 0.2 * np.sin(2 * np.pi * 80 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t))
    channels = [
        ChannelInfo(f"EMG{i + 1}", dimension="mV", sample_frequency=fs)
        for i in range(n_channels)
    ]
    with BufferedEdfWriter(str(path), channels=channels) as writer:
        writer.add_samples(*[(sig * (1 + 0.2 * i)).astype(float)
                             for i in range(n_channels)])
    return str(path)


# ── the mode drives the recording ──────────────────────────────────────


def test_defaults_to_the_single_muscle_practical(main_window) -> None:
    assert main_window._mode() == MODE_SINGLE


def test_channel_count_selector_is_never_shown(main_window, qapp) -> None:
    """It could only ever disagree with the mode, so it has no place on screen."""
    for mode in MODES:
        set_mode(main_window, qapp, mode)
        assert not shown(main_window._tab_adq._box_nchan)


@pytest.mark.parametrize(
    ("mode", "channels"),
    [(MODE_SINGLE, 1), (MODE_PAIR, 2), (MODE_KINEMATICS, 1)],
)
def test_practical_sets_the_channel_count(main_window, qapp, mode, channels) -> None:
    set_mode(main_window, qapp, mode)
    adq = main_window._tab_adq
    assert adq._n_channels == channels
    # The per-channel name boxes follow, so nothing claims a muscle that is
    # not being recorded.
    assert shown(adq._edit_labels[0])
    assert shown(adq._edit_labels[1]) is (channels == 2)


def test_leaving_the_pair_practical_clears_the_second_channel(
    main_window, qapp
) -> None:
    """The bug this whole design exists to prevent."""
    adq = main_window._tab_adq
    set_mode(main_window, qapp, MODE_PAIR)
    assert adq._n_channels == 2

    set_mode(main_window, qapp, MODE_SINGLE)
    assert adq._n_channels == 1
    assert not shown(adq._edit_labels[1])
    assert adq._combo_n_channels.currentIndex() == 0


@pytest.mark.gui
def test_a_practical_that_names_its_channels_hides_the_boxes(
    main_window, qapp
) -> None:
    """And names them without writing into them.

    Writing into the boxes looked simpler and was wrong twice over: the name
    stayed behind on the next practical — an agonist/antagonist recording came
    out labelled "Muscle" and "EMG2" — and it went through the save-on-change
    into QSettings, so choosing the single-muscle practical once overwrote the
    muscle name the operator had stored.
    """
    from emgteach.modes import mode_fixed_labels

    adq = main_window._tab_adq
    adq._edit_labels[0].setText("FCR")
    adq._edit_labels[1].setText("ECR")

    for mode in (MODE_PAIR, MODE_SINGLE, MODE_KINEMATICS, MODE_PAIR):
        set_mode(main_window, qapp, mode)
        fijas = mode_fixed_labels(mode)
        assert shown(adq._box_labels) is (not fijas), mode
        if fijas:
            assert adq._active_labels()[0] not in ("FCR", "ECR"), mode
        else:
            assert adq._active_labels() == ["FCR", "ECR"], mode
        # Whatever the practical calls its channels, the operator's own names
        # are still in the boxes when they come back to them.
        assert [e.text() for e in adq._edit_labels[:2]] == ["FCR", "ECR"], mode


@pytest.mark.parametrize("mode", PRACTICALS)
def test_practical_sets_the_accelerometer(main_window, qapp, mode) -> None:
    from emgteach.modes import mode_uses_acc

    set_mode(main_window, qapp, mode)
    adq = main_window._tab_adq
    uses_acc = mode_uses_acc(mode)
    assert adq._chk_acc.isChecked() is uses_acc
    assert shown(adq._box_acc) is uses_acc
    assert shown(adq._box_fv_guided) is uses_acc


def test_accelerometer_wiring_travels_with_the_accelerometer(
    main_window, qapp
) -> None:
    """The default input is A4 and a rig may have it elsewhere, so this cannot
    be tucked away: a first kinematics recording would read nothing at all."""
    adq = main_window._tab_adq
    set_mode(main_window, qapp, MODE_KINEMATICS)
    assert shown(adq._box_acc_wiring)
    set_mode(main_window, qapp, MODE_SINGLE)
    assert not shown(adq._box_acc_wiring)


# ── the level of detail is part of the practical ───────────────────────


@pytest.mark.parametrize("mode", MODES)
def test_fine_controls_belong_to_the_free_mode(main_window, qapp, mode) -> None:
    """A practical that offered a filter cut-off would be asking the student to
    decide it in the middle of a physiology exercise, which is a different
    lesson from the one it is teaching.

    Two things have left this list since it was written, both because the
    bench showed they were not refinements at all: **"Best of 3"**, which is
    how a maximum is measured rather than a nicety — one attempt has nothing
    to fall back on, and a bad reference silently corrupts every percentage
    after it — and the **fragment editor**, since keeping the part of a
    recording that came out well is hygiene. The numeric region boxes stay,
    because they ask for two figures the student does not have.
    """
    adq, ana, cvm = (
        main_window._tab_adq, main_window._tab_ana, main_window._tab_cvm
    )
    boxes = [adq._box_thr, ana._box_fenv, ana._box_roi, cvm._box_fenv]
    set_mode(main_window, qapp, mode)
    esperado = mode_shows_fine_controls(mode)
    assert esperado is (mode == MODE_KINEMATICS)
    assert all(shown(b) is esperado for b in boxes)
    # Automatic onsets are not among them any more. They used to be hidden in
    # the practicals, which was defensible while there was a MARK button
    # beside them; with manual marking gone it would leave an empty box and a
    # recording with no marks in it at all, and the analysis finds each effort
    # by those marks.
    assert shown(adq._box_autoonset)


def test_the_advanced_tick_is_gone(main_window) -> None:
    """Two independent axes is what made it hard to follow."""
    assert not hasattr(main_window, "_chk_advanced")


@pytest.mark.parametrize("mode", MODES)
def test_classroom_broadcast_is_offered_in_every_mode(
    main_window, qapp, mode
) -> None:
    """Following the recording on their own phones is what the practical is
    for, not a fine adjustment: a teaching laboratory usually has one sensor,
    and this is what turns one recording into something the whole class
    reads."""
    set_mode(main_window, qapp, mode)
    assert shown(main_window._tab_adq._box_aula)


# ── the complexity band ────────────────────────────────────────────────


class TestComplexityBand:
    """It says how much of the reading is interpretation rather than
    measurement — which is the thing a student cannot tell by looking."""

    def test_every_mode_has_its_own_level(self, main_window, qapp) -> None:
        niveles = {mode_complexity(m) for m in MODES}
        assert niveles == {"basic", "intermediate", "advanced"}

    @pytest.mark.parametrize("mode", MODES)
    def test_the_band_follows_the_mode(self, main_window, qapp, mode) -> None:
        set_mode(main_window, qapp, mode)
        texto = main_window._lbl_nivel.text()
        assert texto, f"{mode}: the band says nothing"
        assert mode_complexity_colour(mode) in main_window._lbl_nivel.styleSheet()

    @pytest.mark.parametrize("mode", MODES)
    def test_the_level_fits_beside_the_selector(
        self, main_window, qapp, mode
    ) -> None:
        """It stopped being a band across the window and became a tag beside
        the practical selector, at the selector's width.

        Which is a width it has to fit in: elided, the word that disappears is
        the one naming the level, and a tag reading "Análisis inter…" says
        less than no tag at all. The full caption is the tooltip regardless.
        """
        set_mode(main_window, qapp, mode)
        etiqueta = main_window._lbl_nivel
        ancho_texto = etiqueta.fontMetrics().horizontalAdvance(etiqueta.text())
        assert ancho_texto <= etiqueta.width() - 16, mode
        assert etiqueta.toolTip() == etiqueta.text()

    def test_the_level_sits_in_the_corner_and_not_across_the_window(
        self, main_window
    ) -> None:
        """A full-width band is a lot of emphasis for a caption the selector
        beside it already implies, and emphasis is read as importance."""
        corner = main_window._tabs.cornerWidget(Qt.Corner.TopRightCorner)
        assert main_window._lbl_nivel.parent() is corner

    def test_the_practicals_are_ordered(self) -> None:
        """Their order is the point: one muscle, then two, then derived."""
        assert [mode_complexity(m) for m in PRACTICALS] == [
            "basic", "intermediate", "advanced",
        ]

    def test_every_mode_is_a_practical_on_the_scale(self) -> None:
        """Every mode is a practical with a place on the scale: nothing is
        offered that is not one of the three, and each is named for what it
        measures."""
        assert set(MODES) == set(PRACTICALS)
        colores = {mode_complexity_colour(m) for m in MODES}
        assert len(colores) == len(MODES)


# ── analysis offers what the practical needs ───────────────────────────


def panels_offered(ana) -> set[int]:
    """Panel identifiers currently on offer."""
    return {
        ana._panel_pids[i]
        for i, chk in enumerate(ana._chk_paneles)
        if not chk.isHidden()
    }


def test_each_practical_offers_its_own_panels(main_window, qapp) -> None:
    from emgteach.gui.tabs.analysis import (
        _CORE_PIDS,
        _OVERLAY_PID,
        _RAW2_PID,
    )

    ana = main_window._tab_ana

    set_mode(main_window, qapp, MODE_SINGLE)
    assert panels_offered(ana) == set(_CORE_PIDS)

    # The pair practical is a closed set: each muscle raw, then the two
    # envelopes overlaid. A spectrum there would be about one of the two.
    set_mode(main_window, qapp, MODE_PAIR)
    assert panels_offered(ana) == {0, _RAW2_PID, _OVERLAY_PID}

    # The kinematics practical is the one place nothing is withheld — but
    # not all at once: it opens on its own six (the core and the
    # accelerometer panels) and «More panels…» reveals every other one.
    # Thirteen boxes on one row overflowed into a scroll bar.
    set_mode(main_window, qapp, MODE_KINEMATICS)
    propios = panels_offered(ana)
    assert len(propios) == 6 and propios < set(ana._panel_pids)
    ana._btn_mas_paneles.setChecked(True)
    qapp.processEvents()
    assert panels_offered(ana) == set(ana._panel_pids)
    ana._btn_mas_paneles.setChecked(False)


def test_the_second_raw_panel_sits_next_to_the_first(main_window) -> None:
    """Reading muscle against muscle needs them adjacent, not one at each end."""
    from emgteach.gui.tabs.analysis import _RAW2_PID

    pids = main_window._tab_ana._panel_pids
    assert pids.index(_RAW2_PID) == pids.index(0) + 1


def test_panels_the_mode_hides_are_unticked_and_restored(
    main_window, qapp
) -> None:
    """The plotting code selects by isChecked(), so a panel left ticked would
    still be drawn with no visible way to turn it off."""
    from emgteach.gui.tabs.analysis import _ACC_PIDS

    ana = main_window._tab_ana
    set_mode(main_window, qapp, MODE_KINEMATICS)
    acc = [i for i, pid in enumerate(ana._panel_pids)
           if pid in _ACC_PIDS and ana._chk_paneles[i].isEnabled()]
    for i in acc:
        ana._chk_paneles[i].setChecked(True)

    set_mode(main_window, qapp, MODE_SINGLE)
    assert not any(ana._chk_paneles[i].isChecked() for i in acc)

    set_mode(main_window, qapp, MODE_KINEMATICS)
    assert all(ana._chk_paneles[i].isChecked() for i in acc)


# ── the recording decides the channels, and says so when it cannot ─────


def test_pair_practical_compares_without_being_asked(
    main_window, qapp, tmp_path
) -> None:
    """With two channels in the file the pair is a property of the recording,
    not something to opt into."""
    ana = main_window._tab_ana
    set_mode(main_window, qapp, MODE_PAIR)
    ana._populate_channels(make_edf(tmp_path / "two.edf", 2))
    qapp.processEvents()

    assert ana._chk_compare2.isChecked()
    assert not shown(ana._chk_compare2)          # nothing to opt into
    assert ana._combo_canal.currentText() != ana._combo_canal2.currentText()


def test_pair_practical_warns_on_a_single_channel_file(
    main_window, qapp, tmp_path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(
            lambda parent, title, text, *a, **k: warnings.append((title, text))
        ),
    )

    ana = main_window._tab_ana
    set_mode(main_window, qapp, MODE_PAIR)
    ana._populate_channels(make_edf(tmp_path / "one.edf", 1))
    qapp.processEvents()

    assert len(warnings) == 1
    _, text = warnings[0]
    # It has to name the way out, not just the problem.
    assert "Single-muscle" in text or "un músculo" in text
    assert "kinematics" in text or "Cinemática" in text
    assert not ana._chk_compare2.isChecked()


# ── two muscles recorded, one practical that studies one ───────────────


class TestChoosingWhichMuscle:
    """A two-channel file in a one-muscle practical has to ask.

    Taking the first channel silently is the failure this prevents: every
    panel, metric and report would be about a muscle nobody picked, and
    nothing on screen would say which one it was.
    """

    @staticmethod
    def _capture(monkeypatch) -> list[dict]:
        from PySide6.QtWidgets import QMessageBox

        raised: list[dict] = []

        def fake_exec(self):
            raised.append({
                "text": self.text(),
                "buttons": [b.text() for b in self.buttons()],
            })
            return QMessageBox.StandardButton.NoButton

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        return raised

    @pytest.mark.parametrize("mode", [MODE_SINGLE, MODE_KINEMATICS])
    def test_asks_and_names_the_muscles(
        self, main_window, qapp, tmp_path, monkeypatch, mode
    ) -> None:
        raised = self._capture(monkeypatch)
        set_mode(main_window, qapp, mode)
        main_window._tab_ana._populate_channels(make_edf(tmp_path / "two.edf", 2))
        qapp.processEvents()

        assert len(raised) == 1
        # The buttons carry the channel labels, which is why they are typed at
        # recording time — not "EMG1"/"EMG2" as stored positions.
        assert raised[0]["buttons"] == ["EMG1", "EMG2"]

    def test_the_pair_practical_does_not_ask(
        self, main_window, qapp, tmp_path, monkeypatch
    ) -> None:
        """There both muscles are the point, so there is nothing to choose."""
        raised = self._capture(monkeypatch)
        set_mode(main_window, qapp, MODE_PAIR)
        main_window._tab_ana._populate_channels(make_edf(tmp_path / "two.edf", 2))
        qapp.processEvents()
        assert raised == []

    def test_a_single_channel_file_does_not_ask(
        self, main_window, qapp, tmp_path, monkeypatch
    ) -> None:
        raised = self._capture(monkeypatch)
        set_mode(main_window, qapp, MODE_SINGLE)
        main_window._tab_ana._populate_channels(make_edf(tmp_path / "one.edf", 1))
        qapp.processEvents()
        assert raised == []


# ── normalisation ──────────────────────────────────────────────────────


def test_the_missing_calibration_is_named_in_every_mode(main_window, qapp) -> None:
    """It used to depend on the practical: the basic levels disabled Compute
    until a reference file was chosen and the free one let auto-normalisation
    through. Neither exists now — the maximum is inside the recording — so the
    answer is the same everywhere, and it is a warning rather than a lock: two
    of the three panels need no reference at all."""
    cvm = main_window._tab_cvm
    cvm._edit_path.setText("recording.edf")

    for mode in (MODE_SINGLE, MODE_KINEMATICS):
        set_mode(main_window, qapp, mode)
        cvm._refresh_compute_enabled()
        assert cvm._btn_calcular.isEnabled()
        assert shown(cvm._lbl_calcular_bloqueado)
        assert cvm._lbl_calcular_bloqueado.toolTip()


class TestMvcPanelSelection:
    """The tab always drew all three panels, which is a lot of vertical space
    for a student who is after one of them."""

    def test_all_three_are_offered_and_ticked(self, main_window) -> None:
        chks = main_window._tab_cvm._chk_paneles
        assert len(chks) == 3
        assert all(c.isChecked() for c in chks)

    def test_unticking_drops_the_panel(self, main_window) -> None:
        cvm = main_window._tab_cvm
        cvm._chk_paneles[0].setChecked(False)
        cvm._chk_paneles[1].setChecked(False)
        assert cvm._paneles_activos() == [2]

    def test_nothing_ticked_still_draws_one(self, main_window) -> None:
        """A blank canvas reads as a fault rather than as a choice."""
        cvm = main_window._tab_cvm
        for c in cvm._chk_paneles:
            c.setChecked(False)
        assert cvm._paneles_activos() == [0]


# ── hiding containers, not widgets ─────────────────────────────────────


@pytest.mark.parametrize("mode", MODES)
def test_no_caption_is_left_behind(main_window, qapp, mode) -> None:
    """Several controls sit beside plain QLabels that are not kept as
    attributes, so hiding the widget alone would strand its caption."""
    from PySide6.QtWidgets import QLabel, QTabWidget

    orphans = {
        "Channels:", "ACC ch:", "Warning", "Danger", "k:", "from", "to",
        "Envelope cutoff frequency (Hz):", "Accelerometer:", "Compared with:",
    }
    set_mode(main_window, qapp, mode)
    tabs = main_window.findChild(QTabWidget)
    for index, tab in enumerate(
        (main_window._tab_adq, main_window._tab_ana, main_window._tab_cvm)
    ):
        tabs.setCurrentIndex(index)
        qapp.processEvents()
        if tab is main_window._tab_cvm:
            tab._dismiss_entry_screen()   # its greeting covers the tab
            qapp.processEvents()
        # Real visibility here: a caption is only stranded if the user sees it.
        visible = {
            lbl.text().strip()
            for lbl in tab.findChildren(QLabel)
            if lbl.isVisible() and lbl.text().strip()
        }
        stranded = visible & orphans
        # A caption is fine when its own block is on screen.
        if shown(main_window._tab_adq._box_acc):
            stranded -= {"Accelerometer:", "ACC ch:"}
        if shown(main_window._tab_ana._box_compare):
            stranded.discard("Compared with:")
        # "k:" belongs to the auto-onset control, which is on at every level.
        stranded.discard("k:")
        if mode_shows_fine_controls(mode):
            stranded -= {"Warning", "Danger", "from", "to",
                         "Envelope cutoff frequency (Hz):"}
        assert not stranded, f"{mode}: {sorted(stranded)}"


@pytest.mark.gui
def test_trimming_a_recording_is_offered_in_every_practical(qapp) -> None:
    """Keeping the part that came out well is hygiene, not a fine adjustment.

    A first attempt in a teaching laboratory arrives with a movement artefact,
    a loose electrode or a false start more often than not. The numeric
    "from"/"to" boxes stay advanced — they ask for two figures the student does
    not have — but the editor, which shows the recording and lets them point,
    belongs in every practical.
    """
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget
    from emgteach.modes import MODES

    for mode in MODES:
        tab = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "frag"))
        try:
            tab.apply_mode(mode, False)
            assert not tab._box_fragmentos.isHidden(), mode
        finally:
            tab.cleanup()
