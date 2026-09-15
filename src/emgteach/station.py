"""The station's BITalino address, written once in a text file next to the application.

A laboratory has one BITalino per station, and its address is the one thing
the acquisition tab needs from the station before it can connect. Typed into
the field, it has to be typed again wherever the settings do not survive:
another user account, a reimaged PC, a copy of the application carried on a
USB stick. A text file next to the application travels with it —
``bitalino.txt``, with the address on its first line that is neither blank
nor a comment::

    # BITalino of station 3
    98:D3:91:FE:44:E4

The address takes the same forms as the field: a MAC address, a COM port,
``simulada`` for the BITalino in software, or nothing at all — the file
present but empty — to autodetect. When the file is there, it is the address
the acquisition tab starts with and the one «Default» returns to; the field
can still be edited for the session.

Qt-free, so the connection diagnostic reads the same file.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: The file's name, next to the application.
ADDRESS_FILE = "bitalino.txt"


def app_folder() -> Path:
    """The application's folder: the executable's, or the current one from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def address_file(folder: Path | None = None) -> Path:
    """Where ``bitalino.txt`` is looked for."""
    return (app_folder() if folder is None else Path(folder)) / ADDRESS_FILE


def read_station_address(folder: Path | None = None) -> str | None:
    """The address written in ``bitalino.txt``.

    Returns the first line that is not blank once a ``#`` comment is cut off;
    ``""`` when the file is there with no address in it (autodetect); and
    ``None`` when there is no file to read.
    """
    try:
        text = address_file(folder).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            return entry
    return ""
