"""The station's BITalino address, written once in bitalino.txt next to the app.

Typed into the field, the address had to be typed again wherever the settings
did not survive — another account, a reimaged PC, the application copied on a
stick. The file travels with the application: when it is there, it is the
address the acquisition tab starts with and the one «Default» returns to.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from emgteach import station


def _write(folder: Path, text: str) -> None:
    (folder / station.ADDRESS_FILE).write_text(text, encoding="utf-8")


def test_without_the_file_there_is_no_station_address(tmp_path: Path) -> None:
    assert station.read_station_address(tmp_path) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("98:D3:91:FE:44:E4\n", "98:D3:91:FE:44:E4"),
        ("# station 3\n\n   COM5   \n", "COM5"),
        ("﻿simulada\n", "simulada"),                  # Notepad's BOM
        ("98:D3:91:FE:44:E4   # the one on the shelf\n", "98:D3:91:FE:44:E4"),
        ("", ""),                                           # present, empty: autodetect
        ("# only a comment\n\n", ""),
    ],
)
def test_the_first_line_that_is_not_a_comment(
    tmp_path: Path, text: str, expected: str
) -> None:
    _write(tmp_path, text)
    assert station.read_station_address(tmp_path) == expected


def test_the_folder_is_the_executable_s_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "emgteach.exe"))
    assert station.app_folder() == tmp_path.resolve()


# -- the acquisition tab --------------------------------------------------------


@pytest.fixture
def make_tab(qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    monkeypatch.setattr(station, "app_folder", lambda: tmp_path)
    tabs = []

    def build(saved_port: str | None = None):
        settings = QSettings("emgteach-test", "direccion-del-puesto")
        settings.clear()
        if saved_port is not None:
            settings.setValue("adquisicion/port", saved_port)
        logger = LoggerWidget()
        tab = AcquisitionTab(logger, settings)
        qapp.processEvents()
        tabs.append((tab, logger))
        return tab, logger

    yield build
    for tab, logger in tabs:
        tab.deleteLater()
        logger.deleteLater()
    qapp.processEvents()


@pytest.mark.gui
def test_the_tab_starts_with_the_file_s_address(make_tab, tmp_path: Path) -> None:
    _write(tmp_path, "# station 3\nAA:BB:CC:DD:EE:FF\n")
    tab, logger = make_tab(saved_port="COM5")
    assert tab._edit_mac.text() == "AA:BB:CC:DD:EE:FF"
    # And says where it came from, where the operator reads.
    assert station.ADDRESS_FILE in logger.toPlainText()


@pytest.mark.gui
def test_without_the_file_the_saved_address(make_tab) -> None:
    tab, _ = make_tab(saved_port="COM5")
    assert tab._edit_mac.text() == "COM5"


@pytest.mark.gui
def test_default_returns_to_the_file_s_address(make_tab, tmp_path: Path) -> None:
    _write(tmp_path, "simulada\n")
    tab, _ = make_tab()
    tab._edit_mac.setText("COM9")
    tab._reset_mac()
    assert tab._edit_mac.text() == "simulada"


@pytest.mark.gui
def test_a_station_with_the_file_is_set_up(make_tab, tmp_path: Path) -> None:
    """No address saved in the settings, but the file says it: not a first setup."""
    from emgteach.modes import MODE_SINGLE

    _write(tmp_path, "98:D3:91:FE:44:E4\n")
    tab, _ = make_tab()
    tab.apply_mode(MODE_SINGLE, False)
    assert tab._lbl_first_setup.isHidden()


@pytest.mark.gui
def test_without_file_or_saved_address_it_is_a_first_setup(make_tab) -> None:
    from emgteach.modes import MODE_SINGLE

    tab, _ = make_tab()
    tab.apply_mode(MODE_SINGLE, False)
    assert not tab._lbl_first_setup.isHidden()
