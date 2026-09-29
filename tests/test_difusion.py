"""The broadcast's ports, written once in difusion.txt next to the application.

Which ports get through depends on the network the phones are on, so a
laboratory writes them in a file instead of the application fixing them.
Without the file the defaults hold; a line that cannot be used puts both
defaults back and is returned, to be said once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from emgteach import difusion


def _write(folder: Path, text: str) -> None:
    (folder / difusion.PORTS_FILE).write_text(text, encoding="utf-8")


def test_the_defaults_are_8080_and_8443() -> None:
    assert (difusion.DEFAULT_PAGE_PORT, difusion.DEFAULT_DATA_PORT) == (8080, 8443)


def test_without_the_file_the_defaults_and_nothing_to_say(tmp_path: Path) -> None:
    assert difusion.read_broadcast_ports(tmp_path) == (8080, 8443, None)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pagina = 8090\ndatos = 8091\n", (8090, 8091)),
        ("# ports of the lab\n\n  datos=9000  # the data\npágina = 9001\n", (9001, 9000)),
        ("﻿PAGINA = 8090\n", (8090, 8443)),              # Notepad's BOM, any case
        ("datos = 8444\n", (8080, 8444)),                     # the other keeps its default
        ("datos = 8080\npagina = 9000\n", (9000, 8080)),      # equal only halfway through
        ("", (8080, 8443)),
        ("# only comments\n", (8080, 8443)),
    ],
)
def test_the_ports_written_in_the_file(
    tmp_path: Path, text: str, expected: tuple[int, int]
) -> None:
    _write(tmp_path, text)
    assert difusion.read_broadcast_ports(tmp_path) == (*expected, None)


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("pagina = ocho mil\n", "pagina = ocho mil"),
        ("pagina = 8090\ndatos = 70000\n", "datos = 70000"),
        ("datos = 0\n", "datos = 0"),
        ("pagina = 8090\ndatos = 8090\n", "datos = 8090"),
        ("pagina = 8443\n", "pagina = 8443"),                 # equal to the default data port
        ("puerto = 8090\n", "puerto = 8090"),
        ("8090\n", "8090"),
        ("pagina = 8090\ndatos = x  # typo\n", "datos = x  # typo"),
    ],
)
def test_a_line_that_cannot_be_used_puts_back_both_defaults(
    tmp_path: Path, text: str, bad: str
) -> None:
    _write(tmp_path, text)
    assert difusion.read_broadcast_ports(tmp_path) == (8080, 8443, bad)


def test_the_file_is_looked_for_next_to_the_frozen_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "emgteach.exe"))
    _write(tmp_path, "pagina = 8090\n")
    assert difusion.ports_file() == tmp_path / difusion.PORTS_FILE
    assert difusion.read_broadcast_ports() == (8090, 8443, None)
