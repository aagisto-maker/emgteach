"""The connection diagnostic: does it tell a ready station from one that is not?

Run against the BITalino in software it has to pass, write its report and
never raise; against a port that does not exist it has to fail at the
connection and say so in the report. Windows' answers are faked where the
test must not depend on the machine's Bluetooth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from emgteach import diagnostics, station


@pytest.fixture
def no_bluetooth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "bluetooth_devices", lambda: [])
    monkeypatch.setattr(diagnostics, "bluetooth_com_ports", lambda: [])


def test_the_simulated_board_passes_and_the_report_is_written(tmp_path: Path) -> None:
    said: list[str] = []
    result = diagnostics.run_diagnosis("simulada", seconds=1.0, folder=tmp_path,
                                       say=said.append)
    assert result.ok, "\n".join(said)
    assert result.report_path is not None and result.report_path.parent == tmp_path
    report = result.report_path.read_text(encoding="utf-8")
    assert "SIMULATED" in report
    acquisition = next(c for c in result.checks if c.title == "Acquisition")
    rate = float(acquisition.lines[0].split(": ")[1].split(" Hz")[0])
    assert 900 <= rate <= 1100, acquisition.lines[0]


def test_the_address_comes_from_bitalino_txt(tmp_path: Path) -> None:
    (tmp_path / station.ADDRESS_FILE).write_text("# puesto 3\nsimulada\n", encoding="utf-8")
    result = diagnostics.run_diagnosis(seconds=0.5, folder=tmp_path, say=lambda _s: None)
    assert result.address == "simulada"
    assert station.ADDRESS_FILE in result.source
    assert result.ok


def test_a_port_that_is_not_there_fails_at_the_connection(
    tmp_path: Path, no_bluetooth: None
) -> None:
    said: list[str] = []
    result = diagnostics.run_diagnosis("COM987", seconds=0.5, folder=tmp_path,
                                       say=said.append)
    assert not result.ok
    connection = next(c for c in result.checks if c.title == "Connection")
    assert connection.ok is False
    assert len(connection.lines) == 2, connection.lines  # the error, and what to check
    assert result.report_path is not None
    assert "COM987" in result.report_path.read_text(encoding="utf-8")


def test_without_an_adapter_the_first_check_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(diagnostics, "bluetooth_devices", lambda: [
        {"name": "Generic Bluetooth Radio", "status": "Unknown", "id": r"USB\VID_0A12&PID_0001\5&1"},
    ])
    monkeypatch.setattr(diagnostics, "bluetooth_com_ports", lambda: [])
    # A MAC that no port on any PC leads to: the test must never reach a real board.
    result = diagnostics.run_diagnosis("AA:BB:CC:DD:EE:FF", seconds=0.2,
                                       folder=tmp_path, say=lambda _s: None)
    adapter = result.checks[0]
    assert adapter.title == "Bluetooth adapter" and adapter.ok is False
    assert not result.ok


def test_windows_answers_are_sorted_into_adapters_and_boards() -> None:
    devices = [
        {"name": "Intel(R) Wireless Bluetooth(R)", "status": "OK", "id": r"USB\VID_8087&PID_0026\5&2"},
        {"name": "Microsoft Bluetooth Enumerator", "status": "OK", "id": r"BTH\MS_BTHBRB\7&1"},
        {"name": "BITalino-44-E4", "status": "OK", "id": r"BTHENUM\DEV_98D391FE44E4\8&1"},
    ]
    radios, boards = diagnostics.classify_bluetooth(devices)
    assert [r["name"] for r in radios] == ["Intel(R) Wireless Bluetooth(R)"]
    assert [b["name"] for b in boards] == ["BITalino-44-E4"]


def test_main_returns_zero_when_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(station, "app_folder", lambda: tmp_path)
    monkeypatch.setattr(diagnostics, "app_folder", lambda: tmp_path)
    # main() sets the language from the system's; the language is global, and
    # leaving Spanish behind would change what every later test reads.
    monkeypatch.setattr(diagnostics, "system_language", lambda: "en")
    assert diagnostics.main(["simulada", "--seconds", "0.5"]) == 0
    assert list(tmp_path.glob("diagnostico_bitalino_*.txt"))
