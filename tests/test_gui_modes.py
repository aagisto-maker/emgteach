"""Recording modes and the advanced-options flag.

The mode is not a filter over the interface: it *drives* what is recorded.
Hiding the channel selector without setting the channel count was a real bug —
a two-muscle set-up survived into a screen that could neither show nor change
it, so the labels and load bars claimed two muscles while the rest of the tab
behaved as if there were one. Most of what follows guards against that class
of mistake coming back.

Marked ``gui`` (needs a QApplication).
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE, MODES

pytestmark = pytest.mark.gui


def shown(widget) -> bool:
    """Whether this widget is shown at the current mode.

    ``isVisible()`` is False for everything on a tab that is not the current
    one, so it cannot answer this; the widget's own flag can.
    """
    return not widget.isHidden()


def set_mode(win, qapp, mode: str, advanced: bool | None = None) -> None:
    win._combo_mode.setCurrentIndex(MODES.index(mode))
    if advanced is not None:
        win._chk_advanced.setChecked(advanced)
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
    assert main_window._advanced() is False


def test_channel_count_selector_is_never_shown(main_window, qapp) -> None:
    """It could only ever disagree with the mode, so it has no place on screen."""
    for mode in MODES:
        set_mode(main_window, qapp, mode)
        assert not shown(main_window._tab_adq._box_nchan)


@pytest.mark.parametrize(
    ("mode", "channels"),
    [(MODE_SINGLE, 1), (MODE_PAIR, 2), (MODE_KINEMATICS, 1)],
)
def test_mode_sets_the_channel_count(main_window, qapp, mode, channels) -> None:
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


@pytest.mark.parametrize("mode", MODES)
def test_mode_sets_the_accelerometer(main_window, qapp, mode) -> None:
    set_mode(main_window, qapp, mode)
    adq = main_window._tab_adq
    uses_acc = mode == MODE_KINEMATICS
    assert adq._chk_acc.isChecked() is uses_acc
    assert shown(adq._box_acc) is uses_acc
    assert shown(adq._box_fv_guided) is uses_acc


def test_accelerometer_wiring_follows_the_mode_not_the_flag(
    main_window, qapp
) -> None:
    """The default input is A4 and a rig may have it elsewhere; hiding this
    behind the advanced flag would make a first kinematics recording read
    nothing at all."""
    adq = main_window._tab_adq
    set_mode(main_window, qapp, MODE_KINEMATICS, advanced=False)
    assert shown(adq._box_acc_wiring)
    set_mode(main_window, qapp, MODE_KINEMATICS, advanced=True)
    assert shown(adq._box_acc_wiring)
    set_mode(main_window, qapp, MODE_SINGLE)
    assert not shown(adq._box_acc_wiring)


# ── the advanced flag is orthogonal to the mode ────────────────────────


@pytest.mark.parametrize("mode", MODES)
def test_fine_controls_follow_the_flag_in_every_mode(
    main_window, qapp, mode
) -> None:
    adq, ana, cvm = (
        main_window._tab_adq, main_window._tab_ana, main_window._tab_cvm
    )
    boxes = [
        adq._box_thr, adq._box_aula, adq._box_autoonset, adq._chk_mvc_best3,
        ana._box_fenv, ana._box_roi, cvm._box_fenv,
    ]
    set_mode(main_window, qapp, mode, advanced=False)
    assert not any(shown(b) for b in boxes)
    set_mode(main_window, qapp, mode, advanced=True)
    assert all(shown(b) for b in boxes)


def test_something_still_running_stays_visible(main_window, qapp) -> None:
    """A broadcast nobody can stop is worse than one extra widget."""
    adq = main_window._tab_adq
    set_mode(main_window, qapp, MODE_SINGLE, advanced=True)
    adq._chk_aula.setChecked(True)
    set_mode(main_window, qapp, MODE_SINGLE, advanced=False)
    assert shown(adq._box_aula)
    adq._chk_aula.setChecked(False)


# ── analysis offers what the practical needs ───────────────────────────


def _acc_panel_indices(ana) -> list[int]:
    from emgteach.gui.tabs.analysis import _ACC_PIDS

    return [i for i, pid in enumerate(ana._panel_pids) if pid in _ACC_PIDS]


@pytest.mark.parametrize("mode", MODES)
def test_analysis_matches_the_mode(main_window, qapp, mode) -> None:
    from emgteach.gui.tabs.analysis import _OVERLAY_PID

    set_mode(main_window, qapp, mode, advanced=False)
    ana = main_window._tab_ana
    overlay = ana._panel_pids.index(_OVERLAY_PID)

    assert shown(ana._box_compare) is (mode == MODE_PAIR)
    assert shown(ana._chk_paneles[overlay]) is (mode == MODE_PAIR)
    assert shown(ana._btn_fv) is (mode == MODE_KINEMATICS)
    for i in _acc_panel_indices(ana):
        assert shown(ana._chk_paneles[i]) is (mode == MODE_KINEMATICS)

    # The three teaching panels are always on offer; the further EMG analyses
    # apply to any practical and so follow the flag.
    assert all(shown(c) for c in ana._chk_paneles[:3])
    assert not any(shown(c) for c in ana._chk_paneles[3:8])
    set_mode(main_window, qapp, mode, advanced=True)
    assert all(shown(c) for c in ana._chk_paneles[3:8])


def test_panels_the_mode_hides_are_unticked_and_restored(
    main_window, qapp
) -> None:
    """The plotting code selects by isChecked(), so a panel left ticked would
    still be drawn with no visible way to turn it off."""
    ana = main_window._tab_ana
    set_mode(main_window, qapp, MODE_KINEMATICS, advanced=True)
    acc = [i for i in _acc_panel_indices(ana) if ana._chk_paneles[i].isEnabled()]
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
        staticmethod(lambda parent, title, text, *a, **k: warnings.append((title, text))),
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


@pytest.mark.parametrize("mode", [MODE_SINGLE, MODE_KINEMATICS])
def test_other_practicals_accept_a_single_channel_file(
    main_window, qapp, tmp_path, monkeypatch, mode
) -> None:
    from PySide6.QtWidgets import QMessageBox

    warnings: list = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warnings.append(a)),
    )
    set_mode(main_window, qapp, mode)
    main_window._tab_ana._populate_channels(make_edf(tmp_path / "one.edf", 1))
    qapp.processEvents()
    assert warnings == []


# ── normalisation ──────────────────────────────────────────────────────


def test_auto_normalisation_needs_the_advanced_flag(main_window, qapp) -> None:
    """Auto-normalisation divides the signal by a percentile of itself, which
    makes the Jonsson limits meaningless. Worth keeping for someone who knows
    what it is for; worth removing otherwise."""
    cvm = main_window._tab_cvm
    cvm._edit_path.setText("recording.edf")
    cvm._edit_cvm_path.clear()

    set_mode(main_window, qapp, MODE_SINGLE, advanced=False)
    cvm._refresh_compute_enabled()
    assert not cvm._btn_calcular.isEnabled()

    cvm._edit_cvm_path.setText("reference.edf")
    cvm._refresh_compute_enabled()
    assert cvm._btn_calcular.isEnabled()

    cvm._edit_cvm_path.clear()
    set_mode(main_window, qapp, MODE_SINGLE, advanced=True)
    cvm._refresh_compute_enabled()
    assert cvm._btn_calcular.isEnabled()


# ── hiding containers, not widgets ─────────────────────────────────────


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("advanced", [False, True])
def test_no_caption_is_left_behind(main_window, qapp, mode, advanced) -> None:
    """Several controls sit beside plain QLabels that are not kept as
    attributes, so hiding the widget alone would strand its caption."""
    from PySide6.QtWidgets import QLabel, QTabWidget

    orphans = {
        "Channels:", "ACC ch:", "Warning", "Danger", "k:", "from", "to",
        "Envelope cutoff frequency (Hz):", "Accelerometer:", "Compared with:",
    }
    set_mode(main_window, qapp, mode, advanced=advanced)
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
        if advanced:
            stranded -= {"Warning", "Danger", "k:", "from", "to",
                         "Envelope cutoff frequency (Hz):"}
        assert not stranded, f"{mode}/advanced={advanced}: {sorted(stranded)}"
